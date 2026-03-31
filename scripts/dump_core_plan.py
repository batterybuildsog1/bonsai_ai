from __future__ import annotations

import argparse
import json
import sys

from bonsai_ai_core.errors import ValidationError
from bonsai_ai_core.planner import SYSTEM_PROMPT
from bonsai_ai_core.providers import ProviderRequest, get_provider
from bonsai_ai_core.schema import validate_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--service-tier", default="priority")
    args = parser.parse_args()

    api_key = sys.stdin.read().strip()
    if not api_key:
        raise RuntimeError("Expected API key on stdin.")

    req = ProviderRequest(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        reasoning_effort=args.reasoning_effort,
        service_tier=args.service_tier,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=args.prompt,
    )
    raw_plan = get_provider(req).generate_plan()
    payload: dict[str, object] = {"raw_plan": raw_plan}
    try:
        validate_plan(raw_plan)
        payload["validated"] = True
    except ValidationError as exc:
        payload["validated"] = False
        payload["validation_error"] = str(exc)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
