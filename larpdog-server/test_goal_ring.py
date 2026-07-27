import math
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class GoalRingTests(unittest.TestCase):
    def test_progress_dash_does_not_repeat_around_circle(self) -> None:
        source = (ROOT_DIR / "overlays" / "goal.html").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'track.setAttribute("stroke-dasharray", `${ARC} ${CIRC - ARC}`)',
            source,
        )
        self.assertIn(
            'fill.setAttribute("stroke-dasharray", `${ARC} ${CIRC}`)',
            source,
        )

    def test_visible_arc_is_proportional_to_goal_progress(self) -> None:
        circumference = 2 * math.pi * 120
        arc = circumference * (300 / 360)

        for current, target in ((0, 50), (1, 50), (25, 50), (50, 50)):
            with self.subTest(current=current, target=target):
                ratio = max(0, min(1, current / target))
                dash_offset = arc * (1 - ratio)
                visible_arc = arc - dash_offset
                self.assertAlmostEqual(visible_arc / arc, ratio)


if __name__ == "__main__":
    unittest.main()
