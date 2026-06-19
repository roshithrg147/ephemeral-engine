import os
import json
from typing import List, Dict, Any, Optional, Union, AsyncIterator, Iterator
import httpx

def load_env_file():
    """Loads environment variables from a .env file if it exists."""
    # Find the directory containing this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(current_dir, ".env"),
        os.path.join(current_dir, "../.env"),
        os.path.join(current_dir, "../../.env"),
        ".env",
        "../.env",
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip()
                            # Strip quotes if present
                            if val.startswith('"') and val.endswith('"'):
                                val = val[1:-1]
                            elif val.startswith("'") and val.endswith("'"):
                                val = val[1:-1]
                            os.environ[key] = val
                break
            except Exception:
                pass

# Auto-load environment variables upon import
load_env_file()

class NVIDIA_NIM_Client:
    """Standardized client for calling NVIDIA NIM API completions endpoints."""

    def _map_model(self, model_key: str):
        """Maps a model key to the official NVIDIA NIM model name, parameters, and API key."""
        key_lower = model_key.lower()
        if "qwen" in key_lower:
            model_name = "qwen/qwen3.5-122b-a10b"
            temp = 0.60
            top_p = 0.95
            api_key = os.getenv("NVIDIA_API_KEY_QWEN") or os.getenv("NVIDIA_API_KEY")
        elif "kimi" in key_lower or "kiwi" in key_lower or "moonshot" in key_lower:
            model_name = "moonshotai/kimi-k2.6"
            temp = 1.00
            top_p = 1.00
            api_key = os.getenv("NVIDIA_API_KEY_KIWI") or os.getenv("NVIDIA_API_KEY")
        else:
            # Default fallback to Qwen
            model_name = "qwen/qwen3.5-122b-a10b"
            temp = 0.60
            top_p = 0.95
            api_key = os.getenv("NVIDIA_API_KEY")

        if not api_key:
            raise ValueError(f"NVIDIA API Key not found in environment for key: {model_key}")
            
        return model_name, temp, top_p, api_key

    def _prepare_payload(self, model_name: str, temp: float, top_p: float, 
                         prompt: Union[str, List[Dict[str, str]]], 
                         system_prompt: Optional[str], stream: bool) -> Dict[str, Any]:
        """Prepares the request payload for the NVIDIA completions endpoint."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if isinstance(prompt, list):
            for msg in prompt:
                role = msg.get("role", "user")
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
        else:
            messages.append({"role": "user", "content": prompt})

        return {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "top_p": top_p,
            "max_tokens": 16384,
            "stream": stream
        }

    def call_llm(self, model_key: str, prompt: Union[str, List[Dict[str, str]]], 
                 system_prompt: Optional[str] = None, stream: bool = False) -> Union[str, Iterator[str]]:
        """Synchronously calls the NVIDIA completions endpoint."""
        model_name, temp, top_p, api_key = self._map_model(model_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = self._prepare_payload(model_name, temp, top_p, prompt, system_prompt, stream)

        if stream:
            def gen():
                import time
                max_retries = 3
                backoff = 1.0
                response = None
                client = None
                for attempt in range(max_retries + 1):
                    try:
                        client = httpx.Client(timeout=None)
                        response = client.send(client.build_request("POST", "https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload), stream=True)
                        if response.status_code == 200:
                            break
                        elif response.status_code in [500, 502, 503, 504] and attempt < max_retries:
                            response.close()
                            client.close()
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        else:
                            detail = response.read()
                            response.close()
                            client.close()
                            raise RuntimeError(f"NVIDIA API Error: Status {response.status_code}, Detail: {detail.decode('utf-8')}")
                    except (httpx.HTTPError, httpx.TimeoutException) as e:
                        if response:
                            response.close()
                        if client:
                            client.close()
                        if attempt < max_retries:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise e
                
                try:
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                pass
                finally:
                    response.close()
                    client.close()
            return gen()
        else:
            import time
            max_retries = 3
            backoff = 1.0
            for attempt in range(max_retries + 1):
                try:
                    with httpx.Client(timeout=None) as client:
                        response = client.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            return result["choices"][0]["message"]["content"]
                        elif response.status_code in [500, 502, 503, 504] and attempt < max_retries:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        else:
                            raise RuntimeError(f"NVIDIA API Error: Status {response.status_code}, Detail: {response.text}")
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    if attempt < max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise e

    async def call_llm_async(self, model_key: str, prompt: Union[str, List[Dict[str, str]]], 
                             system_prompt: Optional[str] = None, stream: bool = False) -> Union[str, AsyncIterator[str]]:
        """Asynchronously calls the NVIDIA completions endpoint."""
        model_name, temp, top_p, api_key = self._map_model(model_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = self._prepare_payload(model_name, temp, top_p, prompt, system_prompt, stream)

        if stream:
            async def gen():
                import asyncio
                max_retries = 3
                backoff = 1.0
                response = None
                client = None
                for attempt in range(max_retries + 1):
                    try:
                        client = httpx.AsyncClient(timeout=None)
                        response = await client.send(client.build_request("POST", "https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload), stream=True)
                        if response.status_code == 200:
                            break
                        elif response.status_code in [500, 502, 503, 504] and attempt < max_retries:
                            await response.aclose()
                            await client.aclose()
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                        else:
                            detail = await response.aread()
                            await response.aclose()
                            await client.aclose()
                            raise RuntimeError(f"NVIDIA API Error: Status {response.status_code}, Detail: {detail.decode('utf-8')}")
                    except (httpx.HTTPError, httpx.TimeoutException) as e:
                        if response:
                            await response.aclose()
                        if client:
                            await client.aclose()
                        if attempt < max_retries:
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                        raise e
                
                try:
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                pass
                finally:
                    await response.aclose()
                    await client.aclose()
            return gen()
        else:
            import asyncio
            max_retries = 3
            backoff = 1.0
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        response = await client.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            return result["choices"][0]["message"]["content"]
                        elif response.status_code in [500, 502, 503, 504] and attempt < max_retries:
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                        else:
                            raise RuntimeError(f"NVIDIA API Error: Status {response.status_code}, Detail: {response.text}")
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    if attempt < max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    raise e
