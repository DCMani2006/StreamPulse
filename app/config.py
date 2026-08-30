import os
from typing import List, Optional
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _SettingsBase(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )
except ImportError:
    from pydantic import BaseModel

    class _SettingsBase(BaseModel):
        pass


class Settings(_SettingsBase):
    # General Application Settings
    APP_NAME: str = Field(default_factory=lambda: os.getenv("APP_NAME", "StreamPulse"))
    APP_MODE: str = Field(default_factory=lambda: os.getenv("APP_MODE", "STANDALONE").upper())
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "production"))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1"))
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Redis Connection Settings
    REDIS_HOST: str = Field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    REDIS_PORT: int = Field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    REDIS_PASSWORD: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_PASSWORD", None))
    REDIS_DB: int = Field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    REDIS_URL: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_URL", None))
    REDIS_MAX_CONNECTIONS: int = Field(default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "50")))
    REDIS_TIMEOUT_SECONDS: float = Field(default_factory=lambda: float(os.getenv("REDIS_TIMEOUT_SECONDS", "5.0")))

    # Redis Stream Configuration
    STREAM_RAW_VIDEO: str = Field(default_factory=lambda: os.getenv("STREAM_RAW_VIDEO", "stream:video:raw"))
    CONSUMER_GROUP_NAME: str = Field(default_factory=lambda: os.getenv("CONSUMER_GROUP_NAME", "streampulse_workers"))
    CONSUMER_NAME_PREFIX: str = Field(default_factory=lambda: os.getenv("CONSUMER_NAME_PREFIX", "worker"))
    STREAM_MAXLEN: int = Field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "2000")))

    # PubSub & Storage Prefixes
    PUBSUB_TELEMETRY_PREFIX: str = Field(default_factory=lambda: os.getenv("PUBSUB_TELEMETRY_PREFIX", "channel:telemetry"))
    ALERTS_HISTORY_PREFIX: str = Field(default_factory=lambda: os.getenv("ALERTS_HISTORY_PREFIX", "history:alerts"))
    ALERTS_CONFIG_PREFIX: str = Field(default_factory=lambda: os.getenv("ALERTS_CONFIG_PREFIX", "config:alerts"))
    METRICS_HISTORY_PREFIX: str = Field(default_factory=lambda: os.getenv("METRICS_HISTORY_PREFIX", "metrics:samples"))
    WORKER_HEARTBEAT_PREFIX: str = Field(default_factory=lambda: os.getenv("WORKER_HEARTBEAT_PREFIX", "streampulse:worker"))

    # Rolling Metrics Settings
    METRICS_ROLLING_WINDOW_SEC: int = Field(default_factory=lambda: int(os.getenv("METRICS_ROLLING_WINDOW_SEC", "60")))
    MAX_ALERT_HISTORY_ITEMS: int = Field(default_factory=lambda: int(os.getenv("MAX_ALERT_HISTORY_ITEMS", "1000")))

    # Computer Vision (YOLOv8) Inference Settings
    YOLO_MODEL_PATH: str = Field(default_factory=lambda: os.getenv("YOLO_MODEL_PATH", "yolov8n.pt"))
    YOLO_IMAGE_SIZE: int = Field(default_factory=lambda: int(os.getenv("YOLO_IMAGE_SIZE", "320")))
    YOLO_CONFIDENCE_THRESHOLD: float = Field(default_factory=lambda: float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.35")))
    YOLO_DEVICE: str = Field(default_factory=lambda: os.getenv("YOLO_DEVICE", "cpu"))
    YOLO_HALF_PRECISION: bool = Field(default_factory=lambda: os.getenv("YOLO_HALF_PRECISION", "false").lower() in ("true", "1"))

    # Audio Signal Analysis Settings
    AUDIO_SAMPLE_RATE: int = Field(default_factory=lambda: int(os.getenv("AUDIO_SAMPLE_RATE", "16000")))
    AUDIO_ENERGY_THRESHOLD_DEFAULT: float = Field(default_factory=lambda: float(os.getenv("AUDIO_ENERGY_THRESHOLD_DEFAULT", "0.05")))
    AUDIO_ZCR_THRESHOLD_DEFAULT: float = Field(default_factory=lambda: float(os.getenv("AUDIO_ZCR_THRESHOLD_DEFAULT", "0.10")))

    # Default Alert Rule Thresholds
    DEFAULT_MAX_PERSONS: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_MAX_PERSONS", "5")))
    DEFAULT_RESTRICTED_ZONE: List[float] = Field(
        default_factory=lambda: [0.2, 0.2, 0.8, 0.8]
    )  # Normalized [x1, y1, x2, y2]

    # Latency SLA Target (ms)
    TARGET_LATENCY_SLA_MS: float = Field(default_factory=lambda: float(os.getenv("TARGET_LATENCY_SLA_MS", "300.0")))

    def get_redis_url(self) -> str:
        """Constructs Redis connection URL if not explicitly provided."""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
