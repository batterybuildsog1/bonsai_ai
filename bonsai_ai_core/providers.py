"""Model-provider adapters for structured plan generation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict

from .defaults import DEFAULT_MODELS, ENV_KEYS
from .errors import ProviderError
from .http import post_json
from .schema import plan_schema


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ProviderError("Model response did not contain a JSON object.")
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Failed to parse model JSON: {cleaned[:800]}") from exc


def _resolve_api_key(provider: str, explicit_key: str | None) -> str:
    if explicit_key:
        return explicit_key.strip()
    for env_key in ENV_KEYS[provider]:
        value = os.getenv(env_key)
        if value:
            return value.strip()
    raise ProviderError(f"Missing API key for provider '{provider}'.")


@dataclass
class ProviderRequest:
    provider: str
    system_prompt: str
    user_prompt: str
    model: str | None = None
    api_key: str | None = None
    reasoning_effort: str | None = None
    service_tier: str | None = None


class BaseProvider:
    provider_name = ""

    def __init__(self, req: ProviderRequest):
        self.req = req
        self.api_key = _resolve_api_key(self.provider_name, req.api_key)
        self.model = req.model or DEFAULT_MODELS[self.provider_name]
        self.schema = plan_schema()

    def generate_plan(self) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAIProvider(BaseProvider):
    provider_name = "openai"
    endpoint = "https://api.openai.com/v1/responses"

    def generate_plan(self) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": self.req.system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": self.req.user_prompt}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "bonsai_action_plan",
                    "schema": self.schema,
                    "strict": False,
                }
            },
        }
        if self.req.reasoning_effort:
            payload["reasoning"] = {"effort": self.req.reasoning_effort}
        if self.req.service_tier:
            payload["service_tier"] = self.req.service_tier
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = post_json(self.endpoint, payload, headers)
        except ProviderError as exc:
            response = self._retry_response(payload, headers, exc)
        if isinstance(response.get("output_text"), str) and response["output_text"].strip():
            return _extract_json_from_text(response["output_text"])
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return _extract_json_from_text(content["text"])
        raise ProviderError(f"OpenAI response did not contain plan text: {response}")

    def _retry_response(self, payload: Dict[str, Any], headers: Dict[str, str], exc: ProviderError) -> Dict[str, Any]:
        if self.req.service_tier == "priority" and _should_retry_without_priority(exc):
            payload.pop("service_tier", None)
            return post_json(self.endpoint, payload, headers)
        if _should_retry_without_schema(exc):
            fallback_payload = self._fallback_payload()
            try:
                return post_json(self.endpoint, fallback_payload, headers)
            except ProviderError as fallback_exc:
                if self.req.service_tier == "priority" and _should_retry_without_priority(fallback_exc):
                    fallback_payload.pop("service_tier", None)
                    return post_json(self.endpoint, fallback_payload, headers)
                raise
        raise exc

    def _fallback_payload(self) -> Dict[str, Any]:
        schema_prompt = (
            f"{self.req.system_prompt}\n\n"
            "Return only a JSON object that matches this schema exactly. "
            "Do not wrap the JSON in Markdown.\n"
            f"{json.dumps(self.schema)}"
        )
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": schema_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": self.req.user_prompt}],
                },
            ],
        }
        if self.req.reasoning_effort:
            payload["reasoning"] = {"effort": self.req.reasoning_effort}
        if self.req.service_tier:
            payload["service_tier"] = self.req.service_tier
        return payload


def _should_retry_without_priority(exc: ProviderError) -> bool:
    detail = str(exc).lower()
    return "service_tier" in detail or "priority" in detail


def _should_retry_without_schema(exc: ProviderError) -> bool:
    detail = str(exc).lower()
    return "invalid_json_schema" in detail or "invalid schema for response_format" in detail


class AnthropicProvider(BaseProvider):
    provider_name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"

    def generate_plan(self) -> Dict[str, Any]:
        # Anthropic prompt caching (GA): mark the system prompt and last tool
        # with cache_control so that repeated planning rounds reuse cached
        # prefix tokens, cutting input-token cost by ~90% and latency by ~85%.
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": [
                {
                    "type": "text",
                    "text": self.req.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": [
                {
                    "name": "emit_bonsai_action_plan",
                    "description": "Return a Bonsai action plan that uses only the supported BIM primitives.",
                    "input_schema": self.schema,
                    "strict": True,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tool_choice": {"type": "tool", "name": "emit_bonsai_action_plan"},
            "messages": [{"role": "user", "content": self.req.user_prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        response = post_json(self.endpoint, payload, headers)
        for item in response.get("content", []):
            if item.get("type") == "tool_use" and item.get("name") == "emit_bonsai_action_plan":
                if not isinstance(item.get("input"), dict):
                    raise ProviderError(f"Anthropic tool payload was not JSON: {item}")
                return item["input"]
            if item.get("type") == "text" and item.get("text"):
                return _extract_json_from_text(item["text"])
        raise ProviderError(f"Anthropic response did not contain a plan: {response}")


class GoogleProvider(BaseProvider):
    provider_name = "google"

    def generate_plan(self) -> Dict[str, Any]:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": self.req.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": self.req.user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.schema,
            },
        }
        headers = {"Content-Type": "application/json"}
        response = post_json(endpoint, payload, headers)
        candidates = response.get("candidates", [])
        if not candidates:
            raise ProviderError(f"Gemini response did not include candidates: {response}")
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if part.get("text"):
                return _extract_json_from_text(part["text"])
        raise ProviderError(f"Gemini response did not include JSON text: {response}")


def get_provider(req: ProviderRequest) -> BaseProvider:
    provider_map = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
    }
    try:
        return provider_map[req.provider](req)
    except KeyError as exc:
        raise ProviderError(f"Unsupported provider '{req.provider}'.") from exc
