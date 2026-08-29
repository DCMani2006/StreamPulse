export interface DetectionResult {
  class_id: number;
  label: string;
  confidence: number;
  box: [number, number, number, number]; // [x1, y1, x2, y2]
  normalized_box: [number, number, number, number]; // [nx1, ny1, nx2, ny2]
  tracking_id?: number;
  velocity?: number;
}

export interface AudioAnalysisResult {
  energy_rms: number;
  energy_db: number;
  zero_crossing_rate: number;
  voice_activity_detected: boolean;
  spike_detected: boolean;
  dominant_frequency_hz?: number;
  baseline_rms?: number;
  ambient_std_rms?: number;
  dynamic_threshold_rms?: number;
  high_freq_ratio?: number;
  spectral_flatness?: number;
  speech_harmonic_detected?: boolean;
  delta_percentage_str?: string;
}

export interface LatencyTelemetry {
  t_client: number;
  t_ingest: number;
  t_worker_start: number;
  t_worker_done: number;
  t_broadcast: number;
  ingestion_latency_ms: number;
  queue_dwell_time_ms: number;
  inference_time_ms: number;
  e2e_latency_ms: number;
  sla_met: boolean;
}

export interface VisualTriggerBasis {
  violated: boolean;
  rule: string;
  trigger_classification?: string;
  observed?: number;
  threshold?: number;
  rationale: string;
}

export interface AudioTriggerBasis {
  violated: boolean;
  rule: string;
  observed_rms: number;
  baseline_rms: number;
  delta_percentage: string;
  speech_harmonic_detected: boolean;
  rationale: string;
}

export interface DecisionBasis {
  trigger_type?: string;
  visual_trigger: VisualTriggerBasis;
  audio_trigger: AudioTriggerBasis;
  multimodal_correlation_score: number;
}

export interface ROINormalizedBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface StreamROIConfig {
  stream_id: string;
  roi_enabled: boolean;
  roi_normalized: ROINormalizedBox;
  roi_label: string;
}

export interface TriggeredRuleDetail {
  rule_id: string;
  description: string;
  target_class?: string;
  confidence?: number;
}

export interface DetectionDetail {
  object_id: string;
  class: string;
  confidence: number;
  box_normalized: [number, number, number, number];
  box_pixels: [number, number, number, number];
  is_violator: boolean;
}

export interface VisualContextDetail {
  total_objects_detected: number;
  detections: DetectionDetail[];
  snapshot_annotated_base64: string;
  snapshot_raw_base64: string;
}

export interface AudioContextDetail {
  audio_anomaly_flag: boolean;
  energy_rms: number;
  dominant_frequency_hz: number;
  vad_speech_detected: boolean;
}

export interface SystemTelemetryDetail {
  ingest_latency_ms: number;
  queue_dwell_ms: number;
  inference_latency_ms: number;
  total_e2e_latency_ms: number;
  pipeline_fps: number;
}

export type SeverityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type IncidentCategory = 'TRAFFIC' | 'INDUSTRIAL_SAFETY' | 'FACILITY_SECURITY' | 'ANOMALY';

export interface IncidentAnalysisResult {
  is_incident: boolean;
  category: IncidentCategory;
  severity: SeverityLevel;
  title: string;
  description: string;
  entities_involved: string[];
  recommended_action: string;
  estimated_confidence: number;
}

export interface ForensicAnomalyIncident {
  incident_id: string;
  stream_id: string;
  timestamp_utc: string;
  epoch_ms: number;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  anomaly_summary: string;
  decision_basis?: DecisionBasis;
  anomaly_rationale?: string;
  triggered_rules: TriggeredRuleDetail[];
  visual_context: VisualContextDetail;
  audio_context: AudioContextDetail;
  system_telemetry: SystemTelemetryDetail;
  vlm_synthesis?: IncidentAnalysisResult;
}

export interface AlertTrigger {
  id?: string;
  alert_type: string;
  severity: 'critical' | 'warning' | 'info';
  message: string;
  stream_id: string;
  sequence_id: number;
  timestamp: number;
  details?: Record<string, any>;
  snapshot_url?: string;
  forensic_incident?: ForensicAnomalyIncident;
}

export interface TokenOptimizationStats {
  total_frames: number;
  frames_dropped: number;
  candidate_events: number;
  token_reduction_ratio: number;
  bandwidth_saving_percent: number;
}

export interface StreamTelemetryPayload {
  stream_id: string;
  sequence_id: number;
  frame_id?: number;
  timestamp: number;
  worker_id: string;
  is_static?: boolean;
  delta_score?: number;
  audio_db?: number;
  trigger_fired?: boolean;
  stats?: TokenOptimizationStats;
  detections: DetectionResult[];
  person_count: number;
  total_objects: number;
  audio_analysis?: AudioAnalysisResult;
  alerts: AlertTrigger[];
  forensic_incident?: ForensicAnomalyIncident;
  decision_basis?: DecisionBasis;
  vlm_synthesis?: IncidentAnalysisResult;
  stream_roi?: StreamROIConfig;
  anomaly_rationale?: string;
  latency: LatencyTelemetry;
  frame_width?: number;
  frame_height?: number;
}

export interface LatencyHistoryPoint {
  timeStr: string;
  timestamp: number;
  e2e: number;
  inference: number;
  queue: number;
  ingest: number;
  targetSla: number;
}

export interface AlertRuleConfig {
  stream_id: string;
  operating_mode?: 'security' | 'proctoring';
  max_persons: number;
  min_persons?: number;
  restricted_zone: [number, number, number, number]; // [x1, y1, x2, y2]
  roi_x_threshold?: number;
  prohibited_classes?: string[];
  prohibited_confidence_threshold?: number;
  audio_energy_threshold?: number;
  audio_ema_alpha?: number;
  audio_k_sigma?: number;
  sustained_speech_sec_threshold?: number;
  enable_person_alert?: boolean;
  enable_zone_alert?: boolean;
  enable_audio_alert?: boolean;
  enable_zone_rule?: boolean;
  enable_occupancy_rule?: boolean;
  enable_prohibited_rule?: boolean;
  enable_audio_rule?: boolean;
}

export type StreamSourceType = 'webcam' | 'file' | 'url' | 'preset';

export interface PresetScenario {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  videoUrl: string;
  zone: [number, number, number, number];
  tags: string[];
}
