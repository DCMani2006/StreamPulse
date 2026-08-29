import base64
import io
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from app.schemas import AudioAnalysisResult, LatencyTelemetry

logger = logging.getLogger("streampulse.pipeline")


class AudioDSPAnalyzer:
    """
    Dynamic Ambient Noise Profiler and Spectral Feature Extractor:
    - Tracks ambient noise baseline via Online Exponential Moving Average (EMA, alpha=0.05).
    - Computes continuous ambient standard deviation (sigma) and dynamic threshold (baseline + K*sigma).
    - Extracts spectral features: Zero-Crossing Rate (ZCR), High-Frequency Energy Ratio (>3.5kHz),
      and Spectral Flatness (Wiener entropy) to distinguish harmonic speech from abrupt transient impacts/shrieks.
    - Tracks sustained speech duration to evaluate proctoring/multi-speaker constraints.
    """

    def __init__(self, alpha: float = 0.05, k_sigma: float = 2.5):
        self.alpha = alpha
        self.k_sigma = k_sigma
        self.baseline_rms = 0.03
        self.ambient_var = 0.0004
        self.initialized = False
        self.sustained_speech_sec = 0.0
        self.last_process_time: Optional[float] = None

    def process_chunk(
        self,
        audio_data: Union[str, bytes],
        sample_rate: int = 16000,
        current_time: Optional[float] = None,
    ) -> AudioAnalysisResult:
        """Processes raw PCM audio chunk and returns full spectral analysis and dynamic baseline."""
        now = current_time or 0.0
        time_delta = 0.1  # default 100ms
        if self.last_process_time is not None and now > self.last_process_time:
            time_delta = min(0.5, now - self.last_process_time)
        self.last_process_time = now

        try:
            if isinstance(audio_data, str):
                if "," in audio_data:
                    audio_data = audio_data.split(",", 1)[1]
                raw_bytes = base64.b64decode(audio_data)
            else:
                raw_bytes = audio_data

            if not raw_bytes or len(raw_bytes) < 4:
                return self._empty_result()

            if len(raw_bytes) % 2 == 0:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                samples = np.frombuffer(raw_bytes, dtype=np.float32)

            if len(samples) == 0:
                return self._empty_result()

            # 1. RMS Energy Calculation
            energy_rms = float(np.sqrt(np.mean(np.square(samples))))
            energy_db = float(20.0 * math.log10(max(energy_rms, 1e-5)))

            # 2. Zero-Crossing Rate (ZCR)
            signs = np.sign(samples)
            signs[signs == 0] = 1
            zcr = float(np.sum(np.abs(np.diff(signs))) / (2.0 * len(samples)))

            # 3. Spectral Features via FFT
            dominant_freq = 0.0
            high_freq_ratio = 0.0
            spectral_flatness = 0.0

            if len(samples) >= 64:
                fft_vals = np.abs(np.fft.rfft(samples))
                power_spec = np.square(fft_vals) / len(samples)
                freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)

                # Dominant Peak Frequency
                peak_idx = int(np.argmax(fft_vals))
                dominant_freq = float(freqs[peak_idx])

                # High-Frequency Energy Ratio (>3.5 kHz)
                total_power = float(np.sum(power_spec))
                if total_power > 1e-9:
                    high_freq_mask = freqs >= 3500.0
                    high_power = float(np.sum(power_spec[high_freq_mask]))
                    high_freq_ratio = float(high_power / total_power)

                # Spectral Flatness (Wiener Entropy: Geometric Mean / Arithmetic Mean)
                pos_power = power_spec + 1e-12
                geom_mean = float(np.exp(np.mean(np.log(pos_power))))
                arith_mean = float(np.mean(pos_power))
                if arith_mean > 1e-12:
                    spectral_flatness = float(min(1.0, geom_mean / arith_mean))

            # 4. Voiced Harmonic Speech vs Transient Non-Speech Impact
            # Harmonic speech features low flatness (<= 0.42), low high-freq ratio (<= 0.40), and moderate ZCR
            speech_harmonic_detected = (
                (energy_rms > 0.015)
                and (spectral_flatness <= 0.42)
                and (high_freq_ratio <= 0.40)
                and (0.02 <= zcr <= 0.45)
            )

            # Heuristic Voice Activity
            vad_active = speech_harmonic_detected or ((energy_rms > 0.018) and (0.02 <= zcr <= 0.50))

            # Track sustained speech duration
            if vad_active:
                self.sustained_speech_sec += time_delta
            else:
                self.sustained_speech_sec = max(0.0, self.sustained_speech_sec - time_delta * 1.5)

            # 5. Online EMA Ambient Noise Profiler Updates
            if not self.initialized:
                self.baseline_rms = energy_rms
                self.ambient_var = 0.0004
                self.initialized = True
            else:
                # Update baseline when energy is not an extreme transient spike
                if energy_rms <= self.baseline_rms * 3.5:
                    delta = energy_rms - self.baseline_rms
                    self.baseline_rms = (1.0 - self.alpha) * self.baseline_rms + self.alpha * energy_rms
                    self.ambient_var = (1.0 - self.alpha) * self.ambient_var + self.alpha * (delta ** 2)

            ambient_std = float(math.sqrt(max(self.ambient_var, 1e-6)))
            dynamic_thresh = float(self.baseline_rms + self.k_sigma * ambient_std)

            # Delta percentage relative to ambient baseline
            if self.baseline_rms > 1e-5:
                delta_pct = ((energy_rms - self.baseline_rms) / self.baseline_rms) * 100.0
                delta_str = f"{'+' if delta_pct >= 0 else ''}{int(delta_pct)}%"
            else:
                delta_str = "+0%"

            # Transient or acoustic spike condition
            spike_detected = (energy_rms > dynamic_thresh) and (energy_rms - self.baseline_rms > 0.025)

            return AudioAnalysisResult(
                energy_rms=round(energy_rms, 4),
                energy_db=round(energy_db, 2),
                zero_crossing_rate=round(zcr, 4),
                voice_activity_detected=vad_active,
                spike_detected=spike_detected,
                dominant_frequency_hz=round(dominant_freq, 2),
                baseline_rms=round(self.baseline_rms, 4),
                ambient_std_rms=round(ambient_std, 4),
                dynamic_threshold_rms=round(dynamic_thresh, 4),
                high_freq_ratio=round(high_freq_ratio, 4),
                spectral_flatness=round(spectral_flatness, 4),
                speech_harmonic_detected=speech_harmonic_detected,
                delta_percentage_str=delta_str,
            )
        except Exception as e:
            logger.warning(f"Error in AudioDSPAnalyzer: {e}")
            return self._empty_result()

    def _empty_result(self) -> AudioAnalysisResult:
        ambient_std = float(math.sqrt(max(self.ambient_var, 1e-6)))
        return AudioAnalysisResult(
            energy_rms=0.0,
            energy_db=-100.0,
            zero_crossing_rate=0.0,
            voice_activity_detected=False,
            spike_detected=False,
            dominant_frequency_hz=0.0,
            baseline_rms=round(self.baseline_rms, 4),
            ambient_std_rms=round(ambient_std, 4),
            dynamic_threshold_rms=round(self.baseline_rms + self.k_sigma * ambient_std, 4),
            high_freq_ratio=0.0,
            spectral_flatness=0.0,
            speech_harmonic_detected=False,
            delta_percentage_str="+0%",
        )


def decode_base64_image(base64_str: str) -> Optional[np.ndarray]:
    """
    Safely decodes a base64 encoded image string (JPEG/PNG) into an OpenCV BGR numpy array.
    Uses OpenCV C++ decoder if available, with PIL fallback.
    Handles data URI prefixes and invalid strings gracefully.
    """
    if not base64_str:
        return None

    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]

        image_bytes = base64.b64decode(base64_str)
        if len(image_bytes) == 0:
            return None

        if HAS_CV2:
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return img
        elif HAS_PIL:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            rgb_arr = np.array(pil_img)
            bgr_arr = rgb_arr[:, :, ::-1].copy()
            return bgr_arr
        else:
            logger.error("Neither OpenCV nor Pillow is available for image decoding")
            return None
    except Exception as e:
        logger.warning(f"Error decoding base64 image: {e}")
        return None


def encode_image_to_base64(image: np.ndarray, quality: int = 80) -> str:
    """Encodes an OpenCV BGR image to base64 JPEG format."""
    if HAS_CV2:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        success, buffer = cv2.imencode(".jpg", image, encode_params)
        if not success:
            raise ValueError("Failed to encode image to JPEG format via OpenCV")
        return base64.b64encode(buffer).decode("utf-8")
    elif HAS_PIL:
        rgb_arr = image[:, :, ::-1]
        pil_img = Image.fromarray(rgb_arr)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    else:
        raise RuntimeError("Neither OpenCV nor Pillow is available for image encoding")


def encode_image_to_data_uri(image: np.ndarray, quality: int = 85) -> str:
    """Encodes an OpenCV BGR image into a full RFC 2397 Data URI (data:image/jpeg;base64,...)."""
    b64_str = encode_image_to_base64(image, quality=quality)
    return f"data:image/jpeg;base64,{b64_str}"


def encode_image_to_data_uri_fast(image: np.ndarray, max_dim: int = 640, quality: int = 65) -> str:
    """
    Ultra-fast image downsampling and JPEG encoding optimized for sub-3ms serialization overhead:
    - Downscales image if larger than max_dim (preserving aspect ratio).
    - Uses OpenCV TurboJPEG non-optimized fast path ([IMWRITE_JPEG_QUALITY, 65, IMWRITE_JPEG_OPTIMIZE, 0]).
    - Direct base64 ASCII string serialization.
    """
    if image is None or image.size == 0:
        return ""

    h, w = image.shape[:2]
    if max(h, w) > max_dim and HAS_CV2:
        scale = max_dim / float(max(h, w))
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img_to_encode = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:
        img_to_encode = image

    if HAS_CV2:
        encode_params = [
            int(cv2.IMWRITE_JPEG_QUALITY), int(quality),
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 0,
        ]
        success, buffer = cv2.imencode(".jpg", img_to_encode, encode_params)
        if success:
            b64_str = base64.b64encode(buffer).decode("ascii")
            return f"data:image/jpeg;base64,{b64_str}"

    return encode_image_to_data_uri(image, quality=quality)


def normalize_box(box: List[float], width: int, height: int) -> List[float]:
    """Converts pixel coordinates [x1, y1, x2, y2] to normalized [0.0, 1.0] range."""
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        round(max(0.0, min(1.0, box[0] / width)), 4),
        round(max(0.0, min(1.0, box[1] / height)), 4),
        round(max(0.0, min(1.0, box[2] / width)), 4),
        round(max(0.0, min(1.0, box[3] / height)), 4),
    ]


def calculate_iou(box_a: List[float], box_b: List[float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box_a_area = max(1e-6, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    box_b_area = max(1e-6, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))

    union_area = box_a_area + box_b_area - intersection_area
    if union_area <= 0.0:
        return 0.0

    return float(intersection_area / union_area)


def calculate_ioa(box_a: List[float], box_b: List[float]) -> float:
    """Computes Intersection over Min Area (IoA) between two bounding boxes [x1, y1, x2, y2]."""
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box_a_area = max(1e-6, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    box_b_area = max(1e-6, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))

    min_area = min(box_a_area, box_b_area)
    return float(intersection_area / min_area)


def is_box_inside_zone(
    detection_box: List[float],
    restricted_zone: List[float],
    penetration_threshold: float = 0.10,
) -> Tuple[bool, float]:
    """
    Determines if a detection bounding box penetrates or overlaps a restricted zone.
    Both boxes are expected in normalized [0.0, 1.0] coordinates [x1, y1, x2, y2].
    
    Returns:
        Tuple of (is_penetrated: bool, penetration_ratio: float)
    """
    x_left = max(detection_box[0], restricted_zone[0])
    y_top = max(detection_box[1], restricted_zone[1])
    x_right = min(detection_box[2], restricted_zone[2])
    y_bottom = min(detection_box[3], restricted_zone[3])

    if x_right < x_left or y_bottom < y_top:
        return False, 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    detection_area = (detection_box[2] - detection_box[0]) * (
        detection_box[3] - detection_box[1]
    )

    if detection_area <= 0.0:
        return False, 0.0

    penetration_ratio = intersection_area / detection_area
    return penetration_ratio >= penetration_threshold, penetration_ratio


def draw_forensic_annotations(
    image: np.ndarray,
    detections: List[Dict[str, Any]],
    restricted_zone: Optional[List[float]],
    incident_id: str,
    timestamp_utc: str,
    anomaly_summary: str,
    max_dim: int = 640,
) -> np.ndarray:
    """
    High-speed forensic visual annotator (<2ms execution time):
    - Pre-scales image to max_dim (640px) to minimize drawing and compression pixels.
    - Sliced alpha blending for header and footer overlays without full-frame copies.
    - Tactical corner brackets and violation badges on detected targets.
    """
    if image is None or image.size == 0:
        return image

    raw_h, raw_w = image.shape[:2]
    if max(raw_h, raw_w) > max_dim and HAS_CV2:
        scale = max_dim / float(max(raw_h, raw_w))
        w, h = max(1, int(raw_w * scale)), max(1, int(raw_h * scale))
        annotated = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        annotated = image.copy()
        w, h = raw_w, raw_h

    # 1. Draw Detections using normalized boxes
    for det in detections:
        is_violator = det.get("is_violator", False)
        norm_box = det.get("box_normalized") or det.get("normalized_box")
        if not norm_box or len(norm_box) != 4:
            continue

        x1 = max(0, min(w - 1, int(norm_box[0] * w)))
        y1 = max(0, min(h - 1, int(norm_box[1] * h)))
        x2 = max(0, min(w - 1, int(norm_box[2] * w)))
        y2 = max(0, min(h - 1, int(norm_box[3] * h)))
        if x2 <= x1 or y2 <= y1:
            continue

        label = det.get("class_name") or det.get("class") or det.get("label", "object")
        conf = det.get("confidence", 0.0)

        box_color = (50, 50, 239) if is_violator else (129, 185, 16)
        label_bg = (30, 30, 200) if is_violator else (16, 140, 10)

        if HAS_CV2:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

            corner_len = min(14, max(4, int((x2 - x1) / 4)), max(4, int((y2 - y1) / 4)))
            thick = 3
            cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), box_color, thick)
            cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), box_color, thick)
            cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), box_color, thick)
            cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), box_color, thick)
            cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), box_color, thick)
            cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), box_color, thick)
            cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), box_color, thick)
            cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), box_color, thick)

            tag = f"{'[VIOLATION] ' if is_violator else ''}{label.upper()} {int(conf * 100)}%"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            pill_y1 = max(th + 6, y1 - 3)
            cv2.rectangle(annotated, (x1, pill_y1 - th - 4), (min(w - 1, x1 + tw + 8), pill_y1 + 2), label_bg, -1)
            cv2.putText(
                annotated,
                tag,
                (x1 + 4, pill_y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # 2. Sliced Fast Header & Footer Watermarks
    if HAS_CV2 and h >= 60:
        header_h = 28
        header_slice = annotated[0:header_h, :]
        dark_header = np.zeros_like(header_slice)
        cv2.addWeighted(dark_header, 0.8, header_slice, 0.2, 0, header_slice)
        annotated[0:header_h, :] = header_slice

        header_text = f"STREAMPULSE AUDIT | {incident_id[:12]} | {timestamp_utc}"
        cv2.putText(annotated, header_text, (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (16, 230, 140), 1, cv2.LINE_AA)

        footer_h = 24
        footer_slice = annotated[h - footer_h:h, :]
        dark_footer = np.zeros_like(footer_slice)
        cv2.addWeighted(dark_footer, 0.8, footer_slice, 0.2, 0, footer_slice)
        annotated[h - footer_h:h, :] = footer_slice

        summary_text = f"ANOMALY: {anomaly_summary}"[:90]
        cv2.putText(annotated, summary_text, (10, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (50, 50, 239), 1, cv2.LINE_AA)

    return annotated


def analyze_audio_chunk(
    audio_data: Union[str, bytes],
    sample_rate: int = 16000,
    spike_threshold: float = 0.05,
    zcr_threshold: float = 0.10,
) -> AudioAnalysisResult:
    """Helper function for standalone audio DSP analysis."""
    analyzer = AudioDSPAnalyzer()
    return analyzer.process_chunk(audio_data, sample_rate=sample_rate)


def calculate_latency_metrics(
    t_client: float,
    t_ingest: float,
    t_worker_start: float,
    t_worker_done: float,
    t_broadcast: float,
    sla_target_ms: float = 300.0,
) -> LatencyTelemetry:
    """Computes precise high-resolution latency deltas for all stages of the pipeline."""
    ingestion_latency_ms = max(0.0, (t_ingest - t_client) * 1000.0)
    queue_dwell_time_ms = max(0.0, (t_worker_start - t_ingest) * 1000.0)
    inference_time_ms = max(0.0, (t_worker_done - t_worker_start) * 1000.0)
    e2e_latency_ms = max(0.0, (t_broadcast - t_client) * 1000.0)

    sla_met = e2e_latency_ms <= sla_target_ms

    return LatencyTelemetry(
        t_client=round(t_client, 4),
        t_ingest=round(t_ingest, 4),
        t_worker_start=round(t_worker_start, 4),
        t_worker_done=round(t_worker_done, 4),
        t_broadcast=round(t_broadcast, 4),
        ingestion_latency_ms=round(ingestion_latency_ms, 2),
        queue_dwell_time_ms=round(queue_dwell_time_ms, 2),
        inference_time_ms=round(inference_time_ms, 2),
        e2e_latency_ms=round(e2e_latency_ms, 2),
        sla_met=sla_met,
    )


class FastTracker:
    """
    High-Speed Centroid & Kinematic Velocity Tracker:
    - Maintains per-track normalized coordinates (cx, cy) and last timestamp.
    - Associates detections across frames using Euclidean distance (< 0.15 threshold).
    - Computes 2D velocity vectors (vx, vy) and scalar magnitude (velocity).
    """

    def __init__(self):
        self.tracks: Dict[int, Tuple[float, float, float]] = {}  # {track_id: (cx, cy, timestamp)}
        self.next_id = 100

    def update(self, detections: List[Any], current_time: float) -> Tuple[List[Any], float]:
        new_tracks = {}
        max_vel = 0.0

        for det in detections:
            nb = det.normalized_box if hasattr(det, "normalized_box") else det.get("normalized_box", [0, 0, 1, 1])
            cx = (nb[0] + nb[2]) / 2.0
            cy = (nb[1] + nb[3]) / 2.0

            matched_id = None
            min_dist = float("inf")

            for tid, (prev_cx, prev_cy, prev_t) in self.tracks.items():
                dist = math.hypot(cx - prev_cx, cy - prev_cy)
                if dist < 0.15 and dist < min_dist:
                    min_dist = dist
                    matched_id = tid

            if matched_id is not None:
                prev_cx, prev_cy, prev_t = self.tracks[matched_id]
                dt = max(current_time - prev_t, 1e-4)
                vx = (cx - prev_cx) / dt
                vy = (cy - prev_cy) / dt
                vel = math.hypot(vx, vy)
                new_tracks[matched_id] = (cx, cy, current_time)
            else:
                matched_id = self.next_id
                self.next_id += 1
                vel = 0.0
                new_tracks[matched_id] = (cx, cy, current_time)

            if hasattr(det, "tracking_id"):
                det.tracking_id = matched_id
            else:
                det["id"] = matched_id
                det["velocity"] = round(vel, 3)

            max_vel = max(max_vel, vel)

        self.tracks = new_tracks
        return detections, round(max_vel, 3)

