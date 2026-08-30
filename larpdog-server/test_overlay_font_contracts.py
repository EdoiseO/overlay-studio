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
        filename = "Minecraftia-Regular.ttf"
        self.assertTrue((FONT_STYLESHEET_PATH.parent / filename).is_file())
        self.assertIn(filename, FONT_STYLESHEET)
        self.assertTrue(
            (
                FONT_STYLESHEET_PATH.parent
                / "licenses"
                / "minecraftia-README.txt"
            ).is_file()
        )
        self.assertIn("font-family: 'Minecraftia'", FONT_STYLESHEET)

    def test_minecraft_time_tools_use_bundled_minecraft_typeface(self) -> None:
        shared_styles = (ROOT_DIR / "assets" / "minecraft-time.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('font-family: "Minecraftia"', shared_styles)
        self.assertIn("font-synthesis: none", shared_styles)
        self.assertIn("font-size: clamp(48px, 8.8vw, 72px)", shared_styles)
        self.assertIn("overflow: visible", shared_styles)
        self.assertIn(".time-value { font-size: 48px; }", shared_styles)
        self.assertNotIn("Pixelify Sans", shared_styles)
        for filename in (
            "minecraft-clock-line.html",
            "minecraft-countdown-line.html",
            "minecraft-stopwatch-line.html",
        ):
            with self.subTest(overlay=filename):
                source = (ROOT_DIR / "overlays" / filename).read_text(
                    encoding="utf-8"
                )
                self.assertIn("/assets/fonts/overlay-fonts.css", source)
                self.assertIn("/assets/minecraft-time.css", source)

        for filename in (
            "minecraft-clock.html",
            "minecraft-countdown.html",
            "minecraft-stopwatch.html",
        ):
            with self.subTest(removed_overlay=filename):
                self.assertFalse((ROOT_DIR / "overlays" / filename).exists())

    def test_minecraft_spotify_uses_the_local_minecraftia_font(self) -> None:
        source = (
            ROOT_DIR / "overlays" / "minecraft-spotify.html"
        ).read_text(encoding="utf-8")

        self.assertIn("/assets/fonts/overlay-fonts.css", source)
        self.assertIn('font-family: "Minecraftia"', source)
        self.assertIn("font-synthesis: none", source)
        self.assertNotIn("fonts.googleapis.com", source)

    def test_minecraft_clock_line_is_transparent_and_single_row(self) -> None:
        overlay = (ROOT_DIR / "overlays" / "minecraft-clock-line.html").read_text(
            encoding="utf-8"
        )
        line_styles = (
            ROOT_DIR / "assets" / "minecraft-time-line.css"
        ).read_text(encoding="utf-8")
        shared_styles = (
            ROOT_DIR / "assets" / "minecraft-time.css"
        ).read_text(encoding="utf-8")
        self.assertIn('overlayType: "minecraft-clock-line"', overlay)
        self.assertIn('layout: "line"', overlay)
        self.assertIn("background: none", line_styles)
        self.assertIn("border: 0", line_styles)
        self.assertIn("display: flex", line_styles)
        self.assertIn("align-items: center", line_styles)
        self.assertIn("--line-main-size: clamp(18px, 2.45vw, 24px)", line_styles)
        self.assertIn("--line-secondary-size", line_styles)
        self.assertIn(
            "--line-secondary-size: clamp(14px, 1.9vw, 18px)", line_styles
        )
        self.assertNotIn("--line-secondary-size: var(--line-main-size)", line_styles)
        self.assertIn("--line-divider-height", line_styles)
        self.assertIn(
            "--line-divider-height: var(--line-secondary-size)", line_styles
        )
        self.assertIn("--line-main-size: clamp(11px, 3.5vw, 14px)", line_styles)
        self.assertIn(
            "--line-secondary-size: clamp(9.5px, 3vw, 12px)", line_styles
        )
        self.assertEqual(overlay.count('class="line-divider'), 3)
        self.assertIn("height: var(--line-divider-height)", line_styles)
        self.assertIn("--digit-shadow", shared_styles)
        self.assertIn('"digitShadow"', overlay)
        self.assertIn("white-space: nowrap", line_styles)

        for overlay_type in (
            "minecraft-countdown-line",
            "minecraft-stopwatch-line",
        ):
            with self.subTest(overlay_type=overlay_type):
                source = (
                    ROOT_DIR / "overlays" / f"{overlay_type}.html"
                ).read_text(encoding="utf-8")
                self.assertIn('layout: "line"', source)
                self.assertIn("/assets/minecraft-time-line.css", source)
                self.assertEqual(source.count('class="line-divider'), 3)

    def test_minecraft_catalog_timer_preview_can_run_a_bounded_demo(self) -> None:
        runtime = (ROOT_DIR / "assets" / "minecraft-time.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('query.has("demoSeconds")', runtime)
        self.assertIn('query.get("demoRunning") === "1"', runtime)
        self.assertIn('query.get("demoMinimal") === "1"', runtime)
        self.assertIn('clamp(query.get("demoSeconds"), 1, 359999)', runtime)

    def test_minecraft_minimal_timers_put_green_detail_before_time(self) -> None:
        runtime = (ROOT_DIR / "assets" / "minecraft-time.js").read_text(
            encoding="utf-8"
        )
        line_styles = (
            ROOT_DIR / "assets" / "minecraft-time-line.css"
        ).read_text(encoding="utf-8")
        self.assertIn('"compact-timer"', runtime)
        self.assertIn("const compactTimer", runtime)
        self.assertIn("finished && compactTimer", runtime)
        self.assertIn('"TIME REMAINING" : "TIME ELAPSED"', runtime)
        self.assertIn(
            ".minecraft-time-line.compact-timer #timeDetail", line_styles
        )
        self.assertIn(
            ".minecraft-time-line.compact-timer .time-value", line_styles
        )
        self.assertIn(
            ".minecraft-time-line.compact-timer .tool-zone", line_styles
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
