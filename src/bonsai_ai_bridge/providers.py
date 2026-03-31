from __future__ import annotations

import abc
import os
from typing import Any

import httpx


DEFAULT_MODELS = {
    "openai": "gpt-5.4",
    "anthropic": "claude-opus-4-1-20250805",
    "google": "gemini-2.5-flash-lite",
}


class ProviderError(RuntimeError):
    pass


class BaseProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    async def generate_plan_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        raise NotImplementedError


class OpenAIProvider(BaseProvider):
    name = "openai"

    async def generate_plan_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "reasoning_effort": "medium",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "building_plan",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        _raise_for_status("OpenAI", response)
        data = response.json()
        return data["choices"][0]["message"]["content"]


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    async def generate_plan_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")

        schema_hint = (
            "Return only a JSON object that matches this schema exactly:\n"
            f"{json_schema}\n"
            "Do not wrap the JSON in Markdown."
        )
        payload = {
            "model": model,
            "max_tokens": 8192,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": f"{user_prompt}\n\n{schema_hint}"}],
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )
        _raise_for_status("Anthropic", response)
        data = response.json()
        blocks = data.get("content", [])
        text_parts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
        return "\n".join(text_parts).strip()


class GoogleProvider(BaseProvider):
    name = "google"

    async def generate_plan_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("GEMINI_API_KEY or GOOGLE_API_KEY is not set")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, params={"key": api_key}, json=payload)
        _raise_for_status("Google", response)
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def get_provider(name: str) -> BaseProvider:
    normalized = name.strip().lower()
    providers: dict[str, BaseProvider] = {
        "openai": OpenAIProvider(),
        "anthropic": AnthropicProvider(),
        "google": GoogleProvider(),
        "gemini": GoogleProvider(),
    }
    if normalized not in providers:
        raise ProviderError(f"Unsupported provider: {name}")
    return providers[normalized]


def _raise_for_status(label: str, response: httpx.Response) -> None:
    if response.is_success:
        return
    detail = response.text
    raise ProviderError(f"{label} API error {response.status_code}: {detail}")
