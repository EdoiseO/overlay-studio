from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import overlay_studio


class _SoundPickerWindow:
    def __init__(self, source: Path) -> None:
        self.source = source

    def create_file_dialog(self, *_args, **_kwargs):
        return [str(self.source)]


class CountdownCustomSoundTests(unittest.TestCase):
    def test_sound_signatures_must_match_allowlisted_extensions(self) -> None:
        overlay_studio.validate_countdown_sound(".ogg", b"OggS\x00payload")
        overlay_studio.validate_countdown_sound(
            ".wav",
            b"RIFF\x08\x00\x00\x00WAVEpayload",
        )
        overlay_studio.validate_countdown_sound(".mp3", b"ID3\x04payload")

        with self.assertRaisesRegex(ValueError, "do not match"):
            overlay_studio.validate_countdown_sound(".mp3", b"OggS\x00payload")
        with self.assertRaisesRegex(ValueError, "OGG, MP3, or WAV"):
            overlay_studio.validate_countdown_sound(".exe", b"MZpayload")

    def test_picker_copies_valid_sound_into_bounded_user_assets_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "Raid Alert!.ogg"
            source.write_bytes(b"OggS\x00safe-custom-sound")
            user_assets = root / "user-assets"
            api = overlay_studio.DesktopApi()
            api._window = _SoundPickerWindow(source)

            with patch.object(overlay_studio, "USER_ASSETS_DIR", user_assets):
                result = api.choose_countdown_sound()

            self.assertTrue(result["ok"])
            self.assertEqual(
                result["path"],
                "user-assets/sounds/Raid-Alert.ogg",
            )
            self.assertEqual(
                (user_assets / "sounds" / "Raid-Alert.ogg").read_bytes(),
                source.read_bytes(),
            )

    def test_picker_rejects_spoofed_or_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "not-a-sound.mp3"
            source.write_bytes(b"MZ-not-really-an-mp3")
            api = overlay_studio.DesktopApi()
            api._window = _SoundPickerWindow(source)

            with patch.object(
                overlay_studio,
                "USER_ASSETS_DIR",
                root / "user-assets",
            ):
                spoofed = api.choose_countdown_sound()
            self.assertFalse(spoofed["ok"])
            self.assertIn("do not match", spoofed["detail"])

            source.write_bytes(b"ID3" + b"x" * 32)
            with (
                patch.object(
                    overlay_studio,
                    "USER_ASSETS_DIR",
                    root / "user-assets",
                ),
                patch.object(overlay_studio, "MAX_COUNTDOWN_SOUND_BYTES", 16),
            ):
                oversized = api.choose_countdown_sound()
            self.assertFalse(oversized["ok"])
            self.assertIn("5 MB", oversized["detail"])


if __name__ == "__main__":
    unittest.main()
