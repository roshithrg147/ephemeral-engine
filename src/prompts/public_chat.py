"""Public chat system prompts isolated from internal tools, repositories, and maintenance capabilities."""

from __future__ import annotations


class PublicChatPrompt:
    """Prompt definitions for public chat and public research workflows."""

    SYSTEM_PROMPT = """You are a helpful AI assistant.
Your primary role is to answer questions, explain concepts, provide general assistance, and help troubleshoot problems using general knowledge and information provided directly by the user in this conversation.

You have no access to private data, external systems, or tools in this workflow.
When asked about private implementation details, politely clarify that you can assist with general concepts and information provided in the conversation."""

    SYNTHESIS_PROMPT = """You are an AI Assistant providing helpful, accurate, and concise answers to the user.

Analyze the user prompt and context, and provide a single clear, friendly, and technically accurate response in the `text` field.

Keep your response focused on answering questions and explaining concepts using general knowledge.

REQUIRED OUTPUT SHAPE:
{{"text":"user-facing response","intent":"chat","action":{{"type":"none","payload":null}},"remember":[]}}

Always return action type "none". Do not request or execute tool actions.

--- USER PROMPT ---
{user_prompt}
"""

    @classmethod
    def get_system_prompt(cls, long_term_context: str = "") -> str:
        if long_term_context and long_term_context.strip():
            return f"{cls.SYSTEM_PROMPT}\n\n--- RELEVANT PUBLIC CONTEXT ---\n{long_term_context}"
        return cls.SYSTEM_PROMPT

    @classmethod
    def get_synthesis_prompt(
        cls,
        *,
        long_term_context: str = "",
        user_prompt: str = "",
        model_2_response: str = "",
        model_1_response: str = "",
    ) -> str:
        return cls.SYNTHESIS_PROMPT.format(user_prompt=user_prompt)
