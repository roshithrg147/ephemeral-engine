import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys
    NVIDIA_API_KEY: str = ""

    # API endpoints
    SC_EVM_BASE_URL: str = "http://127.0.0.1:8000"
    SC_EVM_SINGLE_MODEL_BASE_URL: str = "http://127.0.0.1:8001"
    NVIDIA_NIM_CHAT_COMPLETIONS_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"

    # NVIDIA NIM model registry
    MODEL_1_KEY: Literal["nemotron"] = "nemotron"
    MODEL_2_KEY: Literal["gpt-oss"] = "gpt-oss"
    MODEL_1_FLASH: Literal["nvidia/nemotron-3-nano-30b-a3b"] = "nvidia/nemotron-3-nano-30b-a3b"
    MODEL_2_CORE: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    MODEL_1_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    MODEL_1_TOP_P: float = Field(default=0.8, ge=0.0, le=1.0)
    MODEL_2_TEMPERATURE: float = Field(default=1.0, ge=0.0, le=2.0)
    MODEL_2_TOP_P: float = Field(default=1.0, ge=0.0, le=1.0)
    MODEL_1_INPUT_PRICE_PER_1K: float = Field(default=0.0003, ge=0.0)
    MODEL_1_OUTPUT_PRICE_PER_1K: float = Field(default=0.0004, ge=0.0)
    MODEL_2_INPUT_PRICE_PER_1K: float = Field(default=0.0005, ge=0.0)
    MODEL_2_OUTPUT_PRICE_PER_1K: float = Field(default=0.0006, ge=0.0)
    MODEL_CANDIDATE_MAX_TOKENS: int = Field(default=4096, ge=1, le=131_072)
    MODEL_REFORMULATION_MAX_TOKENS: int = Field(default=2048, ge=1, le=131_072)
    MODEL_SYNTHESIS_MAX_TOKENS: int = Field(default=4096, ge=1, le=131_072)
    MODEL_SINGLE_ADAPTER_MAX_TOKENS: int = Field(default=4096, ge=1, le=131_072)

    # Network Security
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Concurrency
    MAX_WORKER_THREADS: int = Field(default=8, ge=2, le=64)
    COMMAND_TIMEOUT_SECONDS: int = Field(default=300, ge=1, le=3600)
    IPC_MAX_PAYLOAD_BYTES: int = Field(default=1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    WORKSPACE_MAX_FILE_BYTES: int = Field(default=2 * 1024 * 1024, ge=1024)
    SANDBOX_ROOT: Path = Field(default=Path("./sandboxes"), validation_alias="SC_EVM_SANDBOX_ROOT")

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

    # Authentication and deployment boundary
    DEPLOYMENT_MODE: Literal["development", "production"] = "development"
    AUTH_MODE: Literal["disabled", "oidc", "firebase"] = "disabled"
    OIDC_ISSUER: str = ""
    OIDC_AUDIENCE: str = ""
    OIDC_JWKS_URL: str = ""
    OIDC_JWT_ALGORITHMS: tuple[str, ...] = ("RS256",)
    OIDC_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=300)
    OIDC_JWKS_CACHE_SECONDS: int = Field(default=300, ge=30, le=86400)
    OIDC_JWKS_MIN_REFRESH_SECONDS: int = Field(default=30, ge=1, le=3600)
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_PATH: str = ""
    DIAGNOSTIC_SCOPE: str = "scevm:diagnostic"
    OPERATOR_SCOPE: str = "scevm:operator"

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
        if self.DEPLOYMENT_MODE == "production":
            if self.AUTH_MODE not in ("oidc", "firebase"):
                raise ValueError(
                    "Production deployment requires AUTH_MODE=oidc or AUTH_MODE=firebase"
                )
            if self.AUTH_MODE == "oidc":
                required_oidc = {
                    "OIDC_ISSUER": self.OIDC_ISSUER,
                    "OIDC_AUDIENCE": self.OIDC_AUDIENCE,
                    "OIDC_JWKS_URL": self.OIDC_JWKS_URL,
                }
                missing = sorted(name for name, value in required_oidc.items() if not value.strip())
                if missing:
                    raise ValueError(f"Production OIDC settings missing: {', '.join(missing)}")
            for name in ("OIDC_ISSUER", "OIDC_JWKS_URL"):
                parsed = urlparse(required_oidc[name])
                if parsed.scheme != "https" or not parsed.netloc:
                    raise ValueError(f"Production {name} must be an absolute HTTPS URL")
            allowed_algorithms = {
                "RS256",
                "RS384",
                "RS512",
                "PS256",
                "PS384",
                "PS512",
                "ES256",
                "ES384",
                "ES512",
            }
            unsupported = sorted(set(self.OIDC_JWT_ALGORITHMS) - allowed_algorithms)
            if unsupported:
                raise ValueError(f"Unsafe or unsupported production JWT algorithms: {unsupported}")
            unsafe_origins = [
                origin
                for origin in self.CORS_ORIGINS
                if origin == "*"
                or urlparse(origin).scheme != "https"
                or not urlparse(origin).netloc
            ]
            if not self.CORS_ORIGINS or unsafe_origins:
                raise ValueError("Production CORS_ORIGINS must contain explicit HTTPS origins")
            if self.DIAGNOSTIC_MODE:
                raise ValueError("Production DIAGNOSTIC_MODE must be disabled")
        return self


# Instantiate global settings
settings = Settings()
