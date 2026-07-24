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
```

Then start Spotify desktop playback on this PC. The overlay receives track changes and audio pulses from the local server. If the server is closed, the edited overlay falls back to its original standalone behavior.

## Custom Dance media

Use **Browse** on the Larpdog Dance page in Overlay Studio. Selected files are copied
into the top-level `user-assets` folder. A source can also be overridden with a URL param:

```text
http://127.0.0.1:8473/overlays/larpdog-dance?dog=user-assets/dancing.gif
```

Dancing assets can be `gif`, `webp`, `apng`, `png`, `webm`, `mp4`, or `mov`; the
overlay swaps the character image for a muted looping video automatically. Resting
images can be `png`, `jpg`, `jpeg`, `gif`, `webp`, or `apng`.

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

## Optional EXE build

After dependencies install, run:

```bat
build-exe.bat
```

The executable is written to `dist\overlay-studio-server.exe`. Keep `config.json` next to the exe.
