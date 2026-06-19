import os
import json
import concurrent.futures
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from src.memory import MemoryManager
from src.clients import NVIDIA_NIM_Client

class ActionPayload(BaseModel):
    command: Optional[str] = Field(None, description="The shell command to execute")
    prompt: Optional[str] = Field(None, description="The prompt for image generation")
    file_path: Optional[str] = Field(None, description="File path to save to")
    file_content: Optional[str] = Field(None, description="File contents to write")

class Action(BaseModel):
    type: str = Field(..., description="Action type: 'none', 'run_command', 'generate_image', 'save_file', 'update_memory'")
    payload: Optional[ActionPayload] = Field(None, description="Arguments for the action")

class RefinedResponse(BaseModel):
    text: str = Field(..., description="The conversational text response to display to the user.")
    intent: str = Field(..., description="The detected user intent (e.g. chat, command, image_generation, file, help, exit).")
    action: Action = Field(..., description="Any automated action to execute.")
    remember: List[str] = Field(default=[], description="List of new facts, preferences, or updates about the user to store in long term memory.")

class AgentOrchestrator:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.nvidia_client = NVIDIA_NIM_Client()
        
        # Configure model names mapped to NVIDIA NIM keys
        self.gemini_model = "qwen"
        self.claude_model = "kimi"
        self.refiner_model = "kimi"
        
        self.authenticate()

    def authenticate(self) -> None:
        """Verify that at least one NVIDIA API key is configured in the environment."""
        key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_API_KEY_KIWI") or os.getenv("NVIDIA_API_KEY_QWEN")
        if not key:
            raise RuntimeError("Authentication failed. Please configure NVIDIA_API_KEY in your environment.")

    def _query_model_raw(self, model_key: str, system_prompt: str, user_prompt: str, history: List[Dict[str, str]]) -> str:
        """Call NVIDIA NIM completions endpoint for a specific model."""
        messages = []
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})
        
        return self.nvidia_client.call_llm(
            model_key=model_key,
            prompt=messages,
            system_prompt=system_prompt
        )

    def generate_response(self, user_prompt: str) -> RefinedResponse:
        """Queries Kimi and Qwen in parallel, then synthesizes/refines the response."""
        # Get memory contexts
        lt_context = self.memory.get_long_term_context()
        st_history = self.memory.get_short_term_history()
        
        system_instructions = f"""You are a personal digital assistant helping the user locally.
{lt_context}
Provide clear, helpful, and technically accurate responses. Keep terminal context in mind."""

        # Call models in parallel threads
        claude_resp = None
        gemini_resp = None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                "claude": executor.submit(
                    self._query_model_raw, "kimi", system_instructions, user_prompt, st_history
                ),
                "gemini": executor.submit(
                    self._query_model_raw, "qwen", system_instructions, user_prompt, st_history
                )
            }
            
            # Wait for results
            for name, future in futures.items():
                try:
                    res = future.result()
                    if name == "claude":
                        claude_resp = res
                    elif name == "gemini":
                        gemini_resp = res
                except Exception as e:
                    # Log error internally and default to None
                    if name == "claude":
                        claude_resp = f"[Kimi failed: {e}]"
                    else:
                        gemini_resp = f"[Qwen failed: {e}]"
                        
        # Synthesize both responses
        refined = self.synthesize_responses(user_prompt, claude_resp, gemini_resp, lt_context, st_history)
        
        # Save learned facts to long-term memory
        for fact in refined.remember:
            self.memory.add_fact(fact)
            
        # Update short term memory with user input and the refined text
        self.memory.add_interaction(user_prompt, refined.text)
        
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
                client.sendall(f"ADD:AGENT_RESPONSE:{text}".encode('utf-8'))
                client.close()
            except Exception:
                pass

    def synthesize_responses(
        self, 
        user_prompt: str, 
        claude_resp: str, 
        gemini_resp: str, 
        lt_context: str, 
        st_history: List[Dict[str, str]]
    ) -> RefinedResponse:
        """Uses NVIDIA NIM Qwen model to weigh both responses and return a RefinedResponse."""
        synthesis_prompt = f"""You are the Synthesizer/Refiner for a Dual-LLM Personal Assistant.
You have received two responses to the user's prompt:
1. Response A (from Moonshot Kimi)
2. Response B (from Qwen)

Your task is to:
1. Analyze both responses, weigh their facts, style, and correctness.
2. Produce a single refined response in the `text` field. It should combine the strengths of both (reasoning/eloquence, structured details) and resolve any conflicts. Keep it friendly and concise.
3. Determine the user's `intent` (chat, command, image_generation, file, help, exit).
4. Decide if the query requires an automated `action` on the user's system:
   - 'run_command': if the user wants to execute a terminal/shell command. Put the command in action.payload.command.
   - 'generate_image': if the user wants to create/draw an image. Put the prompt in action.payload.prompt.
   - 'save_file': if the user wants to write a file. Put the path in action.payload.file_path and content in action.payload.file_content.
   - 'update_memory': if the user wants to update their name or profile details.
   - 'none': if no action is needed.
5. Extract any new facts about the user (e.g. name, preferences, project layout) to permanently remember in the `remember` list. Do NOT repeat facts already present in the User Profile Context or Learned Facts.

--- CONTEXT ---
{lt_context}

--- USER PROMPT ---
{user_prompt}

--- RESPONSE A (Moonshot Kimi) ---
{claude_resp}

--- RESPONSE B (Qwen) ---
{gemini_resp}
"""
        try:
            # We query NVIDIA NIM model
            response_text = self.nvidia_client.call_llm(
                model_key=self.refiner_model,
                prompt=synthesis_prompt,
                system_prompt="You must return your output strictly as a valid raw JSON object. Do not wrap it in markdown code blocks."
            )
            text_clean = response_text.strip()
            if text_clean.startswith("```json"):
                text_clean = text_clean[7:]
            if text_clean.endswith("```"):
                text_clean = text_clean[:-3]
            text_clean = text_clean.strip()
            data = json.loads(text_clean)
            return RefinedResponse(**data)
        except Exception as e:
            # Graceful recovery if synthesis schema fails
            fallback_text = (
                gemini_resp if gemini_resp and "[Qwen failed" not in gemini_resp 
                else (claude_resp if claude_resp else "Both models failed to generate response.")
            )
            return RefinedResponse(
                text=fallback_text,
                intent="chat",
                action=Action(type="none"),
                remember=[]
            )

    def generate_image(self, prompt: str, filename: str = "images/output.png") -> str:
        """Stub image generation since Imagen is removed."""
        print(f"[Stub] generate_image called with prompt: {prompt}")
        return os.path.abspath(filename)
