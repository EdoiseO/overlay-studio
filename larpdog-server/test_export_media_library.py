from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import overlay_studio
from overlay_config import DEFAULT_OVERLAY_CONFIG


class ExportMediaLibraryTests(unittest.TestCase):
    def test_exported_pngs_are_not_offered_as_dance_or_resting_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            user_assets = Path(temporary_dir)
            exports = user_assets / "exports" / "platform-badge"
            exports.mkdir(parents=True)
            (exports / "twitch.png").write_bytes(b"not-a-real-png")
            resting = user_assets / "resting"
            resting.mkdir()
            (resting / "cat.png").write_bytes(b"not-a-real-png")

            with patch.object(overlay_studio, "USER_ASSETS_DIR", user_assets):
                library = overlay_studio.media_library(DEFAULT_OVERLAY_CONFIG)

            paths = {
                item["path"]
                for collection in library.values()
                for item in collection
            }
            self.assertIn("user-assets/resting/cat.png", paths)
            self.assertNotIn("user-assets/exports/platform-badge/twitch.png", paths)


if __name__ == "__main__":
    unittest.main()
