import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.cursor_bundle_composer_hooks import (
    analyze_cursor_bundle_composer_hooks,
)


class CursorBundleComposerHookDiscoveryTests(unittest.TestCase):
    def test_marks_chat_open_as_risky_and_finds_internal_draft_hooks(self):
        bundle = """
        fl.registerCommand("workbench.action.chat.open", async(n,e)=>{
          const t=n.get(w_),i=n.get(eP),r=n.get(uI),
            s=typeof e=="string"?e:e?.query,
            o=await t.createComposer({partialState:s?{text:s,richText:s}:void 0,openInNewTab:!0});
          if(!o){return}
          const a=o.composerId;
          s&&r.fireShouldForceText({composerId:a}),await i.showAndFocus(a)
        })
        class ComposerDataService {
          updateComposerData(e,t){e.setData(t)}
          updateComposerDataSetStore(e,t){t(e.setData)}
        }
        const nativeWrite = this.composerDataService.updateComposerData(handle,{text:"x",richText:"x"});
        """
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workbench.desktop.main.js"
            path.write_text(bundle, encoding="utf-8")

            report = analyze_cursor_bundle_composer_hooks(path)

        self.assertEqual(report["mode"], "cursor-bundle-composer-hook-discovery")
        self.assertEqual(report["safety_mode"], "read_only_static_bundle_scan")
        self.assertFalse(report["control_allowed"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["decision"], "cursor_native_hook_candidates_found")
        self.assertEqual(report["signals"]["chat_open_command_count"], 1)
        self.assertEqual(report["signals"]["show_and_focus_count"], 1)

        risky = report["risky_commands"][0]
        self.assertEqual(risky["command_id"], "workbench.action.chat.open")
        self.assertEqual(risky["recommendation"], "do_not_use_as_background_sender")
        self.assertTrue(risky["draft_write_evidence"])
        self.assertTrue(risky["activation_evidence"])
        self.assertIn("showAndFocus", risky["risk_markers"])

        hook_ids = {hook["hook_id"] for hook in report["hook_candidates"]}
        self.assertIn("composerService.createComposer.partialState", hook_ids)
        self.assertIn("composerDataService.updateComposerData", hook_ids)
        for hook in report["hook_candidates"]:
            self.assertEqual(hook["surface"], "cursor_internal_service")
            self.assertTrue(hook["requires_custom_bridge"])
            self.assertEqual(hook["validation_state"], "static_candidate_unvalidated")
            self.assertFalse(hook["calls_show_and_focus"])

    def test_reports_missing_bundle_without_control_attempts(self):
        report = analyze_cursor_bundle_composer_hooks(
            Path(tempfile.gettempdir()) / "openwukong-missing-cursor-bundle.js"
        )

        self.assertEqual(report["decision"], "cursor_bundle_missing")
        self.assertFalse(report["bundle_found"])
        self.assertFalse(report["control_allowed"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["hook_candidates"], [])

    def test_report_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workbench.desktop.main.js"
            path.write_text("updateComposerData(e,t){e.setData(t)}", encoding="utf-8")

            report = analyze_cursor_bundle_composer_hooks(path)

        json.dumps(report, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
