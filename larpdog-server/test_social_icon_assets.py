import struct
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT_DIR / "assets" / "social-icons"
APPROVED_ICONS = (
    "bluesky-symbol.png",
    "bluesky-tile.png",
    "discord-symbol.png",
    "facebook-round.png",
    "instagram-tile.png",
    "kick-symbol.png",
    "kick-tile.png",
    "linkedin-tile.png",
    "reddit-symbol.png",
    "reddit-tile.png",
    "telegram-round.png",
    "threads-symbol.png",
    "threads-tile.png",
    "tiktok-symbol.png",
    "twitch-symbol.png",
    "whatsapp-tile.png",
    "x-symbol.png",
    "youtube-tile.png",
)


class SocialIconAssetTests(unittest.TestCase):
    def test_approved_icons_are_square_rgba_pngs(self) -> None:
        for filename in APPROVED_ICONS:
            with self.subTest(filename=filename):
                payload = (ICON_DIR / filename).read_bytes()
                self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
                width, height, bit_depth, color_type = struct.unpack(
                    ">IIBB",
                    payload[16:26],
                )
                self.assertEqual((width, height), (512, 512))
                self.assertEqual(bit_depth, 8)
                self.assertIn(color_type, (4, 6), "PNG must retain an alpha channel")

    def test_shared_metadata_only_references_packaged_icons(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        for filename in APPROVED_ICONS:
            with self.subTest(filename=filename):
                self.assertIn(f'/assets/social-icons/{filename}', shared)

    def test_renderers_keep_vector_fallbacks_and_shape_controls(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        bar = (ROOT_DIR / "overlays" / "social.html").read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")
        grouped = (
            ROOT_DIR / "overlays" / "social-grouped.html"
        ).read_text(encoding="utf-8")

        self.assertIn("function createVectorGlyph", shared)
        self.assertIn("image.replaceWith(createVectorGlyph", shared)
        self.assertIn('settings.iconShape === "rounded"', bar)
        self.assertIn('settings.iconShape === "rounded"', rotator)
        self.assertIn('settings.shape === "squircle"', grouped)
        self.assertIn("buildVectorTileArtwork", grouped)


if __name__ == "__main__":
    unittest.main()
