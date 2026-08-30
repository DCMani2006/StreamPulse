import datetime
import logging
import time
import uuid
from collections import deque
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("streampulse.cross_camera")


class CorrelatedProgressionStep(BaseModel):
    time: str
    stream_id: str
    camera_name: str
    event: str
    severity: str = "HIGH"


class CorrelatedMultiCameraIncident(BaseModel):
    type: str = "CORRELATED_INCIDENT"
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    streams_involved: List[str]
    title: str
    progression: List[CorrelatedProgressionStep]
    severity: str = "CRITICAL"
    entities_involved: List[str] = Field(default_factory=list)
    recommended_action: str


CAMERA_LABELS: Dict[str, str] = {
    "cam_01": "Camera 01 - Main Entrance (North Gate)",
    "cam_north_gate": "Camera 01 - Main Entrance (North Gate)",
    "cam_02": "Camera 02 - Warehouse Interior (Bay A)",
    "cam_warehouse_bay": "Camera 02 - Warehouse Interior (Bay A)",
    "cam_03": "Camera 03 - Loading Dock & Freight",
    "cam_loading_dock": "Camera 03 - Loading Dock & Freight",
    "cam_04": "Camera 04 - Perimeter Security Zone",
    "cam_perimeter": "Camera 04 - Perimeter Security Zone",
}


class CrossCameraEventAggregator:
    """
    Real-Time Cross-Stream Multi-Camera Event Correlation Engine:
    - Maintains a rolling 60-second correlation window across all active surveillance feeds.
    - Aggregates multi-camera temporal chains (e.g. Perimeter Fence -> Warehouse Bay A).
    - Synthesizes unified multi-point incident intelligence with chronological progression paths.
    """

    def __init__(self, correlation_window_sec: float = 60.0, max_history: int = 100):
        self.correlation_window_sec = correlation_window_sec
        self.recent_events: deque = deque(maxlen=max_history)
        self.correlated_history: List[CorrelatedMultiCameraIncident] = []
        self.last_correlation_time: Dict[str, float] = {}

    def _format_time(self, epoch_sec: float) -> str:
        d = datetime.datetime.fromtimestamp(epoch_sec, tz=datetime.timezone.utc)
        return d.strftime("%H:%M:%S")

    def record_incident(
        self,
        stream_id: str,
        title: str,
        description: str,
        severity: str,
        category: str,
        entities: List[str],
        action: str,
        timestamp: Optional[float] = None,
    ) -> Optional[CorrelatedMultiCameraIncident]:
        """
        Records an incident from a stream and correlates it against events in other streams.
        Returns a CorrelatedMultiCameraIncident if a multi-camera progression is identified.
        """
        now = timestamp or time.time()
        camera_name = CAMERA_LABELS.get(stream_id, f"Camera [{stream_id}]")

        event_record = {
            "timestamp": now,
            "stream_id": stream_id,
            "camera_name": camera_name,
            "title": title,
            "description": description,
            "severity": severity,
            "category": category,
            "entities": [e.lower() for e in entities],
            "action": action,
        }

        # Check for cross-stream correlation with events from other streams in the last 45s
        correlated_match: Optional[CorrelatedMultiCameraIncident] = None

        for prev in reversed(self.recent_events):
            time_delta = now - prev["timestamp"]
            if time_delta > self.correlation_window_sec:
                break

            # Must be from a DIFFERENT camera feed
            if prev["stream_id"] != stream_id and time_delta <= 35.0:
                # Check entity or severity overlap
                prev_entities = set(prev["entities"])
                curr_entities = set(event_record["entities"])
                shared_entities = prev_entities.intersection(curr_entities)

                has_shared_entities = len(shared_entities) > 0
                has_high_severity = prev["severity"] in ("CRITICAL", "HIGH") or severity in ("CRITICAL", "HIGH")

                pair_key = f"{min(stream_id, prev['stream_id'])}_{max(stream_id, prev['stream_id'])}"
                last_corr = self.last_correlation_time.get(pair_key, 0.0)

                if (has_shared_entities or has_high_severity) and (now - last_corr >= 15.0):
                    self.last_correlation_time[pair_key] = now

                    streams_involved = [prev["stream_id"], stream_id]
                    progression = [
                        CorrelatedProgressionStep(
                            time=self._format_time(prev["timestamp"]),
                            stream_id=prev["stream_id"],
                            camera_name=prev["camera_name"],
                            event=prev["title"],
                            severity=prev["severity"],
                        ),
                        CorrelatedProgressionStep(
                            time=self._format_time(now),
                            stream_id=stream_id,
                            camera_name=camera_name,
                            event=title,
                            severity=severity,
                        ),
                    ]

                    # Synthesize multi-point title
                    all_entities = list(set(prev["entities"] + event_record["entities"]))
                    entity_str = f" involving {', '.join(all_entities[:2])}" if all_entities else ""
                    multi_title = f"Multi-Zone Correlated Progression: {prev['stream_id'].upper()} -> {stream_id.upper()}{entity_str}"

                    correlated_match = CorrelatedMultiCameraIncident(
                        streams_involved=streams_involved,
                        title=multi_title,
                        progression=progression,
                        severity="CRITICAL" if (severity == "CRITICAL" or prev["severity"] == "CRITICAL") else "HIGH",
                        entities_involved=all_entities,
                        recommended_action=f"Alert security patrol: Track sequence from {prev['camera_name']} to {camera_name}. {action}",
                    )

                    self.correlated_history.append(correlated_match)
                    if len(self.correlated_history) > 50:
                        self.correlated_history.pop(0)

                    logger.info(
                        f"[CROSS-STREAM CORRELATION] Synthesized multi-camera incident {correlated_match.correlation_id}: "
                        f"{streams_involved}"
                    )
                    break

        self.recent_events.append(event_record)
        return correlated_match

    def get_correlated_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent multi-camera correlated incidents."""
        return [c.model_dump() for c in reversed(self.correlated_history[-limit:])]

    def get_unified_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns unified chronological event timeline across all cameras."""
        timeline = []
        for e in self.recent_events:
            timeline.append({
                "type": "SINGLE_CAMERA_EVENT",
                "timestamp": e["timestamp"],
                "time_str": self._format_time(e["timestamp"]),
                "stream_id": e["stream_id"],
                "camera_name": e["camera_name"],
                "title": e["title"],
                "severity": e["severity"],
                "category": e["category"],
                "entities": e["entities"],
            })

        for c in self.correlated_history:
            timeline.append({
                "type": "CORRELATED_INCIDENT",
                "timestamp": c.timestamp,
                "time_str": self._format_time(c.timestamp),
                "correlation_id": c.correlation_id,
                "streams_involved": c.streams_involved,
                "title": c.title,
                "severity": c.severity,
                "progression": [p.model_dump() for p in c.progression],
                "recommended_action": c.recommended_action,
                "entities": c.entities_involved,
            })

        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        return timeline[:limit]


# Global Singleton Cross-Camera Aggregator Instance
cross_camera_aggregator = CrossCameraEventAggregator()
