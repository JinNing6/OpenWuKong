import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.wechat_desktop import WeChatDesktopConnector
from openwukong.control.fabric import ControlIntent


class FakeMomentsBackend:
    def __init__(self, *, verify=True):
        self.events = []
        self.verify = verify

    def open_moments(self, target, parameters):
        self.events.append(("open_moments", parameters))
        return {"moments_open": True, "readback_verified": True}

    def read_moments(self, target, parameters):
        self.events.append(("read_moments", parameters))
        return {
            "posts": [{"id": "post-1", "body": "existing"}],
            "readback_verified": True,
        }

    def draft_moment(self, target, parameters):
        self.events.append(("draft_moment", parameters))
        return {
            "draft_saved": True,
            "draft_readback_verified": True,
            "publish_attempts": 0,
        }

    def publish_moment(self, target, parameters):
        self.events.append(("publish_moment", parameters))
        return {
            "published": True,
            "publish_attempts": 1,
            "visibility": parameters["visibility"],
            "readback_verified": self.verify,
        }


class WeChatMomentsTests(unittest.TestCase):
    def _target(self, root):
        return ConnectorTarget(
            pid=7101,
            process_name="Weixin.exe",
            window_title="微信",
            workspace_path=str(root),
        )

    def _publish_intent(self, **parameters):
        return ControlIntent(
            action="wechat.moments.publish",
            allow_submit=True,
            parameters={
                "body": "今天完成了一个小目标",
                "visibility": "public",
                **parameters,
            },
        )

    def test_open_and_read_moments_are_read_only(self):
        backend = FakeMomentsBackend()
        connector = WeChatDesktopConnector(backend=backend)

        opened = connector.execute_action(
            self._target(Path(".")),
            ControlIntent(action="wechat.moments.open"),
        )
        read = connector.execute_action(
            self._target(Path(".")),
            ControlIntent(action="wechat.moments.read"),
        )

        self.assertTrue(opened.success, opened.error)
        self.assertTrue(read.success, read.error)
        self.assertEqual(opened.payload["control_attempts"], 0)
        self.assertEqual(read.payload["control_attempts"], 0)
        self.assertEqual(read.payload["posts"][0]["id"], "post-1")

    def test_moment_draft_does_not_publish(self):
        backend = FakeMomentsBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            ControlIntent(
                action="wechat.moments.draft",
                parameters={"body": "草稿朋友圈", "visibility": "private"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["draft_readback_verified"])
        self.assertEqual(result.payload["publish_attempts"], 0)

    def test_publish_requires_approval_before_backend_call(self):
        backend = FakeMomentsBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            ControlIntent(
                action="wechat.moments.publish",
                parameters={"body": "不能直接发布", "visibility": "public"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_side_effect_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(backend.events, [])

    def test_publish_binds_visibility_and_media_metadata(self):
        backend = FakeMomentsBackend()
        connector = WeChatDesktopConnector(backend=backend)
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            media = root / "photo.png"
            media.write_bytes(b"fake-png")

            result = connector.execute_action(
                self._target(root),
                self._publish_intent(
                    body="带图动态",
                    visibility="partial",
                    media_paths=[str(media)],
                ),
            )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["visibility"], "partial")
        self.assertEqual(result.payload["media"][0]["name"], "photo.png")
        self.assertEqual(result.payload["publish_attempts"], 1)
        self.assertEqual(backend.events[0][1]["visibility"], "partial")

    def test_missing_publish_readback_is_unknown_and_never_retried(self):
        backend = FakeMomentsBackend(verify=False)
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            self._publish_intent(body="只尝试一次"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_verification_failed")
        self.assertEqual(result.payload["publish_attempts"], 1)
        self.assertEqual(len(backend.events), 1)


if __name__ == "__main__":
    unittest.main()
