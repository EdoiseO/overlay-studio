from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
MARKUP = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
STYLES = (ROOT_DIR / "studio" / "app.css").read_text(encoding="utf-8")


class PngExportCustomizerTests(unittest.TestCase):
    def test_shared_export_dialog_and_preview_shortcut_are_present(self) -> None:
        for element_id in (
            "pngExportDialog",
            "pngExportHeightOptions",
            "pngExportModeFieldset",
            "pngExportSourceSelect",
            "pngExportNotice",
            "pngExportDestination",
            "openPngExportFolderButton",
            "confirmPngExportButton",
            "customizerPreviewExportButton",
        ):
            self.assertEqual(MARKUP.count(f'id="{element_id}"'), 1)
        self.assertEqual(MARKUP.count("data-open-png-export"), 3)
        self.assertEqual(MARKUP.count("data-png-export-height="), 3)

    def test_export_eligibility_comes_from_the_manifest(self) -> None:
        self.assertIn("manifestFor(instance.type)?.exportable === true", SCRIPT)
        self.assertIn("manifest?.exportable !== true", SCRIPT)
        self.assertNotIn('instance.type === "rivals-rank" && app.pngExport', SCRIPT)
        self.assertNotIn('instance.type === "goal" && app.pngExport', SCRIPT)

    def test_export_uses_bounded_message_contract_and_validates_sender(self) -> None:
        self.assertIn('type: "overlay-studio-export-request"', SCRIPT)
        self.assertIn('message?.type !== "overlay-studio-export-result"', SCRIPT)
        self.assertIn("event.source !== pending.source", SCRIPT)
        self.assertIn("event.origin !== pending.origin", SCRIPT)
        self.assertIn("PNG_EXPORT_TIMEOUT_MS = 30000", SCRIPT)
        self.assertIn("PNG_EXPORT_MAX_DATA_URL_LENGTH", SCRIPT)
        self.assertIn("PNG_EXPORT_HEIGHTS.includes(Number(message.height))", SCRIPT)

    def test_platform_badge_batch_reuses_social_bar_accounts(self) -> None:
        self.assertIn("function socialBarExportSources()", SCRIPT)
        self.assertIn('instance.type === "social"', SCRIPT)
        self.assertIn("materializeInstanceConfig(instance).social?.accounts", SCRIPT)
        self.assertIn('instance.type === "platform-badge" && app.pngExportMode === "batch"', SCRIPT)
        self.assertIn("platform: account.platform", SCRIPT)
        self.assertIn("handle: account.handle", SCRIPT)
        self.assertIn("filename: `${account.platform}.png`", SCRIPT)

    def test_batch_is_rendered_before_one_atomic_writer_call(self) -> None:
        render_position = SCRIPT.index("for (let index = 0; index < plan.entries.length")
        save_position = SCRIPT.index('callApi("save_png_exports"', render_position)
        self.assertGreater(save_position, render_position)
        self.assertIn("rendered.push({ filename: entry.filename, dataUrl: result.png })", SCRIPT)
        self.assertIn(
            "postCustomizerDraftToFrame(\n        customizerDraftMessage(plan.instance, originalDraft)",
            SCRIPT,
        )

    def test_export_controls_have_responsive_production_styles(self) -> None:
        self.assertIn(".png-export-dialog", STYLES)
        self.assertIn(".png-export-height-options", STYLES)
        self.assertIn(".png-export-mode-options", STYLES)
        self.assertIn(".png-export-notice.warning", STYLES)
        self.assertIn(".png-export-notice.success", STYLES)
        self.assertIn(".png-export-notice.error", STYLES)
        self.assertIn(".png-export-actions", STYLES)
        self.assertIn("@media (max-width: 620px)", STYLES)


if __name__ == "__main__":
    unittest.main()
