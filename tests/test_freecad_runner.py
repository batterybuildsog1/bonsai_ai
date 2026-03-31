from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bonsai_ai.contracts import ArtifactFormat, ArtifactKind
from bonsai_ai.freecad_runner import detect_freecad_executable, run_freecad_handoff


class FreeCADRunnerTests(unittest.TestCase):
    def test_detect_freecad_executable_prefers_explicit_existing_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bonsai_freecad_detect_") as temp_dir:
            executable = Path(temp_dir) / "FreeCAD"
            executable.write_text("#!/bin/sh\n")

            detected = detect_freecad_executable(str(executable), candidates=())

            self.assertEqual(detected, str(executable))

    def test_run_freecad_handoff_writes_skip_report_when_freecad_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bonsai_freecad_runner_") as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "freecad_handoff.json").write_text(json.dumps({"objects": []}))
            (output_dir / "freecad_handoff.py").write_text("print('placeholder')")

            with mock.patch("bonsai_ai.freecad_runner.find_freecad_binary", return_value=None):
                artifacts = run_freecad_handoff(output_dir, executable="definitely-not-freecad")

            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].kind, ArtifactKind.ENGINEERING_REPORT)
            report = json.loads((output_dir / "freecad_run_report.json").read_text())
            self.assertEqual(report["status"], "skipped_missing_freecad")

    def test_run_freecad_handoff_returns_document_artifact_when_execution_succeeds(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bonsai_freecad_runner_") as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "freecad_handoff.json").write_text(json.dumps({"objects": []}))
            (output_dir / "freecad_handoff.py").write_text("print('placeholder')")
            document_path = output_dir / "freecad_handoff.FCStd"
            report_path = output_dir / "freecad_run_report.json"

            def fake_execute(**kwargs):
                document_path.write_text("fcstd")
                report_path.write_text(json.dumps({"status": "completed"}))
                return {"status": "completed"}

            with mock.patch("bonsai_ai.freecad_runner.find_freecad_binary", return_value="/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"):
                with mock.patch("bonsai_ai.freecad_runner._execute_freecad", side_effect=fake_execute):
                    artifacts = run_freecad_handoff(output_dir)

            self.assertEqual(len(artifacts), 2)
            self.assertEqual(artifacts[1].format, ArtifactFormat.FCSTD)


if __name__ == "__main__":
    unittest.main()
