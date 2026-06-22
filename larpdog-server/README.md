# larpdog-server

Local companion for `larpdog-overlay.html`.

It serves the overlay at `http://localhost:8473/`, captures Windows system audio through WASAPI loopback, sends beat/EQ data over `/ws`, and polls Spotify with a cached refresh token after one login.

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
http://localhost:8473/callback
```

5. Copy `config.example.json` to `config.json`, then paste your Spotify `client_id` and `client_secret` into `config.json`.

`config.json` and `.spotify_cache` are ignored by git. Do not commit them.

## Run

```bat
run.bat
```

On first Spotify use, the server opens a browser login. After approval, Spotipy stores a refresh token in `.spotify_cache`, so later restarts do not need a new login.

## OBS

Add a Browser source with this URL:

```text
http://localhost:8473/
```

Then start Spotify playback. The overlay receives track changes and audio pulses from the local server. If the server is closed, the edited overlay falls back to its original standalone behavior.

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
