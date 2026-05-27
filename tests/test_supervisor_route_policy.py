import unittest

from openwukong.connectors import (
    ConnectorActionResult,
    ConnectorManager,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.supervisor.agent_supervisor import AgentSupervisor, TaskGoal


class _RecordingConnector(SessionConnector):
    connector_id = "uia-ide"
    display_name = "Recording UIA"

    def __init__(self):
        self.sent_messages = []

    def supports_target(self, target: ConnectorTarget) -> bool:
        return bool(target.pid)

    def read_conversation(self, target: ConnectorTarget) -> str:
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        self.sent_messages.append((target, message, cooldown))
        return ConnectorActionResult(
            success=True,
            connector_id=self.connector_id,
            action="send_message",
            action_key="sent",
        )


class SupervisorRoutePolicyTests(unittest.TestCase):
    def test_real_steer_blocks_route_policy_before_connector_send(self):
        goal = TaskGoal(
            window_match="微信",
            task_name="Blocked Weixin steer",
            goal="Do not steer without deterministic app route.",
            success_keywords=[],
            failure_keywords=[],
            retry_command="continue",
            connector_hint="uia-ide",
        )
        connector = _RecordingConnector()
        supervisor = AgentSupervisor([goal])
        supervisor.connector_manager = ConnectorManager([connector])
        target = ConnectorTarget(
            pid=58756,
            process_name="Weixin.exe",
            window_title="微信",
            project_name="微信",
        )

        supervisor._steer(goal, target, dry_run=False, steer_content="continue")

        self.assertEqual(connector.sent_messages, [])
        self.assertEqual(goal.retry_count, 0)
        self.assertEqual(supervisor._total_steers, 0)
        self.assertTrue(
            any("route_policy_blocked" in event["detail"] for event in goal.lifecycle)
        )


if __name__ == "__main__":
    unittest.main()
