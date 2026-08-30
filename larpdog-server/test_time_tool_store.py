from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


from time_tool_store import (
    apply_time_tool_update,
    load_time_tool_state,
    load_time_tool_states,
    normalize_time_tool_state,
    remove_time_tool_instance,
    save_time_tool_state,
    snapshot_time_tool_state,
    WallClockGuard,
    time_tool_defaults_for_type,
)


class TimeToolStoreTests(unittest.TestCase):
    def test_framed_time_tool_types_are_not_registered(self) -> None:
        for overlay_type in (
            "minecraft-clock",
            "minecraft-countdown",
            "minecraft-stopwatch",
        ):
            with self.subTest(overlay_type=overlay_type):
                with self.assertRaisesRegex(ValueError, "Unknown time-tool"):
                    time_tool_defaults_for_type(overlay_type)

    def test_timer_line_variants_keep_timer_behavior_and_clean_defaults(self) -> None:
        countdown = apply_time_tool_update(
            {},
            {"durationSeconds": 90, "action": "start"},
            "minecraft-countdown-line",
            now_ms=5_000,
        )
        stopwatch = apply_time_tool_update(
            {},
            {"action": "start"},
            "minecraft-stopwatch-line",
            now_ms=5_000,
        )

        self.assertEqual(countdown["durationSeconds"], 90)
        self.assertTrue(countdown["running"])
        self.assertEqual(countdown["glow"], 0)
        self.assertEqual(countdown["digitShadow"], 0)
        self.assertTrue(stopwatch["running"])
        self.assertEqual(stopwatch["elapsedMs"], 0)
        self.assertEqual(stopwatch["glow"], 0)
        self.assertEqual(stopwatch["digitShadow"], 0)

    def test_clock_line_uses_the_clock_state_contract(self) -> None:
        state = normalize_time_tool_state(
            {
                "timezone": "America/Los_Angeles",
                "timezoneLabel": "WEST",
                "hour12": False,
                "showSeconds": False,
                "showDate": False,
                "digitShadow": 0.45,
            },
            "minecraft-clock-line",
        )

        self.assertEqual(state["timezone"], "America/Los_Angeles")
        self.assertEqual(state["timezoneLabel"], "WEST")
        self.assertFalse(state["hour12"])
        self.assertFalse(state["showSeconds"])
        self.assertFalse(state["showDate"])
        self.assertEqual(state["digitShadow"], 0.45)
        self.assertEqual(state["glow"], 0)

    def test_clock_normalizes_timezone_appearance_and_labels(self) -> None:
        state = normalize_time_tool_state(
            {
                "label": "  SERVER   TIME  ",
                "timezone": "America/Chicago",
                "timezoneLabel": "  CENTRAL  ",
                "hour12": False,
                "accentColor": "#AABBCC",
                "shellColor": "invalid",
                "scale": 99,
                "glow": -2,
            },
            "minecraft-clock-line",
        )

        self.assertEqual(state["label"], "SERVER TIME")
        self.assertEqual(state["timezone"], "America/Chicago")
        self.assertEqual(state["timezoneLabel"], "CENTRAL")
        self.assertFalse(state["hour12"])
        self.assertEqual(state["accentColor"], "aabbcc")
        self.assertEqual(state["shellColor"], "292725")
        self.assertEqual(state["scale"], 1.25)
        self.assertEqual(state["glow"], 0)
        self.assertEqual(state["digitShadow"], 0)

    def test_countdown_rebases_running_state_and_pauses_exactly(self) -> None:
        started = apply_time_tool_update(
            {},
            {"durationSeconds": 600, "action": "start"},
            "minecraft-countdown-line",
            now_ms=10_000,
        )
        self.assertTrue(started["running"])
        self.assertEqual(started["remainingMs"], 600_000)
        self.assertEqual(started["startedAt"], 10_000)

        paused = apply_time_tool_update(
            started,
            {"action": "pause"},
            "minecraft-countdown-line",
            now_ms=15_250,
        )
        self.assertFalse(paused["running"])
        self.assertEqual(paused["remainingMs"], 594_750)
        self.assertEqual(paused["startedAt"], 0)

        resumed = apply_time_tool_update(
            paused,
            {"action": "start"},
            "minecraft-countdown-line",
            now_ms=20_000,
        )
        snapshot = apply_time_tool_update(
            resumed,
            {},
            "minecraft-countdown-line",
            now_ms=22_000,
        )
        self.assertEqual(snapshot["remainingMs"], 592_750)
        self.assertEqual(snapshot["startedAt"], 22_000)

    def test_countdown_duration_change_resets_and_bounds_state(self) -> None:
        running = apply_time_tool_update(
            {},
            {"action": "start"},
            "minecraft-countdown-line",
            now_ms=1_000,
        )
        changed = apply_time_tool_update(
            running,
            {"durationSeconds": 0},
            "minecraft-countdown-line",
            now_ms=2_000,
        )

        self.assertEqual(changed["durationSeconds"], 1)
        self.assertEqual(changed["remainingMs"], 1_000)
        self.assertFalse(changed["running"])
        self.assertEqual(changed["startedAt"], 0)

        shortened = apply_time_tool_update(
            {
                "durationSeconds": 600,
                "remainingMs": 480_000,
                "running": False,
            },
            {"durationSeconds": 300},
            "minecraft-countdown-line",
            now_ms=3_000,
        )
        self.assertEqual(shortened["durationSeconds"], 300)
        self.assertEqual(shortened["remainingMs"], 300_000)
        self.assertFalse(shortened["running"])

    def test_paused_countdown_reads_do_not_consume_remaining_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "time-tools.json"
            save_time_tool_state(
                path,
                {
                    "durationSeconds": 300,
                    "remainingMs": 123_456,
                    "running": False,
                    "startedAt": 0,
                },
                "paused-countdown",
                "minecraft-countdown-line",
            )

            first = load_time_tool_state(
                path,
                "paused-countdown",
                "minecraft-countdown-line",
                now_ms=100_000,
            )
            second = load_time_tool_state(
                path,
                "paused-countdown",
                "minecraft-countdown-line",
                now_ms=3_700_000,
            )

            self.assertEqual(first["remainingMs"], 123_456)
            self.assertEqual(second, first)

    def test_wall_clock_guard_ignores_forward_and_backward_jumps_once(self) -> None:
        logger = mock.Mock()
        guard = WallClockGuard(logger=logger)

        self.assertEqual(guard.logical_now_ms(1_000_000, 10_000), 1_000_000)
        self.assertEqual(guard.logical_now_ms(4_601_000, 11_000), 1_001_000)
        self.assertEqual(guard.logical_now_ms(4_602_000, 12_000), 1_002_000)
        self.assertEqual(guard.logical_now_ms(2_603_000, 13_000), 1_003_000)
        logger.warning.assert_called_once()

    def test_clock_jump_snapshot_rebases_into_the_browser_wall_clock(self) -> None:
        before_jump = {
            "durationSeconds": 60,
            "remainingMs": 60_000,
            "running": True,
            "startedAt": 1_000_000,
        }
        forward = snapshot_time_tool_state(
            before_jump,
            "minecraft-countdown-line",
            now_ms=4_601_000,
            logical_now_ms=1_001_000,
        )
        self.assertEqual(forward["remainingMs"], 59_000)
        self.assertEqual(forward["startedAt"], 4_601_000)

        after_forward = snapshot_time_tool_state(
            forward,
            "minecraft-countdown-line",
            now_ms=4_602_000,
            logical_now_ms=1_002_000,
        )
        self.assertEqual(after_forward["remainingMs"], 58_000)
        self.assertEqual(after_forward["startedAt"], 4_602_000)

        before_backward = {
            **before_jump,
            "startedAt": 4_600_000,
        }
        backward = snapshot_time_tool_state(
            before_backward,
            "minecraft-countdown-line",
            now_ms=2_601_000,
            logical_now_ms=4_601_000,
        )
        self.assertEqual(backward["remainingMs"], 59_000)
        self.assertEqual(backward["startedAt"], 2_601_000)

    def test_countdown_completion_sound_settings_are_bounded_and_testable(self) -> None:
        state = apply_time_tool_update(
            {},
            {
                "soundEnabled": False,
                "soundVolume": 9,
                "action": "test-sound",
            },
            "minecraft-countdown-line",
            now_ms=1_000,
        )

        self.assertFalse(state["soundEnabled"])
        self.assertEqual(state["soundVolume"], 1.0)
        self.assertFalse(state["running"])
        self.assertEqual(state["remainingMs"], 600_000)

        with self.assertRaisesRegex(ValueError, "only available for countdowns"):
            apply_time_tool_update(
                {},
                {"action": "test-sound"},
                "minecraft-stopwatch-line",
                now_ms=1_000,
            )

    def test_stopwatch_accumulates_across_pause_resume_and_reset(self) -> None:
        state = apply_time_tool_update(
            {},
            {"action": "start"},
            "minecraft-stopwatch-line",
            now_ms=1_000,
        )
        state = apply_time_tool_update(
            state,
            {"action": "pause"},
            "minecraft-stopwatch-line",
            now_ms=4_500,
        )
        self.assertEqual(state["elapsedMs"], 3_500)

        state = apply_time_tool_update(
            state,
            {"action": "start"},
            "minecraft-stopwatch-line",
            now_ms=10_000,
        )
        state = apply_time_tool_update(
            state,
            {"action": "pause"},
            "minecraft-stopwatch-line",
            now_ms=12_250,
        )
        self.assertEqual(state["elapsedMs"], 5_750)

        state = apply_time_tool_update(
            state,
            {"action": "reset"},
            "minecraft-stopwatch-line",
            now_ms=13_000,
        )
        self.assertEqual(state["elapsedMs"], 0)
        self.assertFalse(state["running"])

    def test_instances_persist_independently_and_remove_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "time-tools.json"
            save_time_tool_state(
                path,
                {"elapsedMs": 12_000},
                "build-one",
                "minecraft-stopwatch-line",
            )
            save_time_tool_state(
                path,
                {"elapsedMs": 34_000},
                "build-two",
                "minecraft-stopwatch-line",
            )

            states = load_time_tool_states(
                path,
                {
                    "build-one": {"type": "minecraft-stopwatch-line"},
                    "build-two": {"type": "minecraft-stopwatch-line"},
                },
                now_ms=50_000,
            )
            self.assertEqual(states["build-one"]["elapsedMs"], 12_000)
            self.assertEqual(states["build-two"]["elapsedMs"], 34_000)

            remove_time_tool_instance(path, "build-one")
            self.assertEqual(
                load_time_tool_state(
                    path,
                    "build-one",
                    "minecraft-stopwatch-line",
                    now_ms=50_000,
                )["elapsedMs"],
                0,
            )
            self.assertEqual(
                load_time_tool_state(
                    path,
                    "build-two",
                    "minecraft-stopwatch-line",
                    now_ms=50_000,
                )["elapsedMs"],
                34_000,
            )

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown time-tool action"):
            apply_time_tool_update(
                {},
                {"action": "lap"},
                "minecraft-stopwatch-line",
                now_ms=1_000,
            )


if __name__ == "__main__":
    unittest.main()
