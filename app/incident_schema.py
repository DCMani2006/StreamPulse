from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentCategory(str, Enum):
    TRAFFIC = "TRAFFIC"
    INDUSTRIAL_SAFETY = "INDUSTRIAL_SAFETY"
    FACILITY_SECURITY = "FACILITY_SECURITY"
    ANOMALY = "ANOMALY"


class IncidentAnalysisResult(BaseModel):
    """Structured synthesis result produced by Cloud Multimodal VLM (Gemini 2.5 Flash)."""
    is_incident: bool = Field(
        description="True if a genuine incident, safety breach, or hazard is present; False if normal motion or benign activity."
    )
    category: IncidentCategory = Field(
        description="Categorized domain of the event."
    )
    severity: SeverityLevel = Field(
        description="Urgency level based on risk or disruption."
    )
    title: str = Field(
        description="Brief headline describing the event in under 8 words."
    )
    description: str = Field(
        description="Forensic summary detailing what occurred, affected entities, and visual/audio cues."
    )
    entities_involved: List[str] = Field(
        description="Key objects or people identified (e.g. ['Forklift #2', 'Pedestrian', 'SUV'])."
    )
    recommended_action: str = Field(
        description="Clear next step for human operators or automated dispatch."
    )
    estimated_confidence: float = Field(
        description="Confidence score between 0.0 and 1.0."
    )
