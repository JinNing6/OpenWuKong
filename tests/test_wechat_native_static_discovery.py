import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.wechat_native_static_discovery import (
    _keyword_hits_for_bytes,
    _parse_pe_exports_from_bytes,
    main,
    run_wechat_native_static_discovery,
)


class WeChatNativeStaticDiscoveryTests(unittest.TestCase):
    def test_keyword_hits_include_ascii_and_utf16_without_context_leak(self):
        payload = (
            b"prefix Mojo IPC send message"
            + " File Transfer Assistant".encode("utf-16le")
        )
        hits = _keyword_hits_for_bytes(payload)

        self.assertGreaterEqual(hits["mojo"], 1)
        self.assertGreaterEqual(hits["ipc"], 1)
        self.assertGreaterEqual(hits["send"], 1)
        self.assertGreaterEqual(hits["message"], 1)
        self.assertGreaterEqual(hits["file transfer"], 1)
        self.assertNotIn("prefix Mojo IPC send message", hits)

    def test_minimal_pe_export_parser_finds_send_like_exports(self):
        pe = _minimal_pe64_with_exports(
            ["WeChatSendMessage", "MojoBootstrap", "NormalExport"]
        )
        report = _parse_pe_exports_from_bytes(pe)

        self.assertTrue(report["is_pe"], report)
        self.assertEqual(report["machine"], "x64")
        self.assertEqual(report["pe_kind"], "PE32+")
        self.assertIn("WeChatSendMessage", report["export_names"])
        self.assertIn("MojoBootstrap", report["export_names"])

    def test_static_signals_do_not_become_send_ready_without_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dll = root / "ilink_wrapper.dll"
            dll.write_bytes(
                b"not-a-pe but has mojo ipc send message filehelper localhost"
            )

            report = run_wechat_native_static_discovery(
                install_dirs=(str(root),),
                process_snapshot=(),
            )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(
            data["decision"],
            "weixin_static_surfaces_found_without_send_contract",
        )
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["scanned_files"][0]["name"], "ilink_wrapper.dll")
        self.assertIn("name:ilink", data["scanned_files"][0]["static_signals"])
        self.assertIn("keyword:mojo", data["scanned_files"][0]["static_signals"])

    def test_documented_helper_manifest_is_separate_static_contract_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "openwukong-wechat-native-helper.json").write_text(
                json.dumps(
                    {
                        "schema": "openwukong.wechat.native_helper.v1",
                        "command": ["helper.exe"],
                        "background_safe": True,
                        "send_action_ready": True,
                        "requires_foreground": False,
                        "window_input_required": False,
                        "keyboard_input_required": False,
                        "clipboard_required": False,
                    }
                ),
                encoding="utf-8",
            )

            report = run_wechat_native_static_discovery(
                install_dirs=(str(root),),
                process_snapshot=(),
            )
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(
            data["decision"],
            "documented_wechat_native_helper_contract_found",
        )
        self.assertEqual(data["send_attempts"], 0)

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Weixin"
            root.mkdir()
            (root / "mmmojo_64.dll").write_bytes(b"mojo ipc")
            output = Path(td) / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--install-dir",
                        str(root),
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(
            data["decision"],
            "weixin_static_surfaces_found_without_send_contract",
        )
        self.assertEqual(data["scanned_file_count"], 1)
        self.assertEqual(data["control_attempts"], 0)


def _minimal_pe64_with_exports(names):
    buf = bytearray(0x1800)
    buf[:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    optional_size = 240
    struct.pack_into(
        "<HHIIIHH",
        buf,
        0x84,
        0x8664,
        1,
        0,
        0,
        0,
        optional_size,
        0x2022,
    )
    optional_offset = 0x98
    struct.pack_into("<H", buf, optional_offset, 0x20B)
    struct.pack_into("<I", buf, optional_offset + 108, 16)
    struct.pack_into("<II", buf, optional_offset + 112, 0x1000, 0x200)
    section_offset = optional_offset + optional_size
    struct.pack_into(
        "<8sIIIIIIHHI",
        buf,
        section_offset,
        b".rdata\x00\x00",
        0x1000,
        0x1000,
        0x1000,
        0x400,
        0,
        0,
        0,
        0,
        0x40000040,
    )
    name_pointer_rva = 0x1060
    ordinal_rva = 0x1080
    function_rva = 0x10A0
    struct.pack_into(
        "<IIHHIIIIIII",
        buf,
        0x400,
        0,
        0,
        0,
        0,
        0,
        1,
        len(names),
        len(names),
        function_rva,
        name_pointer_rva,
        ordinal_rva,
    )
    string_offset = 0x500
    for index, name in enumerate(names):
        encoded = name.encode("ascii") + b"\x00"
        string_rva = 0x1000 + string_offset - 0x400
        struct.pack_into("<I", buf, 0x460 + index * 4, string_rva)
        struct.pack_into("<H", buf, 0x480 + index * 2, index)
        struct.pack_into("<I", buf, 0x4A0 + index * 4, 0x1200 + index * 4)
        buf[string_offset : string_offset + len(encoded)] = encoded
        string_offset += len(encoded)
    return bytes(buf)


if __name__ == "__main__":
    unittest.main()
