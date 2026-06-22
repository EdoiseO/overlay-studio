# larpdog-server

Local companion for `larpdog-overlay.html`.

It serves the overlay at `http://127.0.0.1:8473/`, captures Windows system audio through WASAPI loopback, sends beat/EQ data over `/ws`, and polls Spotify with a cached refresh token after one login.

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

3. Create a Spotify app at https://developer.spotify.com/dashboard.
4. Add this Redirect URI to the Spotify app:

```text
http://127.0.0.1:8473/callback
```

5. Copy `config.example.json` to `config.json`, then paste your Spotify `client_id` into `config.json`.

`config.json` and `.spotify_cache` are ignored by git. Do not commit them.

## Run

```bat
run.bat
```

On first Spotify use, the server opens a browser login using Spotify PKCE, so this local desktop overlay does not need a client secret. After approval, Spotipy stores a refresh token in `.spotify_cache`, so later restarts do not need a new login.

## OBS

Add a Browser source with this URL:

```text
http://127.0.0.1:8473/
```

For separate OBS sources, use:

```text
http://127.0.0.1:8473/?asset=dog
http://127.0.0.1:8473/?asset=player
```

Then start Spotify playback. The overlay receives track changes and audio pulses from the local server. If the server is closed, the edited overlay falls back to its original standalone behavior.

## Custom character assets

Drop custom files into the top-level `user-assets` folder, then point the overlay at them with URL params:

```text
http://127.0.0.1:8473/?dog=user-assets/dancing.webm&rest=user-assets/resting.png
```

Image assets can be `gif`, `webp`, `apng`, or `png`. Video assets can be `webm`, `mp4`, or `mov`; the overlay swaps the character image for a muted looping video automatically. For best transparency and small files, export transparent WebM:

```bat
ffmpeg -i in.mov -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 user-assets\dancing.webm
```

## Color controls

By default, the overlay recolors itself from album art and falls back to the character palette. You can override that with hex params:

```text
http://127.0.0.1:8473/?colorMode=fixed&a=00ffd0&b=ffd24a&c=ff4d9d
```

- `colorMode=auto`: album art first, then user colors, then the character palette.
- `colorMode=fixed`: always use `a`, `b`, and `c`.
- `colorMode=art`: album art first, then `a`, `b`, and `c`.

## Config notes

- `audio.sensitivity`: higher values react to quieter kicks.
- `audio.device_match`: optional substring if you need a specific loopback device.
- `server.overlay_path`: defaults to `../larpdog-overlay.html`, which works when this folder sits beside the overlay file.
- `spotify.poll_seconds`: default is 3 seconds.

## Optional EXE build

After dependencies install, run:

```bat
build-exe.bat
```

The executable is written to `dist\larpdog-server.exe`. Keep `config.json` next to the exe.
