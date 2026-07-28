"""Operator system prompts for read-only system monitoring and status inspection."""

from __future__ import annotations


class OperatorPrompt:
    """Prompt definitions for read-only operator workflows."""

    SYSTEM_PROMPT = """You are an AI Operator assistant responsible for monitoring system health, operational status, and session metrics.
{lt_context}
You have read-only access to list and inspect workspace files for status verification.
Do not execute commands or modify files."""

    SYNTHESIS_PROMPT = """You are the Synthesizer for an Operator Monitoring Assistant.

Analyze the operational query and provide a clear status summary in the `text` field.

Allowed read actions: 'list_files', 'read_file', or 'none'.

REQUIRED OUTPUT SHAPE:
{{"text":"user-facing response","intent":"status","action":{{"type":"read_file","payload":{{"file_path":"relative/path"}}}},"remember":[]}}

--- CONTEXT ---
{lt_context}

--- USER PROMPT ---
{user_prompt}

--- RESPONSE A (NVIDIA NIM MODEL 2) ---
{model_2_response}

--- RESPONSE B (NVIDIA NIM MODEL 1) ---
{model_1_response}
"""

    @classmethod
    def get_system_prompt(cls, long_term_context: str = "") -> str:
        return cls.SYSTEM_PROMPT.format(lt_context=long_term_context)

    @classmethod
    def get_synthesis_prompt(
        cls,
        *,
        long_term_context: str = "",
        user_prompt: str = "",
        model_2_response: str = "",
        model_1_response: str = "",
    ) -> str:
        return cls.SYNTHESIS_PROMPT.format(
            lt_context=long_term_context,
            user_prompt=user_prompt,
            model_2_response=model_2_response,
            model_1_response=model_1_response,
        )
