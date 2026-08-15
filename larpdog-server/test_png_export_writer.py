from __future__ import annotations

import base64
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import overlay_studio


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", checksum)
    )


def png_data_url(
    width: int = 320,
    height: int = 256,
    color: bytes = b"\x4f\xc8\xbd\xff",
) -> tuple[str, bytes]:
    rows = b"".join(b"\x00" + color * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    content = (
        overlay_studio.PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(rows, 9))
        + png_chunk(b"IEND", b"")
    )
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:image/png;base64,{encoded}", content


class PngExportWriterTests(unittest.TestCase):
    @staticmethod
    def exportable_config() -> dict[str, object]:
        return {
            "instances": {
                "platform-badge-main": {
                    "id": "platform-badge-main",
                    "type": "platform-badge",
                    "name": "Badge",
                    "config": {},
                }
            }
        }

    def test_validates_png_chunks_crc_and_dimensions(self) -> None:
        data_url, content = png_data_url()
        decoded, width, height = overlay_studio.validated_export_png(data_url)
        self.assertEqual(decoded, content)
        self.assertEqual((width, height), (320, 256))

        broken = bytearray(content)
        broken[-5] ^= 1
        broken_url = "data:image/png;base64," + base64.b64encode(broken).decode("ascii")
        with self.assertRaisesRegex(ValueError, "integrity check"):
            overlay_studio.validated_export_png(broken_url)

        unsupported_height, _content = png_data_url(height=300)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            overlay_studio.validated_export_png(unsupported_height)

    def test_stable_filename_is_atomically_replaced(self) -> None:
        api = overlay_studio.DesktopApi()
        first_url, _first_content = png_data_url(color=b"\xff\x00\x00\xff")
        second_url, second_content = png_data_url(color=b"\x00\xff\x00\xff")
        with tempfile.TemporaryDirectory() as temporary_dir:
            user_assets = Path(temporary_dir)
            with (
                patch.object(overlay_studio, "USER_ASSETS_DIR", user_assets),
                patch.object(
                    overlay_studio,
                    "load_overlay_config",
                    return_value=self.exportable_config(),
                ),
            ):
                first = api.save_png_exports(
                    "platform-badge-main",
                    [{"filename": "twitch.png", "dataUrl": first_url}],
                )
                second = api.save_png_exports(
                    "platform-badge-main",
                    [{"filename": "twitch.png", "dataUrl": second_url}],
                )

            target = (
                user_assets
                / "exports"
                / "platform-badge-main"
                / "twitch.png"
            )
            self.assertTrue(first["ok"])
            self.assertEqual(first["replaced"], 0)
            self.assertTrue(second["ok"])
            self.assertEqual(second["replaced"], 1)
            self.assertEqual(target.read_bytes(), second_content)
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_rejects_path_traversal_duplicate_names_and_invalid_instances(self) -> None:
        api = overlay_studio.DesktopApi()
        data_url, _content = png_data_url()
        with tempfile.TemporaryDirectory() as temporary_dir:
            with (
                patch.object(
                    overlay_studio,
                    "USER_ASSETS_DIR",
                    Path(temporary_dir),
                ),
                patch.object(
                    overlay_studio,
                    "load_overlay_config",
                    return_value=self.exportable_config(),
                ),
            ):
                traversal = api.save_png_exports(
                    "platform-badge-main",
                    [{"filename": "../escape.png", "dataUrl": data_url}],
                )
                duplicates = api.save_png_exports(
                    "platform-badge-main",
                    [
                        {"filename": "twitch.png", "dataUrl": data_url},
                        {"filename": "twitch.png", "dataUrl": data_url},
                    ],
                )
                invalid_instance = api.save_png_exports(
                    "../outside",
                    [{"filename": "twitch.png", "dataUrl": data_url}],
                )

            self.assertFalse(traversal["ok"])
            self.assertFalse(duplicates["ok"])
            self.assertFalse(invalid_instance["ok"])
            self.assertFalse((Path(temporary_dir).parent / "escape.png").exists())

    def test_rejects_a_valid_but_non_exportable_overlay_instance(self) -> None:
        api = overlay_studio.DesktopApi()
        data_url, _content = png_data_url()
        config = {
            "instances": {
                "rivals-rank-main": {
                    "id": "rivals-rank-main",
                    "type": "rivals-rank",
                    "name": "Rank",
                    "config": {},
                }
            }
        }
        with patch.object(
            overlay_studio,
            "load_overlay_config",
            return_value=config,
        ):
            result = api.save_png_exports(
                "rivals-rank-main",
                [{"filename": "rank.png", "dataUrl": data_url}],
            )

        self.assertFalse(result["ok"])
        self.assertIn("cannot be exported", result["detail"])


if __name__ == "__main__":
    unittest.main()
