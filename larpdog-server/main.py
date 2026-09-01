from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import datetime as dt
import ipaddress
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from aiohttp import web

from counter_store import apply_counter_update, load_counter_state, save_counter_state
from goal_store import (
    GOAL_OVERLAY_TYPES,
    apply_goal_update,
    goal_defaults_for_type,
    load_goal_state,
    save_goal_state,
)
from overlay_config import (
    LEGACY_INSTANCE_IDS,
    canonical_overlay_type,
    is_valid_instance_id,
    load_overlay_config,
    materialize_instance_config,
    save_overlay_config,
    update_instance_config,
)
from overlay_manifest import OVERLAY_NAME, scan_overlay_manifests
from rivals_store import (
    RivalsStateFileError,
    linked_rivals_uid,
    rivals_status,
    update_rivals_record,
)
from rivals_worker import RivalsPollWorker
from time_tool_store import (
    TIME_TOOL_OVERLAY_TYPES,
    WallClockGuard,
    apply_time_tool_update,
    load_time_tool_state,
    save_time_tool_state,
)


APP_NAME = "overlay-studio-server"
CHALLENGE_COMPLETE_ASSET = (
    "minecraft/sounds/ui/toast/challenge_complete.ogg"
)
MAX_MINECRAFT_ASSET_INDEX_BYTES = 64 * 1024 * 1024
LEGACY_GOAL_OVERLAY_TYPE = "goal"
OVERLAY_ROUTE_PATTERN = (
    OVERLAY_NAME.pattern.removeprefix("^").removesuffix("$")
)
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
        "retry_initial_seconds": 1,
        "retry_max_seconds": 30,
        "retry_stable_seconds": 30,
    },
    "media": {
        "enabled": True,
        "poll_seconds": 2,
        "preferred_source": "spotify",
        "thumbnail_max_bytes": 524288,
        "manager_failure_threshold": 3,
        "retry_initial_seconds": 1,
        "retry_max_seconds": 30,
    },
    "rivals": {
        "enabled": True,
        "poll_seconds": 120,
        "profile_refresh_seconds": 300,
        "live_refresh_seconds": 120,
        "rate_limit_backoff_seconds": 300,
        "transient_backoff_seconds": 120,
        "max_requests_per_hour": 120,
        "timeout_seconds": 12,
    },
}


def find_installed_challenge_complete_sound(
    appdata_dir: Path | None = None,
) -> Path | None:
    if appdata_dir is None:
        appdata_value = os.environ.get("APPDATA")
        if not appdata_value:
            return None
        appdata_dir = Path(appdata_value)
    assets_dir = appdata_dir / ".minecraft" / "assets"
    indexes_dir = assets_dir / "indexes"
    objects_dir = assets_dir / "objects"
    if not indexes_dir.is_dir() or not objects_dir.is_dir():
        return None
    indexed_paths: list[tuple[int, str, Path]] = []
    try:
        index_paths = indexes_dir.glob("*.json")
        for index_path in index_paths:
            try:
                indexed_paths.append(
                    (index_path.stat().st_mtime_ns, index_path.name, index_path)
                )
            except OSError:
                continue
    except OSError:
        return None
    indexes = [item[2] for item in sorted(indexed_paths, reverse=True)]
    for index_path in indexes:
        try:
            if index_path.stat().st_size > MAX_MINECRAFT_ASSET_INDEX_BYTES:
                continue
            manifest = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        objects = manifest.get("objects")
        entry = objects.get(CHALLENGE_COMPLETE_ASSET) if isinstance(objects, dict) else None
        if not isinstance(entry, dict):
            continue
        asset_hash = str(entry.get("hash") or "").lower()
        if len(asset_hash) != 40 or any(
            character not in "0123456789abcdef" for character in asset_hash
        ):
            continue
        candidate = objects_dir / asset_hash[:2] / asset_hash
        try:
            if not candidate.is_file():
                continue
            expected_size = int(entry.get("size") or 0)
            if expected_size > 0 and candidate.stat().st_size != expected_size:
                continue
        except (OSError, TypeError, ValueError):
            continue
        return candidate
    return None


def _normalize_loopback_hostname(value: str | None) -> str | None:
    hostname = str(value or "").strip().rstrip(".").lower()
    if hostname == "localhost":
        return hostname
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    return address.compressed if address.is_loopback else None


def _parse_loopback_host(value: str) -> tuple[str, int] | None:
    if not value or value != value.strip() or any(char in value for char in "/?#"):
        return None
    try:
        parsed = urllib.parse.urlsplit(f"//{value}")
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    hostname = _normalize_loopback_hostname(parsed.hostname)
    if hostname is None:
        return None
    return hostname, port if port is not None else 80


def _parse_loopback_source(
    value: str,
    *,
    allow_path: bool,
) -> tuple[str, int] | None:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "http"
        or parsed.username is not None
        or parsed.password is not None
        or (not allow_path and parsed.path not in {"", "/"})
        or (not allow_path and (parsed.query or parsed.fragment))
    ):
        return None
    hostname = _normalize_loopback_hostname(parsed.hostname)
    if hostname is None:
        return None
    return hostname, port if port is not None else 80


def require_local_json_write(request: web.Request) -> None:
    if request.content_type.lower() != "application/json":
        raise web.HTTPUnsupportedMediaType(
            text="API writes require Content-Type: application/json"
        )

    host = _parse_loopback_host(request.headers.get("Host", ""))
    if host is None:
        raise web.HTTPForbidden(text="API writes require a loopback Host")

    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    if origin is not None:
        source = _parse_loopback_source(origin, allow_path=False)
    elif referer is not None:
        source = _parse_loopback_source(referer, allow_path=True)
    else:
        source = None
    if (origin is not None or referer is not None) and source != host:
        raise web.HTTPForbidden(
            text="Browser API writes must use the same loopback origin"
        )


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
        self._last_win_loss: dict[str, dict[str, Any]] = {}
        self._last_goals: dict[str, dict[str, Any]] = {}
        self._last_rivals: dict[str, dict[str, Any]] = {}

    async def add(self, ws: web.WebSocketResponse) -> None:
        self._clients.add(ws)
        if self._last_track is not None:
            await ws.send_str(json.dumps(self._last_track, separators=(",", ":")))
        for message in self._last_win_loss.values():
            await ws.send_str(json.dumps(message, separators=(",", ":")))
        for message in self._last_goals.values():
            await ws.send_str(json.dumps(message, separators=(",", ":")))
        for message in self._last_rivals.values():
            await ws.send_str(json.dumps(message, separators=(",", ":")))

    async def remove(self, ws: web.WebSocketResponse) -> None:
        self._clients.discard(ws)

    def latest_track(self) -> dict[str, Any]:
        if self._last_track is not None:
            return dict(self._last_track)
        return {
            "type": "track",
            "isPlaying": False,
            "trackId": "",
            "title": "",
            "artist": "",
            "art": None,
            "progressMs": 0,
            "durationMs": 0,
            "source": "windows-media",
            "sourceApp": "",
            "mediaStatus": "idle",
            "spotifyStatus": "waiting",
            "spotifyTrack": None,
        }

    async def broadcast(self, message: dict[str, Any]) -> None:
        if message.get("type") == "track":
            self._last_track = message
        elif message.get("type") == "win-loss":
            key = str(message.get("instanceId") or "")
            self._last_win_loss[key] = message
        elif message.get("type") == "goal":
            key = str(message.get("instanceId") or "")
            cached = dict(message)
            cached.pop("event", None)
            self._last_goals[key] = cached
        elif message.get("type") == "rivals":
            key = str(message.get("instanceId") or "")
            self._last_rivals[key] = message
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
        self.last_device_name = ""

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

    def _capture_once(self, np: Any, sc: Any) -> None:
        sample_rate = int(self.config.get("sample_rate", 48000))
        block_size = int(self.config.get("block_size", 1024))
        fps = max(1, float(self.config.get("fps", 45)))
        bass_bins = max(1, int(self.config.get("bass_bins", 14)))
        target_dt = 1.0 / fps

        mic = self._pick_loopback(sc)
        device_name = str(getattr(mic, "name", mic))
        if device_name != self.last_device_name:
            log(f"Audio loopback capture: {device_name}")
            self.last_device_name = device_name
        with mic.recorder(
            samplerate=sample_rate,
            channels=2,
            blocksize=block_size,
        ) as recorder:
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

                # Keep this math in sync with startRealAudio() in overlay-studio.html.
                bass = float(np.mean(spectrum[:bass_bins]))
                bass_avg = bass_avg * 0.92 + bass * 0.08
                sensitivity = max(
                    0.3,
                    float(self.config.get("sensitivity", 1.0)),
                )
                threshold = bass_avg * (1.35 / sensitivity)
                now = time.perf_counter()
                beat = (
                    bass > threshold
                    and bass > 1e-7
                    and (now - last_beat) > 0.110
                )
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
                    bands.append(
                        clamp01(raw / max(band_avgs[idx] * 2.4, 1e-9))
                    )

                self._schedule_broadcast(
                    {
                        "type": "audio",
                        "level": round(max(pulse, bass_level * 0.55), 4),
                        "beat": bool(beat),
                        "bands": [round(v, 4) for v in bands],
                    }
                )

    def _run_supervised(self, np: Any, sc: Any) -> None:
        retry_initial = max(
            0.1,
            float(self.config.get("retry_initial_seconds", 1)),
        )
        retry_max = max(
            retry_initial,
            float(self.config.get("retry_max_seconds", 30)),
        )
        stable_seconds = max(
            0.0,
            float(self.config.get("retry_stable_seconds", 30)),
        )
        retry_delay = retry_initial
        last_error = ""

        while not self.stop_event.is_set():
            started_at = time.monotonic()
            try:
                self._capture_once(np, sc)
                if self.stop_event.is_set():
                    return
                raise RuntimeError("Audio capture ended unexpectedly")
            except Exception as exc:
                if self.stop_event.is_set():
                    return
                if time.monotonic() - started_at >= stable_seconds:
                    retry_delay = retry_initial
                    last_error = ""
                error = f"{type(exc).__name__}: {exc}"
                if error != last_error:
                    log(
                        "Audio capture interrupted: "
                        f"{exc}; retrying in {retry_delay:g}s"
                    )
                    last_error = error
                if self.stop_event.wait(retry_delay):
                    return
                retry_delay = min(retry_max, retry_delay * 2)

    def _run(self) -> None:
        try:
            import numpy as np
            import soundcard as sc
        except Exception as exc:
            log(f"Audio dependencies unavailable: {exc}")
            return

        self._run_supervised(np, sc)


class MediaSessionWorker:
    def __init__(self, hub: ClientHub, config: dict[str, Any]) -> None:
        self.hub = hub
        self.config = config
        self.task: asyncio.Task[None] | None = None
        self.manager: Any = None
        self.playing_status: Any = None
        self.last_signature = ""
        self.track_cache: dict[str, dict[str, Any]] = {}
        self.last_spotify_track: dict[str, Any] | None = None
        self.last_manager_error = ""

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
        payload = self._empty_track()
        payload["spotifyStatus"] = "waiting"
        payload["spotifyTrack"] = self.last_spotify_track
        await self._broadcast(payload)

    @staticmethod
    def _empty_track(
        *,
        media_status: str = "idle",
        source_app: str = "",
    ) -> dict[str, Any]:
        return {
            "type": "track",
            "isPlaying": False,
            "trackId": "",
            "title": "",
            "artist": "",
            "art": None,
            "progressMs": 0,
            "durationMs": 0,
            "source": "windows-media",
            "sourceApp": source_app,
            "mediaStatus": media_status,
        }

    def _log_manager_error(self, prefix: str, error: Any) -> None:
        message = f"{prefix}: {error}"
        if message == self.last_manager_error:
            return
        self.last_manager_error = message
        log(message)

    async def _ensure_manager(self) -> bool:
        if self.manager is not None:
            return True
        if sys.platform != "win32":
            self._log_manager_error(
                "Windows media sessions unavailable",
                "only supported on Windows",
            )
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
            self.manager = None
            self.playing_status = None
            self._log_manager_error("Windows media sessions unavailable", exc)
            await self._broadcast_idle()
            return False

        if self.manager is None:
            self._log_manager_error(
                "Windows media sessions unavailable",
                "session manager request returned no manager",
            )
            await self._broadcast_idle()
            return False

        log("Windows media session polling enabled.")
        return True

    def _reset_manager(self) -> None:
        manager = self.manager
        self.manager = None
        self.playing_status = None
        close = getattr(manager, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()

    def _select_session(
        self,
        mode: str = "general",
        sessions: list[Any] | None = None,
    ) -> Any:
        if mode not in {"strict", "general"}:
            raise ValueError(f"Unknown media selection mode: {mode}")
        available = (
            list(self.manager.get_sessions())
            if sessions is None
            else sessions
        )
        preferred = str(self.config.get("preferred_source") or "spotify").strip().lower()
        if preferred:
            for session in available:
                source = str(getattr(session, "source_app_user_model_id", "") or "").lower()
                if preferred in source:
                    return session
        if mode == "strict":
            return None
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
        source_app = self._clean_text(
            getattr(session, "source_app_user_model_id", "")
        )
        cache_key = source_app.casefold() or "__unknown__"
        playback = session.get_playback_info()
        is_playing = getattr(playback, "playback_status", None) == self.playing_status
        media_status = "playing" if is_playing else "paused"

        props = await session.try_get_media_properties_async()
        title = self._clean_text(getattr(props, "title", ""))
        artist = self._clean_text(getattr(props, "artist", ""))
        album = self._clean_text(getattr(props, "album_title", ""))
        if not title:
            cached = self.track_cache.get(cache_key)
            if cached:
                payload = dict(cached)
                payload["isPlaying"] = is_playing
                payload["mediaStatus"] = media_status
                progress_ms, duration_ms = self._timeline_values(
                    session,
                    is_playing=is_playing,
                )
                if duration_ms > 0:
                    payload["progressMs"] = progress_ms
                    payload["durationMs"] = duration_ms
                return payload
            return self._empty_track(
                media_status=media_status,
                source_app=source_app,
            )

        identity = self._identity(title, artist, album)
        cached = self.track_cache.get(cache_key)
        if cached and cached.get("trackId") == identity:
            art = cached.get("art")
        else:
            art = await self._thumbnail_data_url(
                getattr(props, "thumbnail", None)
            )

        progress_ms, duration_ms = self._timeline_values(
            session,
            is_playing=is_playing,
        )
        payload = {
            "type": "track",
            "isPlaying": is_playing,
            "trackId": identity,
            "title": title,
            "artist": artist,
            "art": art,
            "progressMs": progress_ms,
            "durationMs": duration_ms,
            "source": "windows-media",
            "sourceApp": source_app,
            "mediaStatus": media_status,
        }
        if cache_key not in self.track_cache and len(self.track_cache) >= 8:
            self.track_cache.pop(next(iter(self.track_cache)))
        self.track_cache[cache_key] = dict(payload)
        return payload

    @staticmethod
    def _track_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: payload.get(key)
            for key in (
                "trackId",
                "title",
                "artist",
                "art",
                "progressMs",
                "durationMs",
                "sourceApp",
            )
        }

    async def _poll_once(self) -> None:
        sessions = list(self.manager.get_sessions())
        spotify_session = self._select_session("strict", sessions)
        general_session = self._select_session("general", sessions)

        # Top-level track fields belong to the general Windows-media route for
        # legacy/root overlays. Spotify-only consumers use the fields below.
        if general_session is None:
            payload = self._empty_track()
        else:
            payload = await self._payload_from_session(general_session)
            if payload is None:
                payload = self._empty_track()

        spotify_payload: dict[str, Any] | None = None
        if spotify_session is not None:
            if spotify_session is general_session:
                spotify_payload = payload
            else:
                spotify_payload = await self._payload_from_session(
                    spotify_session
                )

        if spotify_payload is None:
            spotify_status = "waiting"
        else:
            spotify_status = str(
                spotify_payload.get("mediaStatus") or "paused"
            )
            if spotify_payload.get("title"):
                self.last_spotify_track = self._track_snapshot(
                    spotify_payload
                )

        payload["spotifyStatus"] = spotify_status
        if spotify_payload is None or not spotify_payload.get("title"):
            payload["spotifyTrack"] = self.last_spotify_track
        await self._broadcast(payload)

    async def _run(self) -> None:
        poll_seconds = max(0.5, float(self.config.get("poll_seconds", 2)))
        failure_threshold = max(
            1,
            int(self.config.get("manager_failure_threshold", 3)),
        )
        retry_initial = max(
            0.1,
            float(self.config.get("retry_initial_seconds", 1)),
        )
        retry_max = max(
            retry_initial,
            float(self.config.get("retry_max_seconds", 30)),
        )
        retry_delay = retry_initial
        consecutive_failures = 0

        while True:
            if self.manager is None:
                if not await self._ensure_manager():
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_max, retry_delay * 2)
                    continue
                consecutive_failures = 0
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_failures += 1
                self._log_manager_error("Windows media polling error", exc)
                await self._broadcast_idle()
                if consecutive_failures >= failure_threshold:
                    self._reset_manager()
                    consecutive_failures = 0
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_max, retry_delay * 2)
                    continue
            else:
                consecutive_failures = 0
                retry_delay = retry_initial
                self.last_manager_error = ""
            await asyncio.sleep(poll_seconds)


@web.middleware
async def api_write_guard_middleware(
    request: web.Request,
    handler: Any,
) -> web.StreamResponse:
    if (
        request.path.startswith("/api/")
        and request.method not in {"GET", "HEAD", "OPTIONS"}
    ):
        require_local_json_write(request)
    return await handler(request)


def create_app(config: dict[str, Any], base_dir: Path) -> web.Application:
    app = web.Application(middlewares=[api_write_guard_middleware])
    hub = ClientHub()
    overlay_config_path = base_dir / "overlay-config.json"
    counter_state_path = base_dir / "win-loss.json"
    goal_state_path = base_dir / "goal.json"
    time_tool_state_path = base_dir / "time-tools.json"
    countdown_completion_sound = find_installed_challenge_complete_sound()
    time_tool_clock_guard = WallClockGuard()
    rivals_state_path = base_dir / "rivals.json"
    overlays_dir = base_dir.parent / "overlays"
    rivals_store_lock = asyncio.Lock()
    app["hub"] = hub
    app["config"] = config
    app["base_dir"] = base_dir
    app["overlay_config_path"] = overlay_config_path
    app["counter_state_path"] = counter_state_path
    app["goal_state_path"] = goal_state_path
    app["time_tool_state_path"] = time_tool_state_path
    app["rivals_state_path"] = rivals_state_path
    app["rivals_store_lock"] = rivals_store_lock

    def request_instance(
        request: web.Request,
        expected_type: str | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        saved_config = load_overlay_config(overlay_config_path)
        supplied = request.query.get("i")
        if supplied is None or supplied == "":
            return None, saved_config
        if not is_valid_instance_id(supplied):
            raise web.HTTPBadRequest(text="Invalid overlay instance")
        instance = saved_config["instances"].get(supplied)
        if not isinstance(instance, dict):
            raise web.HTTPNotFound(text="Overlay instance not found")
        if expected_type is not None and instance["type"] != expected_type:
            raise web.HTTPNotFound(text="Overlay instance type does not match")
        return supplied, saved_config

    async def serve_overlay(request: web.Request) -> web.StreamResponse:
        expected_type = {
            "/overlays/larpdog-dance": "larpdog-dance",
            "/overlays/larpdog-dance.html": "larpdog-dance",
            "/overlays/spotify": "spotify",
            "/overlays/spotify.html": "spotify",
        }.get(request.path)
        if expected_type is not None:
            request_instance(request, expected_type)
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        if not overlay_path.exists():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_path}")
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

    async def serve_overlay_config(request: web.Request) -> web.Response:
        instance_id, saved_config = request_instance(request)
        payload = json.dumps(
            materialize_instance_config(saved_config, instance_id),
            separators=(",", ":"),
        )
        return web.Response(
            text=(
                f"window.OVERLAY_STUDIO_CONFIG={payload};"
                "window.LARPDOG_CONFIG=window.OVERLAY_STUDIO_CONFIG;"
            ),
            content_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    async def serve_countdown_completion_sound(
        _request: web.Request,
    ) -> web.StreamResponse:
        if countdown_completion_sound is None:
            raise web.HTTPNotFound(
                text="Installed Challenge Complete sound was not found"
            )
        return web.FileResponse(
            countdown_completion_sound,
            headers={
                "Cache-Control": "private, max-age=3600",
                "Content-Type": "audio/ogg",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def get_overlay_config(request: web.Request) -> web.Response:
        instance_id, saved_config = request_instance(request)
        response_config = (
            materialize_instance_config(saved_config, instance_id)
            if instance_id
            else saved_config
        )
        return web.json_response(
            response_config,
            headers={"Cache-Control": "no-store"},
        )

    async def get_overlays(_request: web.Request) -> web.Response:
        return web.json_response(
            {"overlays": scan_overlay_manifests(overlays_dir)},
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
        instance_id, current_config = request_instance(request)
        if instance_id:
            try:
                updated = update_instance_config(
                    current_config,
                    instance_id,
                    submitted,
                )
            except ValueError as exc:
                raise web.HTTPBadRequest(text=str(exc)) from None
            saved_config = save_overlay_config(overlay_config_path, updated)
            instance_config = materialize_instance_config(
                saved_config,
                instance_id,
            )
            await hub.broadcast(
                {
                    "type": "config",
                    "instanceId": instance_id,
                    "config": instance_config,
                }
            )
            instance = saved_config["instances"][instance_id]
            if LEGACY_INSTANCE_IDS.get(instance["type"]) == instance_id:
                await hub.broadcast({"type": "config", "config": saved_config})
        else:
            saved_config = save_overlay_config(overlay_config_path, submitted)
            await hub.broadcast({"type": "config", "config": saved_config})
        config.setdefault("audio", {})["sensitivity"] = saved_config["audio"]["sensitivity"]
        return web.json_response(saved_config)

    async def serve_win_loss(request: web.Request) -> web.StreamResponse:
        request_instance(request, "win-loss")
        overlay_path = overlays_dir / "win-loss.html"
        if not overlay_path.exists():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_path}")
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

    async def serve_overlay_page(request: web.Request) -> web.StreamResponse:
        overlay_name = request.match_info.get("overlay_name", "")
        if not OVERLAY_NAME.fullmatch(overlay_name):
            raise web.HTTPNotFound(text="Overlay not found")
        canonical_name = canonical_overlay_type(overlay_name)
        overlay_path = overlays_dir / f"{canonical_name}.html"
        if not overlay_path.is_file():
            raise web.HTTPNotFound(text=f"Overlay not found: {overlay_name}")
        request_instance(request, canonical_name)
        return web.FileResponse(overlay_path, headers={"Cache-Control": "no-store"})

    async def get_win_loss(request: web.Request) -> web.Response:
        instance_id, _saved_config = request_instance(request, "win-loss")
        return web.json_response(
            load_counter_state(counter_state_path, instance_id),
            headers={"Cache-Control": "no-store"},
        )

    def request_goal_context(request: web.Request) -> tuple[str | None, str]:
        instance_id, saved_config = request_instance(request)
        if not instance_id:
            # Unaddressed requests intentionally retain the original ring endpoint.
            return None, LEGACY_GOAL_OVERLAY_TYPE
        return instance_id, saved_config["instances"][instance_id]["type"]

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
        instance_id, _saved_config = request_instance(request, "win-loss")
        try:
            state = apply_counter_update(
                load_counter_state(counter_state_path, instance_id),
                submitted,
            )
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        saved_state = save_counter_state(
            counter_state_path,
            state,
            instance_id,
        )
        addressed_message: dict[str, Any] = {
            "type": "win-loss",
            "state": saved_state,
        }
        if instance_id:
            addressed_message["instanceId"] = instance_id
        await hub.broadcast(addressed_message)
        if instance_id == LEGACY_INSTANCE_IDS["win-loss"]:
            await hub.broadcast({"type": "win-loss", "state": saved_state})
        return web.json_response(saved_state)

    async def get_goal(request: web.Request) -> web.Response:
        instance_id, overlay_type = request_goal_context(request)
        if overlay_type not in GOAL_OVERLAY_TYPES:
            raise web.HTTPNotFound(text="Overlay instance type does not match")
        return web.json_response(
            load_goal_state(
                goal_state_path,
                instance_id,
                goal_defaults_for_type(overlay_type),
            ),
            headers={"Cache-Control": "no-store"},
        )

    async def update_goal(request: web.Request) -> web.Response:
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
        instance_id, overlay_type = request_goal_context(request)
        if overlay_type not in GOAL_OVERLAY_TYPES:
            raise web.HTTPNotFound(text="Overlay instance type does not match")
        previous = load_goal_state(
            goal_state_path,
            instance_id,
            goal_defaults_for_type(overlay_type),
        )
        try:
            state = apply_goal_update(previous, submitted)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        saved_state = save_goal_state(goal_state_path, state, instance_id)
        message: dict[str, Any] = {
            "type": "goal",
            "state": saved_state,
        }
        if instance_id:
            message["instanceId"] = instance_id
        action = str(submitted.get("action") or "").strip().lower()
        delta = round(saved_state["current"] - previous["current"], 2)
        if action in {"add", "subtract"} and delta:
            message["event"] = {"amount": delta}
        elif action == "complete" and previous["current"] < previous["target"]:
            message["event"] = {"text": "Goal complete"}
        await hub.broadcast(message)
        return web.json_response(saved_state)

    def request_time_tool_context(request: web.Request) -> tuple[str, str]:
        instance_id, saved_config = request_instance(request)
        if not instance_id:
            raise web.HTTPBadRequest(
                text="Time-tool API requests require an overlay instance"
            )
        overlay_type = saved_config["instances"][instance_id]["type"]
        if overlay_type not in TIME_TOOL_OVERLAY_TYPES:
            raise web.HTTPNotFound(text="Overlay instance type does not match")
        return instance_id, overlay_type

    async def get_time_tool(request: web.Request) -> web.Response:
        instance_id, overlay_type = request_time_tool_context(request)
        return web.json_response(
            load_time_tool_state(
                time_tool_state_path,
                instance_id,
                overlay_type,
                clock_guard=time_tool_clock_guard,
            ),
            headers={"Cache-Control": "no-store"},
        )

    async def update_time_tool(request: web.Request) -> web.Response:
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
        instance_id, overlay_type = request_time_tool_context(request)
        previous = load_time_tool_state(
            time_tool_state_path,
            instance_id,
            overlay_type,
            clock_guard=time_tool_clock_guard,
        )
        try:
            state = apply_time_tool_update(
                previous,
                submitted,
                overlay_type,
                clock_guard=time_tool_clock_guard,
            )
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        if str(submitted.get("action") or "").strip().lower() == "test-sound":
            await hub.broadcast(
                {
                    "type": "time-tool-sound",
                    "overlayType": overlay_type,
                    "instanceId": instance_id,
                    "state": {
                        "soundEnabled": state["soundEnabled"],
                        "soundPreset": state["soundPreset"],
                        "customSound": state["customSound"],
                        "soundVolume": state["soundVolume"],
                    },
                }
            )
            return web.json_response(previous)
        saved_state = save_time_tool_state(
            time_tool_state_path,
            state,
            instance_id,
            overlay_type,
        )
        await hub.broadcast(
            {
                "type": "time-tool",
                "overlayType": overlay_type,
                "instanceId": instance_id,
                "state": saved_state,
            }
        )
        return web.json_response(saved_state)

    def request_rivals_instance(request: web.Request) -> str:
        instance_id, _saved_config = request_instance(request, "rivals-rank")
        if not instance_id:
            raise web.HTTPBadRequest(
                text="Rivals API requests require an overlay instance"
            )
        return instance_id

    async def get_rivals(request: web.Request) -> web.Response:
        instance_id = request_rivals_instance(request)
        try:
            async with rivals_store_lock:
                payload = rivals_status(rivals_state_path, instance_id)
        except RivalsStateFileError as exc:
            log(f"CRITICAL: {exc}")
            raise web.HTTPInternalServerError(text=str(exc)) from None
        return web.json_response(
            payload,
            headers={"Cache-Control": "no-store"},
        )

    async def update_rivals(request: web.Request) -> web.Response:
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
        instance_id = request_rivals_instance(request)
        action = str(submitted.get("action") or "").strip().lower()
        try:
            async with rivals_store_lock:
                previous_uid = linked_rivals_uid(
                    rivals_state_path,
                    instance_id,
                )
                payload = update_rivals_record(
                    rivals_state_path,
                    instance_id,
                    submitted,
                )
                current_uid = linked_rivals_uid(
                    rivals_state_path,
                    instance_id,
                )
        except RivalsStateFileError as exc:
            log(f"CRITICAL: {exc}")
            raise web.HTTPInternalServerError(text=str(exc)) from None
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        rivals_worker: RivalsPollWorker = request.app["rivals_worker"]
        if current_uid is not None and current_uid != previous_uid:
            rivals_worker.wake_for_link(current_uid)
        if action == "refresh":
            payload["refresh"] = (
                rivals_worker.request_manual_refresh(current_uid)
                if current_uid is not None
                else {
                    "accepted": False,
                    "retryAfter": 0,
                    "retryAt": 0,
                    "detail": "Link a Rivals Data account first",
                }
            )
        await hub.broadcast(
            {
                "type": "rivals",
                "instanceId": instance_id,
                "state": payload["state"],
            }
        )
        return web.json_response(payload)

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
        rivals_worker = RivalsPollWorker(
            rivals_state_path,
            hub.broadcast,
            config.get("rivals", {}),
            store_lock=rivals_store_lock,
            logger=log,
        )
        startup_app["audio_worker"] = audio_worker
        startup_app["media_worker"] = media_worker
        startup_app["rivals_worker"] = rivals_worker
        audio_worker.start()
        media_worker.start()
        rivals_worker.start()
        overlay_path = resolve_path(str(config["server"]["overlay_path"]), base_dir)
        log(f"Serving overlay: {overlay_path}")
        log(f"OBS URL: http://{config['server']['host']}:{config['server']['port']}/")

    async def on_cleanup(cleanup_app: web.Application) -> None:
        cleanup_app["audio_worker"].stop()
        await cleanup_app["media_worker"].stop()
        await cleanup_app["rivals_worker"].stop()

    app.router.add_get("/", serve_overlay)
    app.router.add_get("/overlay-studio.html", serve_overlay)
    app.router.add_get("/overlays/larpdog-dance", serve_overlay)
    app.router.add_get("/overlays/larpdog-dance.html", serve_overlay)
    app.router.add_get("/overlays/spotify", serve_overlay)
    app.router.add_get("/overlays/spotify.html", serve_overlay)
    app.router.add_get("/larpdog-overlay.html", serve_overlay)
    app.router.add_get("/overlay-config.js", serve_overlay_config)
    app.router.add_get(
        "/local-assets/countdown-completion.ogg",
        serve_countdown_completion_sound,
    )
    app.router.add_get("/api/config", get_overlay_config)
    app.router.add_post("/api/config", update_overlay_config)
    app.router.add_get("/api/overlays", get_overlays)
    app.router.add_get("/api/now-playing", get_now_playing)
    app.router.add_get("/overlays/win-loss", serve_win_loss)
    app.router.add_get("/overlays/win-loss.html", serve_win_loss)
    app.router.add_get(
        f"/overlays/{{overlay_name:{OVERLAY_ROUTE_PATTERN}}}",
        serve_overlay_page,
    )
    app.router.add_get(
        f"/overlays/{{overlay_name:{OVERLAY_ROUTE_PATTERN}}}.html",
        serve_overlay_page,
    )
    app.router.add_get("/api/win-loss", get_win_loss)
    app.router.add_post("/api/win-loss", update_win_loss)
    app.router.add_get("/api/goal", get_goal)
    app.router.add_post("/api/goal", update_goal)
    app.router.add_get("/api/time-tool", get_time_tool)
    app.router.add_post("/api/time-tool", update_time_tool)
    app.router.add_get("/api/rivals", get_rivals)
    app.router.add_post("/api/rivals", update_rivals)
    assets_dir = resolve_path(str(config["server"]["overlay_path"]), base_dir).parent / "assets"
    resource_root = Path(getattr(sys, "_MEIPASS", assets_dir.parent))
    bundled_fonts_dir = resource_root / "assets" / "fonts"
    fonts_dir = bundled_fonts_dir if bundled_fonts_dir.exists() else assets_dir / "fonts"
    if fonts_dir.exists():
        app.router.add_static("/assets/fonts", fonts_dir, show_index=False)
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
