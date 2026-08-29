import time
import math
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import IsolationForest

from app.schemas import DetectionResult

logger = logging.getLogger("streampulse.ml_anomaly")


class GeneralMLAnomalyDetector:
    """
    Unsupervised ML Anomaly Detector using Scikit-Learn's Isolation Forest:
    - Extracts 7D kinematic + spatial feature vector:
      [cx_norm, cy_norm, width_norm, height_norm, aspect_ratio, speed_x, speed_y]
    - Continuously adapts baseline distribution using a rolling history buffer.
    - Flags statistical outliers (anomalous kinematics, sudden deceleration, crashes, erratic motion).
    """

    def __init__(self, history_size: int = 300, contamination: float = 0.05, min_samples: int = 30):
        self.history = deque(maxlen=history_size)
        self.tracker: Dict[int, deque] = {}  # {tracking_id: deque([(cx, cy, timestamp)], maxlen=8)}
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=60,
            n_jobs=1,
        )
        self.is_fitted = False
        self.min_samples = min_samples
        self.fit_counter = 0

    def _compute_velocity(
        self,
        tracking_id: int,
        cx: float,
        cy: float,
        timestamp: float,
    ) -> Tuple[float, float]:
        """Calculates instantaneous 2D velocity (vx, vy) in normalized coordinates per second."""
        if tracking_id not in self.tracker:
            self.tracker[tracking_id] = deque(maxlen=8)
            self.tracker[tracking_id].append((cx, cy, timestamp))
            return 0.0, 0.0

        history = self.tracker[tracking_id]
        if not history:
            history.append((cx, cy, timestamp))
            return 0.0, 0.0

        prev_cx, prev_cy, prev_time = history[-1]
        dt = max(0.01, timestamp - prev_time)
        vx = (cx - prev_cx) / dt
        vy = (cy - prev_cy) / dt

        history.append((cx, cy, timestamp))

        # Clamp extreme artifact velocities
        vx = max(-5.0, min(5.0, vx))
        vy = max(-5.0, min(5.0, vy))
        return round(vx, 3), round(vy, 3)

    def extract_features(
        self,
        detections: List[Union[DetectionResult, Dict[str, Any]]],
        timestamp: float,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Extracts kinematic + spatial feature vector for each detected object:
        [cx, cy, w, h, aspect_ratio, speed_x, speed_y]
        """
        features = []
        meta_list = []

        for idx, det in enumerate(detections):
            if isinstance(det, DetectionResult):
                norm_box = det.normalized_box
                tracking_id = det.tracking_id or (idx + 100)
                label = det.label
                confidence = det.confidence
            else:
                norm_box = det.get("normalized_box", [0.0, 0.0, 1.0, 1.0])
                tracking_id = det.get("tracking_id", idx + 100)
                label = det.get("label", f"obj_{idx}")
                confidence = det.get("confidence", 0.9)

            x1, y1, x2, y2 = norm_box
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            w = max(1e-4, x2 - x1)
            h = max(1e-4, y2 - y1)
            aspect_ratio = round(w / (h + 1e-5), 3)

            # Compute velocity using kinematic tracker
            vx, vy = self._compute_velocity(tracking_id, cx, cy, timestamp)

            # Compute proximity to nearest neighbor
            min_dist = 2.0
            for j_idx, o_det in enumerate(detections):
                if j_idx == idx:
                    continue
                o_box = o_det.normalized_box if isinstance(o_det, DetectionResult) else o_det.get("normalized_box", [0, 0, 1, 1])
                o_cx = (o_box[0] + o_box[2]) / 2.0
                o_cy = (o_box[1] + o_box[3]) / 2.0
                d = math.sqrt((cx - o_cx) ** 2 + (cy - o_cy) ** 2)
                if d < min_dist:
                    min_dist = d

            feat = [
                round(cx, 3),
                round(cy, 3),
                round(w, 3),
                round(h, 3),
                aspect_ratio,
                vx,
                vy,
                round(min_dist, 3),
            ]
            features.append(feat)
            meta_list.append({
                "object_index": idx,
                "tracking_id": tracking_id,
                "label": label,
                "confidence": confidence,
                "box_normalized": norm_box,
                "velocity": [vx, vy],
                "aspect_ratio": aspect_ratio,
                "neighbor_dist": round(min_dist, 3),
            })

        if not features:
            return np.empty((0, 8)), []

        return np.array(features, dtype=np.float32), meta_list

    def process_frame(
        self,
        detections: List[Union[DetectionResult, Dict[str, Any]]],
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Processes frame detections through Isolation Forest:
        1. Warm-up Phase: Populates baseline history.
        2. Fits model incrementally every 25 observations.
        3. Predicts anomaly scores (-1 for outlier, 1 for normal).
        """
        timestamp = current_time or time.time()

        if not detections:
            return {
                "is_anomaly": False,
                "anomaly_count": 0,
                "max_score": 0.0,
                "details": [],
                "reason": "Empty scene",
                "rationale": "Scene clear (0 objects).",
            }

        features, meta_list = self.extract_features(detections, timestamp)
        if len(features) == 0:
            return {
                "is_anomaly": False,
                "anomaly_count": 0,
                "max_score": 0.0,
                "details": [],
                "reason": "No valid features",
                "rationale": "No features extracted.",
            }

        # 1. Warm-up Phase: Learn baseline motion and spatial patterns
        if len(self.history) < self.min_samples:
            for feat in features:
                self.history.append(feat)
            return {
                "is_anomaly": False,
                "anomaly_count": 0,
                "max_score": 0.0,
                "details": [],
                "reason": "Calibrating baseline ML model...",
                "rationale": f"ML Model Calibrating ({len(self.history)}/{self.min_samples} baseline frames sampled)...",
            }

        # 2. Train / Update Isolation Forest incrementally
        self.fit_counter += 1
        if not self.is_fitted or self.fit_counter % 25 == 0:
            try:
                self.model.fit(np.array(self.history, dtype=np.float32))
                self.is_fitted = True
            except Exception as e:
                logger.warning(f"Error fitting Isolation Forest: {e}")

        # 3. Predict Anomaly Scores (-1 is outlier, 1 is normal)
        anomalies_found = []
        try:
            predictions = self.model.predict(features)
            decision_scores = self.model.decision_function(features)  # Lower score = more anomalous

            for idx, (pred, score) in enumerate(zip(predictions, decision_scores)):
                # Outlier detected by Isolation Forest
                if pred == -1 or score < 0.0:
                    anomaly_score = float(round(-score, 3))
                    anomalies_found.append({
                        "object_index": idx,
                        "tracking_id": meta_list[idx]["tracking_id"],
                        "label": meta_list[idx]["label"],
                        "anomaly_score": max(0.01, anomaly_score),
                        "velocity": meta_list[idx]["velocity"],
                        "aspect_ratio": meta_list[idx]["aspect_ratio"],
                        "feature_vector": [float(x) for x in features[idx]],
                    })
                else:
                    # Add normal observations to keep baseline adaptive
                    self.history.append(features[idx])
        except Exception as e:
            logger.warning(f"Error predicting with Isolation Forest: {e}")

        has_anomaly = len(anomalies_found) > 0
        max_score = max([a["anomaly_score"] for a in anomalies_found]) if has_anomaly else 0.0

        if has_anomaly:
            anom_labels = ", ".join([f"{a['label']} (#{a['tracking_id']})" for a in anomalies_found])
            rationale = (
                f"ML Statistical Outlier (IsolationForest): {len(anomalies_found)} object(s) [{anom_labels}] "
                f"deviated from normal spatial/kinematic distribution (Score={max_score:.2f})."
            )
        else:
            rationale = "ML Baseline Normal: Movement and spatial distribution within statistical confidence bounds."

        return {
            "is_anomaly": has_anomaly,
            "anomaly_count": len(anomalies_found),
            "max_score": round(max_score, 3),
            "details": anomalies_found,
            "rationale": rationale,
        }
