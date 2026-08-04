import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class CustomizerDisclosureTests(unittest.TestCase):
    EXPECTED = {
        "danceView": {
            "open": ("Dancing GIF settings",),
            "closed": ("Motion",),
        },
        "spotifyView": {
            "open": ("Player appearance",),
            "closed": (),
        },
        "flowView": {
            "open": ("Player appearance",),
            "closed": (),
        },
        "goalView": {
            "open": ("Goal progress",),
            "closed": ("Appearance",),
        },
        "goalBarView": {
            "open": ("Goal progress",),
            "closed": ("Layout", "Appearance"),
        },
        "goalPillView": {
            "open": ("Goal progress",),
            "closed": ("Layout", "Appearance"),
        },
        "platformBadgeView": {
            "open": (),
            "closed": ("Appearance",),
        },
        "socialView": {
            "open": (),
            "closed": ("Layout", "Appearance"),
        },
        "socialGroupedView": {
            "open": (),
            "closed": (
                "Composition",
                "Spacing",
                "Typography and label",
                "Canvas layout",
                "Tile fine tuning",
                "Outline and color",
            ),
        },
        "rivalsRankView": {
            "open": ("Player and session",),
            "closed": ("Content and layout", "Color palette"),
        },
        "counterView": {
            "open": ("Scoreboard",),
            "closed": (),
        },
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.markup = (ROOT_DIR / "studio" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.styles = (ROOT_DIR / "studio" / "app.css").read_text(
            encoding="utf-8"
        )

    def _view_chunk(self, view_id: str) -> str:
        start = self.markup.index(
            f'<section class="view detail-view" id="{view_id}">'
        )
        next_view = self.markup.find(
            '<section class="view detail-view"',
            start + 1,
        )
        return self.markup[start : next_view if next_view >= 0 else None]

    def test_customizer_panels_use_consistent_disclosures(self) -> None:
        total = 0
        for view_id, expected in self.EXPECTED.items():
            chunk = self._view_chunk(view_id)
            for heading in expected["open"]:
                with self.subTest(view=view_id, heading=heading, state="open"):
                    self.assertRegex(
                        chunk,
                        re.compile(
                            r'<details class="panel customizer-disclosure" open>'
                            rf'\s*<summary><h2>{re.escape(heading)}</h2></summary>'
                        ),
                    )
                total += 1
            for heading in expected["closed"]:
                with self.subTest(view=view_id, heading=heading, state="closed"):
                    self.assertRegex(
                        chunk,
                        re.compile(
                            r'<details class="panel customizer-disclosure"'
                            r'(?: [^>]*)?>\s*'
                            rf'<summary><h2>{re.escape(heading)}</h2></summary>'
                        ),
                    )
                    self.assertNotRegex(
                        chunk,
                        re.compile(
                            r'<details class="panel customizer-disclosure" open>'
                            rf'\s*<summary><h2>{re.escape(heading)}</h2></summary>'
                        ),
                    )
                total += 1

        self.assertEqual(total, 25)
        self.assertEqual(
            self.markup.count('<details class="panel customizer-disclosure'),
            total,
        )
        self.assertEqual(self.markup.count("</details>"), total)

    def test_action_panels_remain_directly_available(self) -> None:
        self.assertIn('<div class="panel profile-panel">', self.markup)
        self.assertIn('<div class="panel social-grouped-accounts-panel">', self.markup)
        self.assertEqual(self.markup.count("<h2>Social accounts</h2>"), 2)
        self.assertEqual(self.markup.count("<h2>OBS browser source</h2>"), 11)

    def test_closed_disclosures_are_compact_and_have_clear_toggles(self) -> None:
        self.assertIn(".customizer-disclosure:not([open])", self.styles)
        self.assertIn('content: "+";', self.styles)
        self.assertIn('content: "-";', self.styles)
        self.assertIn("border-color: var(--accent);", self.styles)


if __name__ == "__main__":
    unittest.main()
