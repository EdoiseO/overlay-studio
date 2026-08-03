from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class OverlayReorderingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (ROOT_DIR / "studio" / "app.js").read_text(
            encoding="utf-8"
        )
        cls.styles = (ROOT_DIR / "studio" / "app.css").read_text(
            encoding="utf-8"
        )
        cls.desktop = (ROOT_DIR / "overlay_studio.pyw").read_text(
            encoding="utf-8"
        )

    def test_library_cards_use_a_dedicated_drag_handle(self) -> None:
        self.assertIn('handle.className = "card-drag-handle"', self.script)
        self.assertIn("handle.draggable = true", self.script)
        self.assertIn('handle.title = "Drag to reorder"', self.script)
        self.assertIn(".card-drag-grip", self.styles)
        self.assertIn(".overlay-card.drop-before", self.styles)
        self.assertIn(".overlay-card.drop-after", self.styles)

    def test_drag_and_keyboard_paths_persist_the_complete_order(self) -> None:
        self.assertIn(
            'callApi("reorder_overlay_instances", orderedIds)',
            self.script,
        )
        self.assertIn(
            'overlayGrid.addEventListener("dragstart", beginOverlayCardDrag)',
            self.script,
        )
        self.assertIn(
            'overlayGrid.addEventListener("drop", dropOverlayCard)',
            self.script,
        )
        self.assertIn(
            'overlayGrid.addEventListener("keydown", moveOverlayCardWithKeyboard)',
            self.script,
        )
        self.assertIn("def reorder_overlay_instances(", self.desktop)


if __name__ == "__main__":
    unittest.main()
