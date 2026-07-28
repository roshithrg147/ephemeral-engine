"""PromptManager owning persona templates and prompt construction for the reasoning pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.prompts.maintenance import MaintenancePrompt
from src.prompts.operator import OperatorPrompt
from src.prompts.public_chat import PublicChatPrompt
from src.workflow_policy import WorkflowClass

if TYPE_CHECKING:
    from src.security_context import SecurityContext


class PromptManager:
    """Owns persona templates and workflow-isolated prompt construction."""

    REWRITE_SYSTEM_PROMPT = """You are a cognitive query orchestration layer.
Given a conversation history sliding window and a new user prompt, you must perform two tasks:
1. Generate a dense, keyword-heavy string optimized for vector database similarity search.
2. Generate an expanded, fully explicit version of the user prompt where all pronouns, ambiguous references, and fragmented context links are fully resolved into clear architectural entities.

You must return your output strictly as a valid raw JSON object with two keys: "search_vector_query" and "grounded_llm_prompt". Do not wrap it in markdown code blocks. Keep all string values concise and direct.
"""

    ORCHESTRATOR_SYSTEM_PROMPT = MaintenancePrompt.SYSTEM_PROMPT
    SYNTHESIS_SYSTEM_PROMPT = MaintenancePrompt.SYNTHESIS_PROMPT

    AUGMENTED_PROMPT_TEMPLATE = """--- RETRIEVED MEMORY CONTEXT ---
{context_str}

--- CURRENT USER PROMPT ---
{grounded_llm_prompt}"""

    @classmethod
    def build_rewrite_prompt(cls, current_input: str, history: list[dict[str, str]]) -> str:
        history_window = history[-6:]
        formatted_turns = []
        for turn in history_window:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            role_label = "User" if role == "user" else "Assistant"
            formatted_turns.append(f"{role_label}: {content}")

        history_str = "\n".join(formatted_turns)
        return f"Conversation History:\n{history_str}\n\nCurrent User Prompt: {current_input}"

    @classmethod
    def build_orchestrator_system_prompt(
        cls, long_term_context: str, sec_ctx: SecurityContext | None = None
    ) -> str:
        if sec_ctx is not None:
            if sec_ctx.workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
                return PublicChatPrompt.get_system_prompt(long_term_context)
            if sec_ctx.workflow == WorkflowClass.OPERATOR_READ:
                return OperatorPrompt.get_system_prompt(long_term_context)
        return MaintenancePrompt.get_system_prompt(long_term_context)

    @classmethod
    def build_synthesis_prompt(
        cls,
        *,
        long_term_context: str,
        user_prompt: str,
        model_2_response: str,
        model_1_response: str,
        sec_ctx: SecurityContext | None = None,
    ) -> str:
        if sec_ctx is not None:
            if sec_ctx.workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
                return PublicChatPrompt.get_synthesis_prompt(
                    long_term_context=long_term_context,
                    user_prompt=user_prompt,
                    model_2_response=model_2_response,
                    model_1_response=model_1_response,
                )
            if sec_ctx.workflow == WorkflowClass.OPERATOR_READ:
                return OperatorPrompt.get_synthesis_prompt(
                    long_term_context=long_term_context,
                    user_prompt=user_prompt,
                    model_2_response=model_2_response,
                    model_1_response=model_1_response,
                )
        return MaintenancePrompt.get_synthesis_prompt(
            long_term_context=long_term_context,
            user_prompt=user_prompt,
            model_2_response=model_2_response,
            model_1_response=model_1_response,
        )

    @classmethod
    def build_augmented_prompt(cls, *, context_str: str, grounded_llm_prompt: str) -> str:
        return cls.AUGMENTED_PROMPT_TEMPLATE.format(
            context_str=context_str,
            grounded_llm_prompt=grounded_llm_prompt,
        )

    @classmethod
    def json_response_system_prompt(cls, sec_ctx: SecurityContext | None = None) -> str:
        if sec_ctx is not None and sec_ctx.workflow in (
            WorkflowClass.PUBLIC_CHAT,
            WorkflowClass.PUBLIC_RESEARCH,
        ):
            return (
                "Return one valid raw JSON object with keys text, intent, action, and remember. "
                "action must be an object with keys type set to 'none' and payload set to null. "
                "Do not request tool actions or wrap JSON in markdown code blocks."
            )
        return (
            "Return one valid raw JSON object with keys text, intent, action, and remember. "
            "action must be an object with keys type and payload. "
            "Allowed actions are list_files, read_file, save_file, and none. "
            "Use read_file or list_files instead of asking the user for terminal output. "
            "Do not wrap JSON in markdown code blocks."
        )
