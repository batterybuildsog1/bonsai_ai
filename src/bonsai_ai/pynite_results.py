from __future__ import annotations

import math
from typing import Any, Iterable


_DISPLACEMENT_ATTRS = ("DX", "DY", "DZ")
_REACTION_ATTRS = {
    "fx": ("RxnFX", "RXN_FX"),
    "fy": ("RxnFY", "RXN_FY"),
    "fz": ("RxnFZ", "RXN_FZ"),
    "mx": ("RxnMX", "RXN_MX"),
    "my": ("RxnMY", "RXN_MY"),
    "mz": ("RxnMZ", "RXN_MZ"),
}


def summarize_results(model: Any, combo_names: Iterable[str], warnings: list[str]) -> dict[str, Any]:
    combos = list(combo_names)
    summary: dict[str, Any] = {
        "model_counts": {
            "nodes": len(getattr(model, "nodes", {}) or {}),
            "members": len(getattr(model, "members", {}) or {}),
            "plates": len(getattr(model, "plates", {}) or {}),
            "quads": len(getattr(model, "quads", {}) or {}),
        },
        "warnings": list(warnings),
    }

    max_displacement = _max_displacement(getattr(model, "nodes", {}) or {}, combos)
    if max_displacement is not None:
        summary["max_displacement"] = max_displacement

    support_reactions = _support_reactions(getattr(model, "nodes", {}) or {}, combos)
    if support_reactions:
        summary["support_reactions"] = support_reactions

    return summary


def _max_displacement(nodes: dict[str, Any], combo_names: list[str]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for combo_name in combo_names:
        for node_name, node in nodes.items():
            components = [_lookup_combo_value(node, attr, combo_name) for attr in _DISPLACEMENT_ATTRS]
            if any(value is None for value in components):
                continue
            dx, dy, dz = (float(value) for value in components if value is not None)
            magnitude = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
            if best is None or magnitude > float(best["magnitude"]):
                best = {
                    "combo": combo_name,
                    "node": node_name,
                    "components": {"dx": dx, "dy": dy, "dz": dz},
                    "magnitude": magnitude,
                }
    return best


def _support_reactions(nodes: dict[str, Any], combo_names: list[str]) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    for combo_name in combo_names:
        combo_total = {key: 0.0 for key in _REACTION_ATTRS}
        found = False
        for node in nodes.values():
            for key, candidates in _REACTION_ATTRS.items():
                value = _lookup_combo_value(node, candidates, combo_name)
                if value is None:
                    continue
                combo_total[key] += float(value)
                found = True
        if found:
            totals[combo_name] = combo_total
    return totals


def _lookup_combo_value(node: Any, attr_names: str | tuple[str, ...], combo_name: str) -> Any:
    names = (attr_names,) if isinstance(attr_names, str) else attr_names
    for attr_name in names:
        attr_value = getattr(node, attr_name, None)
        if isinstance(attr_value, dict) and combo_name in attr_value:
            return attr_value[combo_name]
        if attr_value is not None and not isinstance(attr_value, dict):
            return attr_value
    return None
