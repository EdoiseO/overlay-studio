from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class RivalsCustomizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.markup = (ROOT_DIR / "studio" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.script = (ROOT_DIR / "studio" / "app.js").read_text(
            encoding="utf-8"
        )
        cls.overlay = (ROOT_DIR / "overlays" / "rivals-rank.html").read_text(
            encoding="utf-8"
        )

    def test_manifest_and_studio_view_share_the_rivals_contract(self) -> None:
        self.assertIn('"studioView": "rivalsRankView"', self.overlay)
        self.assertIn('id="rivalsRankView"', self.markup)
        self.assertIn('"rivalsRankView"', self.script)
        self.assertIn('instance.type === "rivals-rank"', self.script)
        self.assertIn(
            'return { config: { rivals: gatherRivalsSettings() } };',
            self.script,
        )
        self.assertIn('event.data?.config?.rivals', self.overlay)

    def test_overlay_loads_every_custom_font_offered_by_studio(self) -> None:
        self.assertIn("fonts.googleapis.com/css2", self.overlay)
        for family in (
            "Anton",
            "Archivo+Black",
            "Montserrat",
            "Nunito",
            "Poppins",
        ):
            with self.subTest(family=family):
                self.assertIn(f"family={family}", self.overlay)

    def test_account_linking_is_private_and_separate_from_visual_draft(self) -> None:
        gather_start = self.script.index("function gatherRivalsSettings()")
        gather_end = self.script.index("async function sendRivals", gather_start)
        gather = self.script[gather_start:gather_end]
        self.assertNotIn("rivalsUid", gather)
        self.assertIn('callApi("update_rivals", payload, instance.id)', self.script)
        self.assertRegex(
            self.markup,
            re.compile(
                r'<div data-customizer-passive>.*?id="rivalsUid".*?'
                r'id="resetRivalsSessionButton"',
                re.DOTALL,
            ),
        )

    def test_visual_settings_have_live_preview_and_bounded_controls(self) -> None:
        for control_id in (
            "rivalsLabel",
            "rivalsShowName",
            "rivalsShellColor",
            "rivalsTextColor",
            "rivalsAccentColor",
            "rivalsWinColor",
            "rivalsLossColor",
            "rivalsFont",
            "rivalsWeight",
            "rivalsScale",
            "rivalsCorners",
            "rivalsGlow",
        ):
            with self.subTest(control=control_id):
                self.assertEqual(self.markup.count(f'id="{control_id}"'), 1)
        self.assertIn('id="rivalsScale" type="range" min="0.5" max="1.6"', self.markup)
        self.assertIn('id="rivalsCorners" type="range" min="0" max="40"', self.markup)
        self.assertIn('id="rivalsGlow" type="range" min="0" max="2.5"', self.markup)
        self.assertIn(
            "function renderRivals(state, linked = false, force = false, poll = null)",
            self.script,
        )
        self.assertIn("function gatherRivalsSettings()", self.script)

    def test_rate_limit_status_explains_that_updates_are_paused(self) -> None:
        self.assertIn("/rate limit|updates paused/i", self.script)
        self.assertIn("Linked; updates temporarily paused", self.script)
        self.assertIn('pollStatus === "queued"', self.script)
        self.assertIn("Linked; update queued", self.script)
        self.assertIn("Linked; waiting for first update", self.script)
        self.assertIn("Account state unavailable", self.script)

    def test_refresh_and_unlink_controls_use_the_guarded_rivals_action(self) -> None:
        for control_id in (
            "refreshRivalsButton",
            "unlinkRivalsButton",
            "rivalsRefreshStatus",
        ):
            with self.subTest(control_id=control_id):
                self.assertEqual(self.markup.count(f'id="{control_id}"'), 1)
        self.assertIn('{ action: "refresh" }', self.script)
        self.assertIn('{ action: "unlink" }', self.script)
        self.assertIn("Refresh available in", self.script)
        self.assertIn("Updates paused,", self.script)

    def test_live_overlay_starts_unready_instead_of_showing_demo_rank(
        self,
    ) -> None:
        # render() runs before the first API response, so a live OBS source
        # must not seed the demo Grandmaster card even briefly.
        self.assertIn("ready: previewMode", self.overlay)
        self.assertIn('query.get("preview") === "studio"', self.overlay)
        self.assertIn('query.get("customizer") === "1"', self.overlay)
        self.assertIn('location.protocol === "file:"', self.overlay)
        self.assertNotIn("ready: true", self.overlay)
        self.assertIn("Waiting for rank", self.overlay)
        self.assertIn("No data yet", self.overlay)


if __name__ == "__main__":
    unittest.main()
