from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")


class PngExportPartialUiTests(unittest.TestCase):
    def test_partial_result_is_not_collapsed_into_total_failure(self) -> None:
        perform_start = SCRIPT.index("async function performPngExport()")
        perform_end = SCRIPT.index(
            "function setCustomizerPreviewExpanded",
            perform_start,
        )
        perform_source = SCRIPT[perform_start:perform_end]

        self.assertIn(
            "if (!saved?.ok && !isPartialPngExportResult(saved))",
            perform_source,
        )
        partial_position = perform_source.index(
            "if (isPartialPngExportResult(saved))",
        )
        success_position = perform_source.index(
            'setPngExportNotice(\n    "success"',
        )
        self.assertLess(partial_position, success_position)

    def test_partial_result_shows_warning_file_list_and_folder_action(self) -> None:
        helper_start = SCRIPT.index("function showPartialPngExportResult")
        helper_end = SCRIPT.index("function pngExportDestination", helper_start)
        helper_source = SCRIPT[helper_start:helper_end]

        self.assertIn('setPngExportNotice("warning", title, detail)', helper_source)
        self.assertIn("Saved files:", helper_source)
        self.assertIn("Use Open folder to review them.", helper_source)
        self.assertIn("pngExportSavedFileNames(result)", helper_source)
        self.assertIn("showToast(title)", helper_source)


if __name__ == "__main__":
    unittest.main()
