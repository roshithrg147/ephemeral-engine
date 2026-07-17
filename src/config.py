import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys
    NVIDIA_API_KEY: str = ""
    NVIDIA_API_KEY_QWEN: str = ""
    NVIDIA_API_KEY_KIWI: str = ""

    # Model Configurations (Defaults provided, but overridable via .env)
    MODEL_1_FLASH: str = "qwen/qwen3.5-122b-a10b"
    MODEL_2_CORE: str = "moonshotai/kimi-k2.6"

    # Network Security
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Concurrency
    MAX_WORKER_THREADS: int = Field(default=8, ge=2, le=64)
    COMMAND_TIMEOUT_SECONDS: int = Field(default=300, ge=1, le=3600)
    IPC_MAX_PAYLOAD_BYTES: int = Field(default=1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    WORKSPACE_MAX_FILE_BYTES: int = Field(default=2 * 1024 * 1024, ge=1024)

    # GC and Session Management
    GC_TTL_SECONDS: int = Field(default=3600, ge=1)
    GC_INTERVAL_SECONDS: int = Field(default=300, ge=1)
    MAX_ACTIVE_SESSIONS: int = Field(default=1024, ge=1, le=10_000)
    MAX_HISTORY_TURNS: int = Field(default=6, ge=2, le=100)
    AUDIT_LOG_PATH: str = "~/.config/anthropic-agent/audit.log"
    CHROMA_EMBEDDING_MODEL: str = "ONNXMiniLM_L6_V2"
    DEVELOPMENT_PHASE: int = 0
    TELEMETRY_ENABLED: bool = True
    TELEMETRY_REDACT_CONTENT: bool = True
    TELEMETRY_MAX_FILE_SIZE_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024)
    DIAGNOSTIC_MODE: bool = False

    # NVIDIA API Limits
    NVIDIA_MAX_TOKENS: int = Field(default=4096, ge=1, le=131_072)
    NVIDIA_MAX_RETRIES: int = Field(default=3, ge=0, le=10)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("AUDIT_LOG_PATH")
    @classmethod
    def expand_audit_log_path(cls, v: str) -> str:
        return os.path.expanduser(v)


# Instantiate global settings
settings = Settings()
