import unittest

from openwukong.control.wechat_monitor import WeChatMonitor


class FakeMessageSource:
    def __init__(self, batches, *, pid=7101, hwnd=1001):
        self.batches = list(batches)
        self.pid = pid
        self.hwnd = hwnd
        self.login_state = "logged_in"

    def read_state(self):
        return {
            "pid": self.pid,
            "hwnd": self.hwnd,
            "conversation_id": "zhang",
            "login_state": self.login_state,
        }

    def read_messages(self):
        if self.batches:
            return self.batches.pop(0)
        return []

    def read_unread_count(self):
        return 0

    def read_notifications(self):
        return []


class WeChatMonitorTests(unittest.TestCase):
    def test_monitor_emits_only_new_messages_for_bound_conversation(self):
        source = FakeMessageSource(
            [
                [{"id": "m1", "sender": "张三", "text": "hello"}],
                [{"id": "m1", "sender": "张三", "text": "hello"}],
                [{"id": "m2", "sender": "张三", "text": "again"}],
            ]
        )
        monitor = WeChatMonitor(
            source=source,
            pid=7101,
            hwnd=1001,
            conversation_id="zhang",
        )

        first = monitor.poll_once()
        duplicate = monitor.poll_once()
        second = monitor.poll_once()

        self.assertEqual([item["id"] for item in first.messages], ["m1"])
        self.assertEqual(duplicate.messages, ())
        self.assertEqual([item["id"] for item in second.messages], ["m2"])
        self.assertEqual(first.decision, "new_messages")
        self.assertEqual(duplicate.decision, "no_new_messages")
        self.assertEqual(first.control_attempts, 0)

    def test_window_or_login_state_change_stops_monitor(self):
        source = FakeMessageSource([[{"id": "m1", "text": "hello"}]])
        monitor = WeChatMonitor(source=source, pid=7101, hwnd=1001)
        self.assertEqual(monitor.poll_once().decision, "new_messages")

        source.hwnd = 1002
        changed = monitor.poll_once()

        self.assertFalse(changed.ok)
        self.assertEqual(changed.decision, "state_changed")
        self.assertEqual(changed.messages, ())
        self.assertEqual(changed.control_attempts, 0)

    def test_pause_resume_and_quiet_notifications_do_not_control_window(self):
        source = FakeMessageSource([[], [{"id": "m2", "text": "after resume"}]])
        monitor = WeChatMonitor(source=source, pid=7101, hwnd=1001)

        monitor.pause()
        paused = monitor.poll_once()
        monitor.resume()
        quiet = monitor.poll_once()
        new_message = monitor.poll_once()

        self.assertEqual(paused.decision, "monitor_paused")
        self.assertEqual(quiet.decision, "no_new_messages")
        self.assertEqual(new_message.decision, "new_messages")
        self.assertEqual(paused.control_attempts, 0)
        self.assertEqual(new_message.keyboard_input_attempts, 0)
        self.assertEqual(new_message.clipboard_write_attempts, 0)

    def test_monitor_reports_source_errors_without_replaying_messages(self):
        class BrokenSource(FakeMessageSource):
            def read_messages(self):
                raise RuntimeError("source unavailable")

        monitor = WeChatMonitor(source=BrokenSource([]), pid=7101, hwnd=1001)
        result = monitor.poll_once()

        self.assertFalse(result.ok)
        self.assertEqual(result.decision, "source_error")
        self.assertEqual(result.control_attempts, 0)
        self.assertEqual(result.messages, ())


if __name__ == "__main__":
    unittest.main()
