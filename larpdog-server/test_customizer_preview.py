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
        }

        for overlay_type, path in overlay_sources.items():
            with self.subTest(overlay_type=overlay_type):
                source = path.read_text(encoding="utf-8")
                self.assertIn("overlay-studio-draft", source)
                self.assertIn(overlay_type, source)


if __name__ == "__main__":
    unittest.main()
