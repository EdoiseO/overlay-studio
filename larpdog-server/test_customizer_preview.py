import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class CustomizerPreviewContractTests(unittest.TestCase):
    def test_studio_has_one_shared_draft_preview(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertEqual(markup.count('id="customizerPreviewFrame"'), 1)
        self.assertEqual(
            markup.count('id="customizerPreviewExpandButton"'),
            1,
        )
        self.assertIn('type: "overlay-studio-draft"', script)
        self.assertIn('url.searchParams.set("customizer", "1")', script)
        self.assertIn("setCustomizerPreviewExpanded", script)

    def test_customizer_scroll_and_expansion_have_separate_layouts(self) -> None:
        styles = (ROOT_DIR / "studio" / "app.css").read_text(encoding="utf-8")

        self.assertIn("width: calc(100% - 324px)", styles)
        self.assertIn("scrollbar-gutter: stable", styles)
        self.assertIn(".customizer-preview-dock.expanded", styles)

    def test_goal_currency_fields_use_shared_typeahead_selects(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertEqual(markup.count("data-currency-select"), 3)
        self.assertIn('["Canadian Dollar (C$)", "C$"]', script)
        self.assertIn("initializeCurrencySelects", script)
        self.assertIn("setCurrencySymbol", script)

    def test_each_customizable_overlay_accepts_drafts(self) -> None:
        overlay_sources = {
            "larpdog-dance": ROOT_DIR / "overlay-studio.html",
            "spotify": ROOT_DIR / "overlay-studio.html",
            "now-playing-flow": ROOT_DIR / "overlays" / "now-playing-flow.html",
            "goal": ROOT_DIR / "overlays" / "goal.html",
            "goal-bar": ROOT_DIR / "overlays" / "goal-bar.html",
            "goal-pill": ROOT_DIR / "overlays" / "goal-pill.html",
            "win-loss": ROOT_DIR / "overlays" / "win-loss.html",
            "social": ROOT_DIR / "overlays" / "social.html",
            "social-rotator": ROOT_DIR / "overlays" / "social-rotator.html",
        }
        shared_social = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")

        for overlay_type, path in overlay_sources.items():
            with self.subTest(overlay_type=overlay_type):
                source = path.read_text(encoding="utf-8")
                if overlay_type in {"social", "social-rotator"}:
                    source += shared_social
                self.assertIn("overlay-studio-draft", source)
                self.assertIn(overlay_type, source)

    def test_social_overlays_share_bounded_platform_runtime(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        bar = (
            ROOT_DIR / "overlays" / "social.html"
        ).read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")

        self.assertIn('"threads"', shared)
        self.assertIn('"bluesky"', shared)
        self.assertIn("enabled >= 8", shared)
        self.assertIn('get("customizer") === "1"', shared)
        self.assertIn("event.source !== window.parent", shared)
        self.assertNotIn("event.origin !== location.origin", shared)
        self.assertIn("social.createGlyph", bar)
        self.assertIn("social.createGlyph", rotator)
        self.assertIn("symbols-only", bar)
        self.assertIn("symbols-only", rotator)
        self.assertIn("iconBackground", shared)
        self.assertIn("content.hidden = accounts.length === 0", bar)
        self.assertIn("content.hidden = accounts.length === 0", rotator)
        self.assertIn('studioView": "socialView"', bar)
        self.assertIn('studioView": "socialView"', rotator)

    def test_social_customizer_uses_compact_account_picker(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="socialPlatformSelect"', markup)
        self.assertIn('id="socialHandleInput"', markup)
        self.assertIn('id="socialAddButton"', markup)
        self.assertIn('id="socialEmptyState"', markup)
        self.assertIn('id="socialIconBackground"', markup)
        self.assertNotIn('data-social-enabled', markup)
        self.assertIn("function addSocialAccount()", script)
        self.assertIn("function socialHandleFromInput(value)", script)
        self.assertIn("remove.dataset.socialRemove = platform.id", script)
        self.assertIn("if (!account.enabled) return", script)

    def test_state_poll_does_not_restart_rotator_draft(self) -> None:
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")
        preview_start = script.index("function renderCustomizerPreview(")
        preview_end = script.index(
            "function fitCardPreviewHost(",
            preview_start,
        )
        preview_function = script[preview_start:preview_end]

        self.assertNotIn("scheduleCustomizerDraft()", preview_function)
        self.assertIn("if (nextKey === settingsKey) return", rotator)

    def test_tiktok_brand_colors_are_readable_on_dark_shell(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        studio = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        match = re.search(
            r'tiktok:\s+\{[^}]*color:\s+"(#[0-9a-f]+)"'
            r'[^}]*surface:\s+"(#[0-9a-f]+)"'
            r'[^}]*ink:\s+"(#[0-9a-f]+)"',
            shared,
        )

        self.assertIsNotNone(match)
        color, surface, ink = match.groups()
        self.assertGreaterEqual(self._contrast_ratio(color, "#141418"), 4.5)
        self.assertGreaterEqual(self._contrast_ratio(surface, ink), 4.5)
        self.assertIn('{ color: "#25f4ee", dx: -1.15, dy: -.7 }', shared)
        self.assertIn('{ color: "#fe2c55", dx: 1.15, dy: .7 }', shared)
        self.assertIn('surface: "#F6F7FB"', studio)
        self.assertIn(
            'shadow: "-1px -1px #25F4EE, 1px 1px #FE2C55"',
            studio,
        )

    def test_social_handles_are_never_ellipsized(self) -> None:
        bar = (
            ROOT_DIR / "overlays" / "social.html"
        ).read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")

        for source in (bar, rotator):
            self.assertNotIn("text-overflow: ellipsis", source)
            self.assertIn("fitToCanvas", source)
            self.assertIn("--fit-scale", source)
        self.assertIn("min-width: max-content", bar)
        self.assertIn("min-width: max-content", rotator)

    @staticmethod
    def _contrast_ratio(first: str, second: str) -> float:
        def luminance(color: str) -> float:
            channels = [
                int(color[index : index + 2], 16) / 255
                for index in (1, 3, 5)
            ]
            linear = [
                value / 12.92
                if value <= 0.04045
                else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return (
                linear[0] * 0.2126
                + linear[1] * 0.7152
                + linear[2] * 0.0722
            )

        brighter, darker = sorted(
            (luminance(first), luminance(second)),
            reverse=True,
        )
        return (brighter + 0.05) / (darker + 0.05)


if __name__ == "__main__":
    unittest.main()
