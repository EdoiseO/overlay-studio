from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "larpdog-server"))

from overlay_manifest import scan_overlay_manifests  # noqa: E402


RENDERER = (ROOT_DIR / "assets" / "overlay-png-export.js").read_text(
    encoding="utf-8"
)
SOCIAL_GROUPED = (ROOT_DIR / "overlays" / "social-grouped.html").read_text(
    encoding="utf-8"
)
EXPORT_SCRIPT = '<script src="/assets/overlay-png-export.js"></script>'


class PngExportRendererTests(unittest.TestCase):
    def test_only_manifest_approved_overlays_load_the_renderer(self) -> None:
        manifests = scan_overlay_manifests(ROOT_DIR / "overlays")
        for manifest in manifests:
            source = (
                ROOT_DIR / "overlays" / f"{manifest['type']}.html"
            ).read_text(encoding="utf-8")
            with self.subTest(overlay=manifest["type"]):
                self.assertEqual(
                    EXPORT_SCRIPT in source,
                    manifest["exportable"],
                )

    def test_renderer_has_bounded_output_sizes(self) -> None:
        self.assertIn("new Set([256, 512, 1024])", RENDERER)
        self.assertIn("const MAX_OUTPUT_WIDTH = 8192", RENDERER)
        self.assertIn("const MAX_OUTPUT_PIXELS = 12 * 1024 * 1024", RENDERER)
        self.assertIn("OUTPUT_HEIGHTS.has(targetHeight)", RENDERER)

    def test_renderer_neutralizes_preview_scale_and_restores_it(self) -> None:
        self.assertIn('rootStyle.setProperty("--scale", "1")', RENDERER)
        self.assertIn('rootStyle.setProperty("--fit-scale", "1")', RENDERER)
        self.assertIn("previousScale", RENDERER)
        self.assertIn("previousFitScale", RENDERER)

    def test_renderer_self_contains_fonts_and_images(self) -> None:
        self.assertIn('fontCssUrl = new URL("./fonts/overlay-fonts.css"', RENDERER)
        self.assertIn("await fetchDataUrl(absolute)", RENDERER)
        self.assertIn("async function inlineImages", RENDERER)
        self.assertNotIn("fonts.googleapis.com", RENDERER)
        self.assertNotIn("fonts.gstatic.com", RENDERER)

    def test_renderer_scans_only_edges_and_horizontal_crop_bounds(self) -> None:
        self.assertIn("function alphaRowHasContent", RENDERER)
        self.assertIn("function alphaColumnHasContent", RENDERER)
        self.assertIn("function horizontalAlphaBounds", RENDERER)
        self.assertNotIn("let minY", RENDERER)
        self.assertNotIn("let maxY", RENDERER)
        self.assertIn("bounds.touchesEdge", RENDERER)
        self.assertIn("An effect reaches the export edge", RENDERER)

    def test_social_grouped_padding_includes_signed_shadow_offsets(self) -> None:
        self.assertIn("settings.shadowBlur * 2", SOCIAL_GROUPED)
        self.assertIn("base + Math.max(0, -settings.shadowY)", SOCIAL_GROUPED)
        self.assertIn("base + Math.max(0, settings.shadowX)", SOCIAL_GROUPED)
        self.assertIn("base + Math.max(0, settings.shadowY)", SOCIAL_GROUPED)
        self.assertIn("base + Math.max(0, -settings.shadowX)", SOCIAL_GROUPED)

    def test_renderer_uses_the_studio_message_contract(self) -> None:
        self.assertIn('"overlay-studio-export-request"', RENDERER)
        self.assertIn('"overlay-studio-export-result"', RENDERER)
        self.assertIn("event.source !== window.parent", RENDERER)
        self.assertIn("request.overlayType !== registration.overlayType", RENDERER)
        self.assertIn("window.parent.postMessage(response, event.origin)", RENDERER)
        self.assertNotIn('window.parent.postMessage(response, "*")', RENDERER)


if __name__ == "__main__":
    unittest.main()
