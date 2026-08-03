import re
import unittest
from pathlib import Path
from unittest.mock import patch

import overlay_studio


ROOT_DIR = Path(__file__).resolve().parent.parent


class CustomizerPreviewContractTests(unittest.TestCase):
    def test_studio_has_one_shared_draft_preview(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertEqual(markup.count('id="customizerPreviewFrame"'), 1)
        self.assertEqual(
            markup.count('id="customizerPreviewExpandButton"'),
            1,
        )
        self.assertIn('type: "overlay-studio-draft"', script)
        self.assertIn('url.searchParams.set("customizer", "1")', script)
        self.assertIn("setCustomizerPreviewExpanded", script)

    def test_customizer_preview_supports_zoom_pan_and_native_popout(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        popout = (
            ROOT_DIR / "studio" / "preview-window.html"
        ).read_text(encoding="utf-8")

        for element_id in (
            "customizerPreviewZoomOutButton",
            "customizerPreviewZoomResetButton",
            "customizerPreviewZoomInButton",
            "customizerPreviewRecenterButton",
            "customizerPreviewSaveButton",
            "customizerPreviewPopoutButton",
        ):
            self.assertEqual(markup.count(f'id="{element_id}"'), 1)
        self.assertIn('addEventListener("wheel"', script)
        self.assertIn('addEventListener("pointerdown"', script)
        self.assertIn("PREVIEW_ZOOM_MIN = 0.25", script)
        self.assertIn("PREVIEW_ZOOM_MAX = 3", script)
        self.assertIn('callApi(\n      "open_preview_window"', script)
        self.assertIn("window.overlayStudioPreview", popout)
        self.assertIn('addEventListener("pointermove"', popout)
        self.assertIn("frame.contentWindow.postMessage", popout)
        self.assertIn('id="positionReset"', popout)
        self.assertIn('id="saveDraft"', popout)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)", popout)

    def test_native_preview_accepts_only_the_local_overlay_server(self) -> None:
        with patch.object(
            overlay_studio,
            "server_address",
            return_value=("127.0.0.1", 8474),
        ):
            self.assertEqual(
                overlay_studio.validated_preview_source(
                    "http://127.0.0.1:8474/overlays/social-grouped"
                    "?i=grouped-main&customizer=1"
                ),
                "http://127.0.0.1:8474/overlays/social-grouped"
                "?i=grouped-main&customizer=1",
            )
            for source in (
                "https://127.0.0.1:8474/overlays/social-grouped",
                "http://example.com:8474/overlays/social-grouped",
                "http://127.0.0.1:8475/overlays/social-grouped",
                "http://127.0.0.1:8474/api/config",
                "http://user@127.0.0.1:8474/overlays/social-grouped",
                "http://127.0.0.1:8474/overlays/../api/config",
            ):
                with self.subTest(source=source):
                    self.assertIsNone(
                        overlay_studio.validated_preview_source(source)
                    )

    def test_native_preview_bridge_bounds_and_forwards_drafts(self) -> None:
        class PreviewWindow:
            def __init__(self) -> None:
                self.scripts: list[str] = []

            def run_js(self, script: str) -> None:
                self.scripts.append(script)

        api = overlay_studio.DesktopApi()
        window = PreviewWindow()
        api._window = window
        api._preview_window = window
        api._preview_ready = True
        api._preview_config = {
            "source": (
                "http://127.0.0.1:8474/overlays/social-grouped"
                "?i=grouped-main&customizer=1"
            )
        }

        result = api.update_preview_window(
            {
                "type": "overlay-studio-draft",
                "overlayType": "social-grouped",
                "instanceId": "grouped-main",
                "config": {"socialGrouped": {"groups": "twitch:name"}},
            }
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["open"])
        self.assertIn("applyDraft", window.scripts[-1])
        self.assertIsNone(
            api._preview_payload({"value": "x" * 262_145})
        )
        save_result = api.save_preview_draft()
        self.assertTrue(save_result["ok"])
        self.assertIn(
            'window.overlayStudioSavePreviewDraft?.("grouped-main")',
            window.scripts[-1],
        )

    def test_customizer_scroll_and_expansion_have_separate_layouts(self) -> None:
        styles = (ROOT_DIR / "studio" / "app.css").read_text(encoding="utf-8")

        self.assertIn("width: calc(100% - 324px)", styles)
        self.assertIn("scrollbar-gutter: stable", styles)
        self.assertIn(".customizer-preview-dock.expanded", styles)

    def test_goal_currency_fields_use_shared_typeahead_selects(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertEqual(markup.count("data-currency-select"), 3)
        self.assertIn('["Canadian Dollar (C$)", "C$"]', script)
        self.assertIn("initializeCurrencySelects", script)
        self.assertIn("setCurrencySymbol", script)

    def test_each_customizable_overlay_accepts_drafts(self) -> None:
        overlay_sources = {
            "larpdog-dance": ROOT_DIR / "overlay-studio.html",
            "spotify": ROOT_DIR / "overlay-studio.html",
            "now-playing-flow": ROOT_DIR / "overlays" / "now-playing-flow.html",
            "goal": ROOT_DIR / "overlays" / "goal.html",
            "goal-bar": ROOT_DIR / "overlays" / "goal-bar.html",
            "goal-pill": ROOT_DIR / "overlays" / "goal-pill.html",
            "win-loss": ROOT_DIR / "overlays" / "win-loss.html",
            "social": ROOT_DIR / "overlays" / "social.html",
            "social-rotator": ROOT_DIR / "overlays" / "social-rotator.html",
            "social-grouped": ROOT_DIR / "overlays" / "social-grouped.html",
        }
        shared_social = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")

        for overlay_type, path in overlay_sources.items():
            with self.subTest(overlay_type=overlay_type):
                source = path.read_text(encoding="utf-8")
                if overlay_type in {"social", "social-rotator", "social-grouped"}:
                    source += shared_social
                self.assertIn("overlay-studio-draft", source)
                self.assertIn(overlay_type, source)

    def test_social_overlays_share_bounded_platform_runtime(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        bar = (
            ROOT_DIR / "overlays" / "social.html"
        ).read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")

        self.assertIn('"threads"', shared)
        self.assertIn('"bluesky"', shared)
        self.assertIn("enabled >= limit", shared)
        self.assertIn('"social-rotator": 12', shared)
        self.assertIn('get("customizer") === "1"', shared)
        self.assertIn("event.source !== window.parent", shared)
        self.assertNotIn("event.origin !== location.origin", shared)
        self.assertIn("social.createGlyph", bar)
        self.assertIn("social.createGlyph", rotator)
        self.assertIn("symbols-only", bar)
        self.assertIn("symbols-only", rotator)
        self.assertIn("iconBackground", shared)
        self.assertIn("content.hidden = accounts.length === 0", bar)
        self.assertIn("content.hidden = accounts.length === 0", rotator)
        self.assertIn('studioView": "socialView"', bar)
        self.assertIn('studioView": "socialView"', rotator)

    def test_grouped_social_customizer_uses_compact_group_editor(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT_DIR / "studio" / "app.css").read_text(encoding="utf-8")

        self.assertIn('id="socialGroupedView"', markup)
        self.assertIn('id="socialGroupedList"', markup)
        self.assertIn('id="socialGroupedTile"', markup)
        self.assertIn('id="socialGroupedShape"', markup)
        self.assertIn('id="socialGroupedPlatformSelect"', markup)
        self.assertIn('id="socialGroupedHandleInput"', markup)
        self.assertIn('id="socialGroupedAddButton"', markup)
        self.assertIn("function renderSocialGrouped(socialGrouped)", script)
        self.assertIn("function gatherSocialGroupedSettings()", script)
        self.assertIn("function addSocialGroupedAccount()", script)
        self.assertIn("matchingGroup.platforms.push(platform.id)", script)
        self.assertIn("SOCIAL_GROUPED_LIMITS", script)
        self.assertIn("socialGroupedGroupsFromEditor", script)
        self.assertIn(".social-grouped-chip", styles)
        self.assertIn(".social-grouped-row", styles)

    def test_social_customizer_uses_compact_account_picker(self) -> None:
        markup = (ROOT_DIR / "studio" / "index.html").read_text(encoding="utf-8")
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="socialPlatformSelect"', markup)
        self.assertIn('id="socialHandleInput"', markup)
        self.assertIn('id="socialAddButton"', markup)
        self.assertIn('id="socialEmptyState"', markup)
        self.assertIn('id="socialIconBackground"', markup)
        self.assertNotIn('data-social-enabled', markup)
        self.assertIn("function addSocialAccount()", script)
        self.assertIn("function socialHandleFromInput(value, limit = 64)", script)
        self.assertIn("remove.dataset.socialRemove = platform.id", script)
        self.assertIn("if (!account.enabled) return", script)

    def test_state_poll_does_not_restart_rotator_draft(self) -> None:
        script = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")
        preview_start = script.index("function renderCustomizerPreview(")
        preview_end = script.index(
            "function fitCardPreviewHost(",
            preview_start,
        )
        preview_function = script[preview_start:preview_end]

        self.assertNotIn("scheduleCustomizerDraft()", preview_function)
        self.assertIn("if (nextKey === settingsKey) return", rotator)

    def test_now_playing_flow_catalog_preview_uses_demo_track(self) -> None:
        flow = (
            ROOT_DIR / "overlays" / "now-playing-flow.html"
        ).read_text(encoding="utf-8")

        self.assertIn('query.get("catalog") === "1"', flow)
        self.assertIn('title: "Midnight Drive"', flow)
        self.assertIn('artist: "Your Artist"', flow)
        self.assertIn("if (catalogMode) applyTrack(CATALOG_TRACK);", flow)
        self.assertIn("else connect();", flow)

    def test_tiktok_brand_colors_are_readable_on_dark_shell(self) -> None:
        shared = (
            ROOT_DIR / "assets" / "social-platforms.js"
        ).read_text(encoding="utf-8")
        studio = (ROOT_DIR / "studio" / "app.js").read_text(encoding="utf-8")
        match = re.search(
            r'tiktok:\s+\{[^}]*color:\s+"(#[0-9a-f]+)"'
            r'[^}]*surface:\s+"(#[0-9a-f]+)"'
            r'[^}]*ink:\s+"(#[0-9a-f]+)"',
            shared,
        )

        self.assertIsNotNone(match)
        color, surface, ink = match.groups()
        self.assertGreaterEqual(self._contrast_ratio(color, "#141418"), 4.5)
        self.assertGreaterEqual(self._contrast_ratio(surface, ink), 4.5)
        self.assertIn('{ color: "#25f4ee", dx: -1.15, dy: -.7 }', shared)
        self.assertIn('{ color: "#fe2c55", dx: 1.15, dy: .7 }', shared)
        self.assertIn('surface: "#F6F7FB"', studio)
        self.assertIn(
            'shadow: "-1px -1px #25F4EE, 1px 1px #FE2C55"',
            studio,
        )

    def test_social_handles_are_never_ellipsized(self) -> None:
        bar = (
            ROOT_DIR / "overlays" / "social.html"
        ).read_text(encoding="utf-8")
        rotator = (
            ROOT_DIR / "overlays" / "social-rotator.html"
        ).read_text(encoding="utf-8")

        for source in (bar, rotator):
            self.assertNotIn("text-overflow: ellipsis", source)
            self.assertIn("fitToCanvas", source)
            self.assertIn("--fit-scale", source)
        self.assertIn("min-width: max-content", bar)
        self.assertIn("min-width: max-content", rotator)

    @staticmethod
    def _contrast_ratio(first: str, second: str) -> float:
        def luminance(color: str) -> float:
            channels = [
                int(color[index : index + 2], 16) / 255
                for index in (1, 3, 5)
            ]
            linear = [
                value / 12.92
                if value <= 0.04045
                else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return (
                linear[0] * 0.2126
                + linear[1] * 0.7152
                + linear[2] * 0.0722
            )

        brighter, darker = sorted(
            (luminance(first), luminance(second)),
            reverse=True,
        )
        return (brighter + 0.05) / (darker + 0.05)


if __name__ == "__main__":
    unittest.main()
