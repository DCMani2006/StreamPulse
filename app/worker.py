import asyncio
import concurrent.futures
import datetime
import logging
import math
import os
import signal
import socket
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from ultralytics import YOLO

from app.config import settings
from app.pipeline_utils import (
    calculate_latency_metrics,
    decode_base64_image,
    draw_forensic_annotations,
    encode_image_to_data_uri_fast,
    is_box_inside_zone,
    normalize_box,
)
from app.edge_gatekeeper import EdgeGatekeeper
from app.audio_trigger import AudioTransientTrigger
from app.vlm_dispatcher import vlm_dispatcher
from app.services.telemetry_service import telemetry_service
from app.redis_client import redis_manager
from app.schemas import (
    AlertRuleConfig,
    AlertTrigger,
    AudioAnalysisResult,
    AudioContextDetail,
    AudioTriggerBasis,
    DecisionBasis,
    DetectionDetail,
    DetectionResult,
    ForensicAnomalyIncident,
    IncidentAnalysisResult,
    ROINormalizedBox,
    StreamROIConfig,
    StreamTelemetryPayload,
    SystemTelemetryDetail,
    TokenOptimizationStats,
    TriggeredRuleDetail,
    VisualContextDetail,
    VisualTriggerBasis,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("streampulse.worker")


class MLInferenceWorker:
    """
    High-Throughput Edge-to-Cloud Token-Optimization Gateway & Anomaly Filter:
    - Sub-2ms Frame-Delta Gatekeeper (EdgeGatekeeper): drops ~95% of static/redundant surveillance frames.
    - Audio Transient Spike & Decibel Trigger (AudioTransientTrigger): flags acoustic impacts, shouts, and transient rises.
    - YOLOv8 Object Detection on Candidate Event Frames: only runs on active frames or audio triggers.
    - Granular Latency & Token Optimization Telemetry (< 1.5ms overhead for static drops).
    """

    def __init__(self, worker_id: Optional[str] = None):
        hostname = socket.gethostname()
        pid = os.getpid()
        self.worker_id = worker_id or f"{settings.CONSUMER_NAME_PREFIX}-{hostname}-{pid}"
        self.model: Optional[YOLO] = None
        self.running = False
        self.processed_count = 0
        self.total_infer_time_ms = 0.0
        self.alert_config_cache: Dict[str, Tuple[float, AlertRuleConfig]] = {}
        self.roi_config_cache: Dict[str, Tuple[float, StreamROIConfig]] = {}
        self.config_cache_ttl_sec = 3.0
        self.recent_frame_times: List[float] = []
        self.last_snapshot_time: Dict[str, float] = {}
        self.edge_gatekeepers: Dict[str, EdgeGatekeeper] = {}
        self.audio_triggers: Dict[str, AudioTransientTrigger] = {}
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="snapshot-worker")

    def load_model(self) -> None:
        """Loads and warms up the Ultralytics YOLOv8 model for CPU inference."""
        logger.info(f"Loading YOLOv8 model from '{settings.YOLO_MODEL_PATH}' on device='{settings.YOLO_DEVICE}'...")
        try:
            self.model = YOLO(settings.YOLO_MODEL_PATH)
            logger.info("Executing model warmup to eliminate first-request cold-start latency...")
            dummy_frame = np.zeros((settings.YOLO_IMAGE_SIZE, settings.YOLO_IMAGE_SIZE, 3), dtype=np.uint8)
            _ = self.model.predict(
                dummy_frame,
                imgsz=settings.YOLO_IMAGE_SIZE,
                device=settings.YOLO_DEVICE,
                conf=settings.YOLO_CONFIDENCE_THRESHOLD,
                verbose=False,
            )
            logger.info("YOLOv8 model warmup completed successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    async def get_cached_alert_config(self, stream_id: str) -> AlertRuleConfig:
        now = time.time()
        if stream_id in self.alert_config_cache:
            cache_time, config = self.alert_config_cache[stream_id]
            if now - cache_time < self.config_cache_ttl_sec:
                return config
        config = await redis_manager.get_alert_config(stream_id)
        self.alert_config_cache[stream_id] = (now, config)
        return config

    async def get_cached_roi_config(self, stream_id: str) -> StreamROIConfig:
        now = time.time()
        if stream_id in self.roi_config_cache:
            cache_time, roi = self.roi_config_cache[stream_id]
            if now - cache_time < self.config_cache_ttl_sec:
                return roi
        roi = await redis_manager.get_stream_roi(stream_id)
        self.roi_config_cache[stream_id] = (now, roi)
        return roi

    def get_edge_gatekeeper(self, stream_id: str) -> EdgeGatekeeper:
        if stream_id not in self.edge_gatekeepers:
            self.edge_gatekeepers[stream_id] = EdgeGatekeeper(delta_threshold=0.018, warmup_frames=3)
        return self.edge_gatekeepers[stream_id]

    def get_audio_trigger(self, stream_id: str) -> AudioTransientTrigger:
        if stream_id not in self.audio_triggers:
            self.audio_triggers[stream_id] = AudioTransientTrigger(
                sample_rate=settings.AUDIO_SAMPLE_RATE,
                spike_db_threshold=-28.0,
            )
        return self.audio_triggers[stream_id]

    def run_cv_inference(self, image: np.ndarray) -> Tuple[List[DetectionResult], int, int, int]:
        height, width = image.shape[:2]
        detections: List[DetectionResult] = []
        person_count = 0

        if self.model is None:
            return detections, 0, width, height

        try:
            # Native YOLOv8 multi-object tracking with persistent ByteTrack IDs
            results = self.model.track(
                source=image,
                persist=True,
                tracker="bytetrack.yaml",
                imgsz=settings.YOLO_IMAGE_SIZE,
                conf=settings.YOLO_CONFIDENCE_THRESHOLD,
                device=settings.YOLO_DEVICE,
                verbose=False,
            )
        except Exception as e:
            logger.warning(f"ByteTrack tracker error ({e}), falling back to standard prediction.")
            results = self.model.predict(
                image,
                imgsz=settings.YOLO_IMAGE_SIZE,
                conf=settings.YOLO_CONFIDENCE_THRESHOLD,
                device=settings.YOLO_DEVICE,
                verbose=False,
            )

        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            track_ids = (
                boxes.id.int().cpu().tolist()
                if (boxes.id is not None)
                else [None] * len(boxes)
            )
            xyxy_list = boxes.xyxy.cpu().tolist()
            conf_list = boxes.conf.cpu().tolist()
            cls_list = boxes.cls.int().cpu().tolist()

            for idx in range(len(boxes)):
                xyxy = xyxy_list[idx]
                conf = float(conf_list[idx])
                cls_id = int(cls_list[idx])
                t_id = track_ids[idx] if (idx < len(track_ids) and track_ids[idx] is not None) else (100 + idx)
                label = result.names.get(cls_id, f"class_{cls_id}")
                norm_box = normalize_box(xyxy, width, height)

                detections.append(
                    DetectionResult(
                        class_id=cls_id,
                        label=label,
                        confidence=round(conf, 4),
                        box=[round(c, 1) for c in xyxy],
                        normalized_box=[round(c, 4) for c in norm_box],
                        tracking_id=t_id,
                    )
                )

                if label == "person":
                    person_count += 1

        return detections, person_count, width, height

    def evaluate_decision_matrix(
        self,
        stream_id: str,
        sequence_id: int,
        detections: List[DetectionResult],
        person_count: int,
        audio_trigger_fired: bool,
        audio_db: float,
        delta_score: float,
        config: AlertRuleConfig,
        roi_config: StreamROIConfig,
        width: int,
        height: int,
    ) -> Tuple[DecisionBasis, str, List[TriggeredRuleDetail], List[DetectionDetail], List[AlertTrigger]]:
        triggered_rules: List[TriggeredRuleDetail] = []
        alerts: List[AlertTrigger] = []
        now = time.time()

        detection_details: List[DetectionDetail] = []
        for idx, det in enumerate(detections):
            px_box = [int(det.box[0]), int(det.box[1]), int(det.box[2]), int(det.box[3])]
            detection_details.append(
                DetectionDetail(
                    object_id=f"obj_{idx + 1:02d}",
                    class_name=det.label,
                    confidence=round(det.confidence, 4),
                    box_normalized=det.normalized_box,
                    box_pixels=px_box,
                    is_violator=False,
                )
            )

        # 1. Prohibited Items Trigger
        if getattr(config, "enable_prohibited_rule", True):
            prohibited_set = {p.lower() for p in getattr(config, "prohibited_classes", ["knife", "scissors", "gun", "weapon"])}
            conf_thresh = getattr(config, "prohibited_confidence_threshold", 0.55)
            for idx, det in enumerate(detections):
                if det.label.lower() in prohibited_set and det.confidence >= conf_thresh:
                    rationale = f"Prohibited Item Detected: '{det.label}' ({int(det.confidence * 100)}% conf)."
                    detection_details[idx].is_violator = True
                    alerts.append(
                        AlertTrigger(
                            alert_type="prohibited_object",
                            severity="critical",
                            message=f"SECURITY ALERT: Prohibited Object Detected ({det.label.upper()})",
                            stream_id=stream_id,
                            sequence_id=sequence_id,
                            timestamp=now,
                            details={"class": det.label, "confidence": det.confidence, "box": det.box},
                        )
                    )
                    triggered_rules.append(
                        TriggeredRuleDetail(
                            rule_id="RULE_PROHIBITED_OBJECT",
                            description=rationale,
                            target_class=det.label,
                            confidence=det.confidence,
                        )
                    )

        # 2. Audio Transient Spike Trigger
        if audio_trigger_fired:
            audio_rationale = f"Acoustic Transient Spike: Sudden decibel surge ({audio_db:.1f} dBFS) detected."
            alerts.append(
                AlertTrigger(
                    alert_type="audio_spike",
                    severity="warning",
                    message=f"ACOUSTIC TRIGGER: Sudden Noise/Impact Surge ({audio_db:.1f} dBFS)",
                    stream_id=stream_id,
                    sequence_id=sequence_id,
                    timestamp=now,
                    details={"audio_db": audio_db},
                )
            )
            triggered_rules.append(
                TriggeredRuleDetail(
                    rule_id="RULE_AUDIO_TRANSIENT_SPIKE",
                    description=audio_rationale,
                    target_class="acoustic_spike",
                    confidence=0.94,
                )
            )

        # 3. Candidate Visual Event Trigger
        if delta_score >= 0.05:
            vis_rationale = f"Significant Motion Event: Visual pixel delta ({delta_score*100:.1f}%) exceeds candidate threshold."
            triggered_rules.append(
                TriggeredRuleDetail(
                    rule_id="RULE_CANDIDATE_VISUAL_EVENT",
                    description=vis_rationale,
                    target_class="visual_motion",
                    confidence=min(0.99, 0.70 + delta_score),
                )
            )

        # 4. Interactive ROI Sector Intrusion (if enabled)
        if roi_config and roi_config.roi_enabled:
            rn = roi_config.roi_normalized
            roi_zone = [rn.x1, rn.y1, rn.x2, rn.y2]
            for idx, det in enumerate(detections):
                if is_box_inside_zone(det.normalized_box, roi_zone):
                    detection_details[idx].is_violator = True
                    zone_rationale = f"Monitored ROI Sector Breach: '{det.label}' entered '{roi_config.roi_label}' sector."
                    alerts.append(
                        AlertTrigger(
                            alert_type="zone_intrusion",
                            severity="warning",
                            message=f"RESTRICTED ROI: Intrusion into '{roi_config.roi_label}' ({det.label.upper()})",
                            stream_id=stream_id,
                            sequence_id=sequence_id,
                            timestamp=now,
                            details={"class": det.label, "roi_label": roi_config.roi_label},
                        )
                    )
                    triggered_rules.append(
                        TriggeredRuleDetail(
                            rule_id="RULE_RESTRICTED_ZONE",
                            description=zone_rationale,
                            target_class=det.label,
                            confidence=det.confidence,
                        )
                    )

        # Build Explainable DecisionBasis
        has_alerts = len(alerts) > 0
        overall_rationale = (
            f"CANDIDATE_EVENT: Active frame processed ({len(detections)} object(s), Delta={delta_score*100:.1f}%, Audio={audio_db:.1f} dBFS)."
            if (not has_alerts)
            else " | ".join(r.description for r in triggered_rules)
        )

        visual_basis = VisualTriggerBasis(
            violated=delta_score >= 0.05 or any(r.rule_id == "RULE_PROHIBITED_OBJECT" for r in triggered_rules),
            rule="PROHIBITED_ITEM" if any(r.rule_id == "RULE_PROHIBITED_OBJECT" for r in triggered_rules) else ("CANDIDATE_MOTION" if delta_score >= 0.05 else "NONE"),
            trigger_classification="AUTONOMOUS_GLOBAL",
            observed=delta_score,
            threshold=0.018,
            rationale=overall_rationale,
        )

        audio_basis = AudioTriggerBasis(
            violated=audio_trigger_fired,
            rule="TRANSIENT_SPIKE" if audio_trigger_fired else "NONE",
            observed_rms=0.0,
            baseline_rms=0.02,
            delta_percentage=f"{audio_db:.1f} dBFS",
            speech_harmonic_detected=False,
            rationale=f"Audio level: {audio_db:.1f} dBFS",
        )

        decision_basis = DecisionBasis(
            trigger_type="COMBINED" if (audio_trigger_fired and visual_basis.violated) else ("AUTONOMOUS_GLOBAL" if has_alerts else "NONE"),
            visual_trigger=visual_basis,
            audio_trigger=audio_basis,
            multimodal_correlation_score=0.85 if (audio_trigger_fired and visual_basis.violated) else 0.20,
        )

        return decision_basis, overall_rationale, triggered_rules, detection_details, alerts

    def calculate_pipeline_fps(self) -> float:
        now = time.time()
        self.recent_frame_times.append(now)
        self.recent_frame_times = [t for t in self.recent_frame_times if now - t <= 2.0]
        if len(self.recent_frame_times) <= 1:
            return 10.0
        time_span = self.recent_frame_times[-1] - self.recent_frame_times[0]
        if time_span <= 0:
            return 10.0
        return round(len(self.recent_frame_times) / time_span, 1)

    async def process_message(self, msg_id: str, data: Dict[str, str]) -> None:
        t_worker_start = time.time()
        stream_id = data.get("stream_id", "cam_01")
        sequence_id = int(data.get("sequence_id", "0"))
        t_client = float(data.get("t_client", str(t_worker_start)))
        t_ingest = float(data.get("t_ingest", str(t_worker_start)))
        frame_base64 = data.get("frame_base64", "")
        audio_base64 = data.get("audio_base64", "")

        # 1. Audio Transient Spike & Decibel Trigger
        audio_trigger = self.get_audio_trigger(stream_id)
        audio_trigger_fired, audio_db, audio_rms = audio_trigger.process_audio(audio_base64)

        # 2. Sub-2ms Frame-Delta Gatekeeper
        gatekeeper = self.get_edge_gatekeeper(stream_id)
        raw_image = decode_base64_image(frame_base64) if frame_base64 else None

        t_gatekeeper_start = time.time()
        is_static, delta_score, stats = gatekeeper.process_frame(
            raw_image,
            force_trigger=audio_trigger_fired,
        )
        gatekeeper_latency_ms = (time.time() - t_gatekeeper_start) * 1000.0
        stats_obj = TokenOptimizationStats(**stats)
        current_fps = self.calculate_pipeline_fps()

        # FAST-PATH: Drop static / redundant surveillance frames (<1.5ms, >95% VLM token reduction)
        if is_static:
            telemetry_service.record_frame_ingest(
                is_static=True,
                filter_latency_ms=gatekeeper_latency_ms,
                is_candidate_trigger=False,
            )
            roi_telemetry = telemetry_service.get_roi_telemetry()

            t_worker_done = time.time()
            t_broadcast = time.time()
            latency = calculate_latency_metrics(
                t_client=t_client,
                t_ingest=t_ingest,
                t_worker_start=t_worker_start,
                t_worker_done=t_worker_done,
                t_broadcast=t_broadcast,
                sla_target_ms=settings.TARGET_LATENCY_SLA_MS,
            )

            telemetry_payload = StreamTelemetryPayload(
                stream_id=stream_id,
                sequence_id=sequence_id,
                frame_id=sequence_id,
                timestamp=t_broadcast,
                worker_id=self.worker_id,
                is_static=True,
                delta_score=delta_score,
                audio_db=audio_db,
                trigger_fired=False,
                stats=stats_obj,
                roi_telemetry=roi_telemetry,
                detections=[],
                person_count=0,
                total_objects=0,
                alerts=[],
                anomaly_rationale=f"STATIC_FRAME: Redundant video frame filtered (Delta={delta_score:.3f} < {gatekeeper.delta_threshold}). Token reduction: {stats_obj.bandwidth_saving_percent}%.",
                latency=latency,
            )

            await redis_manager.publish_telemetry(stream_id, telemetry_payload.model_dump(by_alias=True))
            await redis_manager.ack_message(msg_id)
            self.processed_count += 1
            self.total_infer_time_ms += latency.inference_time_ms
            return

        # CANDIDATE EVENT PATH: Active visual motion or acoustic trigger
        telemetry_service.record_frame_ingest(
            is_static=False,
            filter_latency_ms=gatekeeper_latency_ms,
            is_candidate_trigger=True,
        )

        detections, person_count, img_width, img_height = self.run_cv_inference(raw_image) if raw_image is not None else ([], 0, 0, 0)
        config = await self.get_cached_alert_config(stream_id)
        roi_config = await self.get_cached_roi_config(stream_id)

        decision_basis, anomaly_rationale, triggered_rules, detection_details, alerts = self.evaluate_decision_matrix(
            stream_id=stream_id,
            sequence_id=sequence_id,
            detections=detections,
            person_count=person_count,
            audio_trigger_fired=audio_trigger_fired,
            audio_db=audio_db,
            delta_score=delta_score,
            config=config,
            roi_config=roi_config,
            width=img_width,
            height=img_height,
        )

        t_worker_done = time.time()
        t_broadcast = time.time()

        latency = calculate_latency_metrics(
            t_client=t_client,
            t_ingest=t_ingest,
            t_worker_start=t_worker_start,
            t_worker_done=t_worker_done,
            t_broadcast=t_broadcast,
            sla_target_ms=settings.TARGET_LATENCY_SLA_MS,
        )

        # 5. Forensic Snapshot & Cloud Multimodal VLM Synthesis for Candidate Events
        forensic_incident: Optional[ForensicAnomalyIncident] = None
        vlm_result: Optional[IncidentAnalysisResult] = None
        now_ts = time.time()
        last_snap = self.last_snapshot_time.get(stream_id, 0.0)
        should_capture_snapshot = (
            len(triggered_rules) > 0
            and raw_image is not None
            and (now_ts - last_snap >= 2.5)
        )

        if should_capture_snapshot:
            self.last_snapshot_time[stream_id] = now_ts
            incident_id = f"inc_{uuid.uuid4()}"
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            timestamp_utc = utc_now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            epoch_ms = int(t_client * 1000)

            # Asynchronous Cloud Multimodal VLM Analysis (Gemini 2.5 Flash)
            try:
                loop = asyncio.get_running_loop()
                vlm_result = await loop.run_in_executor(
                    self.thread_pool,
                    vlm_dispatcher.analyze_candidate_event,
                    stream_id,
                    raw_image,
                    delta_score,
                    audio_db,
                    [d.label for d in detections],
                    [r.rule_id for r in triggered_rules],
                )
                if vlm_result:
                    telemetry_service.record_cloud_dispatch(
                        tokens_used=258,
                        is_incident=vlm_result.is_incident,
                    )
            except Exception as e:
                logger.warning(f"VLM Dispatcher execution error: {e}")

            has_critical = any(
                r.rule_id in ("RULE_AUDIO_TRANSIENT_SPIKE", "RULE_PROHIBITED_OBJECT", "RULE_RESTRICTED_ZONE")
                for r in triggered_rules
            )
            severity = (vlm_result.severity.value if vlm_result else ("CRITICAL" if has_critical else "WARNING"))
            anomaly_summary = (
                f"{vlm_result.category.value} [{vlm_result.severity.value}]: {vlm_result.title}"
                if vlm_result
                else " | ".join([f"{r.rule_id}: {r.target_class or 'event'}" for r in triggered_rules])
            )
            if vlm_result and vlm_result.description:
                anomaly_rationale = vlm_result.description

            annotated_img = draw_forensic_annotations(
                image=raw_image,
                detections=[d.model_dump(by_alias=True) for d in detection_details],
                restricted_zone=None,
                incident_id=incident_id,
                timestamp_utc=timestamp_utc,
                anomaly_summary=anomaly_summary,
                max_dim=640,
            )
            snapshot_annotated_base64 = encode_image_to_data_uri_fast(annotated_img, max_dim=640, quality=65)

            audio_ctx = AudioContextDetail(
                audio_anomaly_flag=audio_trigger_fired,
                energy_rms=audio_rms,
                dominant_frequency_hz=0.0,
                vad_speech_detected=False,
            )

            telemetry_ctx = SystemTelemetryDetail(
                ingest_latency_ms=latency.ingestion_latency_ms,
                queue_dwell_ms=latency.queue_dwell_time_ms,
                inference_latency_ms=latency.inference_time_ms,
                total_e2e_latency_ms=latency.e2e_latency_ms,
                pipeline_fps=current_fps,
            )

            visual_ctx = VisualContextDetail(
                total_objects_detected=len(detections),
                detections=detection_details,
                snapshot_annotated_base64=snapshot_annotated_base64,
                snapshot_raw_base64=None,
            )

            forensic_incident = ForensicAnomalyIncident(
                incident_id=incident_id,
                stream_id=stream_id,
                timestamp_utc=timestamp_utc,
                epoch_ms=epoch_ms,
                severity=severity,
                anomaly_summary=anomaly_summary,
                decision_basis=decision_basis,
                anomaly_rationale=anomaly_rationale,
                triggered_rules=triggered_rules,
                visual_context=visual_ctx,
                audio_context=audio_ctx,
                system_telemetry=telemetry_ctx,
                vlm_synthesis=vlm_result,
            )

            asyncio.create_task(
                redis_manager.log_forensic_incident(
                    stream_id=stream_id,
                    incident_dict=forensic_incident.model_dump(by_alias=True),
                )
            )

            for alert in alerts:
                alert.snapshot_url = snapshot_annotated_base64

        roi_telemetry = telemetry_service.get_roi_telemetry()

        telemetry_payload = StreamTelemetryPayload(
            stream_id=stream_id,
            sequence_id=sequence_id,
            frame_id=sequence_id,
            timestamp=t_broadcast,
            worker_id=self.worker_id,
            is_static=False,
            delta_score=delta_score,
            audio_db=audio_db,
            trigger_fired=audio_trigger_fired or len(alerts) > 0,
            stats=stats_obj,
            roi_telemetry=roi_telemetry,
            detections=detections,
            person_count=person_count,
            total_objects=len(detections),
            alerts=alerts,
            forensic_incident=forensic_incident,
            decision_basis=decision_basis,
            vlm_synthesis=vlm_result,
            stream_roi=roi_config,
            anomaly_rationale=anomaly_rationale,
            latency=latency,
            frame_width=img_width,
            frame_height=img_height,
        )

        payload_dict = telemetry_payload.model_dump(by_alias=True)
        await redis_manager.publish_telemetry(stream_id, payload_dict)

        await redis_manager.record_metric_sample(
            stream_id=stream_id,
            e2e_ms=latency.e2e_latency_ms,
            ingest_ms=latency.ingestion_latency_ms,
            queue_ms=latency.queue_dwell_time_ms,
            infer_ms=latency.inference_time_ms,
            has_alert=len(alerts) > 0,
        )

        for alert in alerts:
            await redis_manager.log_alert_incident(stream_id, alert.model_dump())

        await redis_manager.ack_message(msg_id)
        self.processed_count += 1
        self.total_infer_time_ms += latency.inference_time_ms

    async def run(self) -> None:
        self.running = True
        logger.info(f"Worker '{self.worker_id}' starting Token Optimization Gateway loop on group '{settings.CONSUMER_GROUP_NAME}'...")

        await redis_manager.connect()
        await redis_manager.ensure_consumer_group()
        self.load_model()

        last_heartbeat_time = 0.0
        last_autoclaim_time = 0.0

        while self.running:
            try:
                now = time.time()

                if now - last_heartbeat_time > 5.0:
                    avg_infer = (
                        (self.total_infer_time_ms / self.processed_count)
                        if self.processed_count > 0
                        else 0.0
                    )
                    await redis_manager.update_worker_heartbeat(
                        self.worker_id, self.processed_count, avg_infer
                    )
                    last_heartbeat_time = now

                if now - last_autoclaim_time > 10.0:
                    stale_messages = await redis_manager.autoclaim_stale_messages(
                        consumer_name=self.worker_id,
                        min_idle_time_ms=10000,
                        count=10,
                    )
                    for msg_id, data in stale_messages:
                        logger.info(f"Claimed stale message {msg_id} for processing")
                        await self.process_message(msg_id, data)
                    last_autoclaim_time = now

                messages = await redis_manager.read_stream_group(
                    consumer_name=self.worker_id,
                    count=10,
                    block_ms=100,
                )

                if not messages:
                    await asyncio.sleep(0.01)
                    continue

                for msg_id, data in messages:
                    await self.process_message(msg_id, data)

            except asyncio.CancelledError:
                logger.info("Worker loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        logger.info(f"Worker '{self.worker_id}' stopped gracefully.")
        self.thread_pool.shutdown(wait=False)
        await redis_manager.close()

    def stop(self) -> None:
        self.running = False
        self.thread_pool.shutdown(wait=False)


def main():
    worker = MLInferenceWorker()

    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}, stopping worker...")
        worker.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user.")
    except Exception as e:
        logger.error(f"Worker fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
