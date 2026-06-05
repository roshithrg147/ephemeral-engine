import os
import google.auth
from google import genai
from google.genai import types
from anthropic import AnthropicVertex
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import concurrent.futures
from src.memory import MemoryManager

# Default Vertex AI regions/locations
DEFAULT_GEMINI_LOCATION = "us-central1"
DEFAULT_CLAUDE_LOCATION = "us-east5"

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
        self.project_id = None
        self.google_client = None
        self.claude_client = None
        
        # Configure model names
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        # In Vertex AI, Claude 3.5 Sonnet is often 'claude-3-5-sonnet@20240620' or 'claude-3-5-sonnet-v2'
        # Or 'claude-opus-4-6' as in the user's original script
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
        self.refiner_model = os.getenv("REFINER_MODEL", "gemini-2.5-pro")
        self.imagen_model = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        
        self.authenticate()

    def authenticate(self) -> None:
        """Authenticate and initialize Gemini and Claude clients, prioritizing standard API keys."""
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Try to load Application Default Credentials (ADC) / project_id
        try:
            creds, project_id = google.auth.default()
            self.project_id = project_id
        except Exception:
            self.project_id = None

        # Determine which authentication mechanism to use
        use_gemini_api_key = bool(gemini_api_key)
        use_anthropic_api_key = bool(anthropic_api_key)

        # Initialize Google Gen AI client
        if use_gemini_api_key:
            self.google_client = genai.Client(api_key=gemini_api_key)
        elif self.project_id:
            gemini_loc = os.getenv("VERTEX_GEMINI_LOCATION", DEFAULT_GEMINI_LOCATION)
            self.google_client = genai.Client(vertexai=True, location=gemini_loc, project=self.project_id)
        else:
            raise RuntimeError("Authentication failed. Please configure GEMINI_API_KEY or set up Application Default Credentials (gcloud auth application-default login).")

        # Initialize Claude client
        if use_anthropic_api_key:
            from anthropic import Anthropic
            self.claude_client = Anthropic(api_key=anthropic_api_key, max_retries=0)
            # Automatically map Vertex AI specific model IDs to standard Anthropic ones
            original_claude_model = os.getenv("CLAUDE_MODEL", self.claude_model)
            if "opus" in original_claude_model.lower() or "4-6" in original_claude_model:
                self.claude_model = "claude-3-opus-20240229"
            elif "sonnet" in original_claude_model.lower():
                self.claude_model = "claude-3-5-sonnet-20241022"
            elif "haiku" in original_claude_model.lower():
                self.claude_model = "claude-3-5-haiku-20241022"
            else:
                self.claude_model = original_claude_model
        elif self.project_id:
            claude_loc = os.getenv("VERTEX_CLAUDE_LOCATION", DEFAULT_CLAUDE_LOCATION)
            self.claude_client = AnthropicVertex(region=claude_loc, project_id=self.project_id, max_retries=0)
        else:
            self.claude_client = None

    def _query_gemini_raw(self, system_prompt: str, user_prompt: str, history: List[Dict[str, str]]) -> str:
        """Call Gemini to get a conversational response."""
        # Convert history format
        contents = []
        for turn in history:
            contents.append(types.Content(
                role="user" if turn["role"] == "user" else "model",
                parts=[types.Part.from_text(text=turn["content"])]
            ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        ))
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7
        )
        
        response = self.google_client.models.generate_content(
            model=self.gemini_model,
            contents=contents,
            config=config
        )
        return response.text

    def _query_claude_raw(self, system_prompt: str, user_prompt: str, history: List[Dict[str, str]]) -> str:
        """Call Claude to get a conversational response."""
        if not self.claude_client:
            return "[Claude API Client not configured or authenticated]"
            
        # Format messages for Anthropic
        messages = []
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})
        
        # Vertex AI Anthropic API requires region & project, which is configured in self.claude_client
        msg = self.claude_client.messages.create(
            model=self.claude_model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            timeout=30.0
        )
        return msg.content[0].text

    def generate_response(self, user_prompt: str) -> RefinedResponse:
        """Queries Claude and Gemini in parallel, then synthesizes/refines the response."""
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
            futures = {}
            if self.claude_client:
                futures["claude"] = executor.submit(
                    self._query_claude_raw, system_instructions, user_prompt, st_history
                )
            futures["gemini"] = executor.submit(
                self._query_gemini_raw, system_instructions, user_prompt, st_history
            )
            
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
                        claude_resp = f"[Claude failed: {e}]"
                    else:
                        gemini_resp = f"[Gemini failed: {e}]"
                        
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
        """Uses Gemini structured JSON mode to weigh both responses and return a RefinedResponse."""
        synthesis_prompt = f"""You are the Synthesizer/Refiner for a Dual-LLM Personal Assistant.
You have received two responses to the user's prompt:
1. Response A (from Claude 3.5 Sonnet / 3 Opus)
2. Response B (from Gemini 2.5 Pro)

Your task is to:
1. Analyze both responses, weigh their facts, style, and correctness.
2. Produce a single refined response in the `text` field. It should combine the strengths of both (Claude's reasoning/eloquence, Gemini's structured details) and resolve any conflicts. Keep it friendly and concise.
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

--- RESPONSE A (Claude) ---
{claude_resp}

--- RESPONSE B (Gemini) ---
{gemini_resp}
"""
        try:
            # We configure structured JSON output with Gemini
            response = self.google_client.models.generate_content(
                model=self.refiner_model,
                contents=synthesis_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RefinedResponse,
                    temperature=0.2
                )
            )
            # Parse structured JSON from response.text
            import json
            data = json.loads(response.text)
            return RefinedResponse(**data)
        except Exception as e:
            # Graceful recovery if synthesis schema fails
            fallback_text = (
                gemini_resp if gemini_resp and "[Gemini failed" not in gemini_resp 
                else (claude_resp if claude_resp else "Both models failed to generate response.")
            )
            return RefinedResponse(
                text=fallback_text,
                intent="chat",
                action=Action(type="none"),
                remember=[]
            )

    def generate_image(self, prompt: str, filename: str = "images/output.png") -> str:
        """Generates an image using Imagen 3 and saves it to the workspace."""
        if not self.google_client:
            raise RuntimeError("Google client is not initialized.")
            
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        try:
            # Call Imagen 3 via Vertex or standard API
            response = self.google_client.models.generate_images(
                model=self.imagen_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type='image/png',
                    aspect_ratio='16:9'
                )
            )
            for generated_image in response.generated_images:
                with open(filename, "wb") as f:
                    f.write(generated_image.image.image_bytes)
                return os.path.abspath(filename)
        except Exception as e:
            # Fallback: some configurations support Gemini 3 Pro Image GenerateContent modality
            try:
                response = self.google_client.models.generate_content(
                    model="gemini-3-pro-image-preview", 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE'],
                        temperature=0.7
                    )
                )
                for part in response.parts:
                    if image := part.as_image():
                        image.save(filename)
                        return os.path.abspath(filename)
            except Exception as e2:
                raise RuntimeError(f"Imagen generation failed: {e}. Fallback image modality failed: {e2}")
        
        raise RuntimeError("No image was returned by the model.")
