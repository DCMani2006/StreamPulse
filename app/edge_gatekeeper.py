import time
import numpy as np
from typing import Optional, Tuple, Dict, Any

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class EdgeGatekeeper:
    """
    Sub-2ms Frame-Delta Gatekeeper and Token Optimization Filter:
    - Downscales incoming frames to 160x120 grayscale.
    - Computes normalized Mean Absolute Difference (MAD) against previous reference frame.
    - Filters out static / redundant surveillance frames before expensive VLM / Cloud inference.
    - Tracks total frames received, frames dropped, and token reduction ratio (>95%).
    """

    def __init__(self, delta_threshold: float = 0.018, warmup_frames: int = 3):
        self.delta_threshold = delta_threshold
        self.warmup_frames = warmup_frames
        self.prev_small_gray: Optional[np.ndarray] = None
        self.total_frames_received: int = 0
        self.static_frames_dropped: int = 0
        self.candidate_events_captured: int = 0

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        force_trigger: bool = False,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Evaluates frame for static redundancy vs candidate event.
        Returns:
            is_static (bool): True if frame is redundant and should be dropped.
            delta_score (float): Normalized Mean Absolute Difference [0.0, 1.0].
            stats (dict): Running token reduction stats.
        """
        self.total_frames_received += 1

        if frame_bgr is None or frame_bgr.size == 0 or not HAS_CV2:
            return False, 1.0, self.get_stats()

        # Fast 160x120 grayscale downscale (< 0.8ms on CPU)
        small = cv2.resize(frame_bgr, (160, 120), interpolation=cv2.INTER_LINEAR)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if self.prev_small_gray is None or self.total_frames_received <= self.warmup_frames:
            self.prev_small_gray = gray
            # During warmup, let frames pass as candidate baseline
            self.candidate_events_captured += 1
            return False, 1.0, self.get_stats()

        # Compute Mean Absolute Difference normalized to [0.0, 1.0] (< 0.2ms)
        diff = cv2.absdiff(gray, self.prev_small_gray)
        delta_score = float(np.mean(diff) / 255.0)

        # Update previous frame reference
        self.prev_small_gray = gray

        # If audio trigger or external signal forces capture, mark as candidate event
        if force_trigger:
            self.candidate_events_captured += 1
            return False, round(delta_score, 4), self.get_stats()

        # Static vs Candidate Event Classification
        if delta_score < self.delta_threshold:
            self.static_frames_dropped += 1
            is_static = True
        else:
            self.candidate_events_captured += 1
            is_static = False

        return is_static, round(delta_score, 4), self.get_stats()

    def get_stats(self) -> Dict[str, Any]:
        total = self.total_frames_received
        dropped = self.static_frames_dropped
        candidate = self.candidate_events_captured
        reduction = (dropped / float(total)) if total > 0 else 0.0
        return {
            "total_frames": total,
            "frames_dropped": dropped,
            "candidate_events": candidate,
            "token_reduction_ratio": round(reduction, 4),
            "bandwidth_saving_percent": round(reduction * 100.0, 1),
        }

    def reset_stats(self):
        self.total_frames_received = 0
        self.static_frames_dropped = 0
        self.candidate_events_captured = 0
        self.prev_small_gray = None
