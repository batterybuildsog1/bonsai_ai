from bonsai_ai_bridge.schemas import BuildingPlan, parse_plan_text, validate_plan


def test_parse_plain_json_plan() -> None:
    plan = parse_plan_text(
        """
        {
          "summary": "Create one wall",
          "assumptions": [],
          "actions": [
            {
              "kind": "create_wall",
              "name": "Wall A",
              "params": {
                "x": 0,
                "y": 0,
                "z": 0,
                "length": 4,
                "thickness": 0.2,
                "height": 3
              }
            }
          ]
        }
        """
    )
    assert isinstance(plan, BuildingPlan)
    assert plan.actions[0].kind == "create_wall"


def test_validate_numeric_coercion() -> None:
    plan = BuildingPlan.model_validate(
        {
            "summary": "Curtain wall",
            "assumptions": [],
            "actions": [
                {
                    "kind": "create_panel_grid",
                    "params": {
                        "x": "0",
                        "y": "0",
                        "z": "0",
                        "panel_width": "1.5",
                        "panel_height": "3.0",
                        "thickness": "0.08",
                        "columns": "5",
                        "rows": "2",
                    },
                }
            ],
        }
    )
    normalized, issues = validate_plan(plan)
    assert not issues
    assert normalized.actions[0].params["columns"] == 5
    assert normalized.actions[0].params["panel_width"] == 1.5
