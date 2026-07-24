from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import datetime as dt
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from counter_store import apply_counter_update, load_counter_state, save_counter_state
from overlay_config import load_overlay_config, save_overlay_config


APP_NAME = "overlay-studio-server"
DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 8473,
        "overlay_path": "../overlay-studio.html",
    },
    "audio": {
        "enabled": True,
        "device_match": "",
        "sample_rate": 48000,
        "block_size": 1024,
        "fps": 45,
        "sensitivity": 1.0,
        "bass_bins": 14,
    },
    "media": {
        "enabled": True,
        "poll_seconds": 2,
        "preferred_source": "spotify",
        "thumbnail_max_bytes": 524288,
    },
}


def log(message: str) -> None:
    print(f"[{APP_NAME}] {message}", flush=True)


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object")
        deep_merge(config, loaded)
    else:
        log(f"No config.json found; using defaults from {path.parent}")
    return config


def resolve_path(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def clamp01(value: float) -> float:
    if value <= 0:
        return 0.0
    if value >= 1:
        return 1.0
    return float(value)


def init_winrt_runtime() -> None:
    if sys.platform != "win32":
        return
    try:
        from winrt.runtime import ApartmentType, init_apartment

        init_apartment(ApartmentType.MULTI_THREADED)
    except Exception as exc:
        log(f"Windows media runtime initialization skipped: {exc}")


class ClientHub:
    def __init__(self) -> None:
        self._clients: set[web.WebSocketResponse] = set()
        self._last_track: dict[str, Any] | None = None
        self._last_win_loss: dict[str, Any] | None = None

    async def add(self, ws: web.WebSocketResponse) -> None:
        self._clients.add(ws)
        if self._last_track is not None:
            await ws.send_str(json.dumps(self._last_track, separators=(",", ":")))
        if self._last_win_loss is not None:
            await ws.send_str(json.dumps(self._last_win_loss, separators=(",", ":")))

    async def remove(self, ws: web.WebSocketResponse) -> None:
        self._clients.discard(ws)

    def latest_track(self) -> dict[str, Any]:
        if self._last_track is not None:
            return dict(self._last_track)
        return {
            "type": "track",
            "isPlaying": False,
            "title": "",
            "artist": "",
            "art": None,
            "progressMs": 0,
            "durationMs": 0,
            "source": "windows-media",
        }

    async def broadcast(self, message: dict[str, Any]) -> None:
        if message.get("type") == "track":
            self._last_track = message
        elif message.get("type") == "win-loss":
            self._last_win_loss = message
        if not self._clients:
            return

        data = json.dumps(message, separators=(",", ":"))
        dead: list[web.WebSocketResponse] = []
        for ws in tuple(self._clients):
            if ws.closed:
                dead.append(ws)
                continue
            try:
                await ws.send_str(data)
            except (ConnectionResetError, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


class AudioLoopbackWorker:
    def __init__(self, hub: ClientHub, loop: asyncio.AbstractEventLoop, config: dict[str, Any]) -> None:
        self.hub = hub
        self.loop = loop
        self.config = config
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.config.get("enabled", True):
            log("Audio capture disabled in config.")
            return
        self.thread = threading.Thread(
            target=self._run,
            name="overlay-studio-audio",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _schedule_broadcast(self, payload: dict[str, Any]) -> None:
        if self.loop.is_closed():
            return
        self.loop.call_soon_threadsafe(asyncio.create_task, self.hub.broadcast(payload))

    def _pick_loopback(self, sc: Any) -> Any:
        device_match = str(self.config.get("device_match") or "").strip().lower()
        microphones = list(sc.all_microphones(include_loopback=True))
        if device_match:
            for mic in microphones:
                haystack = f"{getattr(mic, 'name', '')} {getattr(mic, 'id', '')}".lower()
                if device_match in haystack:
                    return mic

        speaker = None
        with contextlib.suppress(Exception):
            speaker = sc.default_speaker()
        speaker_name = str(getattr(speaker, "name", "") or "").lower()
        if speaker_name:
            for mic in microphones:
                if speaker_name in str(getattr(mic, "name", "")).lower():
                    return mic
            with contextlib.suppress(Exception):
                return sc.get_microphone(str(getattr(speaker, "name")), include_loopback=True)

        for mic in microphones:
            name = str(getattr(mic, "name", "")).lower()
            if "loopback" in name or getattr(mic, "isloopback", False):
                return mic

        raise RuntimeError("No WASAPI loopback device found")

    def _run(self) -> None:
        try:
            import numpy as np
            import soundcard as sc
        except Exception as exc:
            log(f"Audio dependencies unavailable: {exc}")
            return

        sample_rate = int(self.config.get("sample_rate", 48000))
        block_size = int(self.config.get("block_size", 1024))
        fps = max(1, float(self.config.get("fps", 45)))
        bass_bins = max(1, int(self.config.get("bass_bins", 14)))
        target_dt = 1.0 / fps

        try:
            mic = self._pick_loopback(sc)
            log(f"Audio loopback capture: {getattr(mic, 'name', mic)}")
            with mic.recorder(samplerate=sample_rate, channels=2, blocksize=block_size) as recorder:
                bass_avg = 1e-9
                band_avgs = np.full(5, 1e-9, dtype=np.float64)
                pulse = 0.0
                last_beat = 0.0
                last_send = 0.0

                while not self.stop_event.is_set():
                    frames = recorder.record(numframes=block_size)
                    mono = np.asarray(frames, dtype=np.float32)
                    if mono.size == 0:
                        continue
                    if mono.ndim > 1:
                        mono = mono.mean(axis=1)
                    mono = np.nan_to_num(mono, copy=False)

                    window = np.hanning(mono.size)
                    spectrum = np.abs(np.fft.rfft(mono * window))
                    if spectrum.size < bass_bins:
                        continue

                    # Keep smoothing/threshold/band math in sync with startRealAudio() in overlay-studio.html.
                    bass = float(np.mean(spectrum[:bass_bins]))
                    bass_avg = bass_avg * 0.92 + bass * 0.08
                    sensitivity = max(0.3, float(self.config.get("sensitivity", 1.0)))
                    threshold = bass_avg * (1.35 / sensitivity)
                    now = time.perf_counter()
                    beat = bass > threshold and bass > 1e-7 and (now - last_beat) > 0.110
                    if beat:
                        pulse = 1.0
                        last_beat = now
                    pulse *= 0.86

                    if now - last_send < target_dt:
                        continue
                    last_send = now

                    bass_level = clamp01(bass / max(bass_avg * 3.0, 1e-9))
                    bands: list[float] = []
                    length = spectrum.size
                    for idx in range(5):
                        lo = int(idx * length / 12)
                        hi = max(lo + 1, int((idx + 1) * length / 12))
                        raw = float(np.mean(spectrum[lo:hi]))
                        band_avgs[idx] = band_avgs[idx] * 0.92 + raw * 0.08
                        bands.append(clamp01(raw / max(band_avgs[idx] * 2.4, 1e-9)))

                    self._schedule_broadcast(
                        {
                            "type": "audio",
                            "level": round(max(pulse, bass_level * 0.55), 4),
                            "beat": bool(beat),
                            "bands": [round(v, 4) for v in bands],
                        }
                    )
        except Exception as exc:
            log(f"Audio capture stopped: {exc}")


class MediaSessionWorker:
    def __init__(self, hub: ClientHub, config: dict[str, Any]) -> None:
        self.hub = hub
        self.config = config
        self.task: asyncio.Task[None] | None = None
        self.manager: Any = None
        self.playing_status: Any = None
        self.last_signature = ""
        self.last_identity = ""
        self.last_art: str | None = None

    def start(self) -> None:
        if not self.config.get("enabled", True):
            log("Windows media now-playing disabled in config.")
            asyncio.create_task(self._broadcast_idle())
            return
        self.task = asyncio.create_task(
            self._run(),
            name="overlay-studio-media-session",
        )

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        signature = json.dumps(payload, sort_keys=True)
        if signature != self.last_signature:
            self.last_signature = signature
            await self.hub.broadcast(payload)

    async def _broadcast_idle(self) -> None:
        await self._broadcast(
            {
                "type": "track",
                "isPlaying": False,
                "title": "",
                "artist": "",
                "art": None,
                "progressMs": 0,
                "durationMs": 0,
                "source": "windows-media",
            }
        )

    async def _ensure_manager(self) -> bool:
        if self.manager is not None:
            return True
        if sys.platform != "win32":
            log("Windows media sessions are only available on Windows.")
            await self._broadcast_idle()
            return False

        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as SessionManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
            )

            self.manager = await SessionManager.request_async()
            self.playing_status = PlaybackStatus.PLAYING
        except Exception as exc:
            log(f"Windows media sessions unavailable: {exc}")
            await self._broadcast_idle()
            return False

        if self.manager is None:
            log("Windows media session manager unavailable.")
            await self._broadcast_idle()
            return False

        log("Windows media session polling enabled.")
        return True

    def _select_session(self) -> Any:
        sessions = list(self.manager.get_sessions())
        preferred = str(self.config.get("preferred_source") or "spotify").strip().lower()
        if preferred:
            for session in sessions:
                source = str(getattr(session, "source_app_user_model_id", "") or "").lower()
                if preferred in source:
                    return session
        return self.manager.get_current_session()

    @staticmethod
    def _clean_text(value: Any) -> str:
        return " ".join(str(value or "").split())

    @classmethod
    def _identity(cls, title: str, artist: str, album: str) -> str:
        return "\0".join((cls._clean_text(title).casefold(), cls._clean_text(artist).casefold(), cls._clean_text(album).casefold()))

    @staticmethod
    def _timedelta_ms(value: Any) -> int:
        if not isinstance(value, dt.timedelta):
            return 0
        return max(0, int(value.total_seconds() * 1000))

    def _timeline_values(self, session: Any, is_playing: bool) -> tuple[int, int]:
        timeline = session.get_timeline_properties()
        start = getattr(timeline, "start_time", dt.timedelta())
        end = getattr(timeline, "end_time", dt.timedelta())
        position = getattr(timeline, "position", dt.timedelta())
        duration = end - start if isinstance(end, dt.timedelta) and isinstance(start, dt.timedelta) else dt.timedelta()
        if duration <= dt.timedelta():
            return 0, 0

        progress = position - start if isinstance(position, dt.timedelta) and isinstance(start, dt.timedelta) else dt.timedelta()
        last_updated = getattr(timeline, "last_updated_time", None)
        if is_playing and isinstance(last_updated, dt.datetime):
            now = dt.datetime.now(last_updated.tzinfo or dt.timezone.utc)
            progress += max(dt.timedelta(), now - last_updated)

        progress = min(max(dt.timedelta(), progress), duration)
        return self._timedelta_ms(progress), self._timedelta_ms(duration)

    async def _thumbnail_data_url(self, thumbnail: Any) -> str | None:
        if thumbnail is None:
            return None

        stream = None
        reader = None
        try:
            stream = await thumbnail.open_read_async()
            size = int(getattr(stream, "size", 0) or 0)
            max_bytes = max(0, int(self.config.get("thumbnail_max_bytes", 524288)))
            if size <= 0 or size > max_bytes:
                return None

            content_type = str(getattr(stream, "content_type", "") or "image/png").strip().lower()
            if not content_type.startswith("image/"):
                return None

            from winrt.windows.storage.streams import DataReader

            reader = DataReader(stream)
            loaded = int(await reader.load_async(size))
            data = bytearray(loaded)
            reader.read_bytes(data)
            encoded = base64.b64encode(bytes(data)).decode("ascii")
            return f"data:{content_type};base64,{encoded}"
        except Exception as exc:
            log(f"Windows media thumbnail unavailable: {exc}")
            return None
        finally:
            for resource in (reader, stream):
                close = getattr(resource, "close", None)
                if callable(close):
                    with contextlib.suppress(Exception):
                        close()

    async def _payload_from_session(self, session: Any) -> dict[str, Any] | None:
        playback = session.get_playback_info()
        is_playing = getattr(playback, "playback_status", None) == self.playing_status
        if not is_playing:
            return {
                "type": "track",
                "isPlaying": False,
                "title": "",
                "artist": "",
                "art": None,
                "progressMs": 0,
                "durationMs": 0,
                "source": "windows-media",
            }

        props = await session.try_get_media_properties_async()
        title = self._clean_text(getattr(props, "title", ""))
        artist = self._clean_text(getattr(props, "artist", ""))
        album = self._clean_text(getattr(props, "album_title", ""))
        if not title:
            if self.last_identity:
                return None
            return {
                "type": "track",
                "isPlaying": False,
                "title": "",
                "artist": "",
                "art": None,
                "progressMs": 0,
                "durationMs": 0,
                "source": "windows-media",
            }

        identity = self._identity(title, artist, album)
        if identity != self.last_identity:
            self.last_identity = identity
            self.last_art = await self._thumbnail_data_url(getattr(props, "thumbnail", None))

        progress_ms, duration_ms = self._timeline_values(session, is_playing=True)
        return {
            "type": "track",
            "isPlaying": True,
            "title": title,
            "artist": artist,
            "art": self.last_art,
            "progressMs": progress_ms,
            "durationMs": duration_ms,
            "source": "windows-media",
        }

    async def _poll_once(self) -> None:
        session = self._select_session()
        if session is None:
            self.last_identity = ""
            self.last_art = None
            await self._broadcast_idle()
            return

        payload = await self._payload_from_session(session)
        if payload is not None:
            if not payload.get("isPlaying"):
                self.last_identity = ""
                self.last_art = None
            await self._broadcast(payload)

    async def _run(self) -> None:
        poll_seconds = max(0.5, float(self.config.get("poll_seconds", 2)))
        if not await self._ensure_manager():
            return

        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log(f"Windows media polling error: {exc}")
                await self._broadcast_idle()
            await asyncio.sleep(poll_seconds)


@web.middleware
async def static_cors_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    response = await handler(request)
    if request.path.startswith(("/assets/", "/user-assets/")):
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response


def create_app(config: dict[str, Any], base_dir: Path) -> web.Application:
    app = web.Application(middlewares=[static_cors_middleware])
    hub = ClientHub()
    overlay_config_path = base_dir / "overlay-config.json"
    counter_state_path = base_dir / "win-loss.json"
    app["hub"] = hub
    app["config"] = config
    app["base_dir"] = base_dir
    app["overlay_config_path"] = overlay_config_path
    app["counter_state_path"] = counter_state_path

    async def serve_overlay(_request: web.Request) -> web.StreamResponse:
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        if not overlay_path.exists():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_path}")
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

    async def serve_overlay_config(_request: web.Request) -> web.Response:
        saved_config = load_overlay_config(overlay_config_path)
        payload = json.dumps(saved_config, separators=(",", ":"))
        return web.Response(
            text=(
                f"window.OVERLAY_STUDIO_CONFIG={payload};"
                "window.LARPDOG_CONFIG=window.OVERLAY_STUDIO_CONFIG;"
            ),
            content_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    async def get_overlay_config(_request: web.Request) -> web.Response:
        return web.json_response(
            load_overlay_config(overlay_config_path),
            headers={"Cache-Control": "no-store"},
        )

    async def get_now_playing(_request: web.Request) -> web.Response:
        return web.json_response(
            hub.latest_track(),
            headers={"Cache-Control": "no-store"},
        )

    async def update_overlay_config(request: web.Request) -> web.Response:
        if request.content_length is not None and request.content_length > 64 * 1024:
            raise web.HTTPRequestEntityTooLarge(
                max_size=64 * 1024,
                actual_size=request.content_length,
            )
        try:
            submitted = await request.json()
        except (json.JSONDecodeError, TypeError):
            raise web.HTTPBadRequest(text="Expected a JSON object") from None
        if not isinstance(submitted, dict):
            raise web.HTTPBadRequest(text="Expected a JSON object")
        saved_config = save_overlay_config(overlay_config_path, submitted)
        config.setdefault("audio", {})["sensitivity"] = saved_config["audio"]["sensitivity"]
        await hub.broadcast({"type": "config", "config": saved_config})
        return web.json_response(saved_config)

    async def serve_win_loss(_request: web.Request) -> web.StreamResponse:
        overlay_path = base_dir.parent / "overlays" / "win-loss.html"
        if not overlay_path.exists():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_path}")
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

    async def get_win_loss(_request: web.Request) -> web.Response:
        return web.json_response(
            load_counter_state(counter_state_path),
            headers={"Cache-Control": "no-store"},
        )

    async def update_win_loss(request: web.Request) -> web.Response:
        if request.content_length is not None and request.content_length > 16 * 1024:
            raise web.HTTPRequestEntityTooLarge(
                max_size=16 * 1024,
                actual_size=request.content_length,
            )
        try:
            submitted = await request.json()
        except (json.JSONDecodeError, TypeError):
            raise web.HTTPBadRequest(text="Expected a JSON object") from None
        if not isinstance(submitted, dict):
            raise web.HTTPBadRequest(text="Expected a JSON object")
        try:
            state = apply_counter_update(load_counter_state(counter_state_path), submitted)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        saved_state = save_counter_state(counter_state_path, state)
        await hub.broadcast({"type": "win-loss", "state": saved_state})
        return web.json_response(saved_state)

    async def ws_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        await hub.add(ws)
        log(f"Websocket connected: {request.remote}")
        try:
            async for _msg in ws:
                pass
        finally:
            await hub.remove(ws)
            log(f"Websocket disconnected: {request.remote}")
        return ws

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "app": APP_NAME})

    async def on_startup(startup_app: web.Application) -> None:
        loop = asyncio.get_running_loop()
        audio_worker = AudioLoopbackWorker(hub, loop, config.get("audio", {}))
        media_worker = MediaSessionWorker(hub, config.get("media", {}))
        startup_app["audio_worker"] = audio_worker
        startup_app["media_worker"] = media_worker
        audio_worker.start()
        media_worker.start()
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        log(f"Serving overlay: {overlay_path}")
        log(f"OBS URL: http://{config['server']['host']}:{config['server']['port']}/")

    async def on_cleanup(cleanup_app: web.Application) -> None:
        cleanup_app["audio_worker"].stop()
        await cleanup_app["media_worker"].stop()

    app.router.add_get("/", serve_overlay)
    app.router.add_get("/overlay-studio.html", serve_overlay)
    app.router.add_get("/overlays/larpdog-dance", serve_overlay)
    app.router.add_get("/overlays/spotify", serve_overlay)
    app.router.add_get("/larpdog-overlay.html", serve_overlay)
    app.router.add_get("/overlay-config.js", serve_overlay_config)
    app.router.add_get("/api/config", get_overlay_config)
    app.router.add_post("/api/config", update_overlay_config)
    app.router.add_get("/api/now-playing", get_now_playing)
    app.router.add_get("/overlays/win-loss", serve_win_loss)
    app.router.add_get("/overlays/win-loss.html", serve_win_loss)
    app.router.add_get("/api/win-loss", get_win_loss)
    app.router.add_post("/api/win-loss", update_win_loss)
    assets_dir = resolve_path(str(config["server"]["overlay_path"]), base_dir).parent / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir, show_index=False)
    user_assets_dir = resolve_path(str(config["server"]["overlay_path"]), base_dir).parent / "user-assets"
    user_assets_dir.mkdir(exist_ok=True)
    app.router.add_static("/user-assets", user_assets_dir, show_index=False)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/health", health)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local audio and Windows media companion for Overlay Studio."
    )
    parser.add_argument(
        "--config",
        default=str(runtime_dir() / "config.json"),
        help="Path to config.json. Defaults to the server folder.",
    )
    return parser.parse_args()


def main() -> None:
    init_winrt_runtime()
    args = parse_args()
    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    base_dir = config_path.parent
    config = load_config(config_path)
    app = create_app(config, base_dir)
    server_cfg = config["server"]
    web.run_app(app, host=str(server_cfg["host"]), port=int(server_cfg["port"]))


if __name__ == "__main__":
    main()
