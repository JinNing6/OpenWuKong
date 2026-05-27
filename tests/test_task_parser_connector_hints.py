import unittest

from openwukong.supervisor.task_parser import _apply_connector_defaults


class TaskParserConnectorHintTests(unittest.TestCase):
    def test_infers_codex_connector_from_user_input(self):
        tasks = [
            {
                "window_match": "openwukong",
                "task_name": "发送测试指令",
                "goal": "在项目中发送测试指令 1",
                "retry_command": "继续发送测试指令 1",
            }
        ]
        enriched = _apply_connector_defaults("帮我在 Codex 里的 openwukong 项目发送测试指令 1", tasks)
        self.assertEqual(enriched[0]["connector_hint"], "codex")

    def test_infers_browser_connector_and_resource_url(self):
        tasks = [
            {
                "window_match": "openwukong-browser",
                "task_name": "打开页面",
                "goal": "访问目标网页并返回摘要",
                "retry_command": "打开页面并读取内容",
            }
        ]
        enriched = _apply_connector_defaults("帮我在浏览器打开 https://example.com/docs 并看看内容", tasks)
        self.assertEqual(enriched[0]["connector_hint"], "browser")
        self.assertEqual(enriched[0]["resource_url"], "https://example.com/docs")

    def test_infers_terminal_connector_and_workspace_path(self):
        tasks = [
            {
                "window_match": "openwukong-terminal",
                "task_name": "运行测试",
                "goal": "在终端执行 pytest",
                "retry_command": "继续执行 pytest",
            }
        ]
        enriched = _apply_connector_defaults("帮我在终端里运行 pytest", tasks)
        self.assertEqual(enriched[0]["connector_hint"], "terminal")
        self.assertEqual(enriched[0]["workspace_path"], ".")


if __name__ == "__main__":
    unittest.main()
