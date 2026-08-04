from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "larpdog-server"))

from main import DEFAULT_CONFIG, create_app  # noqa: E402
from overlay_config import (  # noqa: E402
    PLATFORM_BADGE_FONT_CHOICES,
    PLATFORM_BADGE_PLATFORMS,
    SOCIAL_PLATFORMS,
    add_overlay_instance,
    normalize_overlay_config,
    save_overlay_config,
)


class PlatformBadgeCustomizerTests(unittest.TestCase):
    CONTROL_IDS = {
        "platform": "platformBadgePlatform",
        "handle": "platformBadgeHandle",
        "prefix": "platformBadgePrefix",
        "useBrandColor": "platformBadgeUseBrandColor",
        "badgeColor": "platformBadgeColor",
        "corners": "platformBadgeCorners",
        "scale": "platformBadgeScale",
        "font": "platformBadgeFont",
        "weight": "platformBadgeWeight",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.overlay = (
            ROOT_DIR / "overlays" / "platform-badge.html"
        ).read_text(encoding="utf-8")
        cls.markup = (ROOT_DIR / "studio" / "index.html").read_text(
            encoding="utf-8"
        )
        cls.script = (ROOT_DIR / "studio" / "app.js").read_text(
            encoding="utf-8"
        )
        manifest_match = re.search(
            r'<script type="application/json" id="overlay-manifest">\s*'
            r'(\{.*?\})\s*</script>',
            cls.overlay,
            re.DOTALL,
        )
        if manifest_match is None:
            raise AssertionError("Platform Badge manifest is missing")
        cls.manifest = json.loads(manifest_match.group(1))

    def test_manifest_settings_match_customizer_controls_one_to_one(self) -> None:
        self.assertEqual(
            self.manifest["settings"],
            list(self.CONTROL_IDS),
        )
        for setting, control_id in self.CONTROL_IDS.items():
            with self.subTest(setting=setting):
                self.assertEqual(self.markup.count(f'id="{control_id}"'), 1)

        gather_start = self.script.index("function gatherPlatformBadgeSettings()")
        gather_end = self.script.index("function parseSocialGroupedGroups", gather_start)
        gather = self.script[gather_start:gather_end]
        for setting in self.CONTROL_IDS:
            self.assertRegex(gather, rf"\b{re.escape(setting)}:")

    def test_platform_and_font_choices_match_shared_runtime(self) -> None:
        self.assertEqual(PLATFORM_BADGE_PLATFORMS, set(SOCIAL_PLATFORMS))
        self.assertEqual(len(PLATFORM_BADGE_PLATFORMS), 16)
        self.assertEqual(
            PLATFORM_BADGE_FONT_CHOICES,
            {
                "montserrat",
                "poppins",
                "archivo",
                "nunito",
                "anton",
                "sans",
                "display",
                "round",
                "mono",
                "serif",
            },
        )
        for font in PLATFORM_BADGE_FONT_CHOICES:
            self.assertIn(f'<option value="{font}">', self.markup)

    def test_slider_ranges_match_server_contract(self) -> None:
        expected = {
            "platformBadgeCorners": ("0", "24", "1"),
            "platformBadgeScale": ("0.5", "2", "0.05"),
            "platformBadgeWeight": ("300", "900", "100"),
        }
        for control_id, values in expected.items():
            with self.subTest(control_id=control_id):
                match = re.search(
                    rf'<input id="{control_id}" type="range" '
                    r'min="([^"]+)" max="([^"]+)" step="([^"]+)">',
                    self.markup,
                )
                self.assertIsNotNone(match)
                self.assertEqual(match.groups(), values)
                self.assertEqual(
                    self.markup.count(f'id="{control_id}Output"'),
                    1,
                )

    def test_studio_wires_preview_save_reset_and_conditional_color(self) -> None:
        self.assertIn('"platformBadgeView"', self.script)
        self.assertIn('instance.type === "platform-badge"', self.script)
        self.assertIn("function renderPlatformBadge(platformBadge)", self.script)
        self.assertIn("function gatherPlatformBadgeSettings()", self.script)
        self.assertIn(
            "return { config: { platformBadge: gatherPlatformBadgeSettings() } };",
            self.script,
        )
        self.assertIn('submitted = { platformBadge: gatherPlatformBadgeSettings() };', self.script)
        self.assertIn("section.hidden = useBrandColor;", self.script)
        self.assertIn("control.disabled = useBrandColor;", self.script)
        self.assertIn('id="savePlatformBadgeButton"', self.markup)
        self.assertIn('id="resetPlatformBadgeButton"', self.markup)

    def test_overlay_uses_generic_config_and_live_draft_contract(self) -> None:
        self.assertIn("/api/config?i=", self.overlay)
        self.assertIn('const OVERLAY_TYPE = "platform-badge"', self.overlay)
        self.assertIn('event.data?.type !== "overlay-studio-draft"', self.overlay)
        self.assertIn("event.data.config.platformBadge", self.overlay)
        self.assertIn("message.config.platformBadge", self.overlay)
        self.assertIn("social.contrast(fill)", self.overlay)
        self.assertNotIn("textColor", self.manifest["settings"])


class PlatformBadgeApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary.name) / "larpdog-server"
        self.base_dir.mkdir()
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "platform-badge",
            "platform-badge-main",
            "Platform Badge",
        )
        save_overlay_config(self.base_dir / "overlay-config.json", config)
        server_config = copy.deepcopy(DEFAULT_CONFIG)
        server_config["audio"]["enabled"] = False
        server_config["media"]["enabled"] = False
        app = create_app(server_config, self.base_dir)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()
        self.temporary.cleanup()

    async def test_generic_config_route_persists_and_broadcasts_badge(self) -> None:
        initial = await self.client.get(
            "/api/config?i=platform-badge-main"
        )
        self.assertEqual(initial.status, 200)
        self.assertEqual(
            (await initial.json())["platformBadge"]["platform"],
            "twitch",
        )

        websocket = await self.client.ws_connect("/ws")
        response = await self.client.post(
            "/api/config?i=platform-badge-main",
            json={
                "platformBadge": {
                    "platform": "kick",
                    "handle": "livecreator",
                    "prefix": "@",
                    "useBrandColor": True,
                    "badgeColor": "123456",
                    "corners": 2,
                    "scale": 1.25,
                    "font": "anton",
                    "weight": 800,
                }
            },
        )
        self.assertEqual(response.status, 200)
        message = await websocket.receive_json(timeout=1)
        if message.get("type") == "track":
            message = await websocket.receive_json(timeout=1)
        await websocket.close()

        self.assertEqual(message["type"], "config")
        self.assertEqual(message["instanceId"], "platform-badge-main")
        self.assertEqual(message["config"]["platformBadge"]["platform"], "kick")

        persisted = await self.client.get(
            "/api/config?i=platform-badge-main"
        )
        badge = (await persisted.json())["platformBadge"]
        self.assertEqual(badge["handle"], "livecreator")
        self.assertEqual(badge["scale"], 1.25)
        self.assertEqual(badge["font"], "anton")


if __name__ == "__main__":
    unittest.main()
