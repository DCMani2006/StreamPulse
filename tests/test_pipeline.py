import base64
import json
import time
import numpy as np
import pytest

from app.config import settings
from app.pipeline_utils import (
    AudioDSPAnalyzer,
    calculate_iou,
    calculate_latency_metrics,
    decode_base64_image,
    draw_forensic_annotations,
    encode_image_to_base64,
    encode_image_to_data_uri,
    is_box_inside_zone,
    normalize_box,
)
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
    FrameIngestPayload,
    LatencyTelemetry,
    ROINormalizedBox,
    StreamROIConfig,
    StreamTelemetryPayload,
    SystemMetricsResponse,
    SystemTelemetryDetail,
    TriggeredRuleDetail,
    VisualContextDetail,
    VisualTriggerBasis,
)
from app.worker import MLInferenceWorker


def test_base64_image_encode_decode():
    """Verifies that images can be encoded to JPEG base64 and decoded back losslessly."""
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    img[50:150, 60:200] = [0, 255, 0]

    b64_str = encode_image_to_base64(img, quality=85)
    assert isinstance(b64_str, str)
    assert len(b64_str) > 0

    decoded_img = decode_base64_image(b64_str)
    assert decoded_img is not None
    assert decoded_img.shape == (240, 320, 3)


def test_box_normalization_and_iou():
    """Verifies bounding box coordinate normalization and IoU math."""
    box_px = [100.0, 50.0, 300.0, 250.0]
    norm_box = normalize_box(box_px, width=1000, height=500)
    assert norm_box == [0.1, 0.1, 0.3, 0.5]


def test_audio_dsp_analyzer_ema_and_spectral_features():
    """Verifies AudioDSPAnalyzer online EMA baseline tracking and spectral feature extraction."""
    analyzer = AudioDSPAnalyzer(alpha=0.05, k_sigma=2.5)
    sample_rate = 16000
    duration = 0.1
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    ambient_signal = (0.01 * np.random.randn(num_samples) * 32767).astype(np.int16)
    b64_ambient = base64.b64encode(ambient_signal.tobytes()).decode("utf-8")

    res1 = analyzer.process_chunk(b64_ambient, sample_rate=sample_rate, current_time=1.0)
    assert res1.spike_detected is False
    assert res1.baseline_rms > 0.0

    speech_signal = (0.15 * np.sin(2 * np.pi * 200 * t) * 32767).astype(np.int16)
    b64_speech = base64.b64encode(speech_signal.tobytes()).decode("utf-8")
    res_speech = analyzer.process_chunk(b64_speech, sample_rate=sample_rate, current_time=1.1)
    assert res_speech.speech_harmonic_detected is True
    assert res_speech.spectral_flatness < 0.45


def test_autonomous_global_anomaly_detection():
    """Verifies Autonomous Global Anomaly (Prohibited items, Occupancy limit) with NO ROI required."""
    worker = MLInferenceWorker(worker_id="test-worker")

    config = AlertRuleConfig(
        stream_id="cam_01",
        operating_mode="security",
        max_persons=1,
        prohibited_classes=["cell phone", "laptop", "knife", "scissors"],
        prohibited_confidence_threshold=0.50,
        enable_prohibited_rule=True,
        enable_occupancy_rule=True,
    )

    roi_disabled = StreamROIConfig(
        stream_id="cam_01",
        roi_enabled=False,
        roi_normalized=ROINormalizedBox(x1=0.20, y1=0.30, x2=0.70, y2=0.80),
        roi_label="Disabled Sector",
    )

    # Prohibited object (laptop) detected anywhere on screen
    detections = [
        DetectionResult(
            class_id=63,
            label="laptop",
            confidence=0.89,
            box=[50.0, 50.0, 200.0, 200.0],
            normalized_box=[0.05, 0.05, 0.20, 0.20],
        )
    ]

    decision_basis, rationale, rules, details, alerts = worker.evaluate_decision_matrix(
        stream_id="cam_01",
        sequence_id=1,
        detections=detections,
        person_count=0,
        max_velocity=0.02,
        audio_result=None,
        config=config,
        roi_config=roi_disabled,
        width=1000,
        height=1000,
    )

    assert decision_basis.trigger_type == "AUTONOMOUS_GLOBAL"
    assert decision_basis.visual_trigger.violated is True
    assert decision_basis.visual_trigger.rule == "PROHIBITED_ITEM"
    assert "Autonomous Global Alert" in decision_basis.visual_trigger.rationale
    assert len(rules) == 1
    assert rules[0].rule_id == "RULE_PROHIBITED_OBJECT"


def test_interactive_draggable_roi_spatial_breach():
    """Verifies Dynamic Draggable ROI centroid breach detection when roi_enabled is True."""
    worker = MLInferenceWorker(worker_id="test-worker")

    config = AlertRuleConfig(
        stream_id="cam_01",
        operating_mode="security",
        max_persons=5,
        enable_prohibited_rule=False,
        enable_occupancy_rule=False,
    )

    # User configured interactive ROI
    custom_roi = StreamROIConfig(
        stream_id="cam_01",
        roi_enabled=True,
        roi_normalized=ROINormalizedBox(x1=0.30, y1=0.30, x2=0.70, y2=0.70),
        roi_label="Server Rack Perimeter",
    )

    # 1. Detection centroid OUTSIDE user ROI (cx=0.15, cy=0.15)
    outside_person = [
        DetectionResult(
            class_id=0,
            label="person",
            confidence=0.92,
            box=[100.0, 100.0, 200.0, 200.0],
            normalized_box=[0.10, 0.10, 0.20, 0.20],
        )
    ]

    basis_clean, _, rules_clean, _, _ = worker.evaluate_decision_matrix(
        stream_id="cam_01",
        sequence_id=2,
        detections=outside_person,
        person_count=1,
        max_velocity=0.01,
        audio_result=None,
        config=config,
        roi_config=custom_roi,
        width=1000,
        height=1000,
    )
    assert basis_clean.trigger_type == "NONE"
    assert len(rules_clean) == 0

    # 2. Detection centroid INSIDE user ROI (cx=0.50, cy=0.50)
    inside_person = [
        DetectionResult(
            class_id=0,
            label="person",
            confidence=0.95,
            box=[400.0, 400.0, 600.0, 600.0],
            normalized_box=[0.40, 0.40, 0.60, 0.60],
        )
    ]

    basis_breach, rationale_breach, rules_breach, _, _ = worker.evaluate_decision_matrix(
        stream_id="cam_01",
        sequence_id=3,
        detections=inside_person,
        person_count=1,
        max_velocity=0.03,
        audio_result=None,
        config=config,
        roi_config=custom_roi,
        width=1000,
        height=1000,
    )

    assert basis_breach.trigger_type == "SPATIAL_ROI"
    assert basis_breach.visual_trigger.violated is True
    assert basis_breach.visual_trigger.rule == "RESTRICTED_ROI_SPATIAL"
    assert "Server Rack Perimeter" in rationale_breach
    assert len(rules_breach) == 1
    assert rules_breach[0].rule_id == "RULE_RESTRICTED_ZONE"


def test_combined_global_and_spatial_triggers():
    """Verifies COMBINED trigger classification when both autonomous global and spatial ROI fire simultaneously."""
    worker = MLInferenceWorker(worker_id="test-worker")

    config = AlertRuleConfig(
        stream_id="cam_01",
        operating_mode="security",
        max_persons=1,
        prohibited_classes=["knife"],
        prohibited_confidence_threshold=0.50,
        enable_prohibited_rule=True,
        enable_occupancy_rule=True,
    )

    custom_roi = StreamROIConfig(
        stream_id="cam_01",
        roi_enabled=True,
        roi_normalized=ROINormalizedBox(x1=0.20, y1=0.20, x2=0.80, y2=0.80),
        roi_label="Vault Vault Entry",
    )

    detections = [
        # Person inside ROI
        DetectionResult(
            class_id=0,
            label="person",
            confidence=0.96,
            box=[300.0, 300.0, 500.0, 600.0],
            normalized_box=[0.30, 0.30, 0.50, 0.60],
        ),
        # Prohibited item (knife)
        DetectionResult(
            class_id=43,
            label="knife",
            confidence=0.91,
            box=[350.0, 400.0, 420.0, 480.0],
            normalized_box=[0.35, 0.40, 0.42, 0.48],
        ),
    ]

    basis, rationale, rules, _, _ = worker.evaluate_decision_matrix(
        stream_id="cam_01",
        sequence_id=4,
        detections=detections,
        person_count=1,
        max_velocity=0.05,
        audio_result=None,
        config=config,
        roi_config=custom_roi,
        width=1000,
        height=1000,
    )

    assert basis.trigger_type == "COMBINED"
    assert basis.visual_trigger.violated is True
    assert len(rules) >= 2


def test_forensic_incident_schema_with_roi_and_triggers():
    """Verifies complete ForensicAnomalyIncident JSON serialization with ROI and trigger metadata."""
    incident = ForensicAnomalyIncident(
        incident_id="inc_9a82b1-5542-491a-8219-c90192a81201",
        stream_id="cam_01",
        timestamp_utc="2026-08-29T15:02:00.120Z",
        epoch_ms=1724914920120,
        severity="CRITICAL",
        anomaly_summary="Spatial ROI Breach with Autonomous Prohibited Item",
        decision_basis=DecisionBasis(
            trigger_type="COMBINED",
            visual_trigger=VisualTriggerBasis(
                violated=True,
                rule="PROHIBITED_ITEM + RESTRICTED_ROI_SPATIAL",
                trigger_classification="COMBINED",
                observed=0.45,
                threshold=0.20,
                rationale="Subject entered Server Rack Perimeter holding prohibited laptop.",
            ),
            audio_trigger=AudioTriggerBasis(
                violated=False,
                rule="NONE",
                observed_rms=0.025,
                baseline_rms=0.024,
                delta_percentage="+4%",
                speech_harmonic_detected=False,
                rationale="Acoustics compliant with ambient background.",
            ),
            multimodal_correlation_score=0.86,
        ),
        anomaly_rationale="CRITICAL [COMBINED]: Spatial ROI Breach (Server Rack Perimeter) + Prohibited Item 'laptop' detected.",
        triggered_rules=[
            TriggeredRuleDetail(
                rule_id="RULE_RESTRICTED_ZONE",
                description="Spatial ROI breach in Server Rack Perimeter",
                target_class="person",
                confidence=0.96,
            ),
            TriggeredRuleDetail(
                rule_id="RULE_PROHIBITED_OBJECT",
                description="Prohibited laptop detected",
                target_class="laptop",
                confidence=0.91,
            ),
        ],
        visual_context=VisualContextDetail(
            total_objects_detected=2,
            detections=[
                DetectionDetail(
                    object_id="obj_01",
                    class_name="person",
                    confidence=0.96,
                    box_normalized=[0.40, 0.40, 0.60, 0.70],
                    box_pixels=[400, 400, 600, 700],
                    is_violator=True,
                ),
            ],
            snapshot_annotated_base64="data:image/jpeg;base64,/9j/4AAQSkZJRg==",
            snapshot_raw_base64="data:image/jpeg;base64,/9j/4AAQSkZJRg==",
        ),
        audio_context=AudioContextDetail(
            audio_anomaly_flag=False,
            energy_rms=0.025,
            dominant_frequency_hz=120.0,
            vad_speech_detected=False,
        ),
        system_telemetry=SystemTelemetryDetail(
            ingest_latency_ms=12.4,
            queue_dwell_ms=4.1,
            inference_latency_ms=38.2,
            total_e2e_latency_ms=54.7,
            pipeline_fps=29.2,
        ),
    )

    json_str = incident.model_dump_json(by_alias=True)
    raw_dict = json.loads(json_str)

    assert raw_dict["decision_basis"]["trigger_type"] == "COMBINED"
    assert raw_dict["decision_basis"]["visual_trigger"]["trigger_classification"] == "COMBINED"
    assert raw_dict["visual_context"]["detections"][0]["is_violator"] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
