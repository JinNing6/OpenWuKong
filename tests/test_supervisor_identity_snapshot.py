import unittest

from openwukong.supervisor.agent_supervisor import AgentSupervisor, TaskGoal


class SupervisorIdentitySnapshotTests(unittest.TestCase):
    def test_snapshot_exposes_identity_graph(self):
        goal = TaskGoal(
            window_match="悟空",
            task_name="发送测试指令",
            goal="在项目中发送测试指令 1",
            success_keywords=[],
            failure_keywords=[],
            retry_command="继续发送测试指令 1",
            connector_hint="codex",
        )

        supervisor = AgentSupervisor([goal])
        snapshot = supervisor.get_snapshot()

        self.assertEqual(snapshot["goals"][0]["workspace_id"], "workspace:openwukong")
        self.assertIn("identity", snapshot)
        self.assertEqual(snapshot["identity"]["tasks"][0]["workspace_id"], "workspace:openwukong")
        self.assertGreaterEqual(len(snapshot["identity"]["workspaces"]), 1)


if __name__ == "__main__":
    unittest.main()
