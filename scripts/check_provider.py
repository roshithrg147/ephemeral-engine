import asyncio
import os
import sys

from src.clients import NVIDIA_NIM_Client
from src.config import settings


async def main():
    print("Checking NVIDIA NIM provider connectivity...")
    api_key = settings.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("FAIL: NVIDIA_API_KEY is not configured in settings or environment.", file=sys.stderr)
        sys.exit(1)

    client = NVIDIA_NIM_Client()
    models = [settings.MODEL_1_FLASH, settings.MODEL_2_CORE]

    success = True
    for model in models:
        print(f"Testing reachability and completion for model: {model}...")
        try:
            model_key = "qwen" if "qwen" in model.lower() else "kimi"
            fut = client.call_llm_async(
                model_key=model_key,
                prompt="test connectivity",
                system_prompt="respond with 'ok'",
                max_tokens=5,
            )
            res = await asyncio.wait_for(fut, timeout=10.0)
            print(f"SUCCESS: Model {model} is reachable. Response: {res.strip()}")
            usage = getattr(res, "usage", None)
            if usage:
                print(f"SUCCESS: Usage metadata is present: {usage}")
            else:
                print("WARNING: Usage metadata was not returned by provider.")
        except TimeoutError:
            print(f"FAIL: Request timed out for model {model}.", file=sys.stderr)
            success = False
        except Exception as e:
            print(f"FAIL: Request failed for model {model}: {e}", file=sys.stderr)
            success = False

    await client.aclose()

    if not success:
        print("FAIL: Connectivity verification failed.", file=sys.stderr)
        sys.exit(1)
    print("SUCCESS: Connectivity verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
