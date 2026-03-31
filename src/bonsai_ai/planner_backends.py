from __future__ import annotations

from typing import Optional

from .contracts import DesignBrief, PhysicalModelSpec


class CorePhysicalPlannerBackend:
    """Planner backend that delegates to the existing bonsai_ai_core JSON-plan generator."""

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
        service_tier: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.service_tier = service_tier

    def build_physical_model(self, brief: DesignBrief) -> PhysicalModelSpec:
        core = self._load_core()
        authored_plan = core.build_plan(
            prompt=self._compose_prompt(brief),
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            reasoning_effort=self.reasoning_effort,
            service_tier=self.service_tier,
        )
        semantic_model = core.build_semantic_model(authored_plan)
        compiled_plan = core.compile_plan(authored_plan)
        return PhysicalModelSpec(
            summary=authored_plan["summary"],
            assumptions=authored_plan["assumptions"],
            plan=compiled_plan,
            authored_plan=authored_plan,
            semantic_model=semantic_model,
            metadata={
                "provider": self.provider,
                "model": self.model,
                "authored_action_count": len(authored_plan["actions"]),
                "semantic_element_count": len(semantic_model.get("elements", [])),
                "semantic_assembly_count": len(semantic_model.get("assemblies", [])),
                "compiled_action_count": len(compiled_plan["actions"]),
            },
        )

    @staticmethod
    def _load_core():
        import bonsai_ai_core

        return bonsai_ai_core

    @staticmethod
    def _compose_prompt(brief: DesignBrief) -> str:
        parts = [brief.prompt.strip()]
        if brief.constraints:
            parts.append("Constraints:\n" + "\n".join(f"- {item}" for item in brief.constraints))
        if brief.documents:
            doc_lines = [f"- {doc.name}: {doc.path}" for doc in brief.documents]
            parts.append("Source documents:\n" + "\n".join(doc_lines))
        if brief.scene_context:
            parts.append(f"Scene context:\n{brief.scene_context}")
        return "\n\n".join(part for part in parts if part)
