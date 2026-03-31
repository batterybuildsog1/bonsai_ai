from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


ROLE_STYLES = {
    "column_primary": {"color": "#2b6cb0", "linewidth": 1.8, "alpha": 0.95, "zorder": 4},
    "column_facade": {"color": "#0f766e", "linewidth": 1.3, "alpha": 0.7, "zorder": 3},
    "column_opening": {"color": "#94a3b8", "linewidth": 0.9, "alpha": 0.35, "zorder": 1},
    "brace": {"color": "#c53030", "linewidth": 2.4, "alpha": 1.0, "zorder": 6},
    "roof_brace": {"color": "#c53030", "linewidth": 2.4, "alpha": 1.0, "zorder": 6},
    "collector": {"color": "#dd6b20", "linewidth": 2.1, "alpha": 0.95, "zorder": 5},
    "roof_primary_frame": {"color": "#4a5568", "linewidth": 2.0, "alpha": 0.95, "zorder": 4},
    "perimeter_spandrel": {"color": "#2d3748", "linewidth": 1.8, "alpha": 0.9, "zorder": 3},
    "panel_joint_support": {"color": "#0f766e", "linewidth": 1.9, "alpha": 0.9, "zorder": 4},
    "roof_edge_support": {"color": "#0f766e", "linewidth": 1.9, "alpha": 0.9, "zorder": 4},
    "floor_girder": {"color": "#4a5568", "linewidth": 1.7, "alpha": 0.85, "zorder": 3},
    "floor_beam": {"color": "#718096", "linewidth": 1.2, "alpha": 0.7, "zorder": 2},
    "window_header": {"color": "#6b7280", "linewidth": 1.1, "alpha": 0.7, "zorder": 1},
    "window_sill": {"color": "#9ca3af", "linewidth": 1.0, "alpha": 0.6, "zorder": 1},
    "door_header": {"color": "#6b7280", "linewidth": 1.2, "alpha": 0.75, "zorder": 1},
    "default_beam": {"color": "#4b5563", "linewidth": 1.3, "alpha": 0.75, "zorder": 2},
}


def _beam_style(action: dict) -> dict:
    role = str(action.get("member_role") or "default_beam")
    return ROLE_STYLES.get(role, ROLE_STYLES["default_beam"])


def _column_style(action: dict) -> dict:
    name = str(action.get("name") or "")
    if "Jamb" in name:
        return ROLE_STYLES["column_opening"]
    if "Facade Post" in name:
        return ROLE_STYLES["column_facade"]
    return ROLE_STYLES["column_primary"]


def _load_plan(path: Path) -> dict:
    return json.loads(path.read_text())


def _columns_and_beams(plan: dict) -> tuple[list[dict], list[dict]]:
    actions = plan.get("actions", [])
    columns = [action for action in actions if action.get("type") == "create_column"]
    beams = [action for action in actions if action.get("type") == "create_beam"]
    return columns, beams


def _beam_points(action: dict) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (
        (float(action["x1"]), float(action["y1"]), float(action["base_z"])),
        (
            float(action["x2"]),
            float(action["y2"]),
            float(action.get("end_z", action.get("base_z"))),
        ),
    )


def _column_points(action: dict) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (
        (float(action["x"]), float(action["y"]), float(action["base_z"])),
        (float(action["x"]), float(action["y"]), float(action["base_z"]) + float(action["height"])),
    )


def _plot_3d(columns: list[dict], beams: list[dict], output_path: Path) -> None:
    fig = plt.figure(figsize=(12, 9), dpi=180)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f8fafc")
    fig.patch.set_facecolor("#f8fafc")

    for action in beams:
        (x1, y1, z1), (x2, y2, z2) = _beam_points(action)
        style = _beam_style(action)
        ax.plot(
            [x1, x2],
            [y1, y2],
            [z1, z2],
            color=style["color"],
            linewidth=style["linewidth"],
            alpha=style["alpha"],
        )

    for action in columns:
        (x1, y1, z1), (x2, y2, z2) = _column_points(action)
        style = _column_style(action)
        ax.plot(
            [x1, x2],
            [y1, y2],
            [z1, z2],
            color=style["color"],
            linewidth=style["linewidth"],
            alpha=style["alpha"],
        )

    ax.view_init(elev=24, azim=-58)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title("Tech Ridge Structural Layout")
    ax.grid(False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def _plot_elevation(columns: list[dict], beams: list[dict], output_path: Path, axis: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 8), dpi=180)
    ax.set_facecolor("#f8fafc")
    fig.patch.set_facecolor("#f8fafc")

    if axis == "south":
        beam_filter = lambda action: abs(float(action["y1"])) < 1e-6 and abs(float(action["y2"])) < 1e-6
        col_filter = lambda action: abs(float(action["y"])) < 1e-6
        project = lambda point: (point[0], point[2])
        xlabel = "X (m)"
        title = "South Structural Elevation"
    elif axis == "east":
        max_x = max(float(action["x"]) for action in columns) if columns else 0.0
        beam_filter = lambda action: abs(float(action["x1"]) - max_x) < 1e-6 and abs(float(action["x2"]) - max_x) < 1e-6
        col_filter = lambda action: abs(float(action["x"]) - max_x) < 1e-6
        project = lambda point: (point[1], point[2])
        xlabel = "Y (m)"
        title = "East Structural Elevation"
    else:
        raise ValueError(f"Unsupported elevation axis: {axis}")

    for action in beams:
        if not beam_filter(action):
            continue
        p1, p2 = _beam_points(action)
        (u1, v1), (u2, v2) = project(p1), project(p2)
        style = _beam_style(action)
        ax.plot([u1, u2], [v1, v2], color=style["color"], linewidth=style["linewidth"], alpha=style["alpha"])

    for action in columns:
        if not col_filter(action):
            continue
        p1, p2 = _column_points(action)
        (u1, v1), (u2, v2) = project(p1), project(p2)
        style = _column_style(action)
        ax.plot([u1, u2], [v1, v2], color=style["color"], linewidth=style["linewidth"], alpha=style["alpha"])

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Z (m)")
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#cbd5e1", alpha=0.35)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    plan = _load_plan(Path(args.plan).resolve())
    output_dir = Path(args.output_dir).resolve()
    columns, beams = _columns_and_beams(plan)

    _plot_3d(columns, beams, output_dir / "structural_axon.png")
    _plot_elevation(columns, beams, output_dir / "south_elevation.png", axis="south")
    _plot_elevation(columns, beams, output_dir / "east_elevation.png", axis="east")

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "images": [
                    str(output_dir / "structural_axon.png"),
                    str(output_dir / "south_elevation.png"),
                    str(output_dir / "east_elevation.png"),
                ],
                "columns": len(columns),
                "beams": len(beams),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
