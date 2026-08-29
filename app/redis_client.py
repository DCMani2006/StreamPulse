import asyncio
import json
import logging
import math
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError, ResponseError, TimeoutError

from app.config import settings
from app.schemas import AlertRuleConfig, ROINormalizedBox, StreamROIConfig, SystemMetricsResponse, WorkerHeartbeat

logger = logging.getLogger("streampulse.redis")


class InMemoryPipelineBroker:
    """
    High-performance in-memory stream and Pub/Sub broker fallback.
    Activates automatically when a local Redis server is not running on localhost:6379.
    Ensures zero external dependency setup while retaining decoupled stream mechanics.
    """

    def __init__(self):
        self.stream_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.STREAM_MAXLEN)
        self.subscribers: Set[asyncio.Queue] = set()
        self.alert_configs: Dict[str, AlertRuleConfig] = {}
        self.stream_rois: Dict[str, StreamROIConfig] = {}
        self.alert_history: Dict[str, List[Dict[str, Any]]] = {"global": []}
        self.forensic_incidents: Dict[str, Dict[str, Any]] = {}
        self.forensic_history: Dict[str, List[Dict[str, Any]]] = {"global": []}
        self.metrics_samples: Dict[str, List[Dict[str, Any]]] = {"global": []}
        self.workers: Dict[str, WorkerHeartbeat] = {}
        self.stream_counter = 0

    async def xadd_frame(
        self,
        stream_id: str,
        sequence_id: int,
        t_client: float,
        t_ingest: float,
        frame_base64: Optional[str] = None,
        audio_base64: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        self.stream_counter += 1
        msg_id = f"{int(time.time() * 1000)}-{self.stream_counter}"
        payload = {
            "stream_id": stream_id,
            "sequence_id": str(sequence_id),
            "t_client": str(t_client),
            "t_ingest": str(t_ingest),
            "frame_base64": frame_base64 or "",
            "audio_base64": audio_base64 or "",
            "metadata": json.dumps(metadata or {}),
        }
        try:
            if self.stream_queue.full():
                try:
                    self.stream_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await self.stream_queue.put((msg_id, payload))
        except Exception as e:
            logger.warning(f"In-memory stream buffer: {e}")
        return msg_id

    async def read_stream_group(self, count: int = 10, block_ms: int = 100) -> List[Tuple[str, Dict[str, str]]]:
        messages = []
        try:
            timeout_sec = block_ms / 1000.0
            msg = await asyncio.wait_for(self.stream_queue.get(), timeout=timeout_sec)
            messages.append(msg)
            while len(messages) < count and not self.stream_queue.empty():
                messages.append(self.stream_queue.get_nowait())
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            pass
        return messages

    async def publish_telemetry(self, stream_id: str, payload_dict: Dict[str, Any]) -> None:
        payload_str = json.dumps(payload_dict)
        dead_subscribers = []
        for q in list(self.subscribers):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(payload_str)
            except Exception:
                dead_subscribers.append(q)
        for q in dead_subscribers:
            self.subscribers.discard(q)

    async def subscribe_telemetry(self, stream_id: str) -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        try:
            while True:
                data = await q.get()
                yield data
        finally:
            self.subscribers.discard(q)

    async def set_stream_roi(self, stream_id: str, roi: StreamROIConfig) -> None:
        self.stream_rois[stream_id] = roi

    async def get_stream_roi(self, stream_id: str) -> StreamROIConfig:
        if stream_id in self.stream_rois:
            return self.stream_rois[stream_id]
        return StreamROIConfig(
            stream_id=stream_id,
            roi_enabled=True,
            roi_normalized=ROINormalizedBox(x1=0.20, y1=0.30, x2=0.70, y2=0.80),
            roi_label="Server Rack Perimeter",
        )

    async def record_metric_sample(
        self, stream_id: str, e2e_ms: float, ingest_ms: float, queue_ms: float, infer_ms: float, has_alert: bool
    ) -> None:
        now = time.time()
        sample = {
            "e2e": round(e2e_ms, 2),
            "ingest": round(ingest_ms, 2),
            "queue": round(queue_ms, 2),
            "infer": round(infer_ms, 2),
            "alert": 1 if has_alert else 0,
            "t": now,
        }
        for k in [stream_id, "global"]:
            if k not in self.metrics_samples:
                self.metrics_samples[k] = []
            self.metrics_samples[k].append(sample)
            cutoff = now - settings.METRICS_ROLLING_WINDOW_SEC
            self.metrics_samples[k] = [s for s in self.metrics_samples[k] if s["t"] >= cutoff]

    async def get_rolling_metrics(self, stream_id: Optional[str] = None, window_sec: int = 60) -> SystemMetricsResponse:
        now = time.time()
        cutoff = now - window_sec
        key = stream_id if stream_id else "global"
        samples = [s for s in self.metrics_samples.get(key, []) if s["t"] >= cutoff]

        if not samples:
            return SystemMetricsResponse(
                stream_id=stream_id,
                time_window_seconds=window_sec,
                total_frames_processed=0,
                fps=0.0,
                avg_e2e_latency_ms=0.0,
                avg_ingestion_latency_ms=0.0,
                avg_queue_dwell_time_ms=0.0,
                avg_inference_time_ms=0.0,
                p95_e2e_latency_ms=0.0,
                current_queue_depth=self.stream_queue.qsize(),
                total_alerts_triggered=0,
                sla_compliance_percent=100.0,
            )

        e2e_list = [s["e2e"] for s in samples]
        ingest_list = [s["ingest"] for s in samples]
        queue_list = [s["queue"] for s in samples]
        infer_list = [s["infer"] for s in samples]
        alerts_count = sum(s["alert"] for s in samples)
        sla_met_count = sum(1 for e in e2e_list if e <= settings.TARGET_LATENCY_SLA_MS)

        total_samples = len(e2e_list)
        e2e_sorted = sorted(e2e_list)
        p95_idx = int(math.ceil(0.95 * total_samples)) - 1
        p95_e2e = e2e_sorted[max(0, min(p95_idx, total_samples - 1))]

        return SystemMetricsResponse(
            stream_id=stream_id,
            time_window_seconds=window_sec,
            total_frames_processed=total_samples,
            fps=round(total_samples / float(window_sec), 2),
            avg_e2e_latency_ms=round(sum(e2e_list) / total_samples, 2),
            avg_ingestion_latency_ms=round(sum(ingest_list) / total_samples, 2),
            avg_queue_dwell_time_ms=round(sum(queue_list) / total_samples, 2),
            avg_inference_time_ms=round(sum(infer_list) / total_samples, 2),
            p95_e2e_latency_ms=round(p95_e2e, 2),
            current_queue_depth=self.stream_queue.qsize(),
            total_alerts_triggered=alerts_count,
            sla_compliance_percent=round((sla_met_count / total_samples) * 100.0, 2),
        )

    async def log_alert_incident(self, stream_id: str, alert_dict: Dict[str, Any]) -> None:
        for k in [stream_id, "global"]:
            if k not in self.alert_history:
                self.alert_history[k] = []
            self.alert_history[k].insert(0, alert_dict)
            if len(self.alert_history[k]) > settings.MAX_ALERT_HISTORY_ITEMS:
                self.alert_history[k].pop()

    async def get_alert_history(self, stream_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        key = stream_id if stream_id else "global"
        return self.alert_history.get(key, [])[:limit]

    async def log_forensic_incident(self, stream_id: str, incident_dict: Dict[str, Any]) -> None:
        inc_id = incident_dict.get("incident_id", f"inc_{time.time()}")
        self.forensic_incidents[inc_id] = incident_dict

        for k in [stream_id, "global"]:
            if k not in self.forensic_history:
                self.forensic_history[k] = []
            self.forensic_history[k].insert(0, incident_dict)
            if len(self.forensic_history[k]) > 500:
                self.forensic_history[k].pop()

    async def get_forensic_incidents(self, stream_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        key = stream_id if stream_id else "global"
        return self.forensic_history.get(key, [])[:limit]

    async def get_forensic_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self.forensic_incidents.get(incident_id)

    async def set_alert_config(self, stream_id: str, config: AlertRuleConfig) -> None:
        self.alert_configs[stream_id] = config

    async def get_alert_config(self, stream_id: str) -> AlertRuleConfig:
        if stream_id in self.alert_configs:
            return self.alert_configs[stream_id]
        return AlertRuleConfig(
            stream_id=stream_id,
            max_persons=1,
            prohibited_classes=["cell phone", "knife", "laptop", "scissors", "backpack", "book"],
            prohibited_confidence_threshold=0.50,
            velocity_spike_threshold=0.18,
            enable_zone_rule=True,
            enable_occupancy_rule=True,
            enable_prohibited_rule=True,
            enable_audio_rule=True,
        )

    async def update_worker_heartbeat(self, worker_id: str, processed_count: int, avg_inference_ms: float) -> None:
        self.workers[worker_id] = WorkerHeartbeat(
            worker_id=worker_id,
            last_heartbeat=time.time(),
            status="active",
            processed_count=processed_count,
            avg_inference_ms=round(avg_inference_ms, 2),
        )

    async def get_active_workers(self) -> List[WorkerHeartbeat]:
        now = time.time()
        return [w for w in self.workers.values() if now - w.last_heartbeat < 15]


class RedisPipelineManager:
    """
    Production Redis manager with automatic seamless in-memory broker fallback.
    Guarantees 100% autonomous operation with or without a standalone Redis instance.
    """

    def __init__(self):
        self.redis_pool: Optional[aioredis.ConnectionPool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_in_memory: bool = False
        self.in_memory_broker = InMemoryPipelineBroker()

    async def connect(self) -> None:
        """Initializes Redis connection pool with automatic in-memory fallback."""
        try:
            redis_url = settings.get_redis_url()
            self.redis_pool = aioredis.ConnectionPool.from_url(
                redis_url,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True,
            )
            self.redis_client = aioredis.Redis(connection_pool=self.redis_pool)
            await self.redis_client.ping()
            self.use_in_memory = False
            logger.info(f"Connected to Redis message broker at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            self.use_in_memory = True
            logger.warning(
                f"Redis server not reachable at {settings.REDIS_HOST}:{settings.REDIS_PORT} ({e}). "
                "Activating high-performance in-memory Stream & Pub/Sub broker."
            )

    async def close(self) -> None:
        """Closes Redis connections."""
        if not self.use_in_memory and self.redis_client:
            try:
                await self.redis_client.aclose()
            except Exception:
                pass

    def get_client(self) -> aioredis.Redis:
        if self.use_in_memory or not self.redis_client:
            raise RuntimeError("Running in in-memory broker mode.")
        return self.redis_client

    async def ensure_consumer_group(
        self, stream_name: str = settings.STREAM_RAW_VIDEO, group_name: str = settings.CONSUMER_GROUP_NAME
    ) -> None:
        if self.use_in_memory:
            return
        try:
            client = self.get_client()
            await client.xgroup_create(name=stream_name, groupname=group_name, id="0", mkstream=True)
        except Exception:
            pass

    async def xadd_frame(
        self,
        stream_id: str,
        sequence_id: int,
        t_client: float,
        t_ingest: float,
        frame_base64: Optional[str] = None,
        audio_base64: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_name: str = settings.STREAM_RAW_VIDEO,
    ) -> str:
        if self.use_in_memory:
            return await self.in_memory_broker.xadd_frame(
                stream_id, sequence_id, t_client, t_ingest, frame_base64, audio_base64, metadata
            )

        client = self.get_client()
        payload = {
            "stream_id": stream_id,
            "sequence_id": str(sequence_id),
            "t_client": str(t_client),
            "t_ingest": str(t_ingest),
            "frame_base64": frame_base64 or "",
            "audio_base64": audio_base64 or "",
            "metadata": json.dumps(metadata or {}),
        }
        return await client.xadd(name=stream_name, fields=payload, maxlen=settings.STREAM_MAXLEN, approximate=True)

    async def read_stream_group(
        self,
        consumer_name: str,
        group_name: str = settings.CONSUMER_GROUP_NAME,
        stream_name: str = settings.STREAM_RAW_VIDEO,
        count: int = 10,
        block_ms: int = 100,
    ) -> List[Tuple[str, Dict[str, str]]]:
        if self.use_in_memory:
            return await self.in_memory_broker.read_stream_group(count=count, block_ms=block_ms)

        try:
            client = self.get_client()
            response = await client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_name: ">"},
                count=count,
                block=block_ms,
            )
            if not response:
                return []
            messages = []
            for stream_entry in response:
                for msg_id, data in stream_entry[1]:
                    messages.append((msg_id, data))
            return messages
        except Exception:
            return []

    async def autoclaim_stale_messages(
        self, consumer_name: str, group_name: str = settings.CONSUMER_GROUP_NAME, stream_name: str = settings.STREAM_RAW_VIDEO, min_idle_time_ms: int = 5000, count: int = 10
    ) -> List[Tuple[str, Dict[str, str]]]:
        if self.use_in_memory:
            return []
        try:
            client = self.get_client()
            result = await client.xautoclaim(name=stream_name, groupname=group_name, consumername=consumer_name, min_idle_time=min_idle_time_ms, start_id="0-0", count=count)
            if result and len(result) >= 2:
                return [(msg_id, data) for msg_id, data in result[1] if data]
            return []
        except Exception:
            return []

    async def ack_message(self, msg_id: str, stream_name: str = settings.STREAM_RAW_VIDEO, group_name: str = settings.CONSUMER_GROUP_NAME) -> None:
        if self.use_in_memory:
            return
        try:
            client = self.get_client()
            await client.xack(stream_name, group_name, msg_id)
        except Exception:
            pass

    async def get_queue_depth(self, stream_name: str = settings.STREAM_RAW_VIDEO) -> int:
        if self.use_in_memory:
            return self.in_memory_broker.stream_queue.qsize()
        try:
            client = self.get_client()
            return await client.xlen(stream_name)
        except Exception:
            return 0

    async def publish_telemetry(self, stream_id: str, payload_dict: Dict[str, Any]) -> None:
        if self.use_in_memory:
            return await self.in_memory_broker.publish_telemetry(stream_id, payload_dict)

        client = self.get_client()
        payload_str = json.dumps(payload_dict)
        pipe = client.pipeline(transaction=False)
        pipe.publish(f"{settings.PUBSUB_TELEMETRY_PREFIX}:{stream_id}", payload_str)
        pipe.publish(f"{settings.PUBSUB_TELEMETRY_PREFIX}:global", payload_str)
        await pipe.execute()

    async def subscribe_telemetry(self, stream_id: str) -> AsyncGenerator[str, None]:
        if self.use_in_memory:
            async for msg in self.in_memory_broker.subscribe_telemetry(stream_id):
                yield msg
            return

        channel_name = f"{settings.PUBSUB_TELEMETRY_PREFIX}:{stream_id}"
        client = self.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel_name)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.aclose()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Interactive Draggable ROI State Management
    # -------------------------------------------------------------------------

    async def set_stream_roi(self, stream_id: str, roi_config: StreamROIConfig) -> None:
        """Saves interactive draggable ROI state in Redis and memory."""
        if self.use_in_memory:
            return await self.in_memory_broker.set_stream_roi(stream_id, roi_config)
        client = self.get_client()
        key = f"stream:roi:{stream_id}"
        await client.set(key, roi_config.model_dump_json())

    async def get_stream_roi(self, stream_id: str) -> StreamROIConfig:
        """Retrieves interactive draggable ROI state."""
        if self.use_in_memory:
            return await self.in_memory_broker.get_stream_roi(stream_id)
        client = self.get_client()
        key = f"stream:roi:{stream_id}"
        data = await client.get(key)
        if data:
            try:
                return StreamROIConfig.model_validate_json(data)
            except Exception:
                pass
        return await self.in_memory_broker.get_stream_roi(stream_id)

    async def set_alert_config(self, stream_id: str, config: AlertRuleConfig) -> None:
        if self.use_in_memory:
            return await self.in_memory_broker.set_alert_config(stream_id, config)
        client = self.get_client()
        key = f"{settings.ALERTS_CONFIG_PREFIX}:{stream_id}"
        await client.set(key, config.model_dump_json())

    async def get_alert_config(self, stream_id: str) -> AlertRuleConfig:
        if self.use_in_memory:
            return await self.in_memory_broker.get_alert_config(stream_id)
        client = self.get_client()
        key = f"{settings.ALERTS_CONFIG_PREFIX}:{stream_id}"
        data = await client.get(key)
        if data:
            try:
                return AlertRuleConfig.model_validate_json(data)
            except Exception:
                pass
        return await self.in_memory_broker.get_alert_config(stream_id)

    async def log_alert_incident(self, stream_id: str, alert_dict: Dict[str, Any]) -> None:
        if self.use_in_memory:
            return await self.in_memory_broker.log_alert_incident(stream_id, alert_dict)
        client = self.get_client()
        stream_history_key = f"{settings.ALERTS_HISTORY_PREFIX}:{stream_id}"
        global_history_key = f"{settings.ALERTS_HISTORY_PREFIX}:global"
        alert_json = json.dumps(alert_dict)
        pipe = client.pipeline(transaction=False)
        pipe.lpush(stream_history_key, alert_json)
        pipe.ltrim(stream_history_key, 0, settings.MAX_ALERT_HISTORY_ITEMS - 1)
        pipe.lpush(global_history_key, alert_json)
        pipe.ltrim(global_history_key, 0, settings.MAX_ALERT_HISTORY_ITEMS - 1)
        await pipe.execute()

    async def get_alert_history(self, stream_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self.use_in_memory:
            return await self.in_memory_broker.get_alert_history(stream_id, limit)
        client = self.get_client()
        key = f"{settings.ALERTS_HISTORY_PREFIX}:{stream_id}" if stream_id else f"{settings.ALERTS_HISTORY_PREFIX}:global"
        raw_items = await client.lrange(key, 0, limit - 1)
        alerts = []
        for item in raw_items:
            try:
                alerts.append(json.loads(item))
            except Exception:
                continue
        return alerts

    # -------------------------------------------------------------------------
    # Forensic Anomaly Incident Persistence (24h TTL)
    # -------------------------------------------------------------------------

    async def log_forensic_incident(self, stream_id: str, incident_dict: Dict[str, Any]) -> None:
        """Persists high-fidelity forensic anomaly records in Redis with 24-hour TTL."""
        if self.use_in_memory:
            return await self.in_memory_broker.log_forensic_incident(stream_id, incident_dict)

        client = self.get_client()
        inc_id = incident_dict.get("incident_id", f"inc_{time.time()}")
        payload_str = json.dumps(incident_dict)
        ttl_seconds = 86400  # 24 Hours

        pipe = client.pipeline(transaction=False)
        pipe.lpush("incidents:history", payload_str)
        pipe.ltrim("incidents:history", 0, 499)
        pipe.expire("incidents:history", ttl_seconds)

        pipe.lpush(f"incidents:history:{stream_id}", payload_str)
        pipe.ltrim(f"incidents:history:{stream_id}", 0, 499)
        pipe.expire(f"incidents:history:{stream_id}", ttl_seconds)

        pipe.set(f"incident:{inc_id}", payload_str, ex=ttl_seconds)

        await pipe.execute()

    async def get_forensic_incidents(self, stream_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves forensic anomaly records."""
        if self.use_in_memory:
            return await self.in_memory_broker.get_forensic_incidents(stream_id, limit)

        client = self.get_client()
        key = f"incidents:history:{stream_id}" if stream_id else "incidents:history"
        raw_items = await client.lrange(key, 0, limit - 1)
        incidents = []
        for item in raw_items:
            try:
                incidents.append(json.loads(item))
            except Exception:
                continue
        return incidents

    async def get_forensic_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific forensic anomaly record by ID."""
        if self.use_in_memory:
            return await self.in_memory_broker.get_forensic_incident_by_id(incident_id)

        client = self.get_client()
        raw = await client.get(f"incident:{incident_id}")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    async def record_metric_sample(
        self, stream_id: str, e2e_ms: float, ingest_ms: float, queue_ms: float, infer_ms: float, has_alert: bool = False
    ) -> None:
        if self.use_in_memory:
            return await self.in_memory_broker.record_metric_sample(stream_id, e2e_ms, ingest_ms, queue_ms, infer_ms, has_alert)
        client = self.get_client()
        now = time.time()
        cutoff = now - settings.METRICS_ROLLING_WINDOW_SEC
        sample_data = json.dumps({
            "e2e": round(e2e_ms, 2),
            "ingest": round(ingest_ms, 2),
            "queue": round(queue_ms, 2),
            "infer": round(infer_ms, 2),
            "alert": 1 if has_alert else 0,
            "t": now,
        })
        pipe = client.pipeline(transaction=False)
        pipe.zadd(f"{settings.METRICS_HISTORY_PREFIX}:{stream_id}", {sample_data: now})
        pipe.zremrangebyscore(f"{settings.METRICS_HISTORY_PREFIX}:{stream_id}", 0, cutoff)
        pipe.zadd(f"{settings.METRICS_HISTORY_PREFIX}:global", {sample_data: now})
        pipe.zremrangebyscore(f"{settings.METRICS_HISTORY_PREFIX}:global", 0, cutoff)
        await pipe.execute()

    async def get_rolling_metrics(self, stream_id: Optional[str] = None, window_sec: int = settings.METRICS_ROLLING_WINDOW_SEC) -> SystemMetricsResponse:
        if self.use_in_memory:
            return await self.in_memory_broker.get_rolling_metrics(stream_id, window_sec)
        client = self.get_client()
        now = time.time()
        cutoff = now - window_sec
        key = f"{settings.METRICS_HISTORY_PREFIX}:{stream_id}" if stream_id else f"{settings.METRICS_HISTORY_PREFIX}:global"
        samples_raw = await client.zrangebyscore(key, cutoff, "+inf")
        queue_depth = await self.get_queue_depth()

        if not samples_raw:
            return SystemMetricsResponse(
                stream_id=stream_id,
                time_window_seconds=window_sec,
                total_frames_processed=0,
                fps=0.0,
                avg_e2e_latency_ms=0.0,
                avg_ingestion_latency_ms=0.0,
                avg_queue_dwell_time_ms=0.0,
                avg_inference_time_ms=0.0,
                p95_e2e_latency_ms=0.0,
                current_queue_depth=queue_depth,
                total_alerts_triggered=0,
                sla_compliance_percent=100.0,
            )

        e2e_list = []
        ingest_list = []
        queue_list = []
        infer_list = []
        alerts_count = 0
        sla_met_count = 0

        for raw in samples_raw:
            try:
                data = json.loads(raw)
                e2e = data.get("e2e", 0.0)
                e2e_list.append(e2e)
                ingest_list.append(data.get("ingest", 0.0))
                queue_list.append(data.get("queue", 0.0))
                infer_list.append(data.get("infer", 0.0))
                if data.get("alert", 0) > 0:
                    alerts_count += 1
                if e2e <= settings.TARGET_LATENCY_SLA_MS:
                    sla_met_count += 1
            except Exception:
                continue

        total_samples = len(e2e_list)
        if total_samples == 0:
            return await self.in_memory_broker.get_rolling_metrics(stream_id, window_sec)

        e2e_sorted = sorted(e2e_list)
        p95_idx = int(math.ceil(0.95 * total_samples)) - 1
        p95_e2e = e2e_sorted[max(0, min(p95_idx, total_samples - 1))]

        return SystemMetricsResponse(
            stream_id=stream_id,
            time_window_seconds=window_sec,
            total_frames_processed=total_samples,
            fps=round(total_samples / float(window_sec), 2),
            avg_e2e_latency_ms=round(sum(e2e_list) / total_samples, 2),
            avg_ingestion_latency_ms=round(sum(ingest_list) / total_samples, 2),
            avg_queue_dwell_time_ms=round(sum(queue_list) / total_samples, 2),
            avg_inference_time_ms=round(sum(infer_list) / total_samples, 2),
            p95_e2e_latency_ms=round(p95_e2e, 2),
            current_queue_depth=queue_depth,
            total_alerts_triggered=alerts_count,
            sla_compliance_percent=round((sla_met_count / total_samples) * 100.0, 2),
        )

    async def update_worker_heartbeat(self, worker_id: str, processed_count: int, avg_inference_ms: float) -> None:
        if self.use_in_memory:
            return await self.in_memory_broker.update_worker_heartbeat(worker_id, processed_count, avg_inference_ms)
        client = self.get_client()
        key = f"{settings.WORKER_HEARTBEAT_PREFIX}:{worker_id}"
        payload = json.dumps({
            "worker_id": worker_id,
            "last_heartbeat": time.time(),
            "status": "active",
            "processed_count": processed_count,
            "avg_inference_ms": round(avg_inference_ms, 2),
        })
        await client.set(key, payload, ex=15)

    async def get_active_workers(self) -> List[WorkerHeartbeat]:
        if self.use_in_memory:
            return await self.in_memory_broker.get_active_workers()
        client = self.get_client()
        workers = []
        try:
            keys = await client.keys(f"{settings.WORKER_HEARTBEAT_PREFIX}:*")
            for key in keys:
                data = await client.get(key)
                if data:
                    try:
                        workers.append(WorkerHeartbeat(**json.loads(data)))
                    except Exception:
                        continue
        except Exception:
            pass
        return workers

    async def ping_check(self) -> Tuple[bool, float]:
        if self.use_in_memory:
            return (True, 0.05)
        try:
            client = self.get_client()
            t_start = time.perf_counter()
            pong = await client.ping()
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            return (bool(pong), round(latency_ms, 2))
        except Exception:
            return (False, 0.0)


redis_manager = RedisPipelineManager()
