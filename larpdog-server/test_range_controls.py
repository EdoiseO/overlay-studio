import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class RangeControlContractTests(unittest.TestCase):
    def test_every_slider_has_an_editable_value_source(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        sliders = re.findall(
            r'<input id="([^"]+)" type="range" min="([^"]+)" max="([^"]+)"',
            markup,
        )
        outputs = set(re.findall(r'<output id="([^"]+)">', markup))

        self.assertGreaterEqual(len(sliders), 20)
        for slider_id, minimum, maximum in sliders:
            self.assertTrue(minimum)
            self.assertTrue(maximum)
            self.assertIn(f"{slider_id}Output", outputs)

    def test_range_enhancement_shows_limits_and_safely_commits_values(self) -> None:
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT_DIR / "studio" / "app.css").read_text(encoding="utf-8")

        self.assertIn("function initializeRangeControls()", script)
        self.assertIn('minimum.textContent = `Min ${Number(slider.min)}`', script)
        self.assertIn('maximum.textContent = `Max ${Number(slider.max)}`', script)
        self.assertIn('editor.type = "number"', script)
        self.assertIn("editor.min = slider.min", script)
        self.assertIn("editor.max = slider.max", script)
        self.assertIn("editor.step = slider.step", script)
        self.assertIn("normalizeRangeValue(slider, editor.value)", script)
        self.assertIn('event.key === "Enter"', script)
        self.assertIn('event.key === "Escape"', script)
        self.assertIn("initializeRangeControls();", script)
        self.assertIn(".range-limits", styles)
        self.assertIn(".range-value-input", styles)


if __name__ == "__main__":
    unittest.main()
