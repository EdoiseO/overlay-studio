from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def timedelta_ms(value: Any) -> int:
    if not isinstance(value, dt.timedelta):
        return 0
    return max(0, int(value.total_seconds() * 1000))


async def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Windows media sessions are only available on Windows.")

    from winrt.runtime import ApartmentType, init_apartment
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )

    init_apartment(ApartmentType.MULTI_THREADED)
    manager = await SessionManager.request_async()
    sessions = list(manager.get_sessions())
    session = next(
        (
            candidate
            for candidate in sessions
            if "spotify" in str(candidate.source_app_user_model_id or "").lower()
        ),
        manager.get_current_session(),
    )
    if session is None:
        print(json.dumps({"ok": True, "session": None}, indent=2))
        return

    props = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    timeline = session.get_timeline_properties()
    duration = timeline.end_time - timeline.start_time
    progress = timeline.position - timeline.start_time
    if playback.playback_status == PlaybackStatus.PLAYING and isinstance(timeline.last_updated_time, dt.datetime):
        progress += dt.datetime.now(timeline.last_updated_time.tzinfo or dt.timezone.utc) - timeline.last_updated_time

    print(
        json.dumps(
            {
                "ok": True,
                "sourceAppUserModelId": session.source_app_user_model_id,
                "playbackStatus": getattr(playback.playback_status, "name", str(playback.playback_status)),
                "title": clean_text(props.title),
                "artist": clean_text(props.artist),
                "album": clean_text(props.album_title),
                "progressMs": timedelta_ms(min(max(dt.timedelta(), progress), duration)),
                "durationMs": timedelta_ms(duration),
                "hasThumbnail": props.thumbnail is not None,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
