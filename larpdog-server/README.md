# Overlay Studio server

Local HTTP, websocket, system-audio, and Windows media-session companion for Overlay
Studio. Most users should launch it through the root `Overlay Studio.bat`; use the
commands in this folder for standalone development and troubleshooting.

The default address is `http://127.0.0.1:8473/`. A local `config.json` can change the
port, so use the exact address shown in the desktop app. The service captures Windows
system audio through WASAPI loopback and sends beat/EQ plus Windows now-playing data
over `/ws`.

## One-time setup

1. Install Python 3.11 or newer.
2. In this folder, install dependencies. The easiest path is:

```bat
install.bat
```

Or run the commands manually:

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

3. Copy `config.example.json` to `config.json` if you need to change the port, audio device, or media polling options.

`config.json` and `.spotify_cache*` are ignored by git. Old Spotify cache files may still exist locally from earlier versions; do not commit them.

## Run

```bat
run.bat
```

The server reads now-playing data from Windows media sessions, so Spotify desktop playback works without a Spotify developer app, OAuth login, refresh token, or browser extension.

To verify Windows media metadata before starting the server, run:

```bat
.venv\Scripts\python check-media-session.py
```

## OBS

Add separate OBS Browser sources with these URLs:

```text
http://127.0.0.1:8473/overlays/larpdog-dance
http://127.0.0.1:8473/overlays/spotify
http://127.0.0.1:8473/overlays/win-loss
http://127.0.0.1:8473/overlays/goal
http://127.0.0.1:8473/overlays/goal-bar
http://127.0.0.1:8473/overlays/goal-pill
http://127.0.0.1:8473/overlays/rivals-rank
```

Dedicated overlay pages center their content on a transparent canvas. Use OBS to
position the Browser Source in the scene. The legacy combined overlay and explicit
`?pos=bottom-left`, `bottom-right`, `top-left`, or `top-right` links keep their original
corner anchoring.

Then start Spotify desktop playback on this PC. The overlay receives track changes and audio pulses from the local server. If the server is closed, the edited overlay falls back to its original standalone behavior.

## Custom Dance media

Use **Add media** on the Dancing GIF page in Overlay Studio. Selected files are copied
into `user-assets/dancing` or `user-assets/resting`. The desktop media library supports
one fixed dance or a random pool that chooses a new dance when the song changes and
keeps it across pause and resume. Imported files can be removed from their tile with the
trash button; built-in assets cannot be deleted. Dancing and resting imports live in
separate folders, so deleting from one library does not affect the other. Dancing files
are signature-checked during import, and missing or undecodable selections fall back
without replacing the visible overlay with a broken image. Files up to 25 MB can be
dropped directly onto the media library. Windows `.url` shortcuts to
public HTTPS media or media pages with Open Graph links can be selected or dropped too;
the downloaded file is validated and limited to 25 MB.

Each Dancing GIF instance supports up to five named profiles. Profiles preserve their
own resting image, dancing selection or random pool, scale, sensitivity, and fallback
BPM. The active profile is materialized into the legacy dance, audio, and now-playing
fields so existing overlay pages and OBS browser-source URLs continue to work.

A source can be overridden with a URL param:

```text
http://127.0.0.1:8473/overlays/larpdog-dance?dog=user-assets/dancing.gif
```

Dancing assets can be `gif`, `webp`, `apng`, `png`, `webm`, `mp4`, or `mov`; the
overlay swaps the character image for a muted looping video automatically. Resting
images can be `png`, `jpg`, `jpeg`, `gif`, `webp`, or `apng`.

## Rivals Rank data

The Rivals Rank Tracker links a numeric Rivals Data player ID server-side. Its default
worker, profile, and live-history cadence is five minutes. Requests are deduplicated by
player ID, and cached history is fallback-only after a live refresh rather than an
independent high-frequency request. Normal steady state is therefore about 24
requests/hour per unique linked account, or up to about 36 when every live refresh needs
the cached fallback.

A `429`, 403, 408, 5xx response, or browser challenge stops the current request chain
and pauses every linked tracker. The document-level cooldown and failure ladder survive
process restarts. Repeated limits escalate, successful request cycles reduce the ladder
one step at a time, and a persisted rolling budget hard-caps the app at 120 outbound
Rivals Data requests/hour. New match IDs update each instance's session record; a failed
or malformed response leaves the last successful public state unchanged. The private
player ID, match bookkeeping, cooldown, and request budget live in `rivals.json` and are
never included in `/api/rivals` responses or websocket messages.

Rivals Data is an undocumented fan service, not an official NetEase or Marvel Rivals
API. Treat availability and response shape as best effort.

For best transparency and small files, export transparent WebM:

```bat
ffmpeg -i in.mov -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 user-assets\dancing.webm
```

## Color controls

By default, the overlay recolors itself from album art and falls back to the character palette. You can override that with hex params:

```text
http://127.0.0.1:8473/overlays/spotify?colorMode=fixed&a=00ffd0&b=ffd24a&c=ff4d9d
```

- `colorMode=auto`: album art first, then user colors, then the character palette.
- `colorMode=fixed`: always use `a`, `b`, and `c`.
- `colorMode=art`: album art first, then `a`, `b`, and `c`.

## Config notes

- `audio.sensitivity`: higher values react to quieter kicks.
- `audio.device_match`: optional substring if you need a specific loopback device.
- `server.overlay_path`: defaults to `../overlay-studio.html`.
- `media.poll_seconds`: default is 2 seconds.
- `media.preferred_source`: default is `spotify`; used to pick Spotify when multiple media apps are active.
- `media.thumbnail_max_bytes`: maximum Windows media thumbnail size to embed in websocket messages.
- `rivals.enabled`: enables or disables Rivals Data polling.
- `rivals.poll_seconds`: worker check interval, clamped to 60 through 900 seconds; default is 300. Checks that occur before profile/live data is due do not request cached history.
- `rivals.profile_refresh_seconds`: profile refresh interval, clamped to 120 through 900 seconds; default is 300.
- `rivals.live_refresh_seconds`: live match-history refresh interval, clamped to 60 through 900 seconds; default is 300.
- `rivals.rate_limit_backoff_seconds`: fallback `429` cooldown, clamped to 60 through 3600 seconds; default is 300 and escalates after repeated limits.
- `rivals.transient_backoff_seconds`: initial 403/408/5xx or challenge-page cooldown; default is 120 seconds and uses the same escalation ladder.
- `rivals.max_requests_per_hour`: persisted rolling request cap across every Rivals endpoint and instance; clamped to 12 through 120 and defaults to 120.
- `rivals.timeout_seconds`: per-request timeout, clamped to 3 through 30 seconds.

## Optional EXE build

After dependencies install, run:

```bat
build-exe.bat
```

The executable is written to `dist\overlay-studio-server.exe`. Keep `config.json` next to the exe.
