from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

from openwukong.supervisor.agent_supervisor import SteerOperator


class _Rect:
    def __init__(self, left: int, top: int, right: int, bottom: int):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom


class _FakeWrapper:
    def __init__(
        self,
        *,
        control_type: str = "Edit",
        name: str = "",
        automation_id: str = "",
        rect: tuple[int, int, int, int] = (0, 0, 400, 40),
        enabled: bool = True,
        read_only: bool | None = None,
    ):
        self.element_info = SimpleNamespace(
            control_type=control_type,
            name=name,
            automation_id=automation_id,
        )
        self._rect = _Rect(*rect)
        self._enabled = enabled
        self._read_only = read_only

    def rectangle(self):
        return self._rect

    def is_enabled(self):
        return self._enabled

    def get_value_pattern_attribute(self, name: str):
        if name != "IsReadOnly":
            raise RuntimeError("unsupported attribute")
        return self._read_only


class _FakeWindow:
    def __init__(
        self,
        title: str,
        descendants: list[_FakeWrapper],
        rect: tuple[int, int, int, int] = (0, 0, 1200, 900),
    ):
        self._title = title
        self._descendants = descendants
        self._rect = _Rect(*rect)

    def window_text(self):
        return self._title

    def descendants(self, control_type: str | None = None):
        if control_type is None:
            return list(self._descendants)
        return [
            descendant
            for descendant in self._descendants
            if descendant.element_info.control_type == control_type
        ]

    def rectangle(self):
        return self._rect


class _FakeApp:
    def __init__(self, windows: list[_FakeWindow]):
        self._windows = windows

    def windows(self):
        return list(self._windows)


class SteerOperatorTests(unittest.TestCase):
    def test_find_chat_input_prefers_matched_window(self):
        other_input = _FakeWrapper(
            name="message",
            automation_id="chat-input",
            rect=(40, 760, 820, 820),
        )
        target_input = _FakeWrapper(
            name="message",
            automation_id="chat-input",
            rect=(40, 760, 820, 820),
        )
        app = _FakeApp(
            [
                _FakeWindow("other-project - Cursor", [other_input]),
                _FakeWindow("openwukong - Cursor", [target_input]),
            ]
        )

        found = SteerOperator.find_chat_input(app, "openwukong - Cursor")

        self.assertIs(found, target_input)

    def test_find_chat_input_ignores_search_boxes(self):
        search_box = _FakeWrapper(
            control_type="Edit",
            name="search",
            rect=(20, 50, 280, 80),
        )
        chat_box = _FakeWrapper(
            control_type="Edit",
            name="",
            automation_id="composer-input",
            rect=(40, 760, 980, 830),
        )
        app = _FakeApp([_FakeWindow("openwukong - Cursor", [search_box, chat_box])])

        found = SteerOperator.find_chat_input(app, "openwukong - Cursor")

        self.assertIs(found, chat_box)

    def test_scope_key_is_window_scoped(self):
        self.assertNotEqual(
            SteerOperator._scope_key(42, "openwukong - Cursor"),
            SteerOperator._scope_key(42, "other-project - Cursor"),
        )

    def test_copy_to_clipboard_handles_copy_failure(self):
        fake_module = types.ModuleType("pyperclip")

        def _raise(_: str):
            raise RuntimeError("clipboard unavailable")

        fake_module.copy = _raise
        with mock.patch.dict(sys.modules, {"pyperclip": fake_module}):
            ok, err = SteerOperator._copy_to_clipboard("hello")

        self.assertFalse(ok)
        self.assertIn("clipboard unavailable", err)


if __name__ == "__main__":
    unittest.main()
