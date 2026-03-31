from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


ROLE_STYLE = {
    "primary_column": {"color": "#1f4f8a", "alpha": 0.95},
    "gravity_column": {"color": "#4e83bf", "alpha": 0.85},
    "facade_post": {"color": "#1d8a85", "alpha": 0.45},
    "opening_column": {"color": "#cbd5e1", "alpha": 0.18},
    "brace": {"color": "#d22f2f", "alpha": 0.95},
    "roof_brace": {"color": "#d22f2f", "alpha": 0.95},
    "drag_collector": {"color": "#dd6b20", "alpha": 0.92},
    "roof_collector": {"color": "#e19b27", "alpha": 0.9},
    "roof_primary_frame": {"color": "#6b4a2a", "alpha": 0.9},
    "perimeter_spandrel": {"color": "#3d4754", "alpha": 0.88},
    "panel_joint_support": {"color": "#166170", "alpha": 0.88},
    "roof_edge_support": {"color": "#166170", "alpha": 0.88},
    "floor_girder": {"color": "#5b6472", "alpha": 0.5},
    "floor_beam": {"color": "#8c95a3", "alpha": 0.35},
    "window_header": {"color": "#d1d5db", "alpha": 0.15},
    "window_sill": {"color": "#d1d5db", "alpha": 0.12},
    "door_header": {"color": "#d1d5db", "alpha": 0.15},
    "default_beam": {"color": "#64748b", "alpha": 0.35},
}


def _load_plan(path: Path) -> dict:
    return json.loads(path.read_text())


def _column_role(name: str) -> str:
    lowered = name.lower()
    if "jamb" in lowered:
        return "opening_column"
    if "facade post" in lowered:
        return "facade_post"
    if any(token in lowered for token in ("corner_frame_column", "sidewall_frame_column", "endwall_column")):
        return "primary_column"
    if "interior_gravity_column" in lowered:
        return "gravity_column"
    return "gravity_column"


def _member_prism(start: np.ndarray, end: np.ndarray, width: float, depth: float) -> list[list[tuple[float, float, float]]]:
    direction = end - start
    length = np.linalg.norm(direction)
    if length <= 1e-9:
        return []
    z_axis = direction / length
    ref = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(z_axis, ref))) > 0.98:
        ref = np.array([0.0, 1.0, 0.0])
    x_axis = np.cross(ref, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    half_w = width / 2.0
    half_d = depth / 2.0
    offsets = [
        -half_w * x_axis - half_d * y_axis,
        half_w * x_axis - half_d * y_axis,
        half_w * x_axis + half_d * y_axis,
        -half_w * x_axis + half_d * y_axis,
    ]
    start_corners = [start + offset for offset in offsets]
    end_corners = [end + offset for offset in offsets]
    faces = [
        [tuple(start_corners[i]) for i in [0, 1, 2, 3]],
        [tuple(end_corners[i]) for i in [0, 1, 2, 3]],
        [tuple(start_corners[i]) for i in [0, 1]] + [tuple(end_corners[i]) for i in [1, 0]],
        [tuple(start_corners[i]) for i in [1, 2]] + [tuple(end_corners[i]) for i in [2, 1]],
        [tuple(start_corners[i]) for i in [2, 3]] + [tuple(end_corners[i]) for i in [3, 2]],
        [tuple(start_corners[i]) for i in [3, 0]] + [tuple(end_corners[i]) for i in [0, 3]],
    ]
    return faces


def _plot_plan(plan: dict, output_dir: Path, mode: str) -> None:
    actions = plan.get("actions", [])
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(12, 9), dpi=200)
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("#eef2f7")
    ax.set_facecolor("#eef2f7")

    def visible(role: str) -> bool:
        if mode == "primary_frame":
            return role in {
                "primary_column",
                "gravity_column",
                "brace",
                "roof_brace",
                "drag_collector",
                "roof_collector",
                "roof_primary_frame",
                "perimeter_spandrel",
                "panel_joint_support",
                "roof_edge_support",
            }
        if mode == "primary_columns":
            return role in {
                "primary_column",
                "gravity_column",
                "brace",
                "roof_brace",
                "roof_primary_frame",
                "drag_collector",
                "roof_collector",
            }
        return True

    for action in actions:
        if action.get("type") == "create_column":
            role = _column_role(str(action["name"]))
            if not visible(role):
                continue
            style = ROLE_STYLE[role]
            x = float(action["x"])
            y = float(action["y"])
            z = float(action["base_z"])
            height = float(action["height"])
            width = float(action["width"])
            depth = float(action["depth"])
            start = np.array([x, y, z], dtype=float)
            end = np.array([x, y, z + height], dtype=float)
            faces = _member_prism(start, end, width, depth)
        elif action.get("type") == "create_beam":
            role = str(action.get("member_role") or "default_beam")
            if not visible(role):
                continue
            style = ROLE_STYLE.get(role, ROLE_STYLE["default_beam"])
            start = np.array([float(action["x1"]), float(action["y1"]), float(action["base_z"])], dtype=float)
            end = np.array([
                float(action["x2"]),
                float(action["y2"]),
                float(action.get("end_z", action.get("z2", action["base_z"]))),
            ], dtype=float)
            faces = _member_prism(start, end, float(action["width"]), float(action["depth"]))
        else:
            continue

        if not faces:
            continue
        poly = Poly3DCollection(
            faces,
            facecolors=style["color"],
            edgecolors=style["color"],
            linewidths=0.25,
            alpha=style["alpha"],
        )
        ax.add_collection3d(poly)

    ax.view_init(elev=23, azim=-57)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title(f"Tech Ridge Structural Solids ({mode.replace('_', ' ').title()})")
    ax.grid(False)
    ax.set_box_aspect((29.5, 35.2, 22.5))
    plt.tight_layout()
    plt.savefig(output_dir / "iso.png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    ax.view_init(elev=14, azim=-90)
    plt.savefig(output_dir / "south_oblique.png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["primary_frame", "primary_columns"], default="primary_frame")
    args = parser.parse_args()

    plan = _load_plan(Path(args.plan).resolve())
    output_dir = Path(args.output_dir).resolve()
    _plot_plan(plan, output_dir, args.mode)
    print(json.dumps({"output_dir": str(output_dir), "mode": args.mode}, indent=2))


if __name__ == "__main__":
    main()
