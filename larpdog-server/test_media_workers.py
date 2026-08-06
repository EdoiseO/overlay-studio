from __future__ import annotations

import asyncio
import datetime as dt
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

import main  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parent.parent


class FakeManager:
    def __init__(self, sessions: list[object], current: object | None) -> None:
        self.sessions = sessions
        self.current = current
        self.close = mock.Mock()

    def get_sessions(self) -> list[object]:
        return list(self.sessions)

    def get_current_session(self) -> object | None:
        return self.current


class FakeSession:
    def __init__(
        self,
        source: str,
        *,
        status: str = "playing",
        title: str = "Track",
        artist: str = "Artist",
        progress_ms: int = 10_000,
        duration_ms: int = 60_000,
    ) -> None:
        self.source_app_user_model_id = source
        self.status = status
        self.props = SimpleNamespace(
            title=title,
            artist=artist,
            album_title="Album",
            thumbnail=None,
        )
        self.timeline = SimpleNamespace(
            start_time=dt.timedelta(),
            end_time=dt.timedelta(milliseconds=duration_ms),
            position=dt.timedelta(milliseconds=progress_ms),
            last_updated_time=None,
        )

    def get_playback_info(self) -> SimpleNamespace:
        return SimpleNamespace(playback_status=self.status)

    async def try_get_media_properties_async(self) -> SimpleNamespace:
        return self.props

    def get_timeline_properties(self) -> SimpleNamespace:
        return self.timeline


class FakeStopEvent:
    def __init__(self, waits_before_stop: int) -> None:
        self.waits_before_stop = waits_before_stop
        self.delays: list[float] = []
        self.stopped = False

    def is_set(self) -> bool:
        return self.stopped

    def wait(self, delay: float) -> bool:
        self.delays.append(delay)
        if len(self.delays) >= self.waits_before_stop:
            self.stopped = True
        return self.stopped

    def set(self) -> None:
        self.stopped = True


class MediaSessionSelectionTests(unittest.IsolatedAsyncioTestCase):
    def make_worker(self) -> main.MediaSessionWorker:
        worker = main.MediaSessionWorker(
            mock.AsyncMock(),
            {"preferred_source": "spotify"},
        )
        worker.playing_status = "playing"
        return worker

    def test_strict_selection_does_not_fall_back_to_browser(self) -> None:
        worker = self.make_worker()
        browser = FakeSession("MSEdge", title="Live stream")
        worker.manager = FakeManager([browser], browser)

        self.assertIsNone(worker._select_session("strict"))
        self.assertIs(worker._select_session("general"), browser)

    def test_strict_selection_keeps_a_paused_spotify_session(self) -> None:
        worker = self.make_worker()
        spotify = FakeSession("Spotify.exe", status="paused")
        browser = FakeSession("MSEdge", title="Live stream")
        worker.manager = FakeManager([browser, spotify], browser)

        self.assertIs(worker._select_session("strict"), spotify)
        self.assertIs(worker._select_session("general"), spotify)

    async def test_shared_payload_routes_browser_and_spotify_independently(self) -> None:
        hub = mock.AsyncMock()
        worker = main.MediaSessionWorker(
            hub,
            {"preferred_source": "spotify"},
        )
        worker.playing_status = "playing"
        spotify = FakeSession(
            "Spotify.exe",
            title="Spotify song",
            progress_ms=20_000,
        )
        browser = FakeSession("MSEdge", title="Live stream")
        worker.manager = FakeManager([spotify, browser], browser)

        await worker._poll_once()
        first = hub.broadcast.await_args.args[0]
        self.assertEqual(first["title"], "Spotify song")
        self.assertEqual(first["spotifyStatus"], "playing")
        self.assertNotIn("spotifyTrack", first)

        worker.manager = FakeManager([browser], browser)
        await worker._poll_once()
        second = hub.broadcast.await_args.args[0]
        self.assertEqual(second["title"], "Live stream")
        self.assertEqual(second["sourceApp"], "MSEdge")
        self.assertEqual(second["spotifyStatus"], "waiting")
        self.assertEqual(second["spotifyTrack"]["title"], "Spotify song")

    async def test_paused_spotify_track_is_sent_with_frozen_progress(self) -> None:
        hub = mock.AsyncMock()
        worker = main.MediaSessionWorker(
            hub,
            {"preferred_source": "spotify"},
        )
        worker.playing_status = "playing"
        spotify = FakeSession(
            "Spotify.exe",
            status="paused",
            title="Held song",
            progress_ms=25_000,
        )
        worker.manager = FakeManager([spotify], spotify)

        await worker._poll_once()
        payload = hub.broadcast.await_args.args[0]
        self.assertFalse(payload["isPlaying"])
        self.assertEqual(payload["mediaStatus"], "paused")
        self.assertEqual(payload["spotifyStatus"], "paused")
        self.assertEqual(payload["progressMs"], 25_000)


class WorkerRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_audio_capture_retries_with_bounded_backoff(self) -> None:
        class FailingRecorder:
            def __enter__(self) -> "FailingRecorder":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def record(self, *, numframes: int) -> object:
                raise RuntimeError(f"device unavailable after {numframes}")

        class FakeMicrophone:
            name = "Fake default output"

            def recorder(self, **_kwargs: object) -> FailingRecorder:
                return FailingRecorder()

        loop = mock.MagicMock()
        loop.is_closed.return_value = False
        worker = main.AudioLoopbackWorker(
            mock.AsyncMock(),
            loop,
            {
                "retry_initial_seconds": 1,
                "retry_max_seconds": 3,
                "retry_stable_seconds": 999,
            },
        )
        stop_event = FakeStopEvent(waits_before_stop=4)
        worker.stop_event = stop_event  # type: ignore[assignment]
        fake_numpy = SimpleNamespace(
            float64=float,
            full=lambda count, value, **_kwargs: [value] * count,
        )

        with (
            mock.patch.object(
                worker,
                "_pick_loopback",
                return_value=FakeMicrophone(),
            ) as select_device,
            mock.patch.object(main, "log") as worker_log,
        ):
            worker._run_supervised(fake_numpy, mock.sentinel.soundcard)

        self.assertEqual(select_device.call_count, 4)
        self.assertEqual(stop_event.delays, [1, 2, 3, 3])
        interrupted_logs = [
            call
            for call in worker_log.call_args_list
            if "Audio capture interrupted" in call.args[0]
        ]
        self.assertEqual(len(interrupted_logs), 1)

    async def test_repeated_rpc_failure_rebuilds_media_manager(self) -> None:
        worker = main.MediaSessionWorker(
            mock.AsyncMock(),
            {
                "poll_seconds": 0.5,
                "manager_failure_threshold": 3,
                "retry_initial_seconds": 1,
                "retry_max_seconds": 4,
            },
        )
        managers: list[FakeManager] = []

        async def ensure_manager() -> bool:
            manager = FakeManager([], None)
            managers.append(manager)
            worker.manager = manager
            worker.playing_status = "playing"
            return True

        worker._ensure_manager = mock.AsyncMock(  # type: ignore[method-assign]
            side_effect=ensure_manager
        )
        worker._poll_once = mock.AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                RuntimeError("RPC unavailable"),
                RuntimeError("RPC unavailable"),
                RuntimeError("RPC unavailable"),
                asyncio.CancelledError(),
            ]
        )

        with (
            mock.patch.object(main.asyncio, "sleep", new=mock.AsyncMock()),
            mock.patch.object(main, "log"),
            self.assertRaises(asyncio.CancelledError),
        ):
            await worker._run()

        self.assertEqual(worker._ensure_manager.await_count, 2)
        managers[0].close.assert_called_once_with()


class MediaOverlayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.overlay = (ROOT_DIR / "overlay-studio.html").read_text(
            encoding="utf-8"
        )
        cls.studio = (ROOT_DIR / "studio" / "index.html").read_text(
            encoding="utf-8"
        )

    def test_server_overlay_reconnects_without_latching_to_file_mode(self) -> None:
        self.assertIn("function scheduleOverlayStudioReconnect()", self.overlay)
        self.assertIn("scheduleOverlayStudioReconnect();", self.overlay)
        self.assertIn("overlayServerReconnectDelay * 1.7", self.overlay)
        self.assertIn("Math.min(\n    8000,", self.overlay)
        startup = self.overlay.split("(async () => {", maxsplit=1)[1]
        self.assertNotIn("startStandaloneSources();\n  }", startup)
        self.assertIn('location.protocol === "file:"', startup)

    def test_spotify_card_has_waiting_and_paused_states(self) -> None:
        self.assertIn('message.spotifyStatus === "playing"', self.overlay)
        self.assertIn('message.spotifyStatus === "paused"', self.overlay)
        self.assertIn("showSpotifyWaiting(message.spotifyTrack", self.overlay)
        self.assertIn("setProgress(progressMs, durationMs, playing = true)", self.overlay)
        self.assertIn(".card.held", self.overlay)

    def test_studio_explains_media_and_audio_sources(self) -> None:
        self.assertIn(
            "Other media apps are ignored, and no Spotify login is required.",
            self.studio,
        )
        self.assertIn(
            "including games, browsers, and streams",
            self.studio,
        )
        self.assertIn(
            "including supported browsers and music apps",
            self.studio,
        )


if __name__ == "__main__":
    unittest.main()
