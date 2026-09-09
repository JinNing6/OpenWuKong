import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.cursor_transcript_readback import (
    run_cursor_composer_state_discovery,
    run_cursor_transcript_readback,
)


class CursorTranscriptReadbackTests(unittest.TestCase):
    def test_accepts_required_marker_from_cursor_global_bubble_for_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="composer-1",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={
                    "bubbleId:composer-1:bubble-1": {
                        "type": 2,
                        "text": "done OPENWUKONG_CURSOR_ACCEPTANCE: PASS",
                        "richText": "",
                    }
                },
            )

            report = run_cursor_transcript_readback(
                user_data_root=user_data,
                workspace_path=workspace,
                required_markers=("OPENWUKONG_CURSOR_ACCEPTANCE: PASS",),
            ).to_dict()

        self.assertEqual(report["decision"], "cursor_transcript_readback_accepted")
        self.assertTrue(report["ok"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["bridge_send_attempts"], 0)
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])
        self.assertEqual(report["missing_required_markers"], [])
        self.assertEqual(
            report["required_markers_found"],
            ["OPENWUKONG_CURSOR_ACCEPTANCE: PASS"],
        )
        self.assertEqual(
            report["required_markers_found_anywhere"],
            ["OPENWUKONG_CURSOR_ACCEPTANCE: PASS"],
        )
        self.assertEqual(report["response_marker_locations"][0]["role"], "assistant")
        self.assertIn("OPENWUKONG_CURSOR_ACCEPTANCE: PASS", report["readback_text"])

    def test_rejects_required_marker_from_user_echo_and_blob_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="composer-1",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={
                    "bubbleId:composer-1:bubble-1": {
                        "type": 1,
                        "text": "please echo OPENWUKONG_CURSOR_ACCEPTANCE: PASS",
                    },
                    "agentKv:blob:blob-1": {
                        "content": "prompt contains OPENWUKONG_CURSOR_ACCEPTANCE: PASS",
                    },
                },
            )

            report = run_cursor_transcript_readback(
                user_data_root=user_data,
                workspace_path=workspace,
                required_markers=("OPENWUKONG_CURSOR_ACCEPTANCE: PASS",),
            ).to_dict()

        self.assertEqual(
            report["decision"],
            "cursor_transcript_readback_non_response_marker_only",
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["required_markers_found"], [])
        self.assertEqual(
            report["required_markers_found_anywhere"],
            ["OPENWUKONG_CURSOR_ACCEPTANCE: PASS"],
        )
        self.assertEqual(
            report["missing_required_markers"],
            ["OPENWUKONG_CURSOR_ACCEPTANCE: PASS"],
        )
        self.assertEqual(report["response_marker_locations"], [])
        self.assertEqual(report["non_response_marker_locations"][0]["role"], "user")

    def test_discovers_cursor_composer_state_surfaces_for_hook_planning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="composer-1",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={
                    "composerData:composer-1": {"composerId": "composer-1"},
                    "bubbleId:composer-1:bubble-1": {
                        "type": 2,
                        "text": "done OPENWUKONG_CURSOR_ACCEPTANCE: PASS"
                    },
                    "messageRequestContext:composer-1:req-1": {
                        "message": "OPENWUKONG_CURSOR_ACCEPTANCE: PASS"
                    },
                    "checkpointId:composer-1:checkpoint-1": {"status": "ok"},
                    "agentKv:blob:blob-1": {
                        "content": "OPENWUKONG_CURSOR_ACCEPTANCE: PASS"
                    },
                    "bubbleId:unrelated:bubble-9": {"text": "ignore me"},
                },
            )

            report = run_cursor_composer_state_discovery(
                user_data_root=user_data,
                workspace_path=workspace,
                required_markers=("OPENWUKONG_CURSOR_ACCEPTANCE: PASS",),
            ).to_dict()

        self.assertEqual(report["decision"], "cursor_composer_state_surfaces_found")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["bridge_send_attempts"], 0)
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])
        self.assertEqual(report["key_family_counts"]["composerData"], 1)
        self.assertEqual(report["key_family_counts"]["bubbleId"], 1)
        self.assertEqual(report["key_family_counts"]["messageRequestContext"], 1)
        self.assertEqual(report["key_family_counts"]["checkpointId"], 1)
        self.assertEqual(report["key_family_counts"]["agentKv_blob_matching_marker"], 1)
        self.assertEqual(report["marker_locations"][0]["family"], "bubbleId")
        self.assertIn("cursor_extension_native_hook", report["hook_candidates"])

    def test_discovers_when_selected_composer_has_no_transcript_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="composer-1",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={"bubbleId:other-composer:bubble-1": {"text": "other"}},
            )

            report = run_cursor_composer_state_discovery(
                user_data_root=user_data,
                workspace_path=workspace,
            ).to_dict()

        self.assertEqual(report["decision"], "cursor_composer_state_rows_missing")
        self.assertEqual(report["key_family_counts"]["bubbleId"], 0)
        self.assertEqual(report["hook_candidates"], [])
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])

    def test_reports_pending_when_workspace_exists_but_required_marker_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="composer-1",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={
                    "bubbleId:composer-1:bubble-1": {
                        "text": "still thinking",
                        "richText": "",
                    }
                },
            )

            report = run_cursor_transcript_readback(
                user_data_root=user_data,
                workspace_path=workspace,
                required_markers=("OPENWUKONG_CURSOR_ACCEPTANCE: PASS",),
            ).to_dict()

        self.assertEqual(report["decision"], "cursor_transcript_readback_pending")
        self.assertFalse(report["ok"])
        self.assertEqual(
            report["missing_required_markers"],
            ["OPENWUKONG_CURSOR_ACCEPTANCE: PASS"],
        )
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)

    def test_can_scan_extra_composer_id_from_live_bridge_getter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "openwukong"
            workspace.mkdir(parents=True)
            user_data = root / "Cursor" / "User"
            workspace_store = user_data / "workspaceStorage" / "abc123"
            workspace_store.mkdir(parents=True)
            (workspace_store / "workspace.json").write_text(
                json.dumps({"folder": workspace.as_uri()}),
                encoding="utf-8",
            )
            _create_workspace_state_db(
                workspace_store / "state.vscdb",
                composer_id="workspace-composer",
            )
            _create_global_state_db(
                user_data / "globalStorage" / "state.vscdb",
                rows={
                    "bubbleId:live-composer:bubble-1": {
                        "type": 2,
                        "text": "done OPENWUKONG_CURSOR_LIVE_COMPOSER: PASS"
                    }
                },
            )

            report = run_cursor_transcript_readback(
                user_data_root=user_data,
                workspace_path=workspace,
                required_markers=("OPENWUKONG_CURSOR_LIVE_COMPOSER: PASS",),
                extra_composer_ids=("live-composer",),
            ).to_dict()

        self.assertEqual(report["decision"], "cursor_transcript_readback_accepted")
        self.assertEqual(report["selected_composer_ids"], ["workspace-composer"])
        self.assertEqual(report["scanned_composer_ids"], ["workspace-composer", "live-composer"])
        self.assertIn(
            "bubbleId:live-composer:bubble-1",
            report["scanned_keys"],
        )


def _create_workspace_state_db(path: Path, *, composer_id: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            (
                "composer.composerData",
                json.dumps(
                    {
                        "selectedComposerIds": {"openwukong": composer_id},
                        "lastFocusedComposerId": composer_id,
                    }
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _create_global_state_db(path: Path, *, rows: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in rows.items():
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()
