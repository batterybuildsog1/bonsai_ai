from __future__ import annotations

import json
import math
import os
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List

from .contracts import (
    ArtifactFormat,
    ArtifactKind,
    ArtifactRole,
    DesignPackage,
    MaterialSpec,
    PipelineArtifact,
    SectionSpec,
    StructuralElement,
)


class FreeCADHandoffBuilder:
    """Build a conservative FreeCAD-friendly payload from the analytical model."""

    def build(self, package: DesignPackage) -> Dict[str, Any]:
        analytical_model = package.analytical_model
        if analytical_model is None:
            raise ValueError("analytical_model must be present before FreeCAD handoff export")

        materials = {material.id: material for material in analytical_model.materials}
        sections = {section.id: section for section in analytical_model.sections}
        objects: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []

        for element in analytical_model.elements:
            payload = self._object_from_element(element, sections, materials)
            if payload is None:
                skipped.append({"id": element.id, "kind": element.kind, "reason": "unsupported_geometry"})
                continue
            objects.append(payload)

        return {
            "schema_version": "1.0",
            "generator": "bonsai_ai.freecad_handoff",
            "units": analytical_model.units,
            "summary": analytical_model.metadata.get("summary") or "",
            "assumptions": list(analytical_model.metadata.get("assumptions") or []),
            "analysis_domains": list(analytical_model.metadata.get("analysis_domains") or []),
            "solver": package.analysis_request.solver if package.analysis_request else None,
            "design_codes": list(package.analysis_request.design_codes) if package.analysis_request else [],
            "materials": [self._material_payload(material) for material in analytical_model.materials],
            "sections": [self._section_payload(section) for section in analytical_model.sections],
            "objects": objects,
            "load_cases": [self._load_case_payload(load_case) for load_case in analytical_model.load_cases],
            "load_combinations": [self._load_combination_payload(combo) for combo in analytical_model.load_combinations],
            "metadata": {
                "object_count": len(objects),
                "skipped_elements": skipped,
                "intended_use": "FreeCAD engineering handoff and model reconstruction",
            },
        }

    @staticmethod
    def write_json(path: str | Path, payload: Dict[str, Any]) -> None:
        Path(path).write_text(json.dumps(payload, indent=2))

    @staticmethod
    def write_macro(path: str | Path, *, handoff_filename: str = "freecad_handoff.json") -> None:
        Path(path).write_text(render_freecad_handoff_script(handoff_filename=handoff_filename))

    def _object_from_element(
        self,
        element: StructuralElement,
        sections: Dict[str, SectionSpec],
        materials: Dict[str, MaterialSpec],
    ) -> Dict[str, Any] | None:
        section = sections.get(element.section_id or "")
        material = materials.get(section.material_id) if section else None
        payload = self._box_payload(element)
        if payload is None:
            return None
        payload["section"] = self._section_payload(section) if section else None
        payload["material"] = self._material_payload(material) if material else None
        payload["storey"] = element.storey
        payload["source"] = dict(element.metadata)
        return payload

    def _box_payload(self, element: StructuralElement) -> Dict[str, Any] | None:
        geometry = element.geometry
        rotation_deg = float(element.orientation.get("rotation_deg") or 0.0)

        if element.kind == "wall" and {"start", "end", "height", "thickness"}.issubset(geometry):
            start = [float(value) for value in geometry["start"]]
            end = [float(value) for value in geometry["end"]]
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length <= 0:
                return None
            return self._base_payload(
                element=element,
                base=start,
                dimensions={"length": length, "width": float(geometry["thickness"]), "height": float(geometry["height"])},
                rotation_deg=rotation_deg if rotation_deg else math.degrees(math.atan2(dy, dx)),
            )

        if element.kind == "beam" and {"start", "end", "width", "depth"}.issubset(geometry):
            start = [float(value) for value in geometry["start"]]
            end = [float(value) for value in geometry["end"]]
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length <= 0:
                return None
            return self._base_payload(
                element=element,
                base=start,
                dimensions={"length": length, "width": float(geometry["width"]), "height": float(geometry["depth"])},
                rotation_deg=rotation_deg if rotation_deg else math.degrees(math.atan2(dy, dx)),
            )

        if element.kind == "column" and {"origin", "width", "depth", "height"}.issubset(geometry):
            return self._base_payload(
                element=element,
                base=[float(value) for value in geometry["origin"]],
                dimensions={
                    "length": float(geometry["width"]),
                    "width": float(geometry["depth"]),
                    "height": float(geometry["height"]),
                },
                rotation_deg=rotation_deg,
            )

        if element.kind == "beam" and {"start", "end", "width", "depth"}.issubset(geometry):
            start = [float(value) for value in geometry["start"]]
            end = [float(value) for value in geometry["end"]]
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            dz = end[2] - start[2]
            length = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
            if length <= 0:
                return None
            axis, angle = self._axis_angle_from_x_axis([dx, dy, dz])
            return self._base_payload(
                element=element,
                base=start,
                dimensions={
                    "length": length,
                    "width": float(geometry["width"]),
                    "height": float(geometry["depth"]),
                },
                rotation_axis=axis,
                rotation_deg=angle,
            )

        if element.kind in {"panel", "foundation"} and {"origin", "length", "width", "thickness"}.issubset(geometry):
            return self._base_payload(
                element=element,
                base=[float(value) for value in geometry["origin"]],
                dimensions={
                    "length": float(geometry["length"]),
                    "width": float(geometry["width"]),
                    "height": float(geometry["thickness"]),
                },
                rotation_deg=rotation_deg,
            )

        if element.kind == "panel" and {"origin", "width", "height", "thickness"}.issubset(geometry):
            return self._base_payload(
                element=element,
                base=[float(value) for value in geometry["origin"]],
                dimensions={
                    "length": float(geometry["width"]),
                    "width": float(geometry["thickness"]),
                    "height": float(geometry["height"]),
                },
                rotation_deg=rotation_deg,
            )

        return None

    @staticmethod
    def _base_payload(
        *,
        element: StructuralElement,
        base: List[float],
        dimensions: Dict[str, float],
        rotation_axis: List[float] | None = None,
        rotation_deg: float,
    ) -> Dict[str, Any]:
        return {
            "id": element.id,
            "label": element.metadata.get("source_name") or element.id,
            "kind": element.kind,
            "primitive": "Part::Box",
            "placement": {
                "base": base,
                "rotation_axis": rotation_axis or [0.0, 0.0, 1.0],
                "rotation_deg": rotation_deg,
            },
            "dimensions": dimensions,
        }

    @staticmethod
    def _axis_angle_from_x_axis(direction: List[float]) -> tuple[List[float], float]:
        length = math.sqrt(sum(value * value for value in direction))
        if length <= 1e-9:
            return ([0.0, 0.0, 1.0], 0.0)
        unit = [value / length for value in direction]
        dot = max(-1.0, min(1.0, unit[0]))
        angle = math.degrees(math.acos(dot))
        axis = [0.0, -unit[2], unit[1]]
        axis_length = math.sqrt(sum(value * value for value in axis))
        if axis_length <= 1e-9:
            return ([0.0, 0.0, 1.0], 0.0 if unit[0] >= 0 else 180.0)
        return ([value / axis_length for value in axis], angle)

    @staticmethod
    def _material_payload(material: MaterialSpec) -> Dict[str, Any]:
        return {
            "id": material.id,
            "family": material.family,
            "model": material.model,
            "properties": dict(material.properties),
        }

    @staticmethod
    def _section_payload(section: SectionSpec | None) -> Dict[str, Any] | None:
        if section is None:
            return None
        return {
            "id": section.id,
            "kind": section.kind,
            "material_id": section.material_id,
            "dimensions": dict(section.dimensions),
            "metadata": dict(section.metadata),
        }

    @staticmethod
    def _load_case_payload(load_case) -> Dict[str, Any]:
        return {
            "name": load_case.name,
            "domain": load_case.domain.value,
            "code_basis": load_case.code_basis,
            "category": load_case.category,
            "design_situation": load_case.design_situation,
            "parameters": dict(load_case.parameters),
            "actions": [
                {
                    "target_id": action.target_id,
                    "kind": action.kind,
                    "direction": action.direction,
                    "magnitude": action.magnitude,
                    "distribution": dict(action.distribution),
                    "metadata": dict(action.metadata),
                }
                for action in load_case.actions
            ],
        }

    @staticmethod
    def _load_combination_payload(combo) -> Dict[str, Any]:
        return {
            "name": combo.name,
            "category": combo.category,
            "code_basis": combo.code_basis,
            "case_factors": dict(combo.case_factors),
        }


class FreeCADHandoffExporter:
    """Emit automation-friendly FreeCAD handoff artifacts from the analytical model."""

    def export(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        if not package.analytical_model:
            raise ValueError("analytical_model must be present before FreeCAD handoff export")

        json_path = output_dir / "freecad_handoff.json"
        macro_path = output_dir / "freecad_handoff.py"
        payload = FreeCADHandoffBuilder().build(package)
        payload["source_files"] = {
            "analytical_model": "analytical_model.json",
            "solver_request": "solver_request.json",
        }
        FreeCADHandoffBuilder.write_json(json_path, payload)
        FreeCADHandoffBuilder.write_macro(macro_path, handoff_filename=json_path.name)
        return [
            PipelineArtifact(
                kind=ArtifactKind.ANALYTICAL_MODEL,
                format=ArtifactFormat.JSON,
                path=str(json_path),
                metadata={
                    "role": ArtifactRole.FREECAD_HANDOFF.value,
                    "label": "FreeCAD Handoff JSON",
                    "handoff_target": "freecad",
                },
            ),
            PipelineArtifact(
                kind=ArtifactKind.SOLVER_INPUT,
                format=ArtifactFormat.PY,
                path=str(macro_path),
                metadata={
                    "role": ArtifactRole.SOLVER_INPUT.value,
                    "label": "FreeCAD Handoff Script",
                    "handoff_target": "freecad",
                },
            ),
        ]


def render_freecad_handoff_script(*, handoff_filename: str = "freecad_handoff.json") -> str:
    return dedent(
        f"""\
        import json
        import os
        from pathlib import Path

        try:
            import FreeCAD
        except ImportError as exc:
            raise RuntimeError("Run this script inside FreeCAD.") from exc


        HANDOFF_PATH = Path(os.environ.get("BONSAI_FREECAD_HANDOFF") or Path(__file__).resolve().with_name({handoff_filename!r}))
        OUTPUT_DOCUMENT_PATH = Path(os.environ.get("BONSAI_FREECAD_OUTPUT") or HANDOFF_PATH.with_name("freecad_handoff.FCStd"))
        RESULT_PATH = Path(os.environ.get("BONSAI_FREECAD_RESULT") or HANDOFF_PATH.with_name("freecad_run_report.json"))


        def _vector(values):
            return FreeCAD.Vector(float(values[0]), float(values[1]), float(values[2]))


        def _rotation(placement):
            axis = placement.get("rotation_axis") or [0.0, 0.0, 1.0]
            return FreeCAD.Rotation(_vector(axis), float(placement.get("rotation_deg") or 0.0))


        def _add_box(document, item):
            dims = item["dimensions"]
            placement = item["placement"]
            obj = document.addObject("Part::Box", item["label"])
            obj.Length = float(dims["length"])
            obj.Width = float(dims["width"])
            obj.Height = float(dims["height"])
            obj.Placement = FreeCAD.Placement(_vector(placement["base"]), _rotation(placement))
            for prop_name, prop_value in {{
                "BonsaiId": item["id"],
                "BonsaiKind": item["kind"],
            }}.items():
                if not hasattr(obj, prop_name):
                    obj.addProperty("App::PropertyString", prop_name, "BonsaiAI")
                setattr(obj, prop_name, str(prop_value))
            return obj


        def build_document(handoff_path=HANDOFF_PATH):
            payload = json.loads(Path(handoff_path).read_text())
            document = FreeCAD.ActiveDocument or FreeCAD.newDocument("BonsaiAIHandoff")
            for item in payload.get("objects", []):
                if item.get("primitive") != "Part::Box":
                    continue
                _add_box(document, item)
            document.recompute()
            return document, payload


        def save_document(document, output_path=OUTPUT_DOCUMENT_PATH):
            document.saveAs(str(output_path))
            return output_path


        def write_result(payload, output_path=OUTPUT_DOCUMENT_PATH, result_path=RESULT_PATH, status="completed", error=None):
            result = {{
                "status": status,
                "handoff_path": str(HANDOFF_PATH),
                "output_document": str(output_path),
                "object_count": len(payload.get("objects", [])),
            }}
            if error:
                result["error"] = str(error)
            Path(result_path).write_text(json.dumps(result, indent=2))
            return result


        def main():
            try:
                document, payload = build_document()
                save_document(document)
                write_result(payload)
            except Exception as exc:
                fallback_payload = {{"objects": []}}
                if HANDOFF_PATH.exists():
                    fallback_payload = json.loads(HANDOFF_PATH.read_text())
                write_result(fallback_payload, status="failed", error=exc)
                raise


        if __name__ == "__main__" or __name__ == Path(__file__).stem:
            main()
        """
    )
