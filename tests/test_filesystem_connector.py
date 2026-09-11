import hashlib
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.filesystem import FileSystemConnector
from openwukong.control.fabric import ControlIntent


class FileSystemConnectorTests(unittest.TestCase):
    def make_target(self, root):
        return ConnectorTarget(
            process_name="explorer.exe",
            window_title="文件资源管理器",
            workspace_path=str(root),
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "alpha.txt").write_text("alpha", encoding="utf-8")
        (self.root / "docs" / "beta.md").write_text("beta", encoding="utf-8")
        self.connector = FileSystemConnector()

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_search_and_stat_stay_background_and_verify_state(self):
        target = self.make_target(self.root)
        listed = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.list",
                parameters={"path": "docs", "pattern": "*.txt"},
            ),
        )
        searched = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.search",
                parameters={"query": "alpha", "file_types": [".txt"]},
            ),
        )
        stat = self.connector.execute_action(
            target,
            ControlIntent(action="file.stat", parameters={"path": "docs/alpha.txt"}),
        )

        self.assertTrue(listed.success, listed.error)
        self.assertTrue(searched.success, searched.error)
        self.assertTrue(stat.success, stat.error)
        self.assertEqual(listed.payload["entries"][0]["name"], "alpha.txt")
        self.assertEqual(searched.payload["candidates"][0]["name"], "alpha.txt")
        self.assertEqual(stat.payload["metadata"]["size"], 5)
        self.assertEqual(listed.payload["control_attempts"], 0)
        self.assertEqual(searched.payload["window_input_attempts"], 0)

    def test_copy_move_and_rename_require_confirmation_and_verify_hash(self):
        target = self.make_target(self.root)
        source = self.root / "docs" / "alpha.txt"
        copied = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.copy",
                allow_submit=True,
                parameters={"source": "docs/alpha.txt", "destination": "copy.txt"},
            ),
        )
        moved = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.move",
                allow_submit=True,
                parameters={"source": "copy.txt", "destination": "moved.txt"},
            ),
        )
        renamed = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.rename",
                allow_submit=True,
                parameters={"path": "moved.txt", "new_name": "final.txt"},
            ),
        )

        expected_hash = hashlib.sha256(b"alpha").hexdigest()
        self.assertTrue(copied.success, copied.error)
        self.assertTrue(moved.success, moved.error)
        self.assertTrue(renamed.success, renamed.error)
        self.assertEqual(copied.payload["verification"]["sha256"], expected_hash)
        self.assertTrue((self.root / "final.txt").is_file())
        self.assertFalse((self.root / "moved.txt").exists())
        self.assertEqual(renamed.payload["control_attempts"], 1)

    def test_write_without_confirmation_is_blocked_before_filesystem_mutation(self):
        target = self.make_target(self.root)
        result = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.copy",
                parameters={"source": "docs/alpha.txt", "destination": "copy.txt"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "filesystem_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertFalse((self.root / "copy.txt").exists())

    def test_path_escape_and_overwrite_are_blocked(self):
        target = self.make_target(self.root)
        outside = self.root.parent / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        escaped = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.copy",
                allow_submit=True,
                parameters={"source": "../outside.txt", "destination": "copy.txt"},
            ),
        )
        (self.root / "copy.txt").write_text("existing", encoding="utf-8")
        overwrite = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.copy",
                allow_submit=True,
                parameters={"source": "docs/alpha.txt", "destination": "copy.txt"},
            ),
        )

        self.assertFalse(escaped.success)
        self.assertEqual(escaped.error, "filesystem_path_outside_root")
        self.assertFalse(overwrite.success)
        self.assertEqual(overwrite.error, "filesystem_destination_exists")
        self.assertEqual((self.root / "copy.txt").read_text(encoding="utf-8"), "existing")

    def test_delete_and_open_do_not_silently_perform_unsafe_actions(self):
        target = self.make_target(self.root)
        deleted = self.connector.execute_action(
            target,
            ControlIntent(
                action="file.delete",
                allow_submit=True,
                parameters={"path": "docs/alpha.txt"},
            ),
        )
        opened = self.connector.execute_action(
            target,
            ControlIntent(action="file.open", parameters={"path": "docs/alpha.txt"}),
        )

        self.assertFalse(deleted.success)
        self.assertEqual(deleted.error, "filesystem_delete_not_implemented")
        self.assertFalse(opened.success)
        self.assertEqual(opened.error, "filesystem_open_requires_foreground")
        self.assertTrue((self.root / "docs" / "alpha.txt").exists())


if __name__ == "__main__":
    unittest.main()
