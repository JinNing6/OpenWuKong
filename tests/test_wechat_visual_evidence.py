import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from openwukong.control.wechat_visual_evidence import (
    OcrFrame, OcrLine, find_chat_header, find_moments_surface,
    verify_chat_attachment, verify_chat_send, verify_moments_publish,
)


def line(text, left, top, width=120, height=24):
    return OcrLine(text=text, rect=(left, top, left + width, top + height))


def frame(*lines):
    return OcrFrame(width=900, height=650, lines=tuple(lines))


class WeChatVisualEvidenceTests(unittest.TestCase):
    def test_header_matches_exact_title_next_to_search(self):
        evidence = find_chat_header(frame(
            line("搜索", 40, 50), line("文 件 传 输 助 手", 380, 50, 190),
        ), "文件传输助手")
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["header_rect"], [380, 50, 570, 74])

    def test_sidebar_and_message_body_are_not_target_evidence(self):
        evidence = find_chat_header(frame(
            line("搜索", 40, 50), line("李四", 380, 50),
            line("张三", 40, 140), line("张三", 440, 280),
        ), "张三")
        self.assertFalse(evidence["verified"])

    def test_similar_group_name_does_not_verify_person(self):
        evidence = find_chat_header(frame(
            line("搜索", 40, 50), line("张三工作群", 380, 50),
        ), "张三")
        self.assertFalse(evidence["verified"])

    def test_unpositioned_text_is_not_header_evidence(self):
        self.assertFalse(find_chat_header(frame(), "张三")["verified"])

    def test_sent_bubble_is_distinguished_from_composer_and_sidebar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            image = Image.new("RGB", (900, 650), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((360, 480, 890, 640), outline=(215, 215, 215), width=2)
            image.save(path)
            common = (
                line("搜索", 40, 50), line("文件传输助手", 380, 50, 190),
                line("发送", 835, 605, 45),
            )
            good = verify_chat_send(
                path, frame(*common, line("TEST_123", 580, 350, 150)),
                target_name="文件传输助手", message="TEST_123",
            )
            draft = verify_chat_send(
                path, frame(*common, line("TEST_123", 400, 510, 150)),
                target_name="文件传输助手", message="TEST_123",
            )
            sidebar = verify_chat_send(
                path, frame(*common, line("TEST_123", 40, 160, 150)),
                target_name="文件传输助手", message="TEST_123",
            )
        self.assertTrue(good["verified"], good)
        self.assertFalse(draft["verified"])
        self.assertFalse(sidebar["verified"])
        self.assertNotIn("ocr_text_preview", good)

    def test_attachment_filename_must_be_in_chat_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            image = Image.new("RGB", (900, 650), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((360, 480, 890, 640), outline=(215, 215, 215), width=2)
            image.save(path)
            common = (
                line("搜索", 40, 50), line("文件传输助手", 380, 50, 190),
                line("发送", 835, 605, 45),
            )
            good = verify_chat_attachment(
                path, frame(*common, line("report.pdf", 580, 350, 150)),
                target_name="文件传输助手", filename="report.pdf",
            )
            composer = verify_chat_attachment(
                path, frame(*common, line("report.pdf", 400, 510, 150)),
                target_name="文件传输助手", filename="report.pdf",
            )
        self.assertTrue(good["verified"], good)
        self.assertFalse(composer["verified"])

    def test_moments_surface_requires_feed_marker(self):
        self.assertTrue(find_moments_surface(frame(
            line("朋友圈", 80, 80, 120),
            line("张三的朋友圈", 380, 80, 180),
        ))["verified"])
        self.assertFalse(find_moments_surface(frame(line("文件传输助手", 380, 80, 180)))["verified"])

    def test_moments_publish_requires_new_body_after_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            Image.new("RGB", (900, 650), "white").save(path)
            before = frame(line("朋友圈", 80, 80, 120), line("发布", 780, 80, 70))
            after = frame(
                line("朋友圈", 80, 80, 120),
                line("张三的朋友圈", 380, 80, 180),
                line("刚刚", 380, 160, 60),
                line("今日完成", 380, 190, 120),
            )
            result = verify_moments_publish(
                path, before, after, body="今日完成",
            )
        self.assertTrue(result["verified"], result)
        self.assertFalse(
            verify_moments_publish(path, before, before, body="今日完成")["verified"]
        )


if __name__ == "__main__":
    unittest.main()
