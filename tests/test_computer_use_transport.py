import tempfile
import unittest
from pathlib import Path

from openwukong.control.computer_use_transport import (
    build_computer_use_runtime_probe,
    build_computer_use_static_probe,
)


class ComputerUseTransportTests(unittest.TestCase):
    def test_static_probe_reports_plugin_present_but_native_pipe_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "scripts" / "computer-use-client.mjs"
            script.parent.mkdir(parents=True)
            script.write_text("export {}", encoding="utf-8")

            report = build_computer_use_static_probe(
                plugin_root=root,
                env={},
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "computer-use-static-probe")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["ready"])
        self.assertTrue(data["plugin_installed"])
        self.assertFalse(data["native_pipe_ready"])
        self.assertFalse(data["native_pipe_configured"])
        self.assertEqual(data["decision"], "native_pipe_unavailable")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["computer_use_attempts"], 0)
        self.assertTrue(data["input_actions_activate_window"])

    def test_static_probe_reports_missing_plugin_entrypoint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = build_computer_use_static_probe(
                plugin_root=root,
                env={"SKY_CUA_NATIVE_PIPE_DIRECTORY": "C:/tmp/pipe"},
            )
            data = report.to_dict()

        self.assertFalse(data["ready"])
        self.assertFalse(data["plugin_installed"])
        self.assertEqual(data["decision"], "computer_use_client_missing")
        self.assertIn("computer-use-client.mjs", data["client_script_path"])

    def test_static_probe_discovers_versioned_client_directory_from_explicit_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            older = root / "26.527.31326" / "scripts" / "computer-use-client.mjs"
            newer = root / "26.602.30954" / "scripts" / "computer-use-client.mjs"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("export {}", encoding="utf-8")
            newer.write_text("export {}", encoding="utf-8")

            report = build_computer_use_static_probe(
                plugin_root=root,
                env={},
            )
            data = report.to_dict()

        self.assertTrue(data["plugin_installed"])
        self.assertTrue(data["client_script_path"].endswith("computer-use-client.mjs"))
        self.assertIn("26.602.30954", data["plugin_root"])
        self.assertEqual(data["decision"], "native_pipe_unavailable")

    def test_runtime_probe_records_read_only_window_state_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "scripts" / "computer-use-client.mjs"
            script.parent.mkdir(parents=True)
            script.write_text("export {}", encoding="utf-8")

            def runtime_probe(static_probe):
                self.assertTrue(static_probe["plugin_installed"])
                self.assertTrue(static_probe["native_pipe_configured"])
                return {
                    "ok": True,
                    "list_apps_attempts": 1,
                    "list_apps_ready": True,
                    "window_state_attempts": 1,
                    "window_state_ready": True,
                    "background_snapshot_ready": True,
                    "accessibility_tree_available": True,
                    "observed_app_count": 12,
                    "observed_window_count": 3,
                    "screenshot_count": 1,
                    "computer_use_attempts": 2,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "foreground_activation_attempts": 0,
                }

            report = build_computer_use_runtime_probe(
                plugin_root=root,
                env={"SKY_CUA_NATIVE_PIPE_DIRECTORY": "C:/tmp/pipe"},
                runtime_probe_runner=runtime_probe,
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "computer-use-runtime-probe")
        self.assertTrue(data["ready"])
        self.assertTrue(data["native_pipe_ready"])
        self.assertTrue(data["list_apps_ready"])
        self.assertTrue(data["window_state_ready"])
        self.assertTrue(data["background_snapshot_ready"])
        self.assertEqual(data["decision"], "computer_use_read_only_ready")
        self.assertEqual(data["computer_use_attempts"], 2)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["foreground_activation_attempts"], 0)
        self.assertEqual(data["observed_app_count"], 12)
        self.assertEqual(data["observed_window_count"], 3)

    def test_runtime_probe_blocks_foreground_activation_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "scripts" / "computer-use-client.mjs"
            script.parent.mkdir(parents=True)
            script.write_text("export {}", encoding="utf-8")

            def runtime_probe(static_probe):
                del static_probe
                return {
                    "ok": True,
                    "list_apps_attempts": 1,
                    "list_apps_ready": True,
                    "window_state_attempts": 1,
                    "window_state_ready": True,
                    "background_snapshot_ready": True,
                    "computer_use_attempts": 2,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "foreground_activation_attempts": 1,
                }

            report = build_computer_use_runtime_probe(
                plugin_root=root,
                env={"SKY_CUA_NATIVE_PIPE_DIRECTORY": "C:/tmp/pipe"},
                runtime_probe_runner=runtime_probe,
            )
            data = report.to_dict()

        self.assertFalse(data["ready"])
        self.assertFalse(data["native_pipe_ready"])
        self.assertEqual(data["decision"], "computer_use_runtime_not_read_only")
        self.assertEqual(data["foreground_activation_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
