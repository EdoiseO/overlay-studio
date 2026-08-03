from __future__ import annotations

import copy
import json
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


class RivalsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        server_dir = root / "larpdog-server"
        overlays_dir = root / "overlays"
        assets_dir = root / "assets" / "ranks"
        server_dir.mkdir()
        overlays_dir.mkdir()
        assets_dir.mkdir(parents=True)
        shutil.copyfile(
            ROOT_DIR / "overlays" / "rivals-rank.html",
            overlays_dir / "rivals-rank.html",
        )
        (root / "overlay-studio.html").write_text(
            "<!doctype html><title>Test</title>",
            encoding="utf-8",
        )

        overlay_config = add_overlay_instance(
            normalize_overlay_config({}),
            "rivals-rank",
            "rank-card",
            "Rivals Rank",
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
        self.server_dir = server_dir

    async def asyncTearDown(self) -> None:
        await self.client.close()
        for patch in reversed(self.patches):
            patch.stop()
        self.temporary.cleanup()

    async def test_links_updates_and_never_returns_uid(self) -> None:
        initial = await self.client.get("/api/rivals?i=rank-card")
        self.assertEqual(initial.status, 200)
        initial_payload = await initial.json()
        self.assertFalse(initial_payload["linked"])
        self.assertEqual(initial_payload["poll"]["status"], "unlinked")
        self.assertEqual(initial_payload["state"]["sessionWins"], 0)

        websocket = await self.client.ws_connect("/ws")
        linked = await self.client.post(
            "/api/rivals?i=rank-card",
            json={
                "uid": "https://rivalsdata.com/player/396536339",
                "label": "Ranked run",
                "shellColor": "#20242a",
            },
        )
        self.assertEqual(linked.status, 200)
        linked_payload = await linked.json()
        self.assertTrue(linked_payload["linked"])
        self.assertEqual(linked_payload["poll"]["status"], "waiting")
        self.assertEqual(linked_payload["state"]["label"], "Ranked run")
        self.assertEqual(linked_payload["state"]["shellColor"], "20242a")

        message = await websocket.receive_json(timeout=2)
        self.assertEqual(message["type"], "rivals")
        self.assertEqual(message["instanceId"], "rank-card")
        await websocket.close()

        for payload in (linked_payload, message):
            serialized = json.dumps(payload).lower()
            self.assertNotIn("396536339", serialized)
            self.assertNotIn('"uid"', serialized)

        persisted = json.loads(
            (self.server_dir / "rivals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            persisted["instances"]["rank-card"]["private"]["uid"],
            396536339,
        )
        fetched = await self.client.get("/api/rivals?i=rank-card")
        fetched_text = await fetched.text()
        self.assertNotIn("396536339", fetched_text)
        self.assertNotIn('"uid"', fetched_text.lower())

    async def test_reset_keeps_rank_and_score(self) -> None:
        await self.client.post(
            "/api/rivals?i=rank-card",
            json={"uid": "396536339"},
        )
        path = self.server_dir / "rivals.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        state = document["instances"]["rank-card"]["state"]
        state.update(
            {
                "tier": "grandmaster",
                "division": 2,
                "score": 56,
                "sessionWins": 4,
                "sessionLosses": 2,
            }
        )
        path.write_text(json.dumps(document), encoding="utf-8")

        reset = await self.client.post(
            "/api/rivals?i=rank-card",
            json={"action": "reset-session"},
        )
        payload = await reset.json()
        self.assertEqual(payload["state"]["sessionWins"], 0)
        self.assertEqual(payload["state"]["sessionLosses"], 0)
        self.assertEqual(payload["state"]["tier"], "grandmaster")
        self.assertEqual(payload["state"]["score"], 56)

    async def test_route_and_write_guards(self) -> None:
        overlay = await self.client.get("/overlays/rivals-rank?i=rank-card")
        self.assertEqual(overlay.status, 200)
        await overlay.read()

        unaddressed = await self.client.get("/api/rivals")
        self.assertEqual(unaddressed.status, 400)

        wrong_type = await self.client.get(
            "/api/rivals?i=spotify-overlay"
        )
        self.assertEqual(wrong_type.status, 404)

        invalid_uid = await self.client.post(
            "/api/rivals?i=rank-card",
            json={"uid": "https://attacker.example/player/123"},
        )
        self.assertEqual(invalid_uid.status, 400)

        text_plain = await self.client.post(
            "/api/rivals?i=rank-card",
            data='{"uid":"396536339"}',
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(text_plain.status, 415)

        remote_origin = await self.client.post(
            "/api/rivals?i=rank-card",
            json={"uid": "396536339"},
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(remote_origin.status, 403)


if __name__ == "__main__":
    unittest.main()
