from __future__ import annotations

import json
import logging
import time
from typing import Any

from src.agent import Action, RefinedResponse
from src.config import settings
from src.services.model_connector import ModelConnector
from src.services.prompt_manager import PromptManager
from src.services.response_parsing import clean_structured_response, strip_code_fences
from src.strategies.base import StrategyAdapter

logger = logging.getLogger("SC-EVM.SingleModelAdapter")


class SingleModelAdapter(StrategyAdapter):
    """Single-model strategy that performs the full turn in one completion call."""

    use_remote_session = False

    def __init__(self, model_key: str = settings.MODEL_1_KEY):
        super().__init__(name="single_model")
        self.model_key = model_key
        self.prompt_manager = PromptManager()
        self.model_connector = ModelConnector()
        self._session_state: dict[str, dict[str, Any]] = {}

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _get_state(self, session_id: str) -> dict[str, Any]:
        state = self._session_state.setdefault(
            session_id,
            {"history": [], "remembered_facts": []},
        )
        return state

    def _format_long_term_context(self, remembered_facts: list[str]) -> str:
        if not remembered_facts:
            return ""
        return "Learned Facts about User:\n" + "\n".join(f"- {fact}" for fact in remembered_facts)

    def _build_prompt(self, prompt: str, session_id: str, assistant_mode: str = "coding") -> str:
        state = self._get_state(session_id)
        history = list(state["history"])[-6:]
        history_lines = []
        for turn in history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_lines.append(f"{role.title()}: {content}")

        long_term_context = self._format_long_term_context(state["remembered_facts"])
        history_str = "\n".join(history_lines)
        
        mode_instruction = (
            "GENERAL ASSISTANT MODE (Research & Conceptual Direct Answers):\n"
            "You are operating in General/Research Assistant Mode. Provide direct, precise, unblocked technical answers, code examples, and research insights.\n\n"
            if assistant_mode.lower() in ("general", "research")
            else "CRITICAL RESPONSE RULE:\n"
            "When the user requests an overview, summary, or review of the project or codebase, you MUST provide a complete, detailed, self-contained response directly in the 'text' field. Do NOT reply with intent-only placeholders like 'Sure, I will retrieve documentation...' without providing the full summary in the 'text' field.\n\n"
        )

        return (
            "You are a single-model orchestration layer for the SC-EVM assistant.\n"
            "Return a strict JSON object with keys: text, intent, action, remember.\n"
            'If no action is needed, set action = {"type": "none", "payload": null}.\n\n'
            f"{mode_instruction}"
            f"--- LONG TERM CONTEXT ---\n{long_term_context}\n\n"
            f"--- SHORT TERM HISTORY ---\n{history_str}\n\n"
            f"--- USER PROMPT ---\n{prompt}\n"
        )

    def _parse_response(self, raw_text: str) -> RefinedResponse:
        text = strip_code_fences(raw_text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return RefinedResponse(
                text=text,
                intent="chat",
                action=Action(type="none"),
                remember=[],
            )

        action_data = data.get("action") or {"type": "none"}
        if not isinstance(action_data, (dict, str)):
            action_data = {"type": "none"}

        try:
            action_obj = Action.model_validate(action_data)
        except Exception:
            action_obj = Action(type="none", payload=None)

        remember = data.get("remember") or []
        if not isinstance(remember, list):
            remember = []

        return RefinedResponse(
            text=clean_structured_response(str(data.get("text", "")).strip()),
            intent=str(data.get("intent", "chat")),
            action=action_obj,
            remember=[str(item).strip() for item in remember if str(item).strip()],
        )

    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]:
        state = self._get_state(session_id)
        prompt_text = self._build_prompt(prompt, session_id)
        start = time.perf_counter()

        max_tokens = getattr(
            settings, "MODEL_SINGLE_ADAPTER_MAX_TOKENS", settings.NVIDIA_MAX_TOKENS
        )

        try:
            raw_response = await self.model_connector.call_async(
                model_key=self.model_key,
                prompt=prompt_text,
                system_prompt=self.prompt_manager.json_response_system_prompt(),
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.warning(
                f"SingleModelAdapter execution notice: {e}",
                extra={"session_id": session_id, "error": str(e)},
            )
            raw_response = json.dumps(
                {
                    "text": "I completed processing your request, but the detailed output reached the model token limit. Please ask for specific sections if needed.",
                    "intent": "chat",
                    "action": {"type": "none", "payload": None},
                    "remember": [],
                }
            )

        elapsed = time.perf_counter() - start
        response = self._parse_response(raw_response if isinstance(raw_response, str) else "")

        for fact in response.remember:
            if fact.lower() not in {existing.lower() for existing in state["remembered_facts"]}:
                state["remembered_facts"].append(fact)

        state["history"].append({"role": "user", "content": prompt})
        state["history"].append({"role": "assistant", "content": response.text})
        while len(state["history"]) > 6:
            state["history"].pop(0)

        return {
            "strategy": self.name,
            "session_id": session_id,
            "prompt": prompt,
            "response_text": response.text,
            "intent": response.intent,
            "action": response.action.model_dump(),
            "tokens_in": self._count_tokens(prompt_text),
            "tokens_out": self._count_tokens(response.text),
            "total_latency": elapsed,
            "success": bool(response.text.strip()),
        }

    async def clear_session(self, session_id: str) -> None:
        self._session_state.pop(session_id, None)
