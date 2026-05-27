import unittest

from openwukong.monitor.ai_monitor import (
    _extract_project_name,
    _is_supported_workspace_process,
)


class AIMonitorHelperTests(unittest.TestCase):
    def test_codex_process_is_supported(self):
        self.assertTrue(_is_supported_workspace_process("Codex.exe"))

    def test_browser_processes_are_supported_for_shadow_scan(self):
        self.assertTrue(_is_supported_workspace_process("chrome.exe"))
        self.assertTrue(_is_supported_workspace_process("msedge.exe"))
        self.assertTrue(_is_supported_workspace_process("firefox.exe"))

    def test_extract_project_name_from_codex_style_title(self):
        self.assertEqual(_extract_project_name("openwukong - Codex"), "openwukong")

    def test_extract_project_name_from_browser_title(self):
        self.assertEqual(
            _extract_project_name("local-browser-fixture - Google Chrome"),
            "local-browser-fixture",
        )

    def test_extract_project_name_from_brand_style_title(self):
        self.assertEqual(
            _extract_project_name("OpenWukong - 悟空 · WuKong"),
            "OpenWukong",
        )


if __name__ == "__main__":
    unittest.main()
