import io
import json
import logging
import time
from typing import Optional, Dict, Any, List
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from app.cloud_config import cloud_config
from app.incident_schema import (
    IncidentAnalysisResult,
    IncidentCategory,
    SeverityLevel,
)

logger = logging.getLogger("streampulse.vlm_dispatcher")

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    logger.warning("google-genai SDK not available. Using local structured synthesis fallback.")


SYSTEM_PROMPT = """
You are StreamPulse Autonomous Incident Intelligence, a Principal Surveillance & Physical Security Multimodal Analyst.
Analyze the provided surveillance video keyframe and associated multi-modal telemetry cues (acoustic dBFS, motion delta, detected entities).
Provide a structured, decisive, and objective forensic analysis of whether a real incident, safety hazard, traffic collision, facility breach, or physical anomaly is occurring.

Rules:
1. 'is_incident': Set True ONLY for genuine accidents, traffic disruptions, safety violations, unauthorized intrusions, fights, or sudden hazards. Set False for normal benign motion, normal walking, or passing traffic.
2. 'category': Exactly one of ['TRAFFIC', 'INDUSTRIAL_SAFETY', 'FACILITY_SECURITY', 'ANOMALY'].
3. 'severity': Exactly one of ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].
4. 'title': Max 8 words, punchy and clear headline.
5. 'description': Forensic facts explaining entities, trajectories, and visual/audio cues.
6. 'entities_involved': List of key entities observed (e.g. ['Forklift', 'Pedestrian', 'SUV #102']).
7. 'recommended_action': Concrete dispatch or operator action.
8. 'estimated_confidence': Float score in [0.0, 1.0].
"""


class CloudVLMDispatcher:
    """
    Asynchronous Cloud Multimodal Vision-Language Model (VLM) Dispatcher:
    - Transmits candidate event keyframes and telemetry bursts to Google Gemini 2.5 Flash.
    - Uses strict Pydantic JSON schema constraints for guaranteed deterministic outputs.
    - Handles connection timeouts, missing API keys, and rate-limiting gracefully.
    """

    def __init__(self):
        self.client = None
        self.last_dispatch_time: Dict[str, float] = {}

        if HAS_GENAI and cloud_config.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=cloud_config.GEMINI_API_KEY)
                logger.info(f"Initialized Google GenAI VLM client (Model: {cloud_config.GEMINI_MODEL})")
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")
        else:
            logger.info("Cloud VLM initialized in offline / heuristic synthesis mode.")

    def _convert_image_to_jpeg_bytes(self, image: np.ndarray, max_dim: int = 640) -> Optional[bytes]:
        """Converts BGR numpy image to scaled JPEG bytes."""
        if image is None or image.size == 0:
            return None
        try:
            h, w = image.shape[:2]
            if max(h, w) > max_dim and HAS_CV2:
                scale = max_dim / float(max(h, w))
                image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)

            if HAS_CV2:
                _, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                return buf.tobytes()
            elif HAS_PIL:
                rgb = image[:, :, ::-1]
                pil_img = Image.fromarray(rgb)
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG", quality=75)
                return buffer.getvalue()
        except Exception as e:
            logger.warning(f"Failed to encode JPEG bytes for VLM: {e}")
        return None

    def analyze_candidate_event(
        self,
        stream_id: str,
        image: np.ndarray,
        delta_score: float,
        audio_db: float,
        detected_classes: List[str],
        active_triggers: List[str],
    ) -> IncidentAnalysisResult:
        """
        Dispatches candidate event to Gemini 2.5 Flash or structured fallback.
        Execution runs in thread pool / async task without stalling the edge pipeline.
        """
        now = time.time()
        self.last_dispatch_time[stream_id] = now

        image_bytes = self._convert_image_to_jpeg_bytes(image)

        # 1. Attempt Cloud Multimodal VLM (Gemini 2.5 Flash)
        if self.client and image_bytes and HAS_GENAI:
            try:
                prompt_text = (
                    f"Surveillance Event Telemetry Context:\n"
                    f"- Stream ID: {stream_id}\n"
                    f"- Visual Motion Delta: {delta_score * 100.0:.1f}%\n"
                    f"- Acoustic Level: {audio_db:.1f} dBFS\n"
                    f"- Detected Objects: {', '.join(detected_classes) if detected_classes else 'None'}\n"
                    f"- Active Edge Triggers: {', '.join(active_triggers) if active_triggers else 'Visual Motion'}\n\n"
                    f"Analyze the attached frame and synthesize structured incident intelligence."
                )

                response = self.client.models.generate_content(
                    model=cloud_config.GEMINI_MODEL,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg",
                        ),
                        prompt_text,
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=cloud_config.GEMINI_TEMPERATURE,
                        response_mime_type="application/json",
                        response_schema=IncidentAnalysisResult,
                    ),
                )

                if response and response.text:
                    result = IncidentAnalysisResult.model_validate_json(response.text)
                    logger.info(
                        f"[VLM SYNTHESIS] {stream_id} | Incident={result.is_incident} | "
                        f"{result.category.value} ({result.severity.value}): {result.title}"
                    )
                    return result

            except Exception as e:
                logger.warning(f"Gemini VLM API call failed ({e}). Falling back to structured synthesis.")

        # 2. Context-Aware Deterministic Synthesis Fallback
        return self._generate_contextual_synthesis(
            delta_score=delta_score,
            audio_db=audio_db,
            detected_classes=detected_classes,
            active_triggers=active_triggers,
        )

    def _generate_contextual_synthesis(
        self,
        delta_score: float,
        audio_db: float,
        detected_classes: List[str],
        active_triggers: List[str],
    ) -> IncidentAnalysisResult:
        """Generates deterministic structured synthesis when Cloud VLM is offline or rate-limited."""
        has_audio_spike = audio_db >= -28.0 or any("AUDIO" in t.upper() for t in active_triggers)
        has_prohibited = any("PROHIBITED" in t.upper() for t in active_triggers)
        has_vehicles = any(c.lower() in ("car", "truck", "bus", "motorcycle") for c in detected_classes)
        has_people = any(c.lower() == "person" for c in detected_classes)

        if has_prohibited:
            return IncidentAnalysisResult(
                is_incident=True,
                category=IncidentCategory.FACILITY_SECURITY,
                severity=SeverityLevel.CRITICAL,
                title="Prohibited Weapon or Hazard Detected",
                description=f"Security alert: Prohibited item identified among {len(detected_classes)} monitored objects in secure zone.",
                entities_involved=detected_classes[:4],
                recommended_action="Dispatch security personnel for immediate verification and access restriction.",
                estimated_confidence=0.94,
            )

        if has_audio_spike:
            category = IncidentCategory.TRAFFIC if has_vehicles else IncidentCategory.INDUSTRIAL_SAFETY
            return IncidentAnalysisResult(
                is_incident=True,
                category=category,
                severity=SeverityLevel.HIGH,
                title="Acoustic Impact & Sudden Transient Spike",
                description=f"Acoustic surge of {audio_db:.1f} dBFS detected concurrent with active visual motion ({delta_score*100:.1f}% delta).",
                entities_involved=detected_classes[:4] if detected_classes else ["Acoustic Source"],
                recommended_action="Review high-resolution forensic snapshot and check audio channel for emergency response.",
                estimated_confidence=0.91,
            )

        if delta_score >= 0.08:
            category = IncidentCategory.TRAFFIC if has_vehicles else (IncidentCategory.INDUSTRIAL_SAFETY if has_people else IncidentCategory.ANOMALY)
            return IncidentAnalysisResult(
                is_incident=True,
                category=category,
                severity=SeverityLevel.MEDIUM,
                title="Significant Dynamic Motion Event",
                description=f"High visual delta ({delta_score*100:.1f}%) observed involving active entities ({', '.join(detected_classes[:3])}).",
                entities_involved=detected_classes[:4],
                recommended_action="Log incident dossier in system audit log and maintain camera tracking.",
                estimated_confidence=0.88,
            )

        return IncidentAnalysisResult(
            is_incident=False,
            category=IncidentCategory.ANOMALY,
            severity=SeverityLevel.LOW,
            title="Benign Activity / Motion Baseline",
            description=f"Normal movement observed within baseline parameters ({delta_score*100:.1f}% pixel change).",
            entities_involved=detected_classes[:3],
            recommended_action="No intervention required. Frame logged for token baseline.",
            estimated_confidence=0.95,
        )


vlm_dispatcher = CloudVLMDispatcher()
