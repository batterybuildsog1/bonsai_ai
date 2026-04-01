"""Spec-first planner: ask the AI to generate a building spec from natural language.

This is the glue between the AI and the deterministic BuildingGenerator.
The AI produces a small JSON spec (~200-400 tokens), the generator expands
it into a complete IFC model.

Supports the same providers as ``create_plan()`` (OpenAI, Anthropic, Gemini)
but uses a spec-focused system prompt and structured output.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reuse the core HTTP + provider infrastructure
try:
    from bonsai_ai_core.defaults import DEFAULT_MODELS as CORE_DEFAULT_MODELS
    from bonsai_ai_core.defaults import ENV_KEYS
    from bonsai_ai_core.errors import ProviderError
    from bonsai_ai_core.http import post_json
except ModuleNotFoundError:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bonsai_ai_core.defaults import DEFAULT_MODELS as CORE_DEFAULT_MODELS
    from bonsai_ai_core.defaults import ENV_KEYS
    from bonsai_ai_core.errors import ProviderError
    from bonsai_ai_core.http import post_json

from .building_spec_schema import building_spec_schema
from .spec_validator import validate_spec

# ---------------------------------------------------------------------------
# System prompt for spec generation (<300 words)
# ---------------------------------------------------------------------------

SPEC_SYSTEM_PROMPT = """\
You are a building designer. Given a building description, output a JSON building specification.

The spec defines WHAT the building is, not HOW to build it. Deterministic code handles all \
coordinate math, grid layout, and element placement.

Output ONLY the JSON spec. No commentary.

Required fields:
- footprint: {length (X-axis, meters), width (Y-axis, meters)}
- stories: [{name, height, program}] -- bottom to top

Optional fields (sensible defaults applied if omitted):
- grid: {spacing_x, spacing_y} -- default ~8m, adjusted to fit footprint evenly
- structure: {frame_type, column_section, beam_section, slab_thickness, roof_type}
- facades: {north/south/east/west: {type, windows, curtain_wall}} -- default: concrete walls
- entries: [{face, type, width, height, position}] -- default: one main entrance
- mezzanines: [{story_index, sides, depth, height_fraction}]
- roof: {type, thickness}
- foundation: {type, bearing_elevation, soil_bearing_kpa}

Rules:
- Grid spacing must divide evenly into footprint dimensions. Pick spacings that produce \
whole-number bay counts: e.g. 40m / 8m = 5 bays, 25m / 6.25m = 4 bays.
- Story elevations are auto-calculated from cumulative heights. Do not provide them.
- Use metric units (meters) throughout.
- Keep it minimal: omit fields where defaults suffice.
- For multi-story buildings, the ground floor is usually taller (4.0-4.5m retail/lobby) \
and upper floors are 3.5-4.0m.
"""

# ---------------------------------------------------------------------------
# Provider map
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "openai": CORE_DEFAULT_MODELS["openai"],
    "anthropic": CORE_DEFAULT_MODELS["anthropic"],
    "gemini": CORE_DEFAULT_MODELS["google"],
}

DEFAULT_ENV_VARS = {
    "openai": ENV_KEYS["openai"][0],
    "anthropic": ENV_KEYS["anthropic"][0],
    "gemini": ENV_KEYS["google"][0],
}


def _resolve_api_key(provider: str, api_key: Optional[str]) -> str:
    if api_key:
        return api_key.strip()
    canonical = "google" if provider == "gemini" else provider
    for env_key in ENV_KEYS[canonical]:
        value = os.getenv(env_key)
        if value:
            return value.strip()
    raise ProviderError(f"Missing API key for provider '{provider}'.")


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from model text, handling markdown fences."""
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


# ---------------------------------------------------------------------------
# Provider-specific callers
# ---------------------------------------------------------------------------

def _call_openai(model: str, api_key: str, user_prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SPEC_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "building_spec",
                "schema": schema,
                "strict": False,
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = post_json("https://api.openai.com/v1/responses", payload, headers)
    # Extract text from Responses API output
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return _extract_json(response["output_text"])
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return _extract_json(content["text"])
    raise ProviderError(f"OpenAI response did not contain spec text: {response}")


def _call_anthropic(model: str, api_key: str, user_prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": [
            {
                "type": "text",
                "text": SPEC_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "tools": [
            {
                "name": "emit_building_spec",
                "description": "Return a building specification as structured JSON.",
                "input_schema": schema,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "tool_choice": {"type": "tool", "name": "emit_building_spec"},
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    response = post_json("https://api.anthropic.com/v1/messages", payload, headers)
    for item in response.get("content", []):
        if item.get("type") == "tool_use" and item.get("name") == "emit_building_spec":
            if isinstance(item.get("input"), dict):
                return item["input"]
        if item.get("type") == "text" and item.get("text"):
            return _extract_json(item["text"])
    raise ProviderError(f"Anthropic response did not contain a spec: {response}")


def _call_gemini(model: str, api_key: str, user_prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SPEC_SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
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
            return _extract_json(part["text"])
    raise ProviderError(f"Gemini response did not include JSON text: {response}")


_PROVIDER_CALLERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_spec(
    user_prompt: str,
    provider: str = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Ask the AI to generate a building spec from a natural language description.

    Uses the evaluator-optimizer pattern: generate, validate, revise.

    Parameters
    ----------
    user_prompt : str
        Natural language building description.
    provider : str
        One of "openai", "anthropic", "gemini".
    model : str, optional
        Override default model for the provider.
    api_key : str, optional
        Explicit API key; falls back to environment variables.
    max_retries : int
        Maximum validation-and-retry cycles.

    Returns
    -------
    dict
        A validated building spec conforming to ``BUILDING_SPEC_SCHEMA``.

    Raises
    ------
    ProviderError
        If the provider call fails or the spec cannot be validated after retries.
    """
    provider = provider.strip().lower()
    if provider not in _PROVIDER_CALLERS:
        raise ProviderError(f"Unsupported provider: {provider}")

    resolved_key = _resolve_api_key(provider, api_key)
    resolved_model = model or DEFAULT_MODELS[provider]
    schema = building_spec_schema()
    caller = _PROVIDER_CALLERS[provider]

    prompt = user_prompt.strip()
    last_issues: List[str] = []

    for attempt in range(max_retries):
        effective_prompt = prompt
        if last_issues:
            issue_text = "\n".join(f"  - {issue}" for issue in last_issues)
            effective_prompt = (
                f"{prompt}\n\n"
                "The previous spec had validation issues:\n"
                f"{issue_text}\n"
                "Fix these issues and return a corrected spec."
            )

        raw_spec = caller(resolved_model, resolved_key, effective_prompt, schema)

        # Auto-fill story elevations if missing
        raw_spec = _fill_defaults(raw_spec)

        issues = validate_spec(raw_spec)
        if not issues:
            return raw_spec

        last_issues = issues
        print(f"[spec_planner] Attempt {attempt + 1}: {len(issues)} validation issue(s), retrying...")
        for issue in issues:
            print(f"  - {issue}")

    # Return the spec even with issues, annotated
    raw_spec["_validation_issues"] = last_issues
    print(f"[spec_planner] WARNING: Returning spec with {len(last_issues)} unresolved issue(s)")
    return raw_spec


def _fill_defaults(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Fill auto-calculated defaults that the AI should not have to provide."""

    # Auto-calculate story elevations
    if "stories" in spec:
        elevation = 0.0
        for story in spec["stories"]:
            if "elevation" not in story:
                story["elevation"] = round(elevation, 6)
            elevation = story["elevation"] + story["height"]

    # Auto-assign story names
    if "stories" in spec:
        for i, story in enumerate(spec["stories"]):
            if "name" not in story or not story["name"]:
                story["name"] = f"Level {i + 1}"

    # Auto-adjust grid spacing to fit footprint evenly
    if "footprint" in spec:
        fp = spec["footprint"]
        length = fp.get("length", 0)
        width = fp.get("width", 0)
        if length > 0 and width > 0:
            grid = spec.get("grid", {})
            if "bays_x" not in grid and "spacing_x" not in grid:
                grid["spacing_x"] = 8.0
            if "bays_y" not in grid and "spacing_y" not in grid:
                grid["spacing_y"] = 8.0

            # Adjust spacing to divide evenly
            if "spacing_x" in grid and "bays_x" not in grid:
                grid["spacing_x"] = _adjust_spacing(length, grid["spacing_x"])
            if "spacing_y" in grid and "bays_y" not in grid:
                grid["spacing_y"] = _adjust_spacing(width, grid["spacing_y"])

            spec["grid"] = grid

    return spec


def _adjust_spacing(total: float, target: float) -> float:
    """Adjust target spacing so it divides evenly into total length.

    Picks the closest even-division spacing to the target.
    """
    if target <= 0 or total <= 0:
        return target
    bays = max(1, round(total / target))
    return round(total / bays, 6)
