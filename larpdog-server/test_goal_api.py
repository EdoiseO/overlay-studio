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


class GoalApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        server_dir = root / "larpdog-server"
        overlays_dir = root / "overlays"
        server_dir.mkdir()
        overlays_dir.mkdir()
        shutil.copyfile(
            ROOT_DIR / "overlays" / "goal.html",
            overlays_dir / "goal.html",
        )
        (root / "overlay-studio.html").write_text(
            "<!doctype html><title>Test</title>",
            encoding="utf-8",
        )

        overlay_config = add_overlay_instance(
            normalize_overlay_config({}),
            "goal",
            "tip-goal",
            "Tip Goal",
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

    async def test_updates_persists_and_broadcasts_goal_state(self) -> None:
        initial = await self.client.get("/api/goal?i=tip-goal")
        self.assertEqual(initial.status, 200)
        self.assertEqual((await initial.json())["current"], 0)

        websocket = await self.client.ws_connect("/ws")
        updated = await self.client.post(
            "/api/goal?i=tip-goal",
            json={"action": "add", "amount": 7.5},
        )
        self.assertEqual(updated.status, 200)
        self.assertEqual((await updated.json())["current"], 7.5)
        message = await websocket.receive_json(timeout=2)
        self.assertEqual(message["type"], "goal")
        self.assertEqual(message["instanceId"], "tip-goal")
        self.assertEqual(message["state"]["current"], 7.5)
        self.assertEqual(message["event"]["amount"], 7.5)
        await websocket.close()

        persisted = await self.client.get("/api/goal?i=tip-goal")
        self.assertEqual((await persisted.json())["current"], 7.5)

    async def test_goal_route_and_write_guards(self) -> None:
        overlay = await self.client.get("/overlays/goal?i=tip-goal")
        self.assertEqual(overlay.status, 200)
        await overlay.read()

        wrong_type = await self.client.get("/api/goal?i=spotify-overlay")
        self.assertEqual(wrong_type.status, 404)

        text_plain = await self.client.post(
            "/api/goal?i=tip-goal",
            data='{"action":"add","amount":5}',
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(text_plain.status, 415)

        remote_origin = await self.client.post(
            "/api/goal?i=tip-goal",
            json={"action": "add", "amount": 5},
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(remote_origin.status, 403)


if __name__ == "__main__":
    unittest.main()
