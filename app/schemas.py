from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.incident_schema import (
    IncidentAnalysisResult,
    IncidentCategory,
    SeverityLevel,
)
from app.services.telemetry_service import (
    CloudSavingsDetail,
    ROITelemetrySnapshot,
    TokenStatsDetail,
)


class FrameIngestPayload(BaseModel):
    """Payload sent by edge devices/cameras via WebSocket or HTTP POST."""
    stream_id: str = Field(..., description="Unique stream identifier (e.g. cam_01)")
    sequence_id: Optional[int] = Field(None, description="Monotonic sequence number from client")
    t_client: float = Field(..., description="Epoch timestamp recorded at the edge client (seconds)")
    frame_base64: Optional[str] = Field(None, description="Base64-encoded JPEG/PNG video frame")
    audio_base64: Optional[str] = Field(None, description="Base64-encoded raw PCM audio chunk")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom stream metadata")


class IngestResponse(BaseModel):
    """Immediate acknowledgment response for edge ingestion."""
    status: str = "queued"
    stream_id: str
    sequence_id: int
    t_ingest: float
    message: str = "Frame successfully queued for inference"


class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float
    normalized: bool = False


class DetectionResult(BaseModel):
    """Single object detection result produced by YOLOv8."""
    class_id: int
    label: str
    confidence: float
    box: List[float] = Field(..., description="Pixel coordinates [x1, y1, x2, y2]")
    normalized_box: List[float] = Field(..., description="Normalized coordinates [x1, y1, x2, y2] in [0.0, 1.0]")
    tracking_id: Optional[int] = None
    velocity: Optional[float] = Field(0.0, description="Estimated centroid velocity (normalized units / frame)")


class AudioAnalysisResult(BaseModel):
    """Audio signal processing and dynamic acoustic profiler results."""
    energy_rms: float = Field(..., description="Root-mean-square amplitude")
    energy_db: float = Field(..., description="Estimated decibel level")
    zero_crossing_rate: float = Field(..., description="Zero-crossing rate frequency metric")
    voice_activity_detected: bool = Field(False, description="Whether speech/voice activity is detected")
    spike_detected: bool = Field(False, description="Whether audio energy exceeded the dynamic threshold")
    dominant_frequency_hz: float = Field(0.0, description="Dominant audio frequency component (Hz)")
    baseline_rms: float = Field(0.03, description="Exponential moving average ambient baseline RMS")
    ambient_std_rms: float = Field(0.005, description="Ambient noise standard deviation (sigma)")
    dynamic_threshold_rms: float = Field(0.06, description="Dynamic alert threshold (baseline + K*sigma)")
    high_freq_ratio: float = Field(0.0, description="High-frequency energy ratio (>3.5kHz / total)")
    spectral_flatness: float = Field(0.0, description="Spectral flatness / Wiener entropy (0=harmonic, 1=transient/noise)")
    speech_harmonic_detected: bool = Field(False, description="Whether harmonic voiced speech format is detected")
    delta_percentage_str: str = Field("+0%", description="Percentage delta relative to baseline")


class LatencyTelemetry(BaseModel):
    """Granular latency telemetry capturing every stage of the pipeline."""
    t_client: float = Field(..., description="Client capture epoch timestamp")
    t_ingest: float = Field(..., description="Ingestion gateway arrival epoch timestamp")
    t_worker_start: float = Field(..., description="Worker processing start epoch timestamp")
    t_worker_done: float = Field(..., description="Worker inference completion epoch timestamp")
    t_broadcast: float = Field(..., description="Pub/Sub broadcast dispatch epoch timestamp")
    ingestion_latency_ms: float = Field(..., description="t_ingest - t_client (ms)")
    queue_dwell_time_ms: float = Field(..., description="t_worker_start - t_ingest (ms)")
    inference_time_ms: float = Field(..., description="t_worker_done - t_worker_start (ms)")
    e2e_latency_ms: float = Field(..., description="t_broadcast - t_client (ms)")
    sla_met: bool = Field(True, description="Whether e2e latency satisfies SLA (< 300ms)")


class AlertTrigger(BaseModel):
    """Security or operational alert triggered by active rules."""
    alert_type: str = Field(..., description="Type of alert: person_count, zone_intrusion, audio_spike, prohibited_object")
    severity: str = Field("warning", description="Severity: info, warning, critical")
    message: str = Field(..., description="Human-readable alert description")
    stream_id: str
    sequence_id: int
    timestamp: float
    details: Dict[str, Any] = Field(default_factory=dict)
    snapshot_url: Optional[str] = None


# -----------------------------------------------------------------------------
# Dynamic Draggable ROI Configuration
# -----------------------------------------------------------------------------

class ROINormalizedBox(BaseModel):
    """Normalized coordinate box [x1, y1, x2, y2] in range [0.0, 1.0]."""
    x1: float = Field(0.20, ge=0.0, le=1.0)
    y1: float = Field(0.30, ge=0.0, le=1.0)
    x2: float = Field(0.70, ge=0.0, le=1.0)
    y2: float = Field(0.80, ge=0.0, le=1.0)


class StreamROIConfig(BaseModel):
    """Interactive Draggable Region of Interest (ROI) State."""
    stream_id: str = Field(..., description="Stream identifier (e.g. cam_01)")
    roi_enabled: bool = Field(True, description="Whether custom draggable ROI is active")
    roi_normalized: ROINormalizedBox = Field(default_factory=ROINormalizedBox)
    roi_label: str = Field("Server Rack Perimeter", description="Label for monitored sector")


class AlertRuleConfig(BaseModel):
    """Dynamic alert and multi-modal context configuration for a stream."""
    stream_id: str
    operating_mode: str = Field("security", description="'security' (perimeter/intrusion) or 'proctoring' (exam room)")
    max_persons: int = Field(10, description="Maximum number of detected persons before triggering occupancy breach (default=10)")
    min_persons: Optional[int] = Field(None, description="Minimum number of detected persons (e.g. 1 in proctoring; 0 is a breach)")
    prohibited_classes: List[str] = Field(
        default=["knife", "scissors", "gun", "weapon"],
        description="List of prohibited object classes"
    )
    prohibited_confidence_threshold: float = Field(0.55, description="Minimum confidence for prohibited objects")
    velocity_spike_threshold: float = Field(0.25, description="Sudden bounding box velocity threshold for movement spike")
    audio_ema_alpha: float = Field(0.05, description="Exponential moving average alpha factor for baseline tracking")
    audio_k_sigma: float = Field(2.5, description="Dynamic threshold multiplier K in: baseline + K * sigma")
    enable_zone_rule: bool = False
    enable_occupancy_rule: bool = False
    enable_prohibited_rule: bool = True
    enable_audio_rule: bool = True
    enable_crash_rule: bool = True
    enable_pedestrian_strike_rule: bool = True
    crash_iou_threshold: float = Field(0.18, description="Minimum IoU overlap between vehicles to flag a collision / crash")


# -----------------------------------------------------------------------------
# Explainable Decision Basis Schemas
# -----------------------------------------------------------------------------

class VisualTriggerBasis(BaseModel):
    """Explainable basis for visual detection triggers."""
    violated: bool = Field(..., description="Whether visual trigger was breached")
    rule: str = Field(..., description="Rule identifier: RESTRICTED_ROI_SPATIAL, OCCUPANCY_THRESHOLD, PROHIBITED_ITEM, SUDDEN_VELOCITY_SPIKE, NONE")
    trigger_classification: str = Field("AUTONOMOUS_GLOBAL", description="'AUTONOMOUS_GLOBAL' | 'SPATIAL_ROI' | 'NONE'")
    observed: Optional[float] = Field(None, description="Observed metric value (e.g. Centroid X or person count)")
    threshold: Optional[float] = Field(None, description="Configured rule threshold")
    rationale: str = Field(..., description="Clear human-readable visual rationale")


class AudioTriggerBasis(BaseModel):
    """Explainable basis for acoustic signal triggers."""
    violated: bool = Field(..., description="Whether acoustic trigger was breached")
    rule: str = Field(..., description="Rule identifier: SPECTRAL_TRANSIENT_SPIKE, SUSTAINED_MULTI_SPEAKER_VOICE, NONE")
    observed_rms: float = Field(..., description="Observed instantaneous audio RMS")
    baseline_rms: float = Field(..., description="Dynamic ambient noise baseline RMS")
    delta_percentage: str = Field(..., description="Observed vs baseline delta (e.g. '+175%')")
    speech_harmonic_detected: bool = Field(..., description="True if harmonic conversational speech, False if impact/noise")
    rationale: str = Field(..., description="Clear human-readable acoustic rationale")


class DecisionBasis(BaseModel):
    """Context-aware multi-modal decision matrix breakdown."""
    trigger_type: str = Field("AUTONOMOUS_GLOBAL", description="'AUTONOMOUS_GLOBAL' | 'SPATIAL_ROI' | 'COMBINED' | 'NONE'")
    visual_trigger: VisualTriggerBasis
    audio_trigger: AudioTriggerBasis
    multimodal_correlation_score: float = Field(..., description="Correlation score in [0.0, 1.0]")


# -----------------------------------------------------------------------------
# High-Fidelity Forensic Anomaly Incident Schemas
# -----------------------------------------------------------------------------

class TriggeredRuleDetail(BaseModel):
    """Individual triggered rule detail in a forensic incident."""
    rule_id: str = Field(..., description="Unique rule code (e.g. RULE_RESTRICTED_ZONE)")
    description: str = Field(..., description="Detailed explanation of the rule breach")
    target_class: Optional[str] = Field(None, description="Target object class involved in breach")
    confidence: Optional[float] = Field(None, description="Detection confidence score")


class DetectionDetail(BaseModel):
    """Object detection item in the forensic visual context."""
    object_id: str = Field(..., description="Unique object identifier within the frame (e.g. obj_01)")
    class_name: str = Field(..., alias="class", description="Detected class label")
    confidence: float = Field(..., description="Detection confidence")
    box_normalized: List[float] = Field(..., description="Normalized coordinates [x1, y1, x2, y2] in [0.0, 1.0]")
    box_pixels: List[int] = Field(..., description="Pixel coordinates [x1, y1, x2, y2]")
    is_violator: bool = Field(False, description="Whether this detection triggered a security violation")

    model_config = ConfigDict(populate_by_name=True)


class VisualContextDetail(BaseModel):
    """Comprehensive visual context accompanying an anomaly incident."""
    total_objects_detected: int = Field(..., description="Total object count in frame")
    detections: List[DetectionDetail] = Field(default_factory=list, description="All detected objects")
    snapshot_annotated_base64: str = Field(..., description="Annotated snapshot base64 URI with overlays")
    snapshot_raw_base64: str = Field(..., description="Original raw unmodified frame base64 URI")
    temporal_keyframes: Optional[List[str]] = Field(default_factory=list, description="3-frame sequence [T-1s, T0, T+1s]")


class AudioContextDetail(BaseModel):
    """Acoustic metrics at the instant of the anomaly."""
    audio_anomaly_flag: bool = Field(..., description="True if acoustic spike or anomaly concurrent")
    energy_rms: float = Field(..., description="RMS energy amplitude")
    dominant_frequency_hz: float = Field(..., description="Dominant audio frequency (Hz)")
    vad_speech_detected: bool = Field(..., description="True if human speech activity detected")


class SystemTelemetryDetail(BaseModel):
    """Granular millisecond-level telemetry at the instant of the anomaly."""
    cpu_percent: float = Field(..., description="Server CPU utilization percentage")
    memory_percent: float = Field(..., description="Server RAM utilization percentage")
    e2e_latency_ms: float = Field(..., description="End-to-end processing latency")
    inference_time_ms: float = Field(..., description="Computer vision inference latency")
    queue_dwell_time_ms: float = Field(..., description="Redis Stream queue dwell latency")
    ingestion_latency_ms: float = Field(..., description="Network ingest transport latency")
    pipeline_fps: float = Field(..., description="Active ingestion and processing FPS")


class ForensicAnomalyIncident(BaseModel):
    """Forensic-grade incident bundle created selectively when an anomaly occurs."""
    incident_id: str = Field(..., description="Unique incident identifier (e.g. inc_uuid)")
    stream_id: str = Field(..., description="Stream identifier (e.g. cam_01)")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp")
    epoch_ms: int = Field(..., description="Millisecond epoch timestamp")
    severity: str = Field("CRITICAL", description="Severity level: CRITICAL, WARNING, INFO")
    anomaly_summary: str = Field(..., description="Comprehensive summary of triggered rules")
    decision_basis: DecisionBasis = Field(..., description="Structured decision basis breakdown")
    anomaly_rationale: str = Field(..., description="Human-readable decision rationale")
    triggered_rules: List[TriggeredRuleDetail] = Field(default_factory=list)
    visual_context: VisualContextDetail
    audio_context: AudioContextDetail
    system_telemetry: SystemTelemetryDetail
    vlm_synthesis: Optional[IncidentAnalysisResult] = None
    temporal_keyframes: Optional[List[str]] = Field(default_factory=list, description="3-frame sequence [T-1s, T0, T+1s]")


class TokenOptimizationStats(BaseModel):
    """Running Token Optimization and Static Frame Dropping Metrics."""
    total_frames: int = Field(0, description="Total video frames received at gateway")
    frames_dropped: int = Field(0, description="Static / redundant frames dropped before AI inference")
    candidate_events: int = Field(0, description="Candidate event frames captured for processing")
    token_reduction_ratio: float = Field(0.0, description="Ratio of dropped frames vs total frames (e.g. 0.957)")
    bandwidth_saving_percent: float = Field(0.0, description="Bandwidth and token cost saving percentage")


class StreamTelemetryPayload(BaseModel):
    """Complete inference, edge gatekeeper and telemetry payload broadcasted via WebSocket."""
    stream_id: str
    sequence_id: int
    frame_id: Optional[int] = None
    timestamp: float
    worker_id: str
    is_static: bool = False
    delta_score: float = 0.0
    audio_db: float = -60.0
    trigger_fired: bool = False
    stats: Optional[TokenOptimizationStats] = None
    detections: List[DetectionResult] = Field(default_factory=list)
    person_count: int = 0
    total_objects: int = 0
    audio_analysis: Optional[AudioAnalysisResult] = None
    alerts: List[AlertTrigger] = Field(default_factory=list)
    forensic_incident: Optional[ForensicAnomalyIncident] = None
    decision_basis: Optional[DecisionBasis] = None
    vlm_synthesis: Optional[IncidentAnalysisResult] = None
    roi_telemetry: Optional[ROITelemetrySnapshot] = None
    stream_roi: Optional[StreamROIConfig] = None
    anomaly_rationale: str = Field("NORMAL: Monitored sector within baseline parameters.")
    latency: LatencyTelemetry
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None


class SystemMetricsResponse(BaseModel):
    """Rolling window metrics returned by GET /api/v1/metrics."""
    stream_id: Optional[str] = None
    time_window_seconds: int = 60
    total_frames_processed: int
    fps: float
    avg_e2e_latency_ms: float
    avg_ingestion_latency_ms: float
    avg_queue_dwell_time_ms: float
    avg_inference_time_ms: float
    p95_e2e_latency_ms: float
    current_queue_depth: int
    total_alerts_triggered: int
    sla_compliance_percent: float


class WorkerHeartbeat(BaseModel):
    """Worker instance heartbeat metadata."""
    worker_id: str
    last_heartbeat: float
    status: str = "active"
    processed_count: int = 0
    avg_inference_ms: float = 0.0


class HealthResponse(BaseModel):
    """Comprehensive system health status returned by GET /health."""
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    app_name: str = "StreamPulse"
    environment: str = "production"
    redis_connected: bool
    redis_latency_ms: float
    active_workers_count: int
    workers: List[WorkerHeartbeat] = Field(default_factory=list)
    queue_depth: int
    system_memory_used_mb: float
    system_cpu_percent: float
    uptime_seconds: float
    timestamp: float
