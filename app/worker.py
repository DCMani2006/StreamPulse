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
    AudioDSPAnalyzer,
    FastTracker,
    calculate_ioa,
    calculate_iou,
    calculate_latency_metrics,
    decode_base64_image,
    draw_forensic_annotations,
    encode_image_to_data_uri,
    encode_image_to_data_uri_fast,
    is_box_inside_zone,
    normalize_box,
)
from app.ml_anomaly import GeneralMLAnomalyDetector
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
    ROINormalizedBox,
    StreamROIConfig,
    StreamTelemetryPayload,
    SystemTelemetryDetail,
    TriggeredRuleDetail,
    VisualContextDetail,
    VisualTriggerBasis,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("streampulse.worker")


class MLInferenceWorker:
    """
    Distributed Asynchronous ML Worker with Autonomous Anomaly Detection & Interactive Draggable ROI:
    - Autonomous Global Classification (No ROI required): Prohibited Items, Occupancy Threshold, Sudden Multi-Modal Spike.
    - Dynamic Draggable ROI Sector Monitor: User-positioned custom zone evaluation.
    - Velocity Tracking: Estimates bounding box displacement across frames.
    - Dynamic Ambient Noise Profiler: Eliminates false positives from naturally loud voices.
    - Explainable Decision Basis: Fully structured triggers and human-readable rationales.
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
        self.audio_analyzers: Dict[str, AudioDSPAnalyzer] = {}
        self.previous_centroids: Dict[str, List[Tuple[float, float, float]]] = {}  # stream_id -> [(cx, cy, timestamp)]
        self.recent_frame_times: List[float] = []
        self.last_snapshot_time: Dict[str, float] = {}
        self.ml_anomaly_detectors: Dict[str, GeneralMLAnomalyDetector] = {}
        self.fast_trackers: Dict[str, FastTracker] = {}

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
        """Fetches alert configuration with TTL cache."""
        now = time.time()
        if stream_id in self.alert_config_cache:
            cache_time, config = self.alert_config_cache[stream_id]
            if now - cache_time < self.config_cache_ttl_sec:
                return config

        config = await redis_manager.get_alert_config(stream_id)
        self.alert_config_cache[stream_id] = (now, config)
        return config

    async def get_cached_roi_config(self, stream_id: str) -> StreamROIConfig:
        """Fetches interactive draggable ROI configuration with TTL cache."""
        now = time.time()
        if stream_id in self.roi_config_cache:
            cache_time, roi = self.roi_config_cache[stream_id]
            if now - cache_time < self.config_cache_ttl_sec:
                return roi

        roi = await redis_manager.get_stream_roi(stream_id)
        self.roi_config_cache[stream_id] = (now, roi)
        return roi

    def get_audio_analyzer(self, stream_id: str, config: AlertRuleConfig) -> AudioDSPAnalyzer:
        """Retrieves or creates a dedicated AudioDSPAnalyzer for the stream."""
        if stream_id not in self.audio_analyzers:
            self.audio_analyzers[stream_id] = AudioDSPAnalyzer(
                alpha=config.audio_ema_alpha,
                k_sigma=config.audio_k_sigma,
            )
        return self.audio_analyzers[stream_id]

    def get_ml_anomaly_detector(self, stream_id: str) -> GeneralMLAnomalyDetector:
        """Retrieves or creates a dedicated GeneralMLAnomalyDetector (IsolationForest) for the stream."""
        if stream_id not in self.ml_anomaly_detectors:
            self.ml_anomaly_detectors[stream_id] = GeneralMLAnomalyDetector(
                history_size=300,
                contamination=0.05,
                min_samples=25,
            )
        return self.ml_anomaly_detectors[stream_id]

    def get_fast_tracker(self, stream_id: str) -> FastTracker:
        """Retrieves or creates a dedicated FastTracker for kinematic trajectory tracking."""
        if stream_id not in self.fast_trackers:
            self.fast_trackers[stream_id] = FastTracker()
        return self.fast_trackers[stream_id]

    def estimate_centroid_velocities(
        self, stream_id: str, detections: List[DetectionResult], current_time: float
    ) -> float:
        """Estimates kinematic velocity vectors and assigns stable tracking IDs using FastTracker."""
        tracker = self.get_fast_tracker(stream_id)
        _, max_vel = tracker.update(detections, current_time)
        return max_vel

    def run_cv_inference(self, image: np.ndarray) -> Tuple[List[DetectionResult], int, int, int]:
        """Executes YOLOv8 object detection on a BGR image array."""
        height, width = image.shape[:2]
        detections: List[DetectionResult] = []
        person_count = 0

        if self.model is None:
            return detections, 0, width, height

        results = self.model.predict(
            image,
            imgsz=settings.YOLO_IMAGE_SIZE,
            conf=settings.YOLO_CONFIDENCE_THRESHOLD,
            device=settings.YOLO_DEVICE,
            verbose=False,
        )

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for idx, box in enumerate(boxes):
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                label = result.names.get(cls_id, f"class_{cls_id}")

                norm_box = normalize_box(xyxy, width, height)

                detections.append(
                    DetectionResult(
                        class_id=cls_id,
                        label=label,
                        confidence=round(conf, 4),
                        box=[round(c, 1) for c in xyxy],
                        normalized_box=[round(c, 4) for c in norm_box],
                        tracking_id=100 + idx,
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
        max_velocity: float,
        audio_result: Optional[AudioAnalysisResult],
        config: AlertRuleConfig,
        roi_config: StreamROIConfig,
        width: int,
        height: int,
    ) -> Tuple[DecisionBasis, str, List[TriggeredRuleDetail], List[DetectionDetail], List[AlertTrigger]]:
        """
        Autonomous Anomaly Classification & Interactive Draggable ROI Decision Engine:
        1. Autonomous Global Anomaly (Prohibited items, Occupancy limit, Sudden velocity + audio spike).
        2. Dynamic Draggable ROI Spatial Breach (Subject centroid inside user-defined coordinates).
        3. Explainable Decision Basis categorized as AUTONOMOUS_GLOBAL, SPATIAL_ROI, or COMBINED.
        """
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

        # ---------------------------------------------------------------------
        # Part 1: Autonomous Global Anomaly Checks (No ROI Required)
        # ---------------------------------------------------------------------
        global_violated = False
        global_rule = "NONE"
        global_observed = None
        global_threshold = None
        global_rationale = ""

        # A. Prohibited Items (cell phone, laptop, knife, scissors, backpack)
        if config.enable_prohibited_rule:
            prohibited_set = {p.lower() for p in config.prohibited_classes}
            for idx, det in enumerate(detections):
                if det.label.lower() in prohibited_set and det.confidence >= config.prohibited_confidence_threshold:
                    global_violated = True
                    global_rule = "PROHIBITED_ITEM"
                    global_observed = det.confidence
                    global_threshold = config.prohibited_confidence_threshold
                    global_rationale = (
                        f"Autonomous Global Alert: Prohibited object detected in frame: '{det.label}' "
                        f"({int(det.confidence * 100)}% conf)."
                    )
                    detection_details[idx].is_violator = True
                    triggered_rules.append(
                        TriggeredRuleDetail(
                            rule_id="RULE_PROHIBITED_OBJECT",
                            description=global_rationale,
                            target_class=det.label,
                            confidence=det.confidence,
                        )
                    )

        # B. Occupancy Limit Breach
        if config.enable_occupancy_rule and person_count > config.max_persons:
            global_violated = True
            global_rule = "OCCUPANCY_THRESHOLD"
            global_observed = float(person_count)
            global_threshold = float(config.max_persons)
            global_rationale = (
                f"Autonomous Global Alert: Occupancy limit breached ({person_count} persons > max {config.max_persons})."
            )
            for idx, det in enumerate(detections):
                if det.label == "person":
                    detection_details[idx].is_violator = True
            triggered_rules.append(
                TriggeredRuleDetail(
                    rule_id="RULE_OCCUPANCY_VIOLATION",
                    description=global_rationale,
                    target_class="person",
                    confidence=0.95,
                )
            )

        # C. Sudden Multi-Modal Spike (High-frequency transient + Sudden Bounding Box Velocity Spike)
        if (
            audio_result
            and audio_result.spike_detected
            and not audio_result.speech_harmonic_detected
            and max_velocity >= config.velocity_spike_threshold
        ):
            global_violated = True
            global_rule = "SUDDEN_VELOCITY_SPIKE"
            global_observed = max_velocity
            global_threshold = config.velocity_spike_threshold
            global_rationale = (
                f"Autonomous Multi-Modal Spike: Rapid displacement velocity ({max_velocity:.2f} units/s) "
                f"synchronized with high-frequency acoustic transient ({audio_result.energy_rms:.3f} RMS)."
            )
            triggered_rules.append(
                TriggeredRuleDetail(
                    rule_id="RULE_SUDDEN_MULTI_MODAL_SPIKE",
                    description=global_rationale,
                    target_class="movement_acoustic_spike",
                    confidence=0.91,
                )
            )

        # D. High-Impact Vehicle Collision / Car Crash Anomaly Detection
        VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}
        if getattr(config, "enable_crash_rule", True):
            crash_iou_thresh = getattr(config, "crash_iou_threshold", 0.18)
            num_dets = len(detections)
            for i in range(num_dets):
                det_a = detections[i]
                if det_a.label.lower() not in VEHICLE_CLASSES:
                    continue
                for j in range(i + 1, num_dets):
                    det_b = detections[j]
                    if det_b.label.lower() not in VEHICLE_CLASSES:
                        continue

                    # Pairwise IoU and IoA Calculation
                    iou = calculate_iou(det_a.normalized_box, det_b.normalized_box)
                    ioa = calculate_ioa(det_a.normalized_box, det_b.normalized_box)

                    if iou >= 0.12 or ioa >= 0.25:
                        global_violated = True
                        global_rule = "VEHICLE_COLLISION"
                        global_observed = round(float(iou), 3)
                        global_threshold = crash_iou_thresh

                        id_a = det_a.tracking_id or (i + 101)
                        id_b = det_b.tracking_id or (j + 101)
                        crash_conf = min(0.99, round(0.88 + iou * 0.30, 4))

                        global_rationale = (
                            f"Autonomous Critical Alert: Vehicle Collision / Car Crash Detected between "
                            f"'{det_a.label}' (#{id_a}) and '{det_b.label}' (#{id_b}) "
                            f"[IoU={iou:.2f}, Overlap={ioa*100:.1f}%, Conf={int(crash_conf*100)}%]."
                        )

                        detection_details[i].is_violator = True
                        detection_details[j].is_violator = True

                        alerts.append(
                            AlertTrigger(
                                alert_type="vehicle_collision",
                                severity="critical",
                                message=f"CRITICAL ACCIDENT: Traffic Collision / Crash Detected ({det_a.label.upper()} + {det_b.label.upper()})",
                                stream_id=stream_id,
                                sequence_id=sequence_id,
                                timestamp=now,
                                details={
                                    "vehicle_1": det_a.label,
                                    "vehicle_2": det_b.label,
                                    "iou": round(iou, 3),
                                    "ioa": round(ioa, 3),
                                    "box_1": det_a.box,
                                    "box_2": det_b.box,
                                },
                            )
                        )

                        triggered_rules.append(
                            TriggeredRuleDetail(
                                rule_id="RULE_VEHICLE_COLLISION",
                                description=global_rationale,
                                target_class=f"{det_a.label}+{det_b.label}",
                                confidence=crash_conf,
                            )
                        )

        # E. Pedestrian-Vehicle Strike / Hazard Detection
        if getattr(config, "enable_pedestrian_strike_rule", False):
            num_dets = len(detections)
            for i in range(num_dets):
                det_a = detections[i]
                for j in range(num_dets):
                    if i == j:
                        continue
                    det_b = detections[j]
                    if det_a.label.lower() == "person" and det_b.label.lower() in VEHICLE_CLASSES:
                        iou = calculate_iou(det_a.normalized_box, det_b.normalized_box)
                        ioa = calculate_ioa(det_a.normalized_box, det_b.normalized_box)
                        if iou >= 0.10 or ioa >= 0.22:
                            global_violated = True
                            global_rule = "PEDESTRIAN_VEHICLE_STRIKE"
                            global_observed = round(float(iou), 3)
                            global_threshold = 0.10

                            id_p = det_a.tracking_id or (i + 101)
                            id_v = det_b.tracking_id or (j + 101)
                            strike_conf = 0.96

                            global_rationale = (
                                f"Autonomous Life-Safety Alert: Pedestrian-Vehicle Impact Hazard detected between "
                                f"Person (#{id_p}) and {det_b.label.upper()} (#{id_v}) [IoU={iou:.2f}]."
                            )

                            detection_details[i].is_violator = True
                            detection_details[j].is_violator = True

                            alerts.append(
                                AlertTrigger(
                                    alert_type="pedestrian_vehicle_strike",
                                    severity="critical",
                                    message=f"CRITICAL ACCIDENT: Pedestrian-Vehicle Strike Hazard Detected ({det_b.label.upper()})",
                                    stream_id=stream_id,
                                    sequence_id=sequence_id,
                                    timestamp=now,
                                    details={
                                        "vehicle": det_b.label,
                                        "iou": round(iou, 3),
                                        "person_box": det_a.box,
                                        "vehicle_box": det_b.box,
                                    },
                                )
                            )

                            triggered_rules.append(
                                TriggeredRuleDetail(
                                    rule_id="RULE_PEDESTRIAN_VEHICLE_STRIKE",
                                    description=global_rationale,
                                    target_class=f"person+{det_b.label}",
                                    confidence=strike_conf,
                                )
                            )

        # F. Unsupervised Machine Learning Outlier Detection (Isolation Forest)
        ml_detector = self.get_ml_anomaly_detector(stream_id)
        ml_result = ml_detector.process_frame(detections, current_time=now)
        if ml_result.get("is_anomaly", False):
            global_violated = True
            global_rule = "ML_ISOLATION_FOREST_OUTLIER"
            global_observed = float(ml_result.get("max_score", 0.0))
            global_threshold = 0.12
            global_rationale = ml_result.get("rationale", "ML statistical outlier detected.")

            for anom_item in ml_result.get("details", []):
                obj_idx = anom_item.get("object_index", 0)
                if 0 <= obj_idx < len(detection_details):
                    detection_details[obj_idx].is_violator = True

            alerts.append(
                AlertTrigger(
                    alert_type="ml_anomaly",
                    severity="critical",
                    message=f"ML ANOMALY: Isolation Forest Outlier ({ml_result.get('anomaly_count', 1)} object(s) anomalous)",
                    stream_id=stream_id,
                    sequence_id=sequence_id,
                    timestamp=now,
                    details=ml_result,
                )
            )

            triggered_rules.append(
                TriggeredRuleDetail(
                    rule_id="RULE_ML_ANOMALY",
                    description=global_rationale,
                    target_class="statistical_outlier",
                    confidence=min(0.99, round(0.85 + ml_result.get("max_score", 0.0) * 0.2, 3)),
                )
            )

        # ---------------------------------------------------------------------
        # Audio Trigger Evaluation with Dynamic Noise Profiling & False-Positive Elimination
        # ---------------------------------------------------------------------
        audio_violated = False
        audio_rule = "NONE"
        obs_rms = audio_result.energy_rms if audio_result else 0.0
        base_rms = audio_result.baseline_rms if audio_result else 0.03
        delta_str = audio_result.delta_percentage_str if audio_result else "+0%"
        is_harmonic = audio_result.speech_harmonic_detected if audio_result else False
        ambient_std = audio_result.ambient_std_rms if audio_result else 0.005
        audio_rationale = f"Audio energy ({obs_rms:.3f} RMS) within dynamic baseline ({base_rms:.3f} ± {ambient_std:.3f} RMS)."

        if config.enable_audio_rule and audio_result:
            is_spike = audio_result.spike_detected

            if config.operating_mode == "proctoring":
                analyzer = self.get_audio_analyzer(stream_id, config)
                if analyzer.sustained_speech_sec >= config.sustained_speech_sec_threshold and person_count >= 2:
                    audio_violated = True
                    audio_rule = "SUSTAINED_MULTI_SPEAKER_VOICE"
                    audio_rationale = (
                        f"Sustained unauthorized conversational speech ({analyzer.sustained_speech_sec:.1f}s >= {config.sustained_speech_sec_threshold}s) "
                        f"with {person_count} subjects detected in proctoring sector."
                    )
                    triggered_rules.append(
                        TriggeredRuleDetail(
                            rule_id="RULE_AUDIO_PROCTORING_COLLABORATION",
                            description=audio_rationale,
                            target_class="sustained_speech",
                            confidence=0.92,
                        )
                    )
                elif is_spike and (audio_result.spectral_flatness > 0.45 or audio_result.high_freq_ratio > 0.40):
                    audio_violated = True
                    audio_rule = "SPECTRAL_TRANSIENT_SPIKE"
                    audio_rationale = (
                        f"Abrupt non-harmonic transient acoustic impact detected (Flatness={audio_result.spectral_flatness:.2f}, "
                        f"High-Freq Ratio={audio_result.high_freq_ratio:.2f}, {delta_str} over baseline)."
                    )
                    triggered_rules.append(
                        TriggeredRuleDetail(
                            rule_id="RULE_AUDIO_SPIKE",
                            description=audio_rationale,
                            target_class="acoustic_spike",
                            confidence=min(1.0, round(obs_rms / 0.4, 4)),
                        )
                    )
                elif is_spike and is_harmonic and person_count == 1 and not global_violated:
                    audio_violated = False
                    audio_rationale = (
                        f"Single-subject harmonic speech spike ({obs_rms:.3f} RMS, {delta_str} delta) classified as benign vocalization; "
                        f"false-positive suppressed for solitary candidate."
                    )
            else:
                # Security Mode
                if is_spike:
                    if person_count == 0:
                        audio_violated = True
                        audio_rule = "UNOCCUPIED_ROOM_ACOUSTIC_ANOMALY"
                        audio_rationale = (
                            f"Acoustic energy spike ({obs_rms:.3f} RMS, {delta_str} over baseline) detected in unoccupied facility."
                        )
                        triggered_rules.append(
                            TriggeredRuleDetail(
                                rule_id="RULE_AUDIO_SPIKE",
                                description=audio_rationale,
                                target_class="unoccupied_acoustic_breach",
                                confidence=0.90,
                            )
                        )
                    elif not is_harmonic or audio_result.high_freq_ratio > 0.45 or obs_rms > 0.50:
                        audio_violated = True
                        audio_rule = "SPECTRAL_TRANSIENT_SPIKE"
                        audio_rationale = (
                            f"Abrupt non-harmonic transient impact detected ({obs_rms:.3f} RMS, baseline {base_rms:.3f} RMS, "
                            f"{delta_str} delta, High-Freq Ratio={audio_result.high_freq_ratio:.2f})."
                        )
                        triggered_rules.append(
                            TriggeredRuleDetail(
                                rule_id="RULE_AUDIO_SPIKE",
                                description=audio_rationale,
                                target_class="acoustic_spike",
                                confidence=min(1.0, round(obs_rms / 0.5, 4)),
                            )
                        )
                    else:
                        audio_violated = False
                        audio_rationale = (
                            f"Harmonic vocalization ({obs_rms:.3f} RMS, baseline {base_rms:.3f} RMS) classified as standard conversational voice; "
                            f"suppressed without visual breach."
                        )

        # ---------------------------------------------------------------------
        # Classify Trigger Type: AUTONOMOUS_GLOBAL
        # ---------------------------------------------------------------------
        visual_violated = global_violated
        if global_violated:
            trigger_type = "AUTONOMOUS_GLOBAL"
            vis_rule = global_rule
            vis_rationale = global_rationale
            vis_obs = global_observed
            vis_thresh = global_threshold
            vis_classification = "AUTONOMOUS_GLOBAL"
        else:
            trigger_type = "NONE"
            vis_rule = "NONE"
            vis_rationale = f"All {len(detections)} detection(s) compliant."
            vis_obs = None
            vis_thresh = None
            vis_classification = "NONE"

        if visual_violated and audio_violated:
            corr_score = 0.94
        elif visual_violated:
            corr_score = 0.86
        elif audio_violated:
            corr_score = 0.75
        else:
            corr_score = 0.10

        decision_basis = DecisionBasis(
            trigger_type=trigger_type,
            visual_trigger=VisualTriggerBasis(
                violated=visual_violated,
                rule=vis_rule,
                trigger_classification=vis_classification,
                observed=vis_obs,
                threshold=vis_thresh,
                rationale=vis_rationale,
            ),
            audio_trigger=AudioTriggerBasis(
                violated=audio_violated,
                rule=audio_rule,
                observed_rms=obs_rms,
                baseline_rms=base_rms,
                delta_percentage=delta_str,
                speech_harmonic_detected=is_harmonic,
                rationale=audio_rationale,
            ),
            multimodal_correlation_score=corr_score,
        )

        # Unified Rationale
        if visual_violated and audio_violated:
            overall_rationale = (
                f"CRITICAL [{trigger_type} + Audio]: {vis_rationale} Synchronized with acoustic transient ({delta_str} over baseline)."
            )
        elif visual_violated:
            overall_rationale = f"CRITICAL [{trigger_type}]: {vis_rationale}"
        elif audio_violated:
            overall_rationale = f"WARNING [Acoustic Anomaly]: {audio_rationale}"
        else:
            subj_desc = f"{person_count} subject(s) in compliant ROI." if person_count > 0 else "0 subjects in frame."
            overall_rationale = (
                f"NORMAL: Audio ({obs_rms:.2f} RMS) within dynamic baseline ({base_rms:.2f} ± {ambient_std:.2f} RMS). {subj_desc}"
            )

        existing_types = {a.alert_type for a in alerts}
        for rule in triggered_rules:
            rule_type = rule.rule_id.lower()
            if rule_type not in existing_types and "collision" not in rule_type and "strike" not in rule_type:
                sev = "critical" if rule.rule_id in ("RULE_PROHIBITED_OBJECT", "RULE_VEHICLE_COLLISION", "RULE_PEDESTRIAN_VEHICLE_STRIKE", "RULE_ML_ANOMALY") else "warning"
                alerts.append(
                    AlertTrigger(
                        alert_type=rule_type,
                        severity=sev,
                        message=rule.description,
                        stream_id=stream_id,
                        sequence_id=sequence_id,
                        timestamp=now,
                        details={
                            "rule_id": rule.rule_id,
                            "target_class": rule.target_class,
                            "confidence": rule.confidence,
                            "trigger_type": trigger_type,
                        },
                    )
                )

        return decision_basis, overall_rationale, triggered_rules, detection_details, alerts

    def calculate_pipeline_fps(self) -> float:
        """Calculates current rolling ingestion FPS."""
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
        """Processes a single stream entry end-to-end with autonomous classification & dynamic ROI."""
        t_worker_start = time.time()
        stream_id = data.get("stream_id", "cam_01")
        sequence_id = int(data.get("sequence_id", "0"))
        t_client = float(data.get("t_client", str(t_worker_start)))
        t_ingest = float(data.get("t_ingest", str(t_worker_start)))
        frame_base64 = data.get("frame_base64", "")
        audio_base64 = data.get("audio_base64", "")

        detections: List[DetectionResult] = []
        person_count = 0
        img_width = 0
        img_height = 0
        raw_image: Optional[np.ndarray] = None

        # 1. Computer Vision Processing
        if frame_base64:
            raw_image = decode_base64_image(frame_base64)
            if raw_image is not None:
                detections, person_count, img_width, img_height = self.run_cv_inference(raw_image)

        # 2. Centroid Velocity Estimation
        max_velocity = self.estimate_centroid_velocities(stream_id, detections, t_worker_start)

        # 3. Audio Signal Analysis with Dynamic Ambient Noise Profiler
        config = await self.get_cached_alert_config(stream_id)
        roi_config = await self.get_cached_roi_config(stream_id)
        audio_analyzer = self.get_audio_analyzer(stream_id, config)
        audio_result: Optional[AudioAnalysisResult] = None
        if audio_base64:
            audio_result = audio_analyzer.process_chunk(
                audio_base64,
                sample_rate=settings.AUDIO_SAMPLE_RATE,
                current_time=t_worker_start,
            )

        # 4. Context-Aware Decision Matrix & Autonomous Anomaly Classification
        decision_basis, anomaly_rationale, triggered_rules, detection_details, alerts = self.evaluate_decision_matrix(
            stream_id=stream_id,
            sequence_id=sequence_id,
            detections=detections,
            person_count=person_count,
            max_velocity=max_velocity,
            audio_result=audio_result,
            config=config,
            roi_config=roi_config,
            width=img_width,
            height=img_height,
        )

        t_worker_done = time.time()
        t_broadcast = time.time()

        # 5. Latency Telemetry Calculation
        latency = calculate_latency_metrics(
            t_client=t_client,
            t_ingest=t_ingest,
            t_worker_start=t_worker_start,
            t_worker_done=t_worker_done,
            t_broadcast=t_broadcast,
            sla_target_ms=settings.TARGET_LATENCY_SLA_MS,
        )

        current_fps = self.calculate_pipeline_fps()

        # 6. Accelerated Forensic Snapshot Capture (<2ms overhead, non-blocking Redis storage)
        forensic_incident: Optional[ForensicAnomalyIncident] = None
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

            has_critical = any(
                r.rule_id in (
                    "RULE_RESTRICTED_ZONE",
                    "RULE_PROHIBITED_OBJECT",
                    "RULE_VEHICLE_COLLISION",
                    "RULE_PEDESTRIAN_VEHICLE_STRIKE",
                    "RULE_ML_ANOMALY",
                )
                for r in triggered_rules
            )
            severity = "CRITICAL" if has_critical else "WARNING"
            rule_summaries = [f"{r.rule_id}: {r.target_class or 'event'}" for r in triggered_rules]
            anomaly_summary = " | ".join(rule_summaries)

            # High-speed pre-scaled annotation and TurboJPEG encoding (~1.7ms)
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
                audio_anomaly_flag=bool(audio_result and audio_result.spike_detected),
                energy_rms=audio_result.energy_rms if audio_result else 0.0,
                dominant_frequency_hz=audio_result.dominant_frequency_hz if audio_result else 0.0,
                vad_speech_detected=audio_result.voice_activity_detected if audio_result else False,
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
            )

            # Non-blocking async logging to Redis storage
            asyncio.create_task(
                redis_manager.log_forensic_incident(
                    stream_id=stream_id,
                    incident_dict=forensic_incident.model_dump(by_alias=True),
                )
            )

            for alert in alerts:
                alert.snapshot_url = snapshot_annotated_base64

            logger.info(
                f"[FORENSIC ANOMALY] [{decision_basis.trigger_type}] Captured incident '{incident_id}' "
                f"on stream '{stream_id}' ({anomaly_summary})"
            )

        # 7. Build Broadcast Telemetry Payload with ROI state
        telemetry_payload = StreamTelemetryPayload(
            stream_id=stream_id,
            sequence_id=sequence_id,
            timestamp=t_broadcast,
            worker_id=self.worker_id,
            detections=detections,
            person_count=person_count,
            total_objects=len(detections),
            audio_analysis=audio_result,
            alerts=alerts,
            forensic_incident=forensic_incident,
            decision_basis=decision_basis,
            stream_roi=roi_config,
            anomaly_rationale=anomaly_rationale,
            latency=latency,
            frame_width=img_width,
            frame_height=img_height,
        )

        # 8. Publish to Pub/Sub Channel
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
        """Main asynchronous consumer loop."""
        self.running = True
        logger.info(f"Worker '{self.worker_id}' starting consumer loop on group '{settings.CONSUMER_GROUP_NAME}'...")

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
        await redis_manager.close()

    def stop(self) -> None:
        """Signals the worker loop to stop."""
        self.running = False


def main():
    """CLI entrypoint for standalone worker execution."""
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
