from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from aiohttp import web


APP_NAME = "larpdog-server"
DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 8473,
        "overlay_path": "../larpdog-overlay.html",
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
    "spotify": {
        "enabled": True,
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:8473/callback",
        "cache_path": ".spotify_cache",
        "poll_seconds": 3,
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
        loaded = json.loads(path.read_text(encoding="utf-8"))
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


class ClientHub:
    def __init__(self) -> None:
        self._clients: set[web.WebSocketResponse] = set()
        self._last_track: dict[str, Any] | None = None

    async def add(self, ws: web.WebSocketResponse) -> None:
        self._clients.add(ws)
        if self._last_track is not None:
            await ws.send_str(json.dumps(self._last_track, separators=(",", ":")))

    async def remove(self, ws: web.WebSocketResponse) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if message.get("type") == "track":
            self._last_track = message
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
        self.thread = threading.Thread(target=self._run, name="larpdog-audio", daemon=True)
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
        block_size = int(self.config.get("block_size", 2048))
        fps = max(1, float(self.config.get("fps", 45)))
        sensitivity = max(0.3, float(self.config.get("sensitivity", 1.0)))
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

                    bass = float(np.mean(spectrum[:bass_bins]))
                    bass_avg = bass_avg * 0.92 + bass * 0.08
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


class SpotifyWorker:
    def __init__(
        self,
        hub: ClientHub,
        callback_queue: asyncio.Queue[str],
        config: dict[str, Any],
        base_dir: Path,
    ) -> None:
        self.hub = hub
        self.callback_queue = callback_queue
        self.config = config
        self.base_dir = base_dir
        self.task: asyncio.Task[None] | None = None
        self.auth_manager: Any = None
        self.client: Any = None
        self.last_signature = ""

    def start(self) -> None:
        if not self.config.get("enabled", True):
            log("Spotify polling disabled in config.")
            asyncio.create_task(
                self.hub.broadcast({"type": "track", "isPlaying": False, "title": "", "artist": "", "art": None})
            )
            return
        self.task = asyncio.create_task(self._run(), name="larpdog-spotify")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    def _has_credentials(self) -> bool:
        return bool(self.config.get("client_id") and self.config.get("client_secret"))

    def _build_client(self) -> None:
        from spotipy import Spotify
        from spotipy.oauth2 import CacheFileHandler, SpotifyOAuth

        cache_path = resolve_path(str(self.config.get("cache_path") or ".spotify_cache"), self.base_dir)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_manager = SpotifyOAuth(
            client_id=str(self.config["client_id"]),
            client_secret=str(self.config["client_secret"]),
            redirect_uri=str(self.config["redirect_uri"]),
            scope="user-read-currently-playing user-read-playback-state",
            cache_handler=CacheFileHandler(cache_path=str(cache_path)),
            open_browser=False,
        )
        self.client = Spotify(auth_manager=self.auth_manager)

    async def _ensure_authorized(self) -> bool:
        if self.auth_manager is None or self.client is None:
            self._build_client()

        token = await asyncio.to_thread(self.auth_manager.get_cached_token)
        if token:
            return True

        auth_url = self.auth_manager.get_authorize_url()
        log("Opening Spotify login in your browser.")
        log(auth_url)
        with contextlib.suppress(Exception):
            webbrowser.open(auth_url)

        code = await self.callback_queue.get()
        await asyncio.to_thread(self.auth_manager.get_access_token, code, True)
        log("Spotify authorization saved. Future starts should reuse the cached refresh token.")
        return True

    async def _poll_once(self) -> None:
        data = await asyncio.to_thread(self.client.current_user_playing_track)
        payload: dict[str, Any]
        if not data or not data.get("is_playing") or not data.get("item"):
            payload = {"type": "track", "isPlaying": False, "title": "", "artist": "", "art": None}
        else:
            item = data["item"]
            artists = ", ".join(
                artist.get("name", "") for artist in item.get("artists", []) if artist.get("name")
            )
            images = ((item.get("album") or {}).get("images") or [])
            art = images[0].get("url") if images else None
            payload = {
                "type": "track",
                "isPlaying": True,
                "title": item.get("name") or "",
                "artist": artists,
                "art": art,
                "progressMs": data.get("progress_ms") or 0,
                "durationMs": item.get("duration_ms") or 0,
            }

        signature = json.dumps(payload, sort_keys=True)
        if signature != self.last_signature:
            self.last_signature = signature
            await self.hub.broadcast(payload)

    async def _run(self) -> None:
        if not self._has_credentials():
            log("Spotify credentials missing. Fill config.json to enable now-playing.")
            await self.hub.broadcast({"type": "track", "isPlaying": False, "title": "", "artist": "", "art": None})
            return

        poll_seconds = max(1.0, float(self.config.get("poll_seconds", 3)))
        while True:
            try:
                if await self._ensure_authorized():
                    await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log(f"Spotify polling error: {exc}")
            await asyncio.sleep(poll_seconds)


def create_app(config: dict[str, Any], base_dir: Path) -> web.Application:
    app = web.Application()
    hub = ClientHub()
    callback_queue: asyncio.Queue[str] = asyncio.Queue()
    app["hub"] = hub
    app["callback_queue"] = callback_queue
    app["config"] = config
    app["base_dir"] = base_dir

    async def serve_overlay(_request: web.Request) -> web.StreamResponse:
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        if not overlay_path.exists():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_path}")
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

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

    async def spotify_callback(request: web.Request) -> web.Response:
        if request.query.get("error"):
            return web.Response(
                text=f"Spotify authorization failed: {request.query['error']}",
                content_type="text/plain",
            )
        code = request.query.get("code")
        if not code:
            return web.Response(text="Missing Spotify code.", content_type="text/plain", status=400)
        await callback_queue.put(code)
        return web.Response(
            text="Spotify is connected. You can close this tab and return to OBS.",
            content_type="text/plain",
        )

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "app": APP_NAME})

    async def on_startup(startup_app: web.Application) -> None:
        loop = asyncio.get_running_loop()
        audio_worker = AudioLoopbackWorker(hub, loop, config.get("audio", {}))
        spotify_worker = SpotifyWorker(hub, callback_queue, config.get("spotify", {}), base_dir)
        startup_app["audio_worker"] = audio_worker
        startup_app["spotify_worker"] = spotify_worker
        audio_worker.start()
        spotify_worker.start()
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        log(f"Serving overlay: {overlay_path}")
        log(f"OBS URL: http://{config['server']['host']}:{config['server']['port']}/")

    async def on_cleanup(cleanup_app: web.Application) -> None:
        cleanup_app["audio_worker"].stop()
        await cleanup_app["spotify_worker"].stop()

    app.router.add_get("/", serve_overlay)
    app.router.add_get("/larpdog-overlay.html", serve_overlay)
    assets_dir = resolve_path(str(config["server"]["overlay_path"]), base_dir).parent / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir, show_index=False)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/callback", spotify_callback)
    app.router.add_get("/health", health)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local audio and Spotify companion for larpdog.")
    parser.add_argument(
        "--config",
        default=str(runtime_dir() / "config.json"),
        help="Path to config.json. Defaults to the server folder.",
    )
    return parser.parse_args()


def main() -> None:
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
