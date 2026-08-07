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

FONT_CASES = (
    ("goalFont", "goal.html", None),
    ("goalBarFont", "goal-bar.html", None),
    ("goalPillFont", "goal-pill.html", None),
    ("socialFont", "social.html", SHARED_SOCIAL_SOURCE),
    ("socialFont", "social-rotator.html", SHARED_SOCIAL_SOURCE),
    ("socialGroupedFont", "social-grouped.html", SHARED_SOCIAL_SOURCE),
    ("rivalsFont", "rivals-rank.html", None),
)
WEB_FONTS = {
    "anton": "Anton",
    "archivo": "Archivo+Black",
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

    def test_renderers_load_every_external_font_they_accept(self) -> None:
        for _control_id, filename, shared_source in FONT_CASES:
            with self.subTest(overlay=filename):
                overlay = (ROOT_DIR / "overlays" / filename).read_text(
                    encoding="utf-8"
                )
                supported = font_keys(shared_source or overlay)
                for key in supported & WEB_FONTS.keys():
                    self.assertIn(
                        f"family={WEB_FONTS[key]}",
                        overlay,
                        f"{filename} does not load its {key} font",
                    )


if __name__ == "__main__":
    unittest.main()
