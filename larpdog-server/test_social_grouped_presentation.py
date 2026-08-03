import json
import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class SocialGroupedPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (
            ROOT_DIR / "overlays" / "social-grouped.html"
        ).read_text(encoding="utf-8")
        cls.shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        cls.studio_markup = (
            ROOT_DIR / "studio" / "index.html"
        ).read_text(encoding="utf-8")
        cls.studio_script = (
            ROOT_DIR / "studio" / "app.js"
        ).read_text(encoding="utf-8")
        cls.studio_styles = (
            ROOT_DIR / "studio" / "app.css"
        ).read_text(encoding="utf-8")

    def test_manifest_exposes_continuous_layout_and_studio_view(self) -> None:
        self.assertIn('"groupGap"', self.source)
        self.assertIn('"separate"', self.source)
        self.assertIn('"studioView": "socialGroupedView"', self.source)

    def test_default_renderer_builds_one_three_layer_sticker(self) -> None:
        self.assertIn("function buildMergedSticker(groups, settings)", self.source)
        self.assertIn('class: "out"', self.source)
        self.assertIn('class: "edge"', self.source)
        self.assertIn('class: "fills"', self.source)
        self.assertRegex(
            self.source,
            re.compile(
                r"svg\.append\(layers\.out, layers\.edge, layers\.fills\)"
            ),
        )
        self.assertIn('"data-group": groupIndex', self.source)
        self.assertIn("if (!settings.tile && !settings.separate)", self.source)
        self.assertIn("icons.append(buildMergedSticker(groups, settings))", self.source)

    def test_renderer_uses_shared_platform_metadata_without_shared_svg(self) -> None:
        self.assertIn("../assets/social-platforms.js", self.source)
        self.assertIn("const PLATFORMS = social.PLATFORMS", self.source)
        self.assertNotIn("social.createGlyph", self.source)
        self.assertNotIn("const PLATFORMS = {", self.source)
        self.assertIn("opticalTransform(meta)", self.source)

    def test_brand_tile_variations_keep_readable_platform_art(self) -> None:
        self.assertIn('["squircle", "round", "square"]', self.source)
        self.assertIn("meta.tileInk", self.source)
        self.assertIn("meta.tileStroke", self.source)
        self.assertIn('tileInk: "#ffffff"', self.shared)
        self.assertIn('tileStroke: "#101014"', self.shared)

    def test_layout_keeps_all_font_metric_passes(self) -> None:
        self.assertIn("pack();", self.source)
        self.assertIn("requestAnimationFrame(() => pack())", self.source)
        self.assertIn("document.fonts.ready", self.source)
        self.assertIn("svg.style.aspectRatio", self.source)

    def test_studio_gathers_every_manifest_setting(self) -> None:
        manifest_match = re.search(
            r'<script type="application/json" id="overlay-manifest">\s*'
            r"(\{.*?\})\s*</script>",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(manifest_match)
        manifest = json.loads(manifest_match.group(1))
        gather = self.studio_script.split(
            "function gatherSocialGroupedSettings()",
            maxsplit=1,
        )[1].split("function applySocialGroupedPreset", maxsplit=1)[0]

        for setting in manifest["settings"]:
            with self.subTest(setting=setting):
                self.assertRegex(
                    gather,
                    re.compile(rf"(?m)^\s*{re.escape(setting)}(?:\s*:|\s*,)"),
                )

    def test_studio_progressively_reveals_advanced_controls(self) -> None:
        controls = {
            "round": "socialGroupedRound",
            "overlap": "socialGroupedOverlap",
            "nameGap": "socialGroupedNameGap",
            "textNudge": "socialGroupedTextNudge",
            "letterSpacing": "socialGroupedLetterSpacing",
            "color": "socialGroupedBaseColor",
            "textEdge": "socialGroupedLegacyTextEdgeColor",
            "outline": "socialGroupedOutline",
            "tileOutline": "socialGroupedTileOutline",
            "gap": "socialGroupedGap",
            "align": "socialGroupedAlign",
            "label": "socialGroupedLabel",
            "labelSize": "socialGroupedLabelSize",
            "labelGap": "socialGroupedLabelGap",
            "labelColor": "socialGroupedLabelColor",
            "direction": "socialGroupedDirection",
            "wrap": "socialGroupedWrap",
            "padding": "socialGroupedPadding",
            "shadowX": "socialGroupedShadowX",
            "shadowY": "socialGroupedShadowY",
            "shadowColor": "socialGroupedShadowColor",
        }
        gather = self.studio_script.split(
            "function gatherSocialGroupedSettings()",
            maxsplit=1,
        )[1].split("function applySocialGroupedPreset", maxsplit=1)[0]

        for setting, control_id in controls.items():
            with self.subTest(setting=setting):
                self.assertIn(f'id="{control_id}"', self.studio_markup)
                self.assertIn(f'byId("{control_id}")', gather)

        self.assertIn(
            'id="socialGroupedTileFineTuningSection" hidden',
            self.studio_markup,
        )
        self.assertIn(
            'id="socialGroupedSplitLayoutControls" hidden',
            self.studio_markup,
        )
        self.assertIn(
            'const split = tile || byId("socialGroupedSeparate").checked',
            self.studio_script,
        )

    def test_studio_explains_and_groups_social_color_controls(self) -> None:
        color_ids = (
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

        for control_id in color_ids:
            with self.subTest(control_id=control_id):
                self.assertEqual(
                    self.studio_markup.count(f'id="{control_id}"'),
                    1,
                )

        self.assertIn("Sticker outline colors", self.studio_markup)
        self.assertIn(
            "The thin line between the outer band and each logo.",
            self.studio_markup,
        )
        self.assertIn(
            "The main color used for each social handle.",
            self.studio_markup,
        )
        self.assertIn(
            "Colors the soft effect behind the full sticker.",
            self.studio_markup,
        )
        self.assertIn(".social-color-section", self.studio_styles)
        self.assertIn(".social-color-control", self.studio_styles)


if __name__ == "__main__":
    unittest.main()
