import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class GoalPillPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (ROOT_DIR / "overlays" / "goal-pill.html").read_text(
            encoding="utf-8"
        )

    def test_zero_progress_has_no_forced_fill(self) -> None:
        self.assertIn("width: calc(var(--pct, 0) * 100%)", self.source)
        self.assertNotIn("min-width: var(--bar-h)", self.source)

    def test_installed_overlay_loads_state_without_running_demo(self) -> None:
        self.assertIn('fetch(`/api/goal?i=${encodeURIComponent(instanceId)}`', self.source)
        self.assertIn('query.get("demo") || "off"', self.source)
        self.assertIn("if (!customizerMode)", self.source)

    def test_manifest_opens_the_goal_pill_customizer(self) -> None:
        self.assertIn('"studioView": "goalPillView"', self.source)
        self.assertIn('message.overlayType !== "goal-pill"', self.source)


if __name__ == "__main__":
    unittest.main()
