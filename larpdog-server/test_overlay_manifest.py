from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

import overlay_manifest  # noqa: E402


def write_overlay(path: Path, name: str, *, exportable: object = False) -> None:
    path.write_text(
        f"""<!doctype html>
<script id="overlay-manifest" type="application/json">
{{
  "name": "{name}",
  "description": "Test overlay",
  "category": "utility",
  "exportable": {json.dumps(exportable)},
  "canvas": {{"w": 640, "h": 360}},
  "settings": ["appearance"],
  "studioView": "generic"
}}
</script>
""",
        encoding="utf-8",
    )


class OverlayManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        overlay_manifest.clear_overlay_manifest_cache()

    def tearDown(self) -> None:
        overlay_manifest.clear_overlay_manifest_cache()

    def test_rejects_overlay_files_over_size_limit_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "oversized.html"
            with path.open("wb") as stream:
                stream.truncate(overlay_manifest.MAX_OVERLAY_FILE_BYTES + 1)

            with mock.patch.object(
                Path,
                "open",
                side_effect=AssertionError("oversized file was read"),
            ):
                self.assertIsNone(overlay_manifest.read_overlay_manifest(path))

    def test_scan_uses_cache_until_file_metadata_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            overlays_dir = Path(temporary_dir)
            path = overlays_dir / "sample.html"
            write_overlay(path, "First")

            with mock.patch.object(
                overlay_manifest,
                "read_overlay_manifest",
                wraps=overlay_manifest.read_overlay_manifest,
            ) as reader:
                first = overlay_manifest.scan_overlay_manifests(overlays_dir)
                second = overlay_manifest.scan_overlay_manifests(overlays_dir)

                self.assertEqual(reader.call_count, 1)
                self.assertEqual(first[0]["name"], "First")
                self.assertEqual(second[0]["name"], "First")

                previous_mtime = path.stat().st_mtime_ns
                write_overlay(path, "Second")
                os.utime(
                    path,
                    ns=(previous_mtime + 1_000_000_000,) * 2,
                )
                refreshed = overlay_manifest.scan_overlay_manifests(overlays_dir)

                self.assertEqual(reader.call_count, 2)
                self.assertEqual(refreshed[0]["name"], "Second")

    def test_cached_results_are_not_shared_with_callers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            overlays_dir = Path(temporary_dir)
            write_overlay(overlays_dir / "sample.html", "Original")

            first = overlay_manifest.scan_overlay_manifests(overlays_dir)
            first[0]["name"] = "Changed by caller"
            second = overlay_manifest.scan_overlay_manifests(overlays_dir)

            self.assertEqual(second[0]["name"], "Original")

    def test_exportable_requires_an_explicit_json_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            overlays_dir = Path(temporary_dir)
            write_overlay(
                overlays_dir / "enabled.html",
                "Enabled",
                exportable=True,
            )
            write_overlay(
                overlays_dir / "string.html",
                "String",
                exportable="true",
            )
            write_overlay(overlays_dir / "disabled.html", "Disabled")

            manifests = {
                manifest["type"]: manifest
                for manifest in overlay_manifest.scan_overlay_manifests(overlays_dir)
            }

            self.assertTrue(manifests["enabled"]["exportable"])
            self.assertFalse(manifests["string"]["exportable"])
            self.assertFalse(manifests["disabled"]["exportable"])

    def test_only_approved_static_overlays_are_exportable(self) -> None:
        root_dir = Path(__file__).resolve().parent.parent
        manifests = {
            manifest["type"]: manifest
            for manifest in overlay_manifest.scan_overlay_manifests(
                root_dir / "overlays"
            )
        }
        enabled = {
            overlay_type
            for overlay_type, manifest in manifests.items()
            if manifest["exportable"]
        }
        self.assertEqual(
            enabled,
            {"platform-badge", "social", "social-grouped"},
        )

    def test_manifest_setting_limit_supports_larger_customizers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "many-settings.html"
            settings = [
                f'"setting{index}"'
                for index in range(overlay_manifest.MAX_MANIFEST_SETTINGS + 6)
            ]
            path.write_text(
                """<!doctype html>
<script id="overlay-manifest" type="application/json">
{
  "name": "Many Settings",
  "description": "Test a larger bounded manifest",
  "category": "utility",
  "canvas": {"w": 640, "h": 360},
  "settings": [%s],
  "studioView": "generic"
}
</script>
""" % ",".join(settings),
                encoding="utf-8",
            )

            manifest = overlay_manifest.read_overlay_manifest(path)

            self.assertIsNotNone(manifest)
            self.assertEqual(
                len(manifest["settings"]),
                overlay_manifest.MAX_MANIFEST_SETTINGS,
            )
            self.assertEqual(manifest["settings"][-1], "setting63")


if __name__ == "__main__":
    unittest.main()
