from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer


ROOT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT_DIR / "larpdog-server"
sys.path.insert(0, str(SERVER_DIR))

import main  # noqa: E402
from overlay_config import (  # noqa: E402
    add_overlay_instance,
    materialize_instance_config,
    normalize_overlay_config,
    save_overlay_config,
    update_instance_config,
)


class MinecraftSpotifyPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (
            ROOT_DIR / "overlays" / "minecraft-spotify.html"
        ).read_text(encoding="utf-8")

    def test_overlay_is_a_separate_horizontal_catalog_template(self) -> None:
        self.assertIn('"name": "Minecraft Spotify"', self.source)
        self.assertIn('"canvas": { "w": 720, "h": 260 }', self.source)
        self.assertIn('"studioView": "minecraftSpotifyView"', self.source)
        self.assertIn("minecraftSpotify:", self.source)
        self.assertNotIn('"exportable": true', self.source)

    def test_player_matches_the_original_horizontal_composition(self) -> None:
        self.assertIn("grid-template-columns: 112px minmax(0, 1fr)", self.source)
        self.assertIn('class="art-frame"', self.source)
        self.assertIn('class="track-title"', self.source)
        self.assertIn('class="track-artist"', self.source)
        self.assertIn('class="progress-track"', self.source)
        self.assertIn("border-radius: 0", self.source)
        self.assertIn("clip-path: polygon", self.source)

    def test_progress_uses_a_segmented_minecraft_experience_bar(self) -> None:
        self.assertIn("--xp-cell: 16px", self.source)
        self.assertIn("--xp-gap: 3px", self.source)
        self.assertGreaterEqual(self.source.count("repeating-linear-gradient("), 2)
        self.assertIn("#b9ef72 0 30%", self.source)
        self.assertIn("#2f681d 68% 100%", self.source)

    def test_player_uses_only_strict_spotify_routing(self) -> None:
        self.assertIn('typeof message?.spotifyStatus !== "string"', self.source)
        self.assertIn('message.spotifyStatus === "playing"', self.source)
        self.assertIn('message.spotifyStatus === "paused"', self.source)
        self.assertIn("message.spotifyTrack", self.source)
        self.assertNotIn("if (message.isPlaying)", self.source)

    def test_catalog_preview_mobile_layout_and_customizer_are_supported(self) -> None:
        self.assertIn('query.get("catalog") === "1"', self.source)
        self.assertIn("PREVIEW_TRACK", self.source)
        self.assertIn("@media (max-width: 520px), (max-height: 190px)", self.source)
        self.assertIn('message.overlayType !== "minecraft-spotify"', self.source)
        self.assertIn("applySettings(message.config)", self.source)


class MinecraftSpotifyConfigTests(unittest.TestCase):
    def test_settings_are_independent_and_bounded(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({"instances": {}}),
            "minecraft-spotify",
            "minecraft-spotify-main",
            "Minecraft Spotify",
        )
        block_beats_before = materialize_instance_config(
            config,
            "minecraft-spotify-main",
        )["blockBeats"]
        updated = update_instance_config(
            config,
            "minecraft-spotify-main",
            {
                "minecraftSpotify": {
                    "scale": 99,
                    "cardWidth": 10,
                    "accentColor": "55AA33",
                    "shellColor": "101820",
                    "textColor": "F8F4E8",
                    "pixelShadow": -4,
                }
            },
        )
        materialized = materialize_instance_config(updated, "minecraft-spotify-main")

        self.assertEqual(
            materialized["minecraftSpotify"],
            {
                "scale": 2.0,
                "cardWidth": 380,
                "accentColor": "55aa33",
                "shellColor": "101820",
                "textColor": "f8f4e8",
                "pixelShadow": 0.0,
            },
        )
        self.assertEqual(materialized["blockBeats"], block_beats_before)
        self.assertEqual(
            updated["instances"]["minecraft-spotify-main"]["config"].keys(),
            {"minecraftSpotify"},
        )


class MinecraftSpotifyApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        server_dir = root / "larpdog-server"
        overlays_dir = root / "overlays"
        server_dir.mkdir()
        overlays_dir.mkdir()
        shutil.copyfile(
            ROOT_DIR / "overlays" / "minecraft-spotify.html",
            overlays_dir / "minecraft-spotify.html",
        )
        (root / "overlay-studio.html").write_text(
            "<!doctype html><title>Test</title>",
            encoding="utf-8",
        )
        overlay_config = add_overlay_instance(
            normalize_overlay_config({"instances": {}}),
            "minecraft-spotify",
            "minecraft-spotify-player",
            "Minecraft Spotify Player",
        )
        save_overlay_config(server_dir / "overlay-config.json", overlay_config)
        config = copy.deepcopy(main.DEFAULT_CONFIG)
        config["server"]["overlay_path"] = "../overlay-studio.html"
        for worker_name in ("audio", "media", "rivals"):
            config[worker_name]["enabled"] = False
        self.client = TestClient(TestServer(main.create_app(config, server_dir)))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()
        self.temporary.cleanup()

    async def test_route_loads_and_saved_instance_settings_round_trip(self) -> None:
        overlay = await self.client.get(
            "/overlays/minecraft-spotify?i=minecraft-spotify-player"
        )
        self.assertEqual(overlay.status, 200)
        self.assertIn("Minecraft Spotify", await overlay.text())

        saved = await self.client.post(
            "/api/config?i=minecraft-spotify-player",
            json={
                "minecraftSpotify": {
                    "scale": 1.25,
                    "cardWidth": 600,
                    "accentColor": "55aa33",
                    "shellColor": "101820",
                    "textColor": "f8f4e8",
                    "pixelShadow": 0.5,
                }
            },
        )
        self.assertEqual(saved.status, 200)

        loaded = await self.client.get(
            "/api/config?i=minecraft-spotify-player"
        )
        payload = await loaded.json()
        self.assertEqual(payload["minecraftSpotify"]["cardWidth"], 600)
        self.assertEqual(payload["minecraftSpotify"]["pixelShadow"], 0.5)
        self.assertEqual(payload["blockBeats"]["cardSize"], 440)
        self.assertEqual(payload["spotify"]["cardWidth"], 335)


if __name__ == "__main__":
    unittest.main()
