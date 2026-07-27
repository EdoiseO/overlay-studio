import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class GoalBarPresentationTests(unittest.TestCase):
    def test_horizontal_layout_hides_the_icon_badge(self) -> None:
        source = (ROOT_DIR / "overlays" / "goal-bar.html").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            ".goal:not(.vertical) .badge { display: none !important; }",
            source,
        )
        self.assertNotIn("M4 6h11a2 2 0 0 1 2 2v8", source)

    def test_shell_and_bar_use_separate_corner_radii(self) -> None:
        source = (ROOT_DIR / "overlays" / "goal-bar.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("border-radius: var(--shell-radius)", source)
        self.assertEqual(
            source.count("border-radius: var(--bar-radius)"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
