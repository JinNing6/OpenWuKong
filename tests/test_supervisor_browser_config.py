import json
import tempfile
import unittest
from pathlib import Path

from openwukong.supervisor.agent_supervisor import load_goals, save_example_config


class SupervisorBrowserConfigTests(unittest.TestCase):
    def test_save_example_config_includes_browser_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goals.json"
            save_example_config(str(path))

            data = json.loads(path.read_text(encoding="utf-8"))
            browser_goal = next(
                item for item in data["goals"] if item.get("connector_hint") == "browser"
            )

            self.assertEqual(browser_goal["resource_url"], "http://127.0.0.1:8000/")
            self.assertEqual(browser_goal["workspace_path"], ".")

    def test_load_goals_preserves_browser_fields(self):
        config = {
            "goals": [
                {
                    "window_match": "openwukong-browser",
                    "task_name": "Browser 基线导航",
                    "goal": "访问页面并返回信息",
                    "retry_command": "GET http://127.0.0.1:8000/",
                    "connector_hint": "browser",
                    "workspace_path": ".",
                    "resource_url": "http://127.0.0.1:8000/",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goals.json"
            path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

            goals = load_goals(str(path))

        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].connector_hint, "browser")
        self.assertEqual(goals[0].workspace_path, ".")
        self.assertEqual(goals[0].resource_url, "http://127.0.0.1:8000/")


if __name__ == "__main__":
    unittest.main()
