from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


from time_tool_store import (
    apply_time_tool_update,
    load_time_tool_state,
    load_time_tool_states,
    normalize_time_tool_state,
    remove_time_tool_instance,
    save_time_tool_state,
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
