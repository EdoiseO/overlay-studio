import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class SocialIconAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        self.bar = (
            ROOT_DIR / "overlays" / "social.html"
        ).read_text(encoding="utf-8")
        self.rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")
        self.grouped = (
            ROOT_DIR / "overlays" / "social-grouped.html"
        ).read_text(encoding="utf-8")
        self.overlay_readme = (
            ROOT_DIR / "overlays" / "README.md"
        ).read_text(encoding="utf-8")

    def test_shared_metadata_uses_the_approved_vector_set(self) -> None:
        self.assertIn('const SIMPLE_ICONS_VERSION = "16.28.0"', self.shared)
        self.assertIn("SIMPLE_ICONS_VERSION,", self.shared)
        self.assertEqual(self.shared.count('source: "simple-icons"'), 14)
        self.assertEqual(self.shared.count('source: "fallback"'), 2)
        self.assertNotIn("tileAsset", self.shared)
        self.assertNotIn("symbolAsset", self.shared)

    def test_vector_pipeline_has_no_web_served_png_catalog(self) -> None:
        self.assertFalse((ROOT_DIR / "assets" / "social-icons").exists())
        self.assertIn("Built-in social marks are vector-only", self.overlay_readme)
        self.assertNotIn("assets/social-icons/", self.overlay_readme)

    def test_shared_export_is_recursively_frozen(self) -> None:
        self.assertIn(
            "function deepFreeze(value, seen = new WeakSet())",
            self.shared,
        )
        self.assertIn("deepFreeze(value[key], seen);", self.shared)
        self.assertIn("return Object.freeze(value);", self.shared)
        self.assertIn("window.OverlaySocial = deepFreeze({", self.shared)
        self.assertNotIn("window.OverlaySocial = Object.freeze({", self.shared)

    def test_builtin_renderers_only_use_inline_vectors(self) -> None:
        self.assertIn("function createVectorGlyph", self.shared)
        self.assertIn("return createVectorGlyph(meta, branded, bare);", self.shared)
        self.assertIn('svg.setAttribute("fill", "currentColor")', self.shared)
        for page in (self.bar, self.rotator, self.grouped):
            self.assertIn("social-platforms.js?v=2", page)
        self.assertNotIn("data-social-asset-kind", self.bar)
        self.assertNotIn("data-social-asset-kind", self.rotator)
        self.assertNotIn("asset-tile", self.bar)
        self.assertNotIn("asset-tile", self.rotator)
        self.assertNotIn("asset-tile", self.grouped)
        self.assertNotIn("new Image()", self.grouped)
        self.assertIn("buildVectorTileArtwork", self.grouped)

    def test_grouped_merged_renderer_does_not_use_shared_glyph_factory(self) -> None:
        merged_renderer = self.grouped.split(
            "function buildMergedSticker",
            maxsplit=1,
        )[1].split("function buildMergedIcons", maxsplit=1)[0]

        self.assertIn('const svg = svgElement("svg"', merged_renderer)
        self.assertIn("appendLogo(", merged_renderer)
        self.assertNotIn("createGlyph(", merged_renderer)
        self.assertNotIn("createVectorGlyph(", merged_renderer)
        self.assertNotIn("social.createGlyph(", self.grouped)
        self.assertNotIn("social.createVectorGlyph(", self.grouped)

    def test_existing_logo_customization_modes_remain_available(self) -> None:
        for page in (self.bar, self.rotator):
            with self.subTest(page=page[0:40]):
                self.assertIn('"iconShape"', page)
                self.assertIn('"iconBackground"', page)
                self.assertIn('"brand"', page)
                self.assertIn("shape-circle", page)
                self.assertIn("shape-square", page)
                self.assertIn("shape-diamond", page)
                self.assertIn("shape-hex", page)

        self.assertIn('"tile"', self.grouped)
        self.assertIn('"shape"', self.grouped)
        self.assertIn('"brand"', self.grouped)
        self.assertIn('["squircle", "round", "square"]', self.grouped)

    def test_rotator_guards_logo_and_accent_contrast(self) -> None:
        self.assertIn("const ensureContrast =", self.shared)
        self.assertIn("ensureContrast,", self.shared)
        self.assertIn(
            'contrastRatio("#ffffff", background) >= '
            'contrastRatio("#101014", background)',
            self.shared,
        )
        self.assertIn(
            'x:         { name: "X", color: "#101014", bare: "#ffffff"',
            self.shared,
        )
        self.assertIn(
            "social.ensureContrast(bareGlyph, shell, meta?.bare)",
            self.rotator,
        )
        self.assertIn(
            "social.ensureContrast(brand, shell, meta?.bare)",
            self.rotator,
        )
        self.assertIn("color: var(--glyph-color, #ffffff);", self.rotator)
        self.assertIn("fill: currentColor;", self.rotator)


if __name__ == "__main__":
    unittest.main()
