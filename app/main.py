import asyncio
from contextlib import asynccontextmanager
import json
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psutil

from app.config import settings
from app.redis_client import redis_manager
from app.services.telemetry_service import (
    ROITelemetrySnapshot,
    telemetry_service,
)
from app.schemas import (
    AlertRuleConfig,
    AlertTrigger,
    ForensicAnomalyIncident,
    FrameIngestPayload,
    HealthResponse,
    IngestResponse,
    StreamROIConfig,
    SystemMetricsResponse,
    WorkerHeartbeat,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("streampulse.api")

APP_START_TIME = time.time()
stream_sequence_counters: Dict[str, int] = {}
embedded_worker_instance = None
embedded_worker_task = None
telemetry_broadcast_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application lifecycle: connects broker, launches ML worker, and starts telemetry broadcast."""
    global embedded_worker_instance, embedded_worker_task, telemetry_broadcast_task
    logger.info("Initializing StreamPulse Gateway & Message Broker...")
    await redis_manager.connect()
    await redis_manager.ensure_consumer_group()

    # Launch embedded YOLOv8 ML worker for instant autonomous execution
    try:
        from app.worker import MLInferenceWorker
        embedded_worker_instance = MLInferenceWorker(worker_id="worker-embedded-01")
        embedded_worker_task = asyncio.create_task(embedded_worker_instance.run())
        logger.info("Embedded YOLOv8 ML Analytics Worker started successfully.")
    except Exception as e:
        logger.error(f"Failed to start embedded ML worker: {e}")

    # Launch 2 Hz (500ms) periodic ROI & Token Accounting Telemetry Broadcaster
    async def periodic_telemetry_broadcaster():
        try:
            while True:
                await asyncio.sleep(0.5)
                packet = telemetry_service.get_telemetry_broadcast_packet()
                await redis_manager.publish_telemetry("global", packet)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Periodic telemetry broadcaster error: {e}")

    telemetry_broadcast_task = asyncio.create_task(periodic_telemetry_broadcaster())
    logger.info("StreamPulse Gateway is ready for high-throughput media ingestion and ML broadcast.")
    yield

    logger.info("Shutting down StreamPulse Gateway...")
    if telemetry_broadcast_task:
        telemetry_broadcast_task.cancel()
    if embedded_worker_instance:
        embedded_worker_instance.stop()
    if embedded_worker_task:
        embedded_worker_task.cancel()
    await redis_manager.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="Sub-300ms Event-Driven Real-Time Media Ingestion, YOLOv8 ML Analytics & Autonomous Anomaly Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.APP_NAME,
        "status": "operational",
        "target_latency_sla": f"< {settings.TARGET_LATENCY_SLA_MS} ms",
        "broker_mode": "in_memory" if redis_manager.use_in_memory else "redis_cluster",
        "endpoints": {
            "ws_ingest": "/ws/ingest/{stream_id}",
            "rest_ingest": "/api/v1/stream/ingest",
            "ws_telemetry": "/ws/telemetry/{stream_id}",
            "stream_roi": "/api/v1/stream/roi",
            "health": "/health",
            "metrics": "/api/v1/metrics",
            "incidents": "/api/v1/incidents",
            "incidents_latest": "/api/v1/incidents/latest",
            "alerts_config": "/api/v1/alerts/config",
            "alerts_history": "/api/v1/alerts/history",
            "docs": "/docs",
        },
    }


# -----------------------------------------------------------------------------
# Edge Ingestion Gateways (WebSocket & REST)
# -----------------------------------------------------------------------------

@app.websocket("/ws/ingest/{stream_id}")
async def ws_ingest_endpoint(websocket: WebSocket, stream_id: str):
    """Duplex low-latency WebSocket ingestion endpoint for real-time video/audio frames."""
    await websocket.accept()
    logger.info(f"Ingest WebSocket client connected for stream '{stream_id}'")

    if stream_id not in stream_sequence_counters:
        stream_sequence_counters[stream_id] = 0

    try:
        while True:
            message_text = await websocket.receive_text()
            t_ingest = time.time()

            try:
                data = json.loads(message_text)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
                continue

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                continue

            # Support dynamic ROI update over WebSocket
            if data.get("type") == "update_roi":
                try:
                    roi_cfg = StreamROIConfig(**data.get("roi", {}))
                    await redis_manager.set_stream_roi(stream_id, roi_cfg)
                    await websocket.send_json({"status": "roi_updated", "stream_id": stream_id})
                except Exception as ex:
                    await websocket.send_json({"error": f"Failed to update ROI: {ex}"})
                continue

            t_client = float(data.get("t_client", t_ingest))
            seq_id = data.get("sequence_id")
            if seq_id is None:
                stream_sequence_counters[stream_id] += 1
                seq_id = stream_sequence_counters[stream_id]

            frame_base64 = data.get("frame_base64")
            audio_base64 = data.get("audio_base64")
            metadata = data.get("metadata", {})

            # Non-blocking write to Stream queue
            msg_id = await redis_manager.xadd_frame(
                stream_id=stream_id,
                sequence_id=seq_id,
                t_client=t_client,
                t_ingest=t_ingest,
                frame_base64=frame_base64,
                audio_base64=audio_base64,
                metadata=metadata,
            )

            await websocket.send_json({
                "status": "queued",
                "sequence_id": seq_id,
                "msg_id": msg_id,
                "t_ingest": round(t_ingest, 4),
            })

    except WebSocketDisconnect:
        logger.info(f"Ingest WebSocket client disconnected for stream '{stream_id}'")
    except Exception as e:
        logger.error(f"Error in ingest WebSocket for stream '{stream_id}': {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass


@app.post("/api/v1/stream/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def rest_ingest_endpoint(payload: FrameIngestPayload):
    """HTTP POST fallback for media ingestion."""
    t_ingest = time.time()
    stream_id = payload.stream_id

    if payload.sequence_id is None:
        if stream_id not in stream_sequence_counters:
            stream_sequence_counters[stream_id] = 0
        stream_sequence_counters[stream_id] += 1
        sequence_id = stream_sequence_counters[stream_id]
    else:
        sequence_id = payload.sequence_id

    try:
        await redis_manager.xadd_frame(
            stream_id=stream_id,
            sequence_id=sequence_id,
            t_client=payload.t_client,
            t_ingest=t_ingest,
            frame_base64=payload.frame_base64,
            audio_base64=payload.audio_base64,
            metadata=payload.metadata,
        )

        return IngestResponse(
            status="queued",
            stream_id=stream_id,
            sequence_id=sequence_id,
            t_ingest=round(t_ingest, 4),
            message="Frame successfully queued for inference",
        )
    except Exception as e:
        logger.error(f"Failed to enqueue frame via REST: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue frame: {str(e)}",
        )


# -----------------------------------------------------------------------------
# Dynamic Draggable ROI Endpoints
# -----------------------------------------------------------------------------

@app.post("/api/v1/stream/roi", response_model=StreamROIConfig, tags=["ROI"])
async def update_stream_roi_endpoint(roi: StreamROIConfig):
    """Dynamically updates the interactive draggable ROI coordinates for a stream."""
    await redis_manager.set_stream_roi(roi.stream_id, roi)
    logger.info(
        f"Updated dynamic draggable ROI for stream '{roi.stream_id}': "
        f"enabled={roi.roi_enabled}, box=[{roi.roi_normalized.x1}, {roi.roi_normalized.y1}, "
        f"{roi.roi_normalized.x2}, {roi.roi_normalized.y2}] label='{roi.roi_label}'"
    )
    return roi


@app.get("/api/v1/stream/roi/{stream_id}", response_model=StreamROIConfig, tags=["ROI"])
async def get_stream_roi_endpoint(stream_id: str):
    """Retrieves current interactive draggable ROI configuration for a stream."""
    return await redis_manager.get_stream_roi(stream_id)


# -----------------------------------------------------------------------------
# Telemetry & Client Broadcast Gateway
# -----------------------------------------------------------------------------

@app.websocket("/ws/telemetry/{stream_id}")
async def ws_telemetry_endpoint(websocket: WebSocket, stream_id: str):
    """Real-time telemetry broadcast gateway streaming YOLOv8 inference, forensics, and latencies to UI."""
    await websocket.accept()
    logger.info(f"Telemetry client connected to stream '{stream_id}'")

    async def heartbeat_sender():
        try:
            while True:
                await asyncio.sleep(15.0)
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
        except Exception:
            pass

    heartbeat_task = asyncio.create_task(heartbeat_sender())

    try:
        async for telemetry_json in redis_manager.subscribe_telemetry(stream_id):
            await websocket.send_text(telemetry_json)
    except WebSocketDisconnect:
        logger.info(f"Telemetry client disconnected from stream '{stream_id}'")
    except Exception as e:
        logger.error(f"Error in telemetry WebSocket for stream '{stream_id}': {e}")
    finally:
        heartbeat_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# High-Fidelity Forensic Anomaly Incident REST Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/v1/incidents", response_model=List[Dict[str, Any]], tags=["Forensics"])
async def get_forensic_incidents(
    stream_id: Optional[str] = Query(None, description="Filter incidents by stream ID"),
    limit: int = Query(50, ge=1, le=500, description="Max number of forensic records to return"),
):
    """Retrieves selective forensic anomaly incidents stored in Redis (24h TTL)."""
    incidents = await redis_manager.get_forensic_incidents(stream_id=stream_id, limit=limit)
    return incidents


@app.get("/api/v1/incidents/latest", response_model=Optional[Dict[str, Any]], tags=["Forensics"])
async def get_latest_forensic_incident(
    stream_id: Optional[str] = Query(None, description="Filter by stream ID"),
):
    """Retrieves the most recent forensic anomaly incident."""
    incidents = await redis_manager.get_forensic_incidents(stream_id=stream_id, limit=1)
    if not incidents:
        return None
    return incidents[0]


@app.get("/api/v1/incidents/{incident_id}", response_model=Dict[str, Any], tags=["Forensics"])
async def get_forensic_incident_by_id(incident_id: str):
    """Retrieves a specific forensic anomaly incident record by its unique ID."""
    incident = await redis_manager.get_forensic_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forensic incident with ID '{incident_id}' not found or expired.",
        )
    return incident


# -----------------------------------------------------------------------------
# REST Metrics & System Health
# -----------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    redis_ok, redis_latency = await redis_manager.ping_check()
    active_workers = await redis_manager.get_active_workers()
    queue_depth = await redis_manager.get_queue_depth()

    memory_info = psutil.virtual_memory()
    used_memory_mb = round(memory_info.used / (1024 * 1024), 2)
    cpu_percent = psutil.cpu_percent(interval=None)
    uptime = round(time.time() - APP_START_TIME, 2)

    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        redis_connected=redis_ok,
        redis_latency_ms=redis_latency,
        active_workers_count=max(1, len(active_workers)),
        workers=active_workers,
        queue_depth=queue_depth,
        system_memory_used_mb=used_memory_mb,
        system_cpu_percent=cpu_percent,
        uptime_seconds=uptime,
        timestamp=time.time(),
    )


@app.get("/api/v1/metrics", response_model=SystemMetricsResponse, tags=["Metrics"])
async def get_metrics(
    stream_id: Optional[str] = Query(None, description="Optional stream ID filter"),
    window_sec: int = Query(60, ge=5, le=3600, description="Rolling time window in seconds"),
):
    metrics = await redis_manager.get_rolling_metrics(stream_id=stream_id, window_sec=window_sec)
    return metrics


@app.post("/api/v1/alerts/config", response_model=AlertRuleConfig, tags=["Alerts"])
async def update_alert_config(config: AlertRuleConfig):
    await redis_manager.set_alert_config(config.stream_id, config)
    logger.info(f"Updated alert configuration for stream '{config.stream_id}'")
    return config


@app.get("/api/v1/alerts/config/{stream_id}", response_model=AlertRuleConfig, tags=["Alerts"])
async def get_alert_config_endpoint(stream_id: str):
    return await redis_manager.get_alert_config(stream_id)


@app.get("/api/v1/alerts/history", response_model=List[Dict[str, Any]], tags=["Alerts"])
async def get_alert_history_endpoint(
    stream_id: Optional[str] = Query(None, description="Stream ID to filter incidents"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of incidents to return"),
):
    incidents = await redis_manager.get_alert_history(stream_id=stream_id, limit=limit)
    return incidents


# -----------------------------------------------------------------------------
# Token Accounting & Cost-ROI Telemetry Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/v1/telemetry/roi", response_model=ROITelemetrySnapshot, tags=["Telemetry"])
async def get_roi_telemetry_endpoint():
    """Retrieves real-time token accounting, bandwidth savings, and projected cost ROI."""
    return telemetry_service.get_roi_telemetry()


@app.post("/api/v1/telemetry/reset", tags=["Telemetry"])
async def reset_telemetry_endpoint():
    """Resets real-time token accounting counters."""
    telemetry_service.reset()
    return {"status": "ok", "message": "Telemetry & ROI counters reset successfully"}


# -----------------------------------------------------------------------------
# Domain Preset Context Switcher Endpoint
# -----------------------------------------------------------------------------

class PresetUpdateRequest(BaseModel):
    preset: str = "TRAFFIC"


@app.post("/api/v1/context/preset", tags=["VLM Context"])
async def set_context_preset_endpoint(req: PresetUpdateRequest):
    """Dynamically updates the surveillance domain context for Gemini 2.5 Flash."""
    from app.vlm_dispatcher import vlm_dispatcher
    vlm_dispatcher.set_preset(req.preset)
    return {"status": "ok", "preset": req.preset.upper()}


