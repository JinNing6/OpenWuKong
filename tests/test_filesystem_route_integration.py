import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.filesystem import FileSystemConnector
from openwukong.connectors.registry import ConnectorManager
from openwukong.connectors.route_policy import build_control_route_plan
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.connectors.base import ConnectorTarget


class FileSystemRouteIntegrationTests(unittest.TestCase):
    def test_explorer_route_prefers_workspace_filesystem_connector(self):
        target = ConnectorTarget(
            process_name="explorer.exe",
            window_title="文件资源管理器",
        )
        plan = build_control_route_plan(target)
        self.assertEqual(plan.primary_route.route_id, "filesystem-native")

    def test_fabric_dispatches_filesystem_connector_for_bound_workspace(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            target = ConnectorTarget(
                process_name="explorer.exe",
                window_title="文件资源管理器",
                workspace_path=str(root),
            )
            fabric = ControlFabric(
                connector_manager=ConnectorManager([FileSystemConnector()]),
                require_connector_session_ready=True,
            )
            report = fabric.dispatch(target, ControlIntent(action="file.list"))

        data = report.to_dict()
        self.assertEqual(data["decision"], "dispatch_connector")
        self.assertEqual(data["selected_route"], "filesystem-native")
        self.assertEqual(data["selected_connector_id"], "filesystem")
        self.assertTrue(data["connector_ready"])
        self.assertTrue(data["background_safe"])
        self.assertFalse(data["foreground_required"])


if __name__ == "__main__":
    unittest.main()
