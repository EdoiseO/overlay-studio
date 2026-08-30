import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class PaletteCustomizerTests(unittest.TestCase):
    COLOR_FAMILIES = {
        "Spotify": ("colorA", "colorB", "colorC"),
        "Minecraft Spotify": (
            "minecraftSpotifyAccentColor",
            "minecraftSpotifyShellColor",
            "minecraftSpotifyTextColor",
        ),
        "Goal Ring": ("goalColor", "goalTrack", "goalLabelColor"),
        "Goal Bar": (
            "goalBarColor",
            "goalBarShellColor",
            "goalBarTrack",
            "goalBarLabelColor",
        ),
        "Goal Pill": (
            "goalPillColor",
            "goalPillShellColor",
            "goalPillTrack",
            "goalPillLabelColor",
        ),
        "Minecraft Time Tools": (
            "timeToolAccentColor",
            "timeToolShellColor",
            "timeToolTextColor",
        ),
        "Rivals Rank": (
            "rivalsShellColor",
            "rivalsTextColor",
            "rivalsAccentColor",
            "rivalsWinColor",
            "rivalsLossColor",
        ),
        "Platform Badge": ("platformBadgeColor",),
        "Social Bar and Rotator": (
            "socialColor",
            "socialShellColor",
            "socialTextColor",
        ),
        "Match Record": ("counterAccent",),
    }
    SOCIAL_GROUPED_COLORS = (
        "socialGroupedOuterColor",
        "socialGroupedEdgeColor",
        "socialGroupedTextColor",
        "socialGroupedTextOuterColor",
        "socialGroupedTextEdgeColor",
        "socialGroupedLabelColor",
        "socialGroupedBaseColor",
        "socialGroupedLegacyTextEdgeColor",
        "socialGroupedShadowColor",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.markup = (ROOT_DIR / "studio" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.styles = (ROOT_DIR / "studio" / "app.css").read_text(
            encoding="utf-8"
        )

    def test_every_color_input_is_unique_named_and_accessible(self) -> None:
        color_ids = tuple(
            control_id
            for family in self.COLOR_FAMILIES.values()
            for control_id in family
        ) + self.SOCIAL_GROUPED_COLORS

        self.assertEqual(len(color_ids), 39)
        self.assertEqual(self.markup.count('type="color"'), len(color_ids))

        for control_id in color_ids:
            with self.subTest(control_id=control_id):
                self.assertEqual(self.markup.count(f'id="{control_id}"'), 1)
                self.assertRegex(
                    self.markup,
                    re.compile(
                        rf'<input(?=[^>]*id="{re.escape(control_id)}")'
                        rf'(?=[^>]*type="color")'
                        rf'(?=[^>]*aria-label="[^"]+")[^>]*>'
                    ),
                )
                self.assertEqual(
                    self.markup.count(f'id="{control_id}Label"'),
                    1,
                )

    def test_each_fixed_overlay_palette_has_context_and_descriptions(self) -> None:
        sections = re.findall(
            r'<section class="palette-detail-section"[^>]*>(.*?)</section>',
            self.markup,
            re.DOTALL,
        )

        for family_name, color_ids in self.COLOR_FAMILIES.items():
            with self.subTest(family=family_name):
                matching = [
                    section
                    for section in sections
                    if all(f'id="{control_id}"' in section for control_id in color_ids)
                ]
                self.assertEqual(len(matching), 1)
                section = matching[0]
                self.assertIn("<h3", section)
                self.assertIn("<p>", section)
                self.assertGreaterEqual(
                    section.count('class="palette-detail-copy"'),
                    len(color_ids),
                )

    def test_palette_component_is_shared_and_responsive(self) -> None:
        self.assertNotIn('class="palette-control', self.markup)
        self.assertNotIn(".social-color-section", self.styles)
        self.assertIn(".palette-detail-section", self.styles)
        self.assertIn(".palette-detail-heading", self.styles)
        self.assertIn(".palette-detail-control", self.styles)
        self.assertIn("@container (max-width: 330px)", self.styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.styles)


if __name__ == "__main__":
    unittest.main()
