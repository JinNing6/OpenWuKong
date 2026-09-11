import struct
import unittest
from pathlib import Path

from openwukong.control.windows_file_clipboard import build_dropfiles_payload


class WindowsFileClipboardTests(unittest.TestCase):
    def test_dropfiles_payload_contains_unicode_paths_and_double_terminator(self):
        payload = build_dropfiles_payload([Path("C:/tmp/测试.txt"), Path("C:/tmp/two.bin")])
        header = struct.unpack("<IiiII", payload[:20])
        names = payload[20:].decode("utf-16-le")

        self.assertEqual(header, (20, 0, 0, 0, 1))
        self.assertTrue(names.endswith("\x00\x00"))
        self.assertIn("测试.txt", names)
        self.assertIn("two.bin", names)

    def test_empty_file_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "clipboard_file_list_empty"):
            build_dropfiles_payload([])

    def test_nul_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "clipboard_file_path_contains_nul"):
            build_dropfiles_payload(["C:/tmp/bad\x00.txt"])


if __name__ == "__main__":
    unittest.main()
