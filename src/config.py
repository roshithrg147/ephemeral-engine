import os

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys
    NVIDIA_API_KEY: str = ""
    NVIDIA_API_KEY_QWEN: str = ""
    NVIDIA_API_KEY_KIWI: str = ""

    # API endpoints
    SC_EVM_BASE_URL: str = "http://127.0.0.1:8000"
    SC_EVM_SINGLE_MODEL_BASE_URL: str = "http://127.0.0.1:8001"
    NVIDIA_NIM_CHAT_COMPLETIONS_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"

    # NVIDIA NIM model registry
    MODEL_1_KEY: str = "qwen"
    MODEL_2_KEY: str = "kiwi"
    MODEL_1_FLASH: str = "qwen/qwen3.5-122b-a10b"
    MODEL_2_CORE: str = "moonshotai/kimi-k2.6"
    MODEL_1_ALIASES: tuple[str, ...] = ("qwen", "model_1", "model1")
    MODEL_2_ALIASES: tuple[str, ...] = (
        "kiwi",
        "kimi",
        "moonshot",
        "claude",
        "opus",
        "model_2",
        "model2",
    )
    MODEL_1_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    MODEL_1_TOP_P: float = Field(default=0.8, ge=0.0, le=1.0)
    MODEL_2_TEMPERATURE: float = Field(default=1.0, ge=0.0, le=2.0)
    MODEL_2_TOP_P: float = Field(default=1.0, ge=0.0, le=1.0)
    MODEL_1_INPUT_PRICE_PER_1K: float = Field(default=0.0003, ge=0.0)
    MODEL_1_OUTPUT_PRICE_PER_1K: float = Field(default=0.0004, ge=0.0)
    MODEL_2_INPUT_PRICE_PER_1K: float = Field(default=0.0005, ge=0.0)
    MODEL_2_OUTPUT_PRICE_PER_1K: float = Field(default=0.0006, ge=0.0)
    MODEL_CANDIDATE_MAX_TOKENS: int = Field(default=2048, ge=1, le=131_072)
    MODEL_REFORMULATION_MAX_TOKENS: int = Field(default=512, ge=1, le=131_072)
    MODEL_SYNTHESIS_MAX_TOKENS: int = Field(default=1536, ge=1, le=131_072)

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
    SESSION_TOKEN_BUDGET: int = Field(default=2500, ge=1)
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
    NVIDIA_CONNECT_TIMEOUT_SECONDS: float = Field(default=3.0, ge=0.1, le=60.0)
    NVIDIA_READ_TIMEOUT_SECONDS: float = Field(default=60.0, ge=1.0, le=600.0)
    NVIDIA_WRITE_TIMEOUT_SECONDS: float = Field(default=45.0, ge=1.0, le=600.0)
    NVIDIA_POOL_TIMEOUT_SECONDS: float = Field(default=5.0, ge=0.1, le=60.0)
    NVIDIA_READ_TIMEOUT_RETRIES: int = Field(default=1, ge=0, le=3)
    NVIDIA_MAX_CONNECTIONS: int = Field(default=64, ge=1, le=1024)
    NVIDIA_MAX_KEEPALIVE_CONNECTIONS: int = Field(default=64, ge=1, le=1024)

    # Retrieval and dual-anchor distance policy
    RETRIEVAL_RESULT_LIMIT: int = Field(default=3, ge=1, le=100)
    RETRIEVAL_BASE_DISTANCE_THRESHOLD: float = Field(default=0.52, ge=0.0, le=2.0)
    RETRIEVAL_ABSOLUTE_DISTANCE_CEILING: float = Field(default=0.48, ge=0.0, le=2.0)
    RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR: float = Field(default=0.38, ge=0.0, le=2.0)
    RETRIEVAL_NEIGHBOR_DELTA_LIMIT: float = Field(default=0.12, ge=0.0, le=2.0)
    RETRIEVAL_TOP_ANCHOR_DELTA_LIMIT: float = Field(default=0.18, ge=0.0, le=2.0)
    RETRIEVAL_CALIBRATION_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    RETRIEVAL_MIN_DISTANCE_THRESHOLD: float = Field(default=0.1, ge=0.0, le=2.0)
    RETRIEVAL_MAX_DISTANCE_THRESHOLD: float = Field(default=0.9, ge=0.0, le=2.0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("AUDIT_LOG_PATH")
    @classmethod
    def expand_audit_log_path(cls, v: str) -> str:
        return os.path.expanduser(v)

    @model_validator(mode="after")
    def validate_routing_and_thresholds(self) -> "Settings":
        """Reject ambiguous model routing and invalid bounded-policy ordering."""
        model_1_keys = {self.MODEL_1_KEY.lower(), *(key.lower() for key in self.MODEL_1_ALIASES)}
        model_2_keys = {self.MODEL_2_KEY.lower(), *(key.lower() for key in self.MODEL_2_ALIASES)}
        overlap = model_1_keys & model_2_keys
        if overlap:
            raise ValueError(f"Model role aliases overlap: {sorted(overlap)}")
        if self.NVIDIA_MAX_KEEPALIVE_CONNECTIONS > self.NVIDIA_MAX_CONNECTIONS:
            raise ValueError(
                "NVIDIA_MAX_KEEPALIVE_CONNECTIONS cannot exceed NVIDIA_MAX_CONNECTIONS"
            )
        if self.RETRIEVAL_MIN_DISTANCE_THRESHOLD > self.RETRIEVAL_MAX_DISTANCE_THRESHOLD:
            raise ValueError(
                "RETRIEVAL_MIN_DISTANCE_THRESHOLD cannot exceed RETRIEVAL_MAX_DISTANCE_THRESHOLD"
            )
        if self.RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR > self.RETRIEVAL_ABSOLUTE_DISTANCE_CEILING:
            raise ValueError(
                "RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR cannot exceed "
                "RETRIEVAL_ABSOLUTE_DISTANCE_CEILING"
            )
        return self


# Instantiate global settings
settings = Settings()
