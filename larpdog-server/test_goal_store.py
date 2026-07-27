from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from goal_store import (  # noqa: E402
    DEFAULT_GOAL_STATE,
    apply_goal_update,
    load_goal_state,
    normalize_goal_state,
    remove_goal_instance,
    save_goal_state,
)


class GoalStoreTests(unittest.TestCase):
    def test_normalizes_untrusted_goal_values(self) -> None:
        state = normalize_goal_state(
            {
                "label": "  A   very long goal  ",
                "current": -10,
                "target": float("inf"),
                "format": "unknown",
                "symbol": "USD dollars",
                "color": "#ABCDEF",
                "track": "not-a-color",
                "font": "comic-sans",
                "weight": 784,
                "particles": "off",
                "percent": "yes",
                "scale": 9,
                "glow": -3,
            }
        )

        self.assertEqual(state["label"], "A very long goal")
        self.assertEqual(state["current"], 0)
        self.assertEqual(state["target"], DEFAULT_GOAL_STATE["target"])
        self.assertEqual(state["format"], "currency")
        self.assertEqual(state["symbol"], "USD ")
        self.assertEqual(state["color"], "abcdef")
        self.assertEqual(state["track"], DEFAULT_GOAL_STATE["track"])
        self.assertEqual(state["font"], "serif")
        self.assertEqual(state["weight"], 800)
        self.assertFalse(state["particles"])
        self.assertTrue(state["percent"])
        self.assertEqual(state["scale"], 1.2)
        self.assertEqual(state["glow"], 0)

    def test_applies_goal_actions_with_bounds(self) -> None:
        state = normalize_goal_state({"current": 10, "target": 50})

        state = apply_goal_update(state, {"action": "add", "amount": 7.5})
        self.assertEqual(state["current"], 17.5)
        state = apply_goal_update(state, {"action": "subtract", "amount": 30})
        self.assertEqual(state["current"], 0)
        state = apply_goal_update(state, {"action": "complete"})
        self.assertEqual(state["current"], 50)
        state = apply_goal_update(state, {"action": "reset"})
        self.assertEqual(state["current"], 0)

        with self.assertRaisesRegex(ValueError, "Unknown goal action"):
            apply_goal_update(state, {"action": "launch"})

    def test_round_trips_and_removes_independent_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "goal.json"
            save_goal_state(
                path,
                normalize_goal_state({"label": "Followers", "current": 12}),
                "follower-goal",
            )
            save_goal_state(
                path,
                normalize_goal_state({"label": "Tips", "current": 25}),
                "tip-goal",
            )

            self.assertEqual(
                load_goal_state(path, "follower-goal")["current"],
                12,
            )
            self.assertEqual(load_goal_state(path, "tip-goal")["current"], 25)

            remove_goal_instance(path, "follower-goal")

            self.assertEqual(
                load_goal_state(path, "follower-goal"),
                DEFAULT_GOAL_STATE,
            )
            self.assertEqual(load_goal_state(path, "tip-goal")["current"], 25)


if __name__ == "__main__":
    unittest.main()
