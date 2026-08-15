from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
STUDIO_MARKUP = (ROOT_DIR / "studio" / "index.html").read_text(
    encoding="utf-8"
)
SHARED_SOCIAL_SOURCE = (
    ROOT_DIR / "assets" / "social-platforms.js"
).read_text(encoding="utf-8")
FONT_STYLESHEET_PATH = ROOT_DIR / "assets" / "fonts" / "overlay-fonts.css"
FONT_STYLESHEET = FONT_STYLESHEET_PATH.read_text(encoding="utf-8")

FONT_CASES = (
    ("goalFont", "goal.html", None),
    ("goalBarFont", "goal-bar.html", None),
    ("goalPillFont", "goal-pill.html", None),
    ("socialFont", "social.html", SHARED_SOCIAL_SOURCE),
    ("socialFont", "social-rotator.html", SHARED_SOCIAL_SOURCE),
    ("socialGroupedFont", "social-grouped.html", SHARED_SOCIAL_SOURCE),
    ("rivalsFont", "rivals-rank.html", None),
    ("platformBadgeFont", "platform-badge.html", SHARED_SOCIAL_SOURCE),
)
WEB_FONTS = {
    "anton": "Anton",
    "archivo": "Archivo Black",
    "montserrat": "Montserrat",
    "nunito": "Nunito",
    "poppins": "Poppins",
    "round": "Fredoka",
}


def select_options(control_id: str) -> set[str]:
    match = re.search(
        rf'<select id="{re.escape(control_id)}">(.*?)</select>',
        STUDIO_MARKUP,
        re.DOTALL,
    )
    if not match:
        return set()
    return set(re.findall(r'<option value="([^"]+)"', match.group(1)))


def font_keys(source: str) -> set[str]:
    match = re.search(
        r"const FONTS\s*=\s*\{(.*?)\n\s*\};",
        source,
        re.DOTALL,
    )
    if not match:
        return set()
    return set(
        re.findall(
            r"^\s*([a-z][a-z0-9-]*):",
            match.group(1),
            re.MULTILINE,
        )
    )


class OverlayFontContractTests(unittest.TestCase):
    def test_customizer_options_are_supported_by_their_renderers(self) -> None:
        for control_id, filename, shared_source in FONT_CASES:
            with self.subTest(control=control_id, overlay=filename):
                overlay = (ROOT_DIR / "overlays" / filename).read_text(
                    encoding="utf-8"
                )
                supported = font_keys(shared_source or overlay)
                offered = select_options(control_id)
                self.assertTrue(offered)
                self.assertTrue(supported)
                self.assertEqual(offered - supported, set())

    def test_renderers_load_the_local_font_bundle(self) -> None:
        for _control_id, filename, shared_source in FONT_CASES:
            with self.subTest(overlay=filename):
                overlay = (ROOT_DIR / "overlays" / filename).read_text(
                    encoding="utf-8"
                )
                supported = font_keys(shared_source or overlay)
                self.assertIn("/assets/fonts/overlay-fonts.css", overlay)
                for key in supported & WEB_FONTS.keys():
                    self.assertIn(
                        f"font-family: '{WEB_FONTS[key]}'",
                        FONT_STYLESHEET,
                        f"the local bundle does not define {key}",
                    )

    def test_font_bundle_has_no_network_dependency(self) -> None:
        self.assertNotIn("https://", FONT_STYLESHEET)
        for overlay_path in (ROOT_DIR / "overlays").glob("*.html"):
            source = overlay_path.read_text(encoding="utf-8")
            self.assertNotIn("fonts.googleapis.com", source, overlay_path.name)
            self.assertNotIn("fonts.gstatic.com", source, overlay_path.name)

    def test_every_bundled_font_file_and_license_exists(self) -> None:
        font_urls = re.findall(r"url\(\./([^\)]+\.woff2)\)", FONT_STYLESHEET)
        self.assertEqual(len(font_urls), 39)
        for filename in font_urls:
            with self.subTest(font=filename):
                self.assertTrue((FONT_STYLESHEET_PATH.parent / filename).is_file())
        for family in WEB_FONTS:
            license_name = {
                "archivo": "archivoblack",
                "round": "fredoka",
            }.get(family, family)
            with self.subTest(license=family):
                self.assertTrue(
                    (
                        FONT_STYLESHEET_PATH.parent
                        / "licenses"
                        / f"{license_name}-OFL.txt"
                    ).is_file()
                )

    def test_font_bundle_is_in_both_frozen_builds(self) -> None:
        desktop_build = (ROOT_DIR / "build-app.bat").read_text(encoding="utf-8")
        server_spec = (
            ROOT_DIR / "larpdog-server" / "overlay-studio-server.spec"
        ).read_text(encoding="utf-8")
        self.assertIn("assets\\fonts;assets\\fonts", desktop_build)
        self.assertIn("../assets/fonts", server_spec)


if __name__ == "__main__":
    unittest.main()
