import unittest
from datetime import datetime, timedelta, timezone

from openwukong.control.surface_capabilities import (
    CapabilityEvidence,
    SurfaceCapabilityProfile,
    profile_from_accessibility_window,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


NOW = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)


class SurfaceCapabilityTests(unittest.TestCase):
    def make_profile(self, **kwargs):
        values = {
            "process_name": "Weixin.exe",
            "pid": 123,
            "hwnd": 456,
            "observed_at": NOW,
            "capabilities": {
                "wechat.chat.read": {
                    "route": "uia-semantic",
                    "confidence": 90,
                    "read_only": True,
                }
            },
            "evidence": (
                CapabilityEvidence(source="uia", field="message_list", value=True),
            ),
        }
        values.update(kwargs)
        return SurfaceCapabilityProfile(**values)

    def test_profile_supports_only_observed_action(self):
        profile = self.make_profile()
        self.assertTrue(profile.supports("wechat.chat.read", now=NOW))
        self.assertFalse(profile.supports("wechat.chat.send_text", now=NOW))
        self.assertFalse(profile.supports("wechat.chat.read", minimum_confidence=95, now=NOW))

    def test_binding_requires_positive_matching_window_and_process(self):
        profile = self.make_profile()
        self.assertTrue(profile.is_bound(pid=123, hwnd=456))
        self.assertFalse(profile.is_bound(pid=124, hwnd=456))
        self.assertFalse(self.make_profile(pid=0).is_bound(pid=0, hwnd=456))

    def test_expired_and_future_profiles_cannot_execute(self):
        expired = self.make_profile(observed_at=NOW - timedelta(minutes=10))
        future = self.make_profile(observed_at=NOW + timedelta(seconds=10))
        self.assertFalse(expired.is_fresh(now=NOW))
        self.assertFalse(expired.supports("wechat.chat.read", now=NOW))
        self.assertFalse(future.is_fresh(now=NOW))

    def test_write_capability_without_bound_window_is_not_executable(self):
        profile = self.make_profile(
            hwnd=0,
            capabilities={"desktop.set_value": {"route": "uia-semantic", "confidence": 95}},
        )
        self.assertFalse(profile.supports("desktop.set_value", now=NOW))

    def test_round_trip_retains_typed_evidence_and_time(self):
        profile = self.make_profile()
        restored = SurfaceCapabilityProfile.from_dict(profile.to_dict())
        self.assertEqual(restored.to_dict(), profile.to_dict())
        self.assertIs(restored.evidence[0].value, True)

    def test_naive_timestamp_and_invalid_confidence_are_rejected(self):
        with self.assertRaises(ValueError):
            self.make_profile(observed_at=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            self.make_profile(capabilities={"desktop.invoke": {"route": "uia", "confidence": 101}})

    def test_generic_snapshot_exposes_primitives_not_wechat_send(self):
        window = AccessibilityWindowSnapshot(
            pid=123,
            hwnd=456,
            process_name="Weixin.exe",
            window_title="微信",
            elements=(
                AccessibilityElementSnapshot(
                    control_type="Edit", name="", rect=(0, 0, 100, 50),
                    patterns=("Value", "Text"), is_enabled=True,
                ),
                AccessibilityElementSnapshot(
                    control_type="Button", name="Unknown", rect=(100, 0, 150, 50),
                    patterns=("Invoke",), is_enabled=True,
                ),
            ),
        )
        profile = profile_from_accessibility_window(window, observed_at=NOW)
        self.assertTrue(profile.supports("desktop.read_text", now=NOW))
        self.assertTrue(profile.supports("desktop.set_value", now=NOW))
        self.assertFalse(profile.supports("wechat.chat.send_text", now=NOW))
        self.assertEqual(profile.to_dict()["control_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
