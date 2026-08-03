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

    def test_shared_metadata_uses_the_approved_vector_set(self) -> None:
        self.assertIn('const SIMPLE_ICONS_VERSION = "16.28.0"', self.shared)
        self.assertIn("SIMPLE_ICONS_VERSION,", self.shared)
        self.assertEqual(self.shared.count('source: "simple-icons"'), 14)
        self.assertEqual(self.shared.count('source: "fallback"'), 2)
        self.assertNotIn("tileAsset", self.shared)
        self.assertNotIn("symbolAsset", self.shared)

    def test_builtin_renderers_only_use_inline_vectors(self) -> None:
        self.assertIn("function createVectorGlyph", self.shared)
        self.assertIn("return createVectorGlyph(meta, branded, bare);", self.shared)
        self.assertNotIn("data-social-asset-kind", self.bar)
        self.assertNotIn("data-social-asset-kind", self.rotator)
        self.assertNotIn("asset-tile", self.bar)
        self.assertNotIn("asset-tile", self.rotator)
        self.assertNotIn("asset-tile", self.grouped)
        self.assertNotIn("new Image()", self.grouped)
        self.assertIn("buildVectorTileArtwork", self.grouped)

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


if __name__ == "__main__":
    unittest.main()
