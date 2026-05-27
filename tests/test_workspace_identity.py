import os
import tempfile
import types
import unittest

from openwukong.supervisor.identity import WorkspaceIdentityModel


class WorkspaceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.model = WorkspaceIdentityModel()

    def test_workspace_for_goal_prefers_canonical_name_from_path(self):
        with tempfile.TemporaryDirectory(prefix="openwukong-identity-") as td:
            repo_dir = os.path.join(td, "openwukong")
            os.makedirs(repo_dir, exist_ok=True)
            goal = types.SimpleNamespace(
                task_id="task-1",
                task_name="测试任务",
                connector_hint="codex",
                window_match="悟空",
                matched_window_title="",
                workspace_path=repo_dir,
                resource_url="",
                status=types.SimpleNamespace(value="pending"),
            )

            workspace = self.model.workspace_for_goal(goal)

        self.assertTrue(workspace.workspace_id.startswith("workspace:openwukong:"))
        self.assertEqual(workspace.canonical_name, "openwukong")
        self.assertTrue(workspace.root_path.lower().endswith("openwukong"))

    def test_bind_workspace_state_to_goal_uses_workspace_identity(self):
        goal = types.SimpleNamespace(
            task_id="task-2",
            task_name="发送测试指令",
            connector_hint="codex",
            window_match="悟空",
            matched_window_title="",
            matched_pid=0,
            workspace_path="",
            resource_url="",
            status=types.SimpleNamespace(value="pending"),
        )
        matched_state = types.SimpleNamespace(
            pid=321,
            process_name="Codex.exe",
            project_name="openwukong",
            window_title="OpenWukong - Codex",
        )
        unrelated_state = types.SimpleNamespace(
            pid=322,
            process_name="Cursor.exe",
            project_name="otherrepo",
            window_title="main.py - otherrepo - Cursor",
        )

        state, session, score = self.model.bind_workspace_state_to_goal(
            goal,
            [unrelated_state, matched_state],
        )

        self.assertIs(state, matched_state)
        self.assertEqual(session.workspace_id, "workspace:openwukong")
        self.assertEqual(session.connector_id, "codex")
        self.assertGreaterEqual(score, 1000)

    def test_bind_workspace_state_prefers_exact_project_over_alias_substring(self):
        goal = types.SimpleNamespace(
            task_id="task-exact",
            task_name="Exact project match",
            connector_hint="codex",
            window_match="openwukong",
            matched_window_title="",
            matched_pid=0,
            workspace_path="",
            resource_url="",
            status=types.SimpleNamespace(value="pending"),
        )
        substring_state = types.SimpleNamespace(
            pid=700,
            process_name="Codex.exe",
            project_name="openwukong-archive",
            window_title="openwukong-archive - Codex",
        )
        exact_state = types.SimpleNamespace(
            pid=701,
            process_name="Codex.exe",
            project_name="openwukong",
            window_title="openwukong - Codex",
        )

        state, session, score = self.model.bind_workspace_state_to_goal(
            goal,
            [substring_state, exact_state],
        )

        self.assertIs(state, exact_state)
        self.assertEqual(session.project_name, "openwukong")
        self.assertGreaterEqual(score, 1100)

    def test_known_root_is_reused_for_pathless_state(self):
        with tempfile.TemporaryDirectory(prefix="openwukong-registry-") as td:
            repo_dir = os.path.join(td, "openwukong")
            os.makedirs(repo_dir, exist_ok=True)
            self.model.register_workspace_root("openwukong", repo_dir)

            state = types.SimpleNamespace(
                pid=777,
                process_name="Codex.exe",
                project_name="openwukong",
                window_title="OpenWukong - Codex",
            )

            workspace = self.model.workspace_for_state(state)

        self.assertEqual(workspace.root_path, os.path.abspath(repo_dir))
        self.assertTrue(workspace.workspace_id.startswith("workspace:openwukong:"))

    def test_file_path_is_raised_to_workspace_root_when_marker_exists(self):
        with tempfile.TemporaryDirectory(prefix="openwukong-root-") as td:
            repo_dir = os.path.join(td, "openwukong")
            nested_dir = os.path.join(repo_dir, "src", "openwukong")
            os.makedirs(nested_dir, exist_ok=True)
            os.makedirs(os.path.join(repo_dir, ".git"), exist_ok=True)
            file_path = os.path.join(nested_dir, "main.py")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write("print('ok')\n")

            workspace = self.model.resolve_workspace(
                workspace_path=file_path,
                name_hint="openwukong",
            )

        self.assertEqual(workspace.root_path, os.path.abspath(repo_dir))
        self.assertTrue(workspace.workspace_id.startswith("workspace:openwukong:"))

    def test_build_snapshot_aggregates_workspaces_sessions_tasks_actions(self):
        goal = types.SimpleNamespace(
            task_id="task-3",
            task_name="Git检查",
            connector_hint="git",
            window_match="openwukong",
            matched_window_title="",
            workspace_path=".",
            resource_url="",
            status=types.SimpleNamespace(value="running"),
        )
        state = types.SimpleNamespace(
            pid=654,
            process_name="Codex.exe",
            project_name="openwukong",
            window_title="OpenWukong - Codex",
        )
        workspace = self.model.workspace_for_goal(goal)
        action = self.model.create_action_record(
            task_id="task-3",
            workspace_id=workspace.workspace_id,
            session_id="session:test",
            connector_id="git",
            action_type="send_message",
            status="ok",
            detail="git status --short --branch",
        )

        snapshot = self.model.build_snapshot([goal], [state], [action])

        self.assertEqual(len(snapshot.workspaces), 1)
        self.assertTrue(snapshot.workspaces[0].workspace_id.startswith("workspace:openwukong:"))
        self.assertEqual(len(snapshot.sessions), 1)
        self.assertEqual(snapshot.sessions[0].workspace_id, snapshot.workspaces[0].workspace_id)
        self.assertEqual(len(snapshot.tasks), 1)
        self.assertEqual(snapshot.tasks[0].workspace_id, snapshot.workspaces[0].workspace_id)
        self.assertEqual(len(snapshot.actions), 1)
        self.assertEqual(snapshot.actions[0].action_id, action.action_id)


if __name__ == "__main__":
    unittest.main()
