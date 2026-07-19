import concurrent.futures
import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from src.config import settings
from src.services.model_connector import ModelConnector
from src.services.prompt_manager import PromptManager
from src.services.response_parsing import strip_code_fences

logger = logging.getLogger("SC-EVM.Agent")
_MODEL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(2, settings.MAX_WORKER_THREADS),
    thread_name_prefix="sc-evm-model",
)
try:
    from src.telemetry_sink import log_error
except ImportError:

    def log_error(ctx, msg):
        logger.warning("Telemetry sink unavailable", extra={"context": ctx, "message": msg})


class MemorySnapshot(BaseModel):
    long_term_context: str = ""
    short_term_history: list[dict[str, str]] = Field(default_factory=list)


class ActionPayload(BaseModel):
    command: str | None = Field(None, description="The shell command to execute")
    prompt: str | None = Field(None, description="The prompt for image generation")
    file_path: str | None = Field(None, description="File path to save to")
    file_content: str | None = Field(None, description="File contents to write")


class Action(BaseModel):
    type: str = Field(
        ...,
        description="Action type: 'none', 'run_command', 'generate_image', 'save_file', 'update_memory'",
    )
    payload: ActionPayload | None = Field(None, description="Arguments for the action")


class RefinedResponse(BaseModel):
    text: str = Field(..., description="The conversational text response to display to the user.")
    intent: str = Field(
        ...,
        description="The detected user intent (e.g. chat, command, image_generation, file, help, exit).",
    )
    action: Action = Field(..., description="Any automated action to execute.")
    remember: list[str] = Field(
        default_factory=list,
        description="List of new facts, preferences, or updates about the user to store in long term memory.",
    )
    usage_records: list[dict[str, Any]] | None = None


class AgentOrchestrator:
    def __init__(
        self,
        model_connector: ModelConnector | None = None,
        prompt_manager: PromptManager | None = None,
    ):
        self.model_connector = model_connector or ModelConnector()
        self.prompt_manager = prompt_manager or PromptManager()
        self.model_1_key = settings.MODEL_1_KEY
        self.model_2_key = settings.MODEL_2_KEY
        self.synthesis_model_key = self.model_2_key

        self.authenticate()

    def authenticate(self) -> None:
        """Verify that at least one NVIDIA API key is configured in the environment."""
        from src.config import settings

        key = (
            settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY_KIWI or settings.NVIDIA_API_KEY_QWEN
        )
        if not key:
            raise RuntimeError(
                "Authentication failed. Please configure NVIDIA_API_KEY in your environment."
            )

    def _query_model_raw(
        self, model_key: str, system_prompt: str, user_prompt: str, history: list[dict[str, str]]
    ) -> str:
        """Call NVIDIA NIM completions endpoint for a specific model."""
        messages = []
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})

        return self.model_connector.call(
            model_key=model_key,
            prompt=messages,
            system_prompt=system_prompt,
            max_tokens=settings.MODEL_CANDIDATE_MAX_TOKENS,
        )

    def generate_response(
        self, memory_snapshot: MemorySnapshot | dict[str, Any], user_prompt: str
    ) -> RefinedResponse:
        """Queries Kimi and Qwen in parallel, then synthesizes/refines the response."""
        if isinstance(memory_snapshot, dict):
            memory_snapshot = MemorySnapshot(**memory_snapshot)

        lt_context = memory_snapshot.long_term_context
        st_history = list(memory_snapshot.short_term_history)
        system_instructions = self.prompt_manager.build_orchestrator_system_prompt(lt_context)

        # Call models in parallel threads
        model_1_response = None
        model_2_response = None

        futures = {
            "model_2": _MODEL_EXECUTOR.submit(
                self._query_model_raw,
                self.model_2_key,
                system_instructions,
                user_prompt,
                st_history,
            ),
            "model_1": _MODEL_EXECUTOR.submit(
                self._query_model_raw,
                self.model_1_key,
                system_instructions,
                user_prompt,
                st_history,
            ),
        }

        for name, future in futures.items():
            try:
                result = future.result()
                if name == "model_2":
                    model_2_response = result
                else:
                    model_1_response = result
            except Exception as e:
                log_error(f"agent.generate_response.{name}", str(e))
                if name == "model_2":
                    model_2_response = f"[Model 2 failed: {e}]"
                else:
                    model_1_response = f"[Model 1 failed: {e}]"

        # Synthesize both responses
        refined = self.synthesize_responses(
            user_prompt,
            model_2_response,
            model_1_response,
            lt_context,
        )

        # Send refined response to the clipboard daemon
        self.send_to_clipboard_daemon(refined.text)

        return refined

    def send_to_clipboard_daemon(self, text: str) -> None:
        """Pushes the refined response text to the MyClipboard UNIX socket."""
        import socket

        SOCKET_PATH = os.path.expanduser("~/.config/anthropic-agent/daemon.sock")
        if os.path.exists(SOCKET_PATH):
            try:
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.connect(SOCKET_PATH)
                # Send with special prefix to distinguish from normal clips
                client.sendall(f"ADD:AGENT_RESPONSE:{text}".encode())
                client.close()
            except ConnectionRefusedError:
                # Daemon is not running or listening, gracefully ignore
                logger.info("Clipboard daemon unavailable; skipping response handoff")
            except Exception as e:
                logging.getLogger("SC-EVM.Error").error(
                    f"Clipboard daemon connection failed: {e}", exc_info=True
                )
                log_error("agent.clipboard_daemon", str(e))

    def synthesize_responses(
        self,
        user_prompt: str,
        model_2_response: Any,
        model_1_response: Any,
        lt_context: str,
    ) -> RefinedResponse:
        """Use the configured NVIDIA NIM synthesis role to refine both responses."""
        synthesis_prompt = self.prompt_manager.build_synthesis_prompt(
            long_term_context=lt_context,
            user_prompt=user_prompt,
            model_2_response=model_2_response,
            model_1_response=model_1_response,
        )
        try:
            response_text = self.model_connector.call(
                model_key=self.synthesis_model_key,
                prompt=synthesis_prompt,
                system_prompt=self.prompt_manager.json_response_system_prompt(),
                max_tokens=settings.MODEL_SYNTHESIS_MAX_TOKENS,
            )
            text_clean = strip_code_fences(response_text)
            data = json.loads(text_clean)
            refined = RefinedResponse(**data)

            # Compile usage records
            from src.clients import get_model_price

            records = []

            # 1. Model 2 candidate call
            model_2_usage = getattr(model_2_response, "usage", None)
            if model_2_usage:
                records.append(
                    {
                        "measurement_type": "exact",
                        "provider": "nvidia",
                        "model": self.model_2_key,
                        "tokenizer": None,
                        "input_tokens": model_2_usage.get("prompt_tokens"),
                        "output_tokens": model_2_usage.get("completion_tokens"),
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": None,
                        "price_table_version": "v1.0",
                        "calculated_cost": (model_2_usage.get("prompt_tokens", 0) / 1000.0)
                        * get_model_price(self.model_2_key)["input_1k"]
                        + (model_2_usage.get("completion_tokens", 0) / 1000.0)
                        * get_model_price(self.model_2_key)["output_1k"],
                    }
                )
            else:
                records.append(
                    {
                        "measurement_type": "estimate",
                        "provider": "nvidia",
                        "model": self.model_2_key,
                        "tokenizer": None,
                        "input_tokens": len(user_prompt) // 4,
                        "output_tokens": len(
                            getattr(model_2_response, "text", str(model_2_response))
                        )
                        // 4,
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": "exact usage not returned by provider",
                        "price_table_version": "v1.0",
                        "calculated_cost": None,
                    }
                )

            # 2. Model 1 candidate call
            model_1_usage = getattr(model_1_response, "usage", None)
            if model_1_usage:
                records.append(
                    {
                        "measurement_type": "exact",
                        "provider": "nvidia",
                        "model": self.model_1_key,
                        "tokenizer": None,
                        "input_tokens": model_1_usage.get("prompt_tokens"),
                        "output_tokens": model_1_usage.get("completion_tokens"),
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": None,
                        "price_table_version": "v1.0",
                        "calculated_cost": (model_1_usage.get("prompt_tokens", 0) / 1000.0)
                        * get_model_price(self.model_1_key)["input_1k"]
                        + (model_1_usage.get("completion_tokens", 0) / 1000.0)
                        * get_model_price(self.model_1_key)["output_1k"],
                    }
                )
            else:
                records.append(
                    {
                        "measurement_type": "estimate",
                        "provider": "nvidia",
                        "model": self.model_1_key,
                        "tokenizer": None,
                        "input_tokens": len(user_prompt) // 4,
                        "output_tokens": len(
                            getattr(model_1_response, "text", str(model_1_response))
                        )
                        // 4,
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": "exact usage not returned by provider",
                        "price_table_version": "v1.0",
                        "calculated_cost": None,
                    }
                )

            # 3. Synthesis call
            synth_usage = getattr(response_text, "usage", None)
            if synth_usage:
                records.append(
                    {
                        "measurement_type": "exact",
                        "provider": "nvidia",
                        "model": self.synthesis_model_key,
                        "tokenizer": None,
                        "input_tokens": synth_usage.get("prompt_tokens"),
                        "output_tokens": synth_usage.get("completion_tokens"),
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": None,
                        "price_table_version": "v1.0",
                        "calculated_cost": (synth_usage.get("prompt_tokens", 0) / 1000.0)
                        * get_model_price(self.synthesis_model_key)["input_1k"]
                        + (synth_usage.get("completion_tokens", 0) / 1000.0)
                        * get_model_price(self.synthesis_model_key)["output_1k"],
                    }
                )
            else:
                records.append(
                    {
                        "measurement_type": "estimate",
                        "provider": "nvidia",
                        "model": self.synthesis_model_key,
                        "tokenizer": None,
                        "input_tokens": len(synthesis_prompt) // 4,
                        "output_tokens": len(text_clean) // 4,
                        "cached_tokens": None,
                        "retry_usage": None,
                        "missing_reason": "exact usage not returned by provider",
                        "price_table_version": "v1.0",
                        "calculated_cost": None,
                    }
                )

            refined.usage_records = records
            return refined
        except Exception as e:
            log_error("agent.synthesize", str(e))
            # Graceful recovery if synthesis schema fails
            fallback_text = (
                model_1_response
                if model_1_response and "[Model 1 failed" not in str(model_1_response)
                else (
                    model_2_response
                    if model_2_response
                    else "Both models failed to generate response."
                )
            )
            return RefinedResponse(
                text=str(fallback_text), intent="chat", action=Action(type="none"), remember=[]
            )

    def generate_image(self, prompt: str, filename: str = "images/output.png") -> str:
        """Stub image generation since Imagen is removed."""
        print(f"[Stub] generate_image called with prompt: {prompt}")
        return os.path.abspath(filename)
