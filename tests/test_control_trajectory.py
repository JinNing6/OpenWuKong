import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.trajectory import (
    ControlTrajectoryRecorder,
    build_trajectory_artifact,
    extract_trajectory_artifacts,
)


class ControlTrajectoryTests(unittest.TestCase):
    def test_recorder_writes_manifest_and_step_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ControlTrajectoryRecorder(
                tmp,
                trajectory_id="traj-test",
                scenario="no-foreground-smoke",
                target_id="chrome:devtools",
                metadata={"suite": "focused"},
            )

            recorder.record_step(
                phase="dispatch",
                action="read_page",
                report={
                    "mode": "control-fabric-dispatch-plan",
                    "control_attempts": 0,
                    "decision": "dispatch_connector",
                },
            )
            recorder.record_step(
                phase="execute",
                action="read_page",
                report={
                    "mode": "connector-action",
                    "control_attempts": 1,
                    "ok": True,
                },
            )

            root = Path(tmp) / "traj-test"
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            step_files = sorted((root / "steps").glob("*.json"))

        self.assertEqual(manifest["mode"], "control-trajectory")
        self.assertEqual(manifest["schema_version"], "control-trajectory-v1")
        self.assertEqual(manifest["scenario"], "no-foreground-smoke")
        self.assertEqual(manifest["target_id"], "chrome:devtools")
        self.assertEqual(manifest["metadata"], {"suite": "focused"})
        self.assertEqual(manifest["step_count"], 2)
        self.assertEqual(manifest["control_attempts"], 1)
        self.assertEqual(len(step_files), 2)

    def test_artifact_builder_hashes_existing_file_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "post.json"
            path.write_text("{}", encoding="utf-8")

            artifact = build_trajectory_artifact(
                path,
                role="post_action_state",
                media_type="application/json",
                compute_hash=True,
            ).to_dict()

        self.assertEqual(artifact["role"], "post_action_state")
        self.assertEqual(artifact["media_type"], "application/json")
        self.assertEqual(len(artifact["sha256"]), 64)
        self.assertTrue(artifact["artifact_id"].startswith("artifact-"))

    def test_extracts_existing_nested_artifact_paths_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "background.png"
            state = root / "state.json"
            profile_dir = root / "profile"
            missing = root / "missing.json"
            screenshot.write_bytes(b"fake png")
            state.write_text("{}", encoding="utf-8")
            profile_dir.mkdir()

            artifacts = extract_trajectory_artifacts(
                {
                    "profile_path": str(profile_dir),
                    "background_screenshots": [
                        {
                            "ok": True,
                            "output_path": str(screenshot),
                        }
                    ],
                    "app_state": {
                        "artifact_path": str(state),
                    },
                    "post_action": {
                        "report_path": str(missing),
                    },
                }
            )

        by_role = {artifact.role: artifact.to_dict() for artifact in artifacts}
        self.assertEqual(
            set(by_role),
            {
                "background_screenshots_output_path",
                "app_state_artifact_path",
            },
        )
        self.assertEqual(
            by_role["background_screenshots_output_path"]["media_type"],
            "image/png",
        )
        self.assertEqual(
            by_role["app_state_artifact_path"]["media_type"],
            "application/json",
        )
        self.assertEqual(
            len(by_role["background_screenshots_output_path"]["sha256"]),
            64,
        )


if __name__ == "__main__":
    unittest.main()
