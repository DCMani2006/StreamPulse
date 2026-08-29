import os
from typing import Optional
from pydantic import BaseModel, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _CloudSettingsBase(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )
except ImportError:
    class _CloudSettingsBase(BaseModel):
        pass


class CloudVLMConfig(_CloudSettingsBase):
    """Configuration for Cloud Multimodal Vision-Language Model (VLM) Tier."""
    GEMINI_API_KEY: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", None)),
        description="Google Gemini API Key for Multimodal VLM analysis",
    )
    GEMINI_MODEL: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        description="Target Gemini model for video/audio multimodal analysis",
    )
    GEMINI_TEMPERATURE: float = Field(
        default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
        description="Inference temperature (0.1-0.3 for structured classification)",
    )
    ENABLE_VLM_DISPATCH: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_VLM_DISPATCH", "true").lower() in ("true", "1"),
        description="Whether to dispatch candidate event frames to Cloud VLM",
    )
    VLM_RATE_LIMIT_COOLDOWN_SEC: float = Field(
        default_factory=lambda: float(os.getenv("VLM_RATE_LIMIT_COOLDOWN_SEC", "2.0")),
        description="Minimum cooldown period between VLM API calls per stream",
    )


cloud_config = CloudVLMConfig()
