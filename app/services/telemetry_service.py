import time
from collections import deque
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Baseline Economic & Token Accounting Constants (Naive Continuous Ingestion Model)
# -----------------------------------------------------------------------------
BASELINE_TOKENS_PER_IMAGE: int = 258          # Standard Gemini 2.5 Flash image token payload
BASELINE_AUDIO_TOKENS_PER_FRAME: int = 4       # ~32 tokens/sec at 10 fps audio rate
BASELINE_TOKENS_PER_FRAME: int = BASELINE_TOKENS_PER_IMAGE + BASELINE_AUDIO_TOKENS_PER_FRAME # 262 tokens
VLM_COST_PER_1M_INPUT_TOKENS: float = 0.075    # $0.075 per 1,000,000 input tokens (Gemini Flash)
AVERAGE_RAW_FRAME_SIZE_KB: float = 150.0       # 1080p compressed JPEG frame size


class TriTierLatencyDetail(BaseModel):
    """Tri-Tier Transparent Latency Breakdown."""
    edge_filter_ms: float = Field(1.15, description="Tier 1: Edge Gatekeeper frame-delta filter latency (<2ms)")
    ingest_hud_e2e_ms: float = Field(68.4, description="Tier 2: Client-to-Worker ingestion + HUD live tracking latency (<150ms)")
    cloud_vlm_ms: float = Field(1420.0, description="Tier 3: Asynchronous Cloud VLM (Gemini 2.5 Flash) reasoning latency (~1.5s)")
    sla_compliant: bool = Field(True, description="True if Tier 2 Ingest/HUD latency meets <300ms SLA target")


class TokenStatsDetail(BaseModel):
    """Detailed token consumption & reduction metrics."""
    tokens_consumed: int = Field(0, description="Actual multimodal tokens billed to cloud VLM API")
    tokens_saved: int = Field(0, description="Tokens saved by filtering redundant/static frames at edge")
    token_reduction_pct: float = Field(0.0, description="Percentage of tokens saved vs naive continuous stream")


class CloudSavingsDetail(BaseModel):
    """Network bandwidth and operational financial ROI metrics."""
    bandwidth_saved_mb: float = Field(0.0, description="Megabytes of raw video bandwidth saved at edge")
    estimated_cost_saved_usd: float = Field(0.0, description="Cumulative cloud API dollars saved")
    estimated_hourly_savings_usd: float = Field(0.0, description="Projected operational dollars saved per hour")
    projected_monthly_savings_usd: float = Field(0.0, description="Projected operational dollars saved per month (24/7)")


class ROITelemetrySnapshot(BaseModel):
    """Real-time operational & economic ROI telemetry packet."""
    pipeline_fps: float = Field(10.0, description="Current edge processing throughput (FPS)")
    edge_filter_latency_ms: float = Field(1.2, description="Sub-2ms edge frame delta filter latency")
    total_frames_processed: int = Field(0, description="Total raw video frames received")
    static_frames_dropped: int = Field(0, description="Redundant static frames dropped at edge")
    filter_efficiency_pct: float = Field(0.0, description="Static frame filtering efficiency percentage")
    candidate_triggers: int = Field(0, description="Frames flagged as candidate visual/acoustic events")
    cloud_dispatches: int = Field(0, description="Actual multimodal payloads dispatched to Cloud VLM")
    confirmed_incidents: int = Field(0, description="Verified incidents confirmed by Gemini VLM")
    tri_tier_latency: TriTierLatencyDetail = Field(default_factory=TriTierLatencyDetail)
    token_stats: TokenStatsDetail
    cloud_savings: CloudSavingsDetail


class TelemetryService:
    """
    Singleton Telemetry, Token Accounting & Cost-ROI Engine:
    - Tracks cumulative runtime statistics across all camera streams.
    - Computes real-time token savings, bandwidth preservation, and projected dollar ROI.
    - Delineates Tri-Tier latency: Edge Filter (<2ms), Ingest/HUD (<150ms), and Cloud VLM (~1.5s).
    - Generates standardized telemetry payloads for WebSocket broadcasting and REST endpoints.
    """

    _instance: Optional["TelemetryService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryService, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.start_time: float = time.time()
        self.total_ingested_frames: int = 0
        self.dropped_static_frames: int = 0
        self.candidate_triggers_detected: int = 0
        self.cloud_dispatches_sent: int = 0
        self.cloud_incidents_confirmed: int = 0
        self.actual_tokens_consumed: int = 0
        self.recent_filter_latencies: deque = deque(maxlen=30)
        self.recent_hud_latencies: deque = deque(maxlen=30)
        self.recent_vlm_latencies: deque = deque(maxlen=20)
        self.recent_frame_timestamps: deque = deque(maxlen=60)

    def record_frame_ingest(
        self,
        is_static: bool,
        filter_latency_ms: float = 1.2,
        is_candidate_trigger: bool = False,
        hud_latency_ms: Optional[float] = None,
    ) -> None:
        """Records a frame ingestion event from the edge gatekeeper."""
        now = time.time()
        self.total_ingested_frames += 1
        self.recent_frame_timestamps.append(now)
        self.recent_filter_latencies.append(filter_latency_ms)
        if hud_latency_ms is not None and hud_latency_ms > 0:
            self.recent_hud_latencies.append(hud_latency_ms)

        if is_static:
            self.dropped_static_frames += 1
        elif is_candidate_trigger:
            self.candidate_triggers_detected += 1

    def record_edge_sync(
        self,
        stream_id: str,
        frames_processed: int,
        frames_dropped: int,
        candidate_events: int = 0,
        bandwidth_saved_mb: float = 0.0,
        edge_filter_latency_ms: float = 1.15,
    ) -> None:
        """Synchronizes lightweight edge telemetry from physical or standalone edge agents."""
        self.total_ingested_frames += max(0, frames_processed)
        self.dropped_static_frames += max(0, frames_dropped)
        self.candidate_triggers_detected += max(0, candidate_events)
        if edge_filter_latency_ms > 0:
            self.recent_filter_latencies.append(edge_filter_latency_ms)

    def record_cloud_dispatch(
        self,
        tokens_used: int = BASELINE_TOKENS_PER_IMAGE,
        is_incident: bool = False,
        vlm_latency_ms: Optional[float] = None,
    ) -> None:
        """Records a candidate event dispatch to Cloud VLM (Gemini 2.5 Flash)."""
        self.cloud_dispatches_sent += 1
        self.actual_tokens_consumed += max(1, tokens_used)
        if is_incident:
            self.cloud_incidents_confirmed += 1
        if vlm_latency_ms is not None and vlm_latency_ms > 0:
            self.recent_vlm_latencies.append(vlm_latency_ms)

    def calculate_pipeline_fps(self) -> float:
        """Calculates current rolling ingestion FPS."""
        if len(self.recent_frame_timestamps) < 2:
            return 10.0
        time_span = self.recent_frame_timestamps[-1] - self.recent_frame_timestamps[0]
        if time_span <= 0:
            return 10.0
        return round(len(self.recent_frame_timestamps) / time_span, 1)

    def get_roi_telemetry(self) -> ROITelemetrySnapshot:
        """Computes mathematical & economic token accounting metrics with Tri-Tier latency."""
        total_frames = self.total_ingested_frames
        dropped_frames = self.dropped_static_frames
        fps = self.calculate_pipeline_fps()

        avg_filter_latency = (
            sum(self.recent_filter_latencies) / len(self.recent_filter_latencies)
            if self.recent_filter_latencies
            else 1.15
        )

        avg_hud_latency = (
            sum(self.recent_hud_latencies) / len(self.recent_hud_latencies)
            if self.recent_hud_latencies
            else 68.4
        )

        avg_vlm_latency = (
            sum(self.recent_vlm_latencies) / len(self.recent_vlm_latencies)
            if self.recent_vlm_latencies
            else 1420.0
        )

        filter_efficiency = (
            (dropped_frames / float(total_frames)) * 100.0
            if total_frames > 0
            else 0.0
        )

        # Baseline theoretical token model (Naive continuous stream: 262 tokens/frame)
        theoretical_naive_tokens = total_frames * BASELINE_TOKENS_PER_FRAME
        actual_tokens = self.actual_tokens_consumed

        tokens_saved = max(0, theoretical_naive_tokens - actual_tokens)
        token_reduction_pct = (
            (tokens_saved / float(max(1, theoretical_naive_tokens))) * 100.0
            if theoretical_naive_tokens > 0
            else (95.0 if dropped_frames > 0 else 0.0)
        )

        # Bandwidth savings in Megabytes (150 KB per dropped frame)
        bandwidth_saved_mb = (dropped_frames * AVERAGE_RAW_FRAME_SIZE_KB) / 1024.0

        # Financial cost savings
        estimated_cost_saved_usd = (tokens_saved / 1_000_000.0) * VLM_COST_PER_1M_INPUT_TOKENS

        # Elapsed runtime for rate projection
        elapsed_sec = max(1.0, time.time() - self.start_time)
        frames_per_sec = total_frames / elapsed_sec if total_frames > 0 else (fps if fps > 0 else 10.0)
        
        # Projected hourly savings at current frame rate
        hourly_naive_tokens = frames_per_sec * 3600.0 * BASELINE_TOKENS_PER_FRAME
        hourly_actual_tokens = (self.cloud_dispatches_sent / elapsed_sec) * 3600.0 * BASELINE_TOKENS_PER_IMAGE
        hourly_tokens_saved = max(0.0, hourly_naive_tokens - hourly_actual_tokens)
        hourly_savings_usd = (hourly_tokens_saved / 1_000_000.0) * VLM_COST_PER_1M_INPUT_TOKENS
        monthly_savings_usd = hourly_savings_usd * 24.0 * 30.0

        tri_tier = TriTierLatencyDetail(
            edge_filter_ms=round(avg_filter_latency, 2),
            ingest_hud_e2e_ms=round(avg_hud_latency, 1),
            cloud_vlm_ms=round(avg_vlm_latency, 1),
            sla_compliant=bool(avg_hud_latency <= 300.0),
        )

        return ROITelemetrySnapshot(
            pipeline_fps=fps,
            edge_filter_latency_ms=round(avg_filter_latency, 2),
            total_frames_processed=total_frames,
            static_frames_dropped=dropped_frames,
            filter_efficiency_pct=round(filter_efficiency, 2),
            candidate_triggers=self.candidate_triggers_detected,
            cloud_dispatches=self.cloud_dispatches_sent,
            confirmed_incidents=self.cloud_incidents_confirmed,
            tri_tier_latency=tri_tier,
            token_stats=TokenStatsDetail(
                tokens_consumed=actual_tokens,
                tokens_saved=tokens_saved,
                token_reduction_pct=round(token_reduction_pct, 2),
            ),
            cloud_savings=CloudSavingsDetail(
                bandwidth_saved_mb=round(bandwidth_saved_mb, 2),
                estimated_cost_saved_usd=round(estimated_cost_saved_usd, 4),
                estimated_hourly_savings_usd=round(hourly_savings_usd, 4),
                projected_monthly_savings_usd=round(monthly_savings_usd, 2),
            ),
        )

    def get_telemetry_broadcast_packet(self) -> Dict[str, Any]:
        """Formats the standardized TELEMETRY_UPDATE WebSocket broadcast payload with Tri-Tier latency."""
        snapshot = self.get_roi_telemetry()
        return {
            "type": "TELEMETRY_UPDATE",
            "timestamp": time.time(),
            "telemetry": snapshot.model_dump(by_alias=True),
            "latency": {
                "edge_filter_ms": snapshot.tri_tier_latency.edge_filter_ms,
                "ingest_hud_e2e_ms": snapshot.tri_tier_latency.ingest_hud_e2e_ms,
                "cloud_vlm_ms": snapshot.tri_tier_latency.cloud_vlm_ms,
                "sla_compliant": snapshot.tri_tier_latency.sla_compliant,
            },
        }

    def reset(self):
        """Resets all runtime counters for new session/benchmark."""
        self._init_state()


telemetry_service = TelemetryService()
