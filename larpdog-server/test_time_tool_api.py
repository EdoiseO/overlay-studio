from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer


SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

import main  # noqa: E402
from overlay_config import (  # noqa: E402
    add_overlay_instance,
    normalize_overlay_config,
    save_overlay_config,
)


class TimeToolApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        server_dir = root / "larpdog-server"
        overlays_dir = root / "overlays"
        server_dir.mkdir()
        overlays_dir.mkdir()
        for overlay_type in (
            "pixel-clock-line",
            "pixel-countdown-line",
            "pixel-stopwatch-line",
        ):
            shutil.copyfile(
                ROOT_DIR / "overlays" / f"{overlay_type}.html",
                overlays_dir / f"{overlay_type}.html",
            )
        shutil.copyfile(
            ROOT_DIR / "overlays" / "goal.html",
            overlays_dir / "goal.html",
        )
        (root / "overlay-studio.html").write_text(
            "<!doctype html><title>Test</title>",
            encoding="utf-8",
        )

        overlay_config = normalize_overlay_config({"instances": {}})
        for overlay_type, instance_id, name in (
            ("pixel-clock-line", "server-clock", "Server Clock"),
            ("pixel-clock-line", "hud-clock", "HUD Clock"),
            ("pixel-countdown-line", "break-countdown", "Break Countdown"),
            ("pixel-countdown-line", "line-countdown", "Line Countdown"),
            ("pixel-stopwatch-line", "build-stopwatch", "Build Stopwatch"),
            ("pixel-stopwatch-line", "line-stopwatch", "Line Stopwatch"),
            ("goal", "tip-goal", "Tip Goal"),
        ):
            overlay_config = add_overlay_instance(
                overlay_config,
                overlay_type,
                instance_id,
                name,
            )
        save_overlay_config(server_dir / "overlay-config.json", overlay_config)

        config = copy.deepcopy(main.DEFAULT_CONFIG)
        config["server"]["overlay_path"] = "../overlay-studio.html"
        app = main.create_app(config, server_dir)
        self.patches = [
            mock.patch.object(main.AudioLoopbackWorker, "start"),
            mock.patch.object(main.AudioLoopbackWorker, "stop"),
            mock.patch.object(main.MediaSessionWorker, "start"),
            mock.patch.object(
                main.MediaSessionWorker,
                "stop",
                new_callable=mock.AsyncMock,
            ),
            mock.patch.object(main.RivalsPollWorker, "start"),
            mock.patch.object(
                main.RivalsPollWorker,
                "stop",
                new_callable=mock.AsyncMock,
            ),
        ]
        for patch in self.patches:
            patch.start()
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()
        for patch in reversed(self.patches):
            patch.stop()
        self.temporary.cleanup()

    async def test_clock_settings_persist_and_broadcast(self) -> None:
        initial = await self.client.get("/api/time-tool?i=server-clock")
        self.assertEqual(initial.status, 200)
        self.assertEqual((await initial.json())["timezone"], "local")

        websocket = await self.client.ws_connect("/ws")
        updated = await self.client.post(
            "/api/time-tool?i=server-clock",
            json={
                "timezone": "America/Chicago",
                "timezoneLabel": "CENTRAL",
                "hour12": False,
                "showSeconds": False,
            },
        )
        self.assertEqual(updated.status, 200)
        state = await updated.json()
        self.assertEqual(state["timezone"], "America/Chicago")
        self.assertEqual(state["timezoneLabel"], "CENTRAL")
        self.assertFalse(state["hour12"])
        self.assertFalse(state["showSeconds"])

        message = await websocket.receive_json(timeout=2)
        self.assertEqual(message["type"], "time-tool")
        self.assertEqual(message["overlayType"], "pixel-clock-line")
        self.assertEqual(message["instanceId"], "server-clock")
        self.assertEqual(message["state"]["timezone"], "America/Chicago")
        await websocket.close()

        persisted = await self.client.get("/api/time-tool?i=server-clock")
        self.assertEqual((await persisted.json())["timezoneLabel"], "CENTRAL")

    async def test_clock_line_uses_the_clock_settings_contract(self) -> None:
        updated = await self.client.post(
            "/api/time-tool?i=hud-clock",
            json={
                "timezone": "UTC",
                "timezoneLabel": "UTC",
                "hour12": False,
                "showSeconds": True,
                "showDate": False,
                "digitShadow": 0.35,
            },
        )
        self.assertEqual(updated.status, 200)
        state = await updated.json()
        self.assertEqual(state["timezone"], "UTC")
        self.assertEqual(state["timezoneLabel"], "UTC")
        self.assertFalse(state["hour12"])
        self.assertTrue(state["showSeconds"])
        self.assertFalse(state["showDate"])
        self.assertEqual(state["digitShadow"], 0.35)

        persisted = await self.client.get("/api/time-tool?i=hud-clock")
        self.assertEqual(await persisted.json(), state)

    async def test_countdown_controls_rebase_and_persist(self) -> None:
        with mock.patch("time_tool_store.time.time", return_value=1_000):
            started = await self.client.post(
                "/api/time-tool?i=break-countdown",
                json={"durationSeconds": 600, "action": "start"},
            )
        self.assertEqual(started.status, 200)
        started_state = await started.json()
        self.assertTrue(started_state["running"])
        self.assertEqual(started_state["startedAt"], 1_000_000)

        with mock.patch("time_tool_store.time.time", return_value=1_005):
            paused = await self.client.post(
                "/api/time-tool?i=break-countdown",
                json={"action": "pause"},
            )
        paused_state = await paused.json()
        self.assertFalse(paused_state["running"])
        self.assertEqual(paused_state["remainingMs"], 595_000)

        with mock.patch("time_tool_store.time.time", return_value=2_000):
            persisted = await self.client.get(
                "/api/time-tool?i=break-countdown"
            )
        self.assertEqual((await persisted.json())["remainingMs"], 595_000)

    async def test_line_timers_keep_persistent_timer_controls(self) -> None:
        countdown = await self.client.post(
            "/api/time-tool?i=line-countdown",
            json={"durationSeconds": 90, "action": "start"},
        )
        stopwatch = await self.client.post(
            "/api/time-tool?i=line-stopwatch",
            json={"action": "start"},
        )

        self.assertEqual(countdown.status, 200)
        self.assertEqual(stopwatch.status, 200)
        countdown_state = await countdown.json()
        stopwatch_state = await stopwatch.json()
        self.assertEqual(countdown_state["durationSeconds"], 90)
        self.assertTrue(countdown_state["running"])
        self.assertTrue(stopwatch_state["running"])
        self.assertEqual(countdown_state["digitShadow"], 0)
        self.assertEqual(stopwatch_state["glow"], 0)

    async def test_countdown_sound_test_persists_volume_and_broadcasts_event(self) -> None:
        websocket = await self.client.ws_connect("/ws")
        response = await self.client.post(
            "/api/time-tool?i=line-countdown",
            json={
                "action": "test-sound",
                "soundEnabled": True,
                "soundVolume": 0.65,
            },
        )
        self.assertEqual(response.status, 200)
        state = await response.json()
        self.assertTrue(state["soundEnabled"])
        self.assertEqual(state["soundVolume"], 0.65)

        state_message = await websocket.receive_json(timeout=2)
        sound_message = await websocket.receive_json(timeout=2)
        self.assertEqual(state_message["type"], "time-tool")
        self.assertEqual(sound_message["type"], "time-tool-sound")
        self.assertEqual(sound_message["overlayType"], "pixel-countdown-line")
        self.assertEqual(sound_message["instanceId"], "line-countdown")
        await websocket.close()

    async def test_stopwatch_is_independent_from_countdown(self) -> None:
        with mock.patch("time_tool_store.time.time", return_value=2_000):
            started = await self.client.post(
                "/api/time-tool?i=build-stopwatch",
                json={"action": "start"},
            )
        self.assertEqual(started.status, 200)

        with mock.patch("time_tool_store.time.time", return_value=2_007.25):
            paused = await self.client.post(
                "/api/time-tool?i=build-stopwatch",
                json={"action": "pause"},
            )
        self.assertEqual((await paused.json())["elapsedMs"], 7_250)

        countdown = await self.client.get(
            "/api/time-tool?i=break-countdown"
        )
        self.assertEqual((await countdown.json())["remainingMs"], 600_000)

    async def test_routes_require_matching_addressed_instances(self) -> None:
        for overlay_type, instance_id in (
            ("pixel-clock-line", "server-clock"),
            ("pixel-clock-line", "hud-clock"),
            ("pixel-countdown-line", "break-countdown"),
            ("pixel-countdown-line", "line-countdown"),
            ("pixel-stopwatch-line", "build-stopwatch"),
            ("pixel-stopwatch-line", "line-stopwatch"),
        ):
            with self.subTest(overlay_type=overlay_type):
                response = await self.client.get(
                    f"/overlays/{overlay_type}?i={instance_id}"
                )
                self.assertEqual(response.status, 200)
                await response.read()

        unaddressed = await self.client.get("/api/time-tool")
        self.assertEqual(unaddressed.status, 400)
        wrong_type = await self.client.get("/api/time-tool?i=tip-goal")
        self.assertEqual(wrong_type.status, 404)
        mismatched_page = await self.client.get(
            "/overlays/pixel-clock-line?i=build-stopwatch"
        )
        self.assertEqual(mismatched_page.status, 404)

    async def test_legacy_obs_routes_serve_the_renamed_time_overlays(self) -> None:
        for legacy_type, instance_id, expected_title in (
            ("minecraft-clock-line", "server-clock", "Pixel Clock Line"),
            (
                "minecraft-countdown-line",
                "break-countdown",
                "Pixel Countdown Line",
            ),
            (
                "minecraft-stopwatch-line",
                "build-stopwatch",
                "Pixel Stopwatch Line",
            ),
        ):
            for suffix in ("", ".html"):
                with self.subTest(legacy_type=legacy_type, suffix=suffix):
                    response = await self.client.get(
                        f"/overlays/{legacy_type}{suffix}?i={instance_id}"
                    )
                    self.assertEqual(response.status, 200)
                    self.assertIn(expected_title, await response.text())


if __name__ == "__main__":
    unittest.main()
