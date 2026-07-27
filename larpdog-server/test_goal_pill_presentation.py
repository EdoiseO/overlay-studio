import json
import re
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

    def test_manifest_color_names_match_the_canonical_query_contract(self) -> None:
        match = re.search(
            r'<script type="application/json" id="overlay-manifest">\s*'
            r"(?P<manifest>\{.*?\})\s*</script>",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        settings = json.loads(match.group("manifest"))["settings"]

        self.assertIn("track", settings)
        self.assertIn("labelColor", settings)
        self.assertNotIn("trackColor", settings)
        self.assertNotIn("textColor", settings)
        self.assertIn(
            'query.get("track") || query.get("trackColor")',
            self.source,
        )
        self.assertIn(
            'query.get("labelColor") || query.get("textColor")',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
