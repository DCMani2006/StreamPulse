import argparse
import asyncio
import base64
import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("streampulse.test_stream")


class StreamPulseTester:
    """
    End-to-end testing suite for StreamPulse:
    - Captures frames from local webcam, local video file, or generates synthetic animated video.
    - Implements Edge Motion & Temporal Sampling (decimating static frames for ~70% bandwidth reduction).
    - Encodes and streams frames via WebSocket to /ws/ingest/{stream_id}.
    - Concurrently subscribes to /ws/telemetry/{stream_id}.
    - Renders real-time bounding boxes, alerts, and latency telemetry in an OpenCV HUD.
    """

    def __init__(
        self,
        stream_id: str = "cam_01",
        host: str = "localhost",
        port: int = 8000,
        fps: int = 10,
        video_source: Optional[str] = None,
        use_synthetic: bool = False,
        enable_motion_sampling: bool = True,
        motion_threshold: float = 8.0,
        keyframe_interval_sec: float = 1.0,
        no_gui: bool = False,
        duration: Optional[int] = None,
    ):
        self.stream_id = stream_id
        self.host = host
        self.port = port
        self.target_fps = fps
        self.frame_interval = 1.0 / max(1, fps)
        self.video_source = video_source
        self.use_synthetic = use_synthetic
        self.enable_motion_sampling = enable_motion_sampling
        self.motion_threshold = motion_threshold
        self.keyframe_interval_sec = keyframe_interval_sec
        self.no_gui = no_gui
        self.duration = duration

        self.ws_ingest_url = f"ws://{host}:{port}/ws/ingest/{stream_id}"
        self.ws_telemetry_url = f"ws://{host}:{port}/ws/telemetry/{stream_id}"

        self.running = False
        self.latest_telemetry: Optional[Dict[str, Any]] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.sequence_counter = 0
        self.frames_sent = 0
        self.frames_skipped = 0
        self.frames_received = 0

        # Motion sampling state
        self.prev_gray_frame: Optional[np.ndarray] = None
        self.last_keyframe_time = 0.0

        # Synthetic animation state
        self.anim_t = 0.0

    def generate_synthetic_frame(self, width: int = 640, height: int = 480) -> np.ndarray:
        """Generates a synthetic animated test frame with moving objects and audio simulation."""
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.anim_t += 0.05

        # Background gradient
        for y in range(height):
            val = int(20 + 25 * (y / height))
            frame[y, :] = (val, val, val + 15)

        # Draw a simulated person / moving circle
        cx = int(width / 2 + (width / 3) * math.sin(self.anim_t))
        cy = int(height / 2 + (height / 4) * math.cos(self.anim_t * 0.7))
        cv2.circle(frame, (cx, cy), 35, (0, 200, 255), -1)
        cv2.circle(frame, (cx, cy - 50), 20, (0, 220, 255), -1)

        # Draw simulated moving vehicle / rectangle
        vx = int(width / 2 + (width / 2.5) * math.cos(self.anim_t * 0.5))
        vy = int(height * 0.75)
        cv2.rectangle(frame, (vx - 40, vy - 20), (vx + 40, vy + 20), (255, 120, 0), -1)

        # Add timestamp and synthetic banner
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            f"SYNTHETIC STREAM [{self.stream_id}] {timestamp_str}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            2,
        )

        return frame

    def generate_synthetic_audio_chunk(self) -> str:
        """Generates a synthetic mono 16kHz PCM audio chunk encoded as base64."""
        sample_rate = 16000
        num_samples = int(sample_rate * self.frame_interval)
        freq = 440.0 + 100.0 * math.sin(self.anim_t * 2.0)
        t = np.linspace(0, self.frame_interval, num_samples, endpoint=False)
        audio = 0.1 * np.sin(2 * np.pi * freq * t)

        # Introduce intermittent acoustic spike
        if math.sin(self.anim_t * 0.8) > 0.85:
            audio += 0.4 * np.random.normal(0, 1, num_samples)

        audio_int16 = (audio * 32767).astype(np.int16)
        return base64.b64encode(audio_int16.tobytes()).decode("utf-8")

    def should_transmit_frame(self, frame: np.ndarray, current_time: float) -> bool:
        """
        Temporal & Motion Sampling:
        Calculates mean absolute difference against previous frame.
        Transmits frame if:
        1. Periodic keyframe interval has elapsed (e.g. 1.0s I-frame), OR
        2. Motion energy exceeds the dynamic threshold.
        Drops static/redundant frames to save ~70% network bandwidth.
        """
        if not self.enable_motion_sampling:
            return True

        # Periodic Keyframe guarantee
        if current_time - self.last_keyframe_time >= self.keyframe_interval_sec:
            self.last_keyframe_time = current_time
            small_gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 120))
            self.prev_gray_frame = small_gray
            return True

        # Motion differential check
        small_gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 120))
        if self.prev_gray_frame is None:
            self.prev_gray_frame = small_gray
            self.last_keyframe_time = current_time
            return True

        diff = cv2.absdiff(small_gray, self.prev_gray_frame)
        motion_score = float(np.mean(diff))

        if motion_score >= self.motion_threshold:
            self.prev_gray_frame = small_gray
            return True

        self.frames_skipped += 1
        return False

    async def ingest_producer_task(self):
        """Captures/generates frames and streams them non-blockingly over WebSocket."""
        cap = None
        source_label = "synthetic"

        if self.video_source:
            logger.info(f"Opening video file / RTSP feed: {self.video_source}...")
            cap = cv2.VideoCapture(self.video_source)
            if not cap.isOpened():
                logger.error(f"Failed to open video source: {self.video_source}. Falling back to synthetic.")
                cap = None
            else:
                source_label = f"file: {os.path.basename(self.video_source)}"
                logger.info(f"Video file opened successfully: {source_label}")
        elif not self.use_synthetic:
            logger.info("Attempting to initialize local webcam (device 0)...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.warning("Webcam not available or could not be opened. Falling back to synthetic frame generator.")
                cap = None
            else:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                source_label = "webcam (device 0)"
                logger.info("Webcam opened successfully.")

        retry_count = 0
        while self.running:
            try:
                logger.info(f"Connecting to Ingest WebSocket: {self.ws_ingest_url}")
                async with websockets.connect(self.ws_ingest_url) as ws:
                    logger.info("Connected to Ingest WebSocket successfully.")
                    retry_count = 0

                    while self.running:
                        t_start = time.perf_counter()
                        t_client = time.time()

                        # Capture or generate frame
                        if cap is not None and cap.isOpened():
                            ret, frame = cap.read()
                            if not ret:
                                # Loop video file if reached end
                                if self.video_source:
                                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                    ret, frame = cap.read()
                                if not ret:
                                    frame = self.generate_synthetic_frame()
                        else:
                            frame = self.generate_synthetic_frame()

                        self.latest_frame = frame.copy()

                        # Edge Temporal / Motion Sampling filter
                        if self.should_transmit_frame(frame, t_client):
                            # Encode frame to JPEG base64
                            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                            _, buffer = cv2.imencode(".jpg", frame, encode_params)
                            frame_b64 = base64.b64encode(buffer).decode("utf-8")
                            audio_b64 = self.generate_synthetic_audio_chunk()

                            self.sequence_counter += 1
                            payload = {
                                "stream_id": self.stream_id,
                                "sequence_id": self.sequence_counter,
                                "t_client": t_client,
                                "frame_base64": frame_b64,
                                "audio_base64": audio_b64,
                                "metadata": {
                                    "source": source_label,
                                    "motion_sampling": self.enable_motion_sampling,
                                },
                            }

                            await ws.send(json.dumps(payload))
                            self.frames_sent += 1

                            # Non-blocking wait for optional ACK
                            try:
                                await asyncio.wait_for(ws.recv(), timeout=0.04)
                            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                                pass

                        # Regulate to target FPS
                        elapsed = time.perf_counter() - t_start
                        sleep_time = max(0.0, self.frame_interval - elapsed)
                        await asyncio.sleep(sleep_time)

            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                if self.running:
                    retry_count += 1
                    wait_time = min(5.0, 0.5 * retry_count)
                    logger.warning(f"Ingest WebSocket disconnected ({e}). Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Error in ingest producer: {e}")
                await asyncio.sleep(1.0)

        if cap is not None:
            cap.release()

    async def telemetry_consumer_task(self):
        """Subscribes to /ws/telemetry/{stream_id} and processes inference telemetry."""
        retry_count = 0
        while self.running:
            try:
                logger.info(f"Connecting to Telemetry WebSocket: {self.ws_telemetry_url}")
                async with websockets.connect(self.ws_telemetry_url) as ws:
                    logger.info("Subscribed to real-time Telemetry channel.")
                    retry_count = 0

                    while self.running:
                        msg_text = await ws.recv()
                        try:
                            data = json.loads(msg_text)
                            if data.get("type") == "ping":
                                continue
                            self.latest_telemetry = data
                            self.frames_received += 1
                        except Exception as e:
                            logger.warning(f"Failed to parse telemetry: {e}")

            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                if self.running:
                    retry_count += 1
                    wait_time = min(5.0, 0.5 * retry_count)
                    logger.warning(f"Telemetry WebSocket disconnected ({e}). Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Error in telemetry consumer: {e}")
                await asyncio.sleep(1.0)

    def draw_hud(self, display_img: np.ndarray, telemetry: Optional[Dict[str, Any]]) -> np.ndarray:
        """Renders bounding boxes, alert indicators, and latency telemetry onto the display image."""
        h, w = display_img.shape[:2]

        # Draw ROI from telemetry if available
        roi = telemetry.get("stream_roi") if telemetry else None
        if roi and roi.get("roi_enabled"):
            norm = roi.get("roi_normalized", {})
            zx1 = int(w * norm.get("x1", 0.2))
            zy1 = int(h * norm.get("y1", 0.3))
            zx2 = int(w * norm.get("x2", 0.7))
            zy2 = int(h * norm.get("y2", 0.8))
            label = roi.get("roi_label", "RESTRICTED ROI")
        else:
            zx1, zy1, zx2, zy2 = int(w * 0.2), int(h * 0.3), int(w * 0.7), int(h * 0.8)
            label = "RESTRICTED ROI"

        alerts = telemetry.get("alerts", []) if telemetry else []
        has_zone_alert = any(a.get("alert_type") == "zone_intrusion" for a in alerts)
        zone_color = (0, 0, 255) if has_zone_alert else (255, 200, 0)

        # Draw ROI boundary
        cv2.rectangle(display_img, (zx1, zy1), (zx2, zy2), zone_color, 2)
        cv2.putText(
            display_img,
            f"{'⚠️ BREACH: ' if has_zone_alert else '● '}{label}",
            (zx1 + 8, zy1 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            zone_color,
            1,
        )

        # Draw Detection Bounding Boxes
        if telemetry and "detections" in telemetry:
            for det in telemetry["detections"]:
                box = det.get("box", [])
                conf = det.get("confidence", 0.0)
                lbl = det.get("label", "object")
                is_violator = det.get("is_violator", False)

                if len(box) == 4:
                    x1, y1, x2, y2 = [int(v) for v in box]
                    box_color = (0, 0, 255) if is_violator else (0, 255, 0)
                    cv2.rectangle(display_img, (x1, y1), (x2, y2), box_color, 2)

                    tag = f"{lbl.upper()} {int(conf * 100)}%"
                    cv2.rectangle(display_img, (x1, y1 - 20), (x1 + 130, y1), box_color, -1)
                    cv2.putText(
                        display_img,
                        tag,
                        (x1 + 4, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                    )

        # Render Telemetry HUD Overlay Panel (Top Right)
        panel_w = 310
        panel_h = 210
        cv2.rectangle(display_img, (w - panel_w - 10, 10), (w - 10, panel_h + 10), (20, 20, 20), -1)
        cv2.rectangle(display_img, (w - panel_w - 10, 10), (w - 10, panel_h + 10), (60, 60, 60), 1)

        cv2.putText(display_img, "STREAMPULSE TELEMETRY", (w - panel_w + 5, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 2)

        if telemetry and "latency" in telemetry:
            lat = telemetry["latency"]
            e2e = lat.get("e2e_latency_ms", 0.0)
            infer = lat.get("inference_time_ms", 0.0)
            queue = lat.get("queue_dwell_time_ms", 0.0)
            sla_met = lat.get("sla_met", True)
            sla_color = (0, 255, 0) if sla_met else (0, 0, 255)

            cv2.putText(display_img, f"E2E Latency:   {e2e:.1f} ms", (w - panel_w + 5, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, sla_color, 1)
            cv2.putText(display_img, f"ML Inference:  {infer:.1f} ms", (w - panel_w + 5, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            cv2.putText(display_img, f"Queue Dwell:   {queue:.1f} ms", (w - panel_w + 5, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            cv2.putText(display_img, f"SLA (<300ms):  {'PASS' if sla_met else 'FAIL'}", (w - panel_w + 5, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.45, sla_color, 1)

        # Motion sampling stats
        total_frames = self.frames_sent + self.frames_skipped
        savings = (self.frames_skipped / max(1, total_frames)) * 100
        cv2.putText(display_img, f"Bandwidth Opt: ~{savings:.0f}% saved", (w - panel_w + 5, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1)
        cv2.putText(display_img, f"Frames Sent:   {self.frames_sent} (Skip {self.frames_skipped})", (w - panel_w + 5, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
        cv2.putText(display_img, f"Active Stream: {self.stream_id}", (w - panel_w + 5, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)

        # Active Alert Banners (Top Left)
        if alerts:
            for idx, alert in enumerate(alerts[:2]):
                msg = alert.get("message", "ALERT")
                banner_y = 35 + (idx * 30)
                cv2.rectangle(display_img, (20, banner_y - 20), (w - panel_w - 30, banner_y + 6), (0, 0, 180), -1)
                cv2.putText(display_img, f"WARNING: {msg}", (30, banner_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        return display_img

    async def gui_display_loop(self):
        """Renders the live OpenCV preview window."""
        window_name = f"StreamPulse Live Stream & Telemetry HUD [{self.stream_id}]"

        if not self.no_gui:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 960, 640)

        start_time = time.time()

        while self.running:
            if self.duration and (time.time() - start_time >= self.duration):
                logger.info(f"Test duration of {self.duration} seconds reached.")
                self.running = False
                break

            if self.latest_frame is not None:
                display = self.latest_frame.copy()
                display = self.draw_hud(display, self.latest_telemetry)

                if not self.no_gui:
                    cv2.imshow(window_name, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27 or key == ord("q"):
                        logger.info("Escape key pressed. Stopping test stream.")
                        self.running = False
                        break
                else:
                    # In headless mode, log summary every 2 seconds
                    if self.frames_received > 0 and self.frames_received % (self.target_fps * 2) == 0:
                        if self.latest_telemetry and "latency" in self.latest_telemetry:
                            lat = self.latest_telemetry["latency"]
                            total_f = self.frames_sent + self.frames_skipped
                            saving = (self.frames_skipped / max(1, total_f)) * 100
                            logger.info(
                                f"[Headless HUD] Sent: {self.frames_sent} (Saved {saving:.0f}%) | Received: {self.frames_received} | "
                                f"E2E: {lat.get('e2e_latency_ms')}ms | Infer: {lat.get('inference_time_ms')}ms | "
                                f"Objects: {self.latest_telemetry.get('total_objects')}"
                            )

            await asyncio.sleep(0.03)

        if not self.no_gui:
            cv2.destroyAllWindows()

    async def run(self):
        """Starts all concurrent tasks."""
        self.running = True
        logger.info(f"Starting StreamPulse test suite on stream '{self.stream_id}' at {self.target_fps} FPS...")

        producer_task = asyncio.create_task(self.ingest_producer_task())
        consumer_task = asyncio.create_task(self.telemetry_consumer_task())
        display_task = asyncio.create_task(self.gui_display_loop())

        try:
            await asyncio.gather(producer_task, consumer_task, display_task)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            logger.info(f"StreamPulse Test Completed. Total Frames Sent: {self.frames_sent}, Skipped: {self.frames_skipped}, Received: {self.frames_received}")


def parse_args():
    parser = argparse.ArgumentParser(description="StreamPulse End-to-End Test Suite")
    parser.add_argument("--stream-id", type=str, default="cam_01", help="Stream ID (default: cam_01)")
    parser.add_argument("--host", type=str, default="localhost", help="StreamPulse host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="StreamPulse port (default: 8000)")
    parser.add_argument("--fps", type=int, default=10, help="Target ingestion FPS (default: 10)")
    parser.add_argument("--video", "--video-file", dest="video_source", type=str, default=None, help="Path to local video file or RTSP/HTTP URL stream")
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic video generator instead of webcam")
    parser.add_argument("--disable-motion-sampling", dest="enable_motion_sampling", action="store_false", help="Disable edge motion/temporal decimation")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode without opening OpenCV window")
    parser.add_argument("--duration", type=int, default=None, help="Test duration in seconds (optional)")
    return parser.parse_args()


def main():
    args = parse_args()
    tester = StreamPulseTester(
        stream_id=args.stream_id,
        host=args.host,
        port=args.port,
        fps=args.fps,
        video_source=args.video_source,
        use_synthetic=args.synthetic,
        enable_motion_sampling=args.enable_motion_sampling,
        no_gui=args.no_gui,
        duration=args.duration,
    )

    try:
        asyncio.run(tester.run())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test encountered fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
