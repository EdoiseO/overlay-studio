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


if __name__ == "__main__":
    unittest.main()
