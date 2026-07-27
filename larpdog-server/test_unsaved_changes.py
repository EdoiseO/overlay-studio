import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import overlay_studio


ROOT_DIR = Path(__file__).resolve().parent.parent


class UnsavedChangesContractTests(unittest.TestCase):
    def test_studio_exposes_warning_dialog_and_reversible_preference(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="unsavedChangesDialog"', markup)
        self.assertIn('id="dontWarnUnsavedChanges"', markup)
        self.assertIn('id="confirmUnsavedChangesSetting"', markup)
        self.assertIn("customizerDraftKey() !== app.customizerBaseline", script)
        self.assertIn("requestUnsavedAction", script)
        self.assertIn("window.overlayStudioRequestClose", script)

    def test_warning_preference_is_persisted(self) -> None:
        api = overlay_studio.DesktopApi()
        with tempfile.TemporaryDirectory() as temporary_dir:
            settings_path = Path(temporary_dir) / "app-settings.json"
            with patch.object(overlay_studio, "APP_SETTINGS_PATH", settings_path):
                result = api.set_confirm_unsaved_changes(False)

            self.assertTrue(result["ok"])
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertIs(saved["confirmUnsavedChanges"], False)

    def test_native_close_is_cancelled_only_when_warning_is_needed(self) -> None:
        api = overlay_studio.DesktopApi()
        api._unsaved_changes = True
        api._close_dialog_pending = True

        with patch.object(
            overlay_studio,
            "load_json",
            return_value={"confirmUnsavedChanges": True},
        ):
            self.assertFalse(api._on_window_closing())

        with patch.object(
            overlay_studio,
            "load_json",
            return_value={"confirmUnsavedChanges": False},
        ):
            self.assertTrue(api._on_window_closing())

    def test_frozen_server_starts_as_independent_pyinstaller_process(self) -> None:
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.dict(os.environ, {"PYINSTALLER_RESET_ENVIRONMENT": "0"}),
        ):
            options = overlay_studio.server_process_options()

        self.assertEqual(
            options["env"]["PYINSTALLER_RESET_ENVIRONMENT"],
            "1",
        )
        self.assertIsNot(options["env"], os.environ)

    def test_source_server_does_not_override_process_environment(self) -> None:
        with patch.object(sys, "frozen", False, create=True):
            options = overlay_studio.server_process_options()

        self.assertNotIn("env", options)


if __name__ == "__main__":
    unittest.main()
