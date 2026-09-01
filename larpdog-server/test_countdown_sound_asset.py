from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import main  # noqa: E402


class CountdownSoundAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.appdata_dir = Path(self.temporary.name)
        self.assets_dir = self.appdata_dir / ".minecraft" / "assets"
        self.indexes_dir = self.assets_dir / "indexes"
        self.objects_dir = self.assets_dir / "objects"
        self.indexes_dir.mkdir(parents=True)
        self.objects_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_asset(
        self,
        payload: bytes,
        *,
        asset_hash: str | None = None,
        size: int | None = None,
        index_name: str = "test.json",
    ) -> Path:
        asset_hash = asset_hash or hashlib.sha1(payload).hexdigest()
        object_path = self.objects_dir / asset_hash[:2] / asset_hash
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(payload)
        manifest = {
            "objects": {
                main.CHALLENGE_COMPLETE_ASSET: {
                    "hash": asset_hash,
                    "size": len(payload) if size is None else size,
                }
            }
        }
        (self.indexes_dir / index_name).write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return object_path

    def test_finds_exact_installed_challenge_complete_object(self) -> None:
        expected = self.write_asset(b"OggS\x00challenge")

        actual = main.find_installed_challenge_complete_sound(
            self.appdata_dir
        )

        self.assertEqual(actual, expected)

    def test_skips_invalid_newer_index_and_uses_valid_older_index(self) -> None:
        expected = self.write_asset(
            b"OggS\x00valid",
            index_name="older.json",
        )
        invalid_manifest = {
            "objects": {
                main.CHALLENGE_COMPLETE_ASSET: {
                    "hash": "../not-a-sha1",
                    "size": 1,
                }
            }
        }
        newer = self.indexes_dir / "newer.json"
        newer.write_text(json.dumps(invalid_manifest), encoding="utf-8")
        newer.touch()

        actual = main.find_installed_challenge_complete_sound(
            self.appdata_dir
        )

        self.assertEqual(actual, expected)

    def test_rejects_object_when_manifest_size_does_not_match(self) -> None:
        self.write_asset(b"OggS\x00truncated", size=999)

        actual = main.find_installed_challenge_complete_sound(
            self.appdata_dir
        )

        self.assertIsNone(actual)

    def test_returns_none_without_a_minecraft_asset_store(self) -> None:
        empty_appdata = self.appdata_dir / "empty"

        self.assertIsNone(
            main.find_installed_challenge_complete_sound(empty_appdata)
        )


if __name__ == "__main__":
    unittest.main()
