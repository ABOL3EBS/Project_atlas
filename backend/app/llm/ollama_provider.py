import json
from collections.abc import AsyncIterator

import httpx

from .base import LLMProvider


def _ollama_reachable(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5)
        return response.is_success
    except httpx.HTTPError:
        return False


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload = {"model": self._model, "prompt": prompt, "system": system, "stream": False}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/api/generate", json=payload, timeout=300
            )
            response.raise_for_status()
            return response.json()["response"]

    async def stream(self, prompt: str, *, system: str | None = None) -> AsyncIterator[str]:
        payload = {"model": self._model, "prompt": prompt, "system": system, "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", f"{self._base_url}/api/generate", json=payload, timeout=300
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("response")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break

    def check(self) -> bool:
        return _ollama_reachable(self._base_url)