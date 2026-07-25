# Overlay Studio

Overlay Studio is a Windows desktop library for running, previewing, and customizing
local OBS browser-source overlays.

<p align="center">
  <img src="assets/larpdog-demo.gif" alt="Dancing GIF overlay demo" width="520">
</p>

## Included overlays

| Overlay | Purpose |
| --- | --- |
| **Dancing GIF** | Displays a resting image until audio or playback activates an audio-reactive dance GIF or video. |
| **Spotify Overlay** | Shows live Windows now-playing metadata, album artwork, and playback progress. |
| **Match Record** | Displays a transparent win/loss banner with editable title, color, and counters. |

## Requirements

- Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- OBS Studio for streaming
- Spotify desktop, or another app that publishes Windows media-session metadata

Current Windows 11 and Microsoft Edge installations normally include WebView2 already.
Python is only required when running from source or rebuilding the executable.

## Quickstart

For a fresh source checkout, run `larpdog-server\install.bat` once before continuing.
Packaged copies can start immediately.

1. Open `Overlay Studio.bat`.
2. Confirm the top-right status says **Running**.
3. Click an installed overlay card to open its live preview.
4. Choose **Copy OBS URL**.
5. In OBS, add a **Browser Source** and paste the copied URL.
6. Set the browser source canvas to `1920 x 1080`.

`Overlay Studio.bat` launches `Overlay Studio.exe` when the packaged build is present.
If it is missing, the launcher uses the local Python environment instead.

The overlay server starts automatically. Closing the desktop window leaves the server
running so active OBS sources do not disappear. To shut everything down, open
**Server Controls** and choose **Stop** before closing Overlay Studio.

## Live previews

The four-column library shows the current output of every installed overlay. Clicking a
card opens a larger live preview with actions to:

- copy the OBS browser-source URL;
- open the source in a browser;
- enter the overlay's customization page.

These previews render the same live pages used by OBS. The dark preview background is
only added inside Overlay Studio; the OBS sources remain transparent.

## Custom media

Open **Dancing GIF** and give it a personal overlay name such as **Dancing Cats**. Use
the resting and dancing media libraries to preview and select imported assets. Dancing
media can use one fixed selection or a random pool that chooses a new dance each time
playback becomes active. Overlay Studio copies imported files into `user-assets/`, so
moving or deleting the original file does not break the overlay.

Supported dancing media:

```text
.gif .webp .apng .png .webm .mp4 .mov
```

Supported resting images:

```text
.png .jpg .jpeg .gif .webp .apng
```

Use square media when possible. The current default dance GIF is `362 x 362`.
New imports are organized under `user-assets/dancing/` and `user-assets/resting/`.

## OBS source URLs

The default server address is `http://127.0.0.1:8473/`. Copy the exact URLs shown by
Overlay Studio because a local `config.json` may use a different port.

```text
http://127.0.0.1:8473/overlays/larpdog-dance
http://127.0.0.1:8473/overlays/spotify
http://127.0.0.1:8473/overlays/win-loss
```

Saved changes are broadcast to connected OBS sources automatically.

## Match Record automation

Chat tools such as Streamer.bot can update Match Record by sending JSON to
`POST /api/win-loss`. Supported actions are:

```text
win
loss
undo-win
undo-loss
reset
```

PowerShell example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"action":"win"}' `
  -Uri "http://127.0.0.1:8473/api/win-loss"
```

The same endpoint accepts direct `wins`, `losses`, `title`, and six-digit `accent`
values.

## Install from source

Run the dependency installer once:

```bat
larpdog-server\install.bat
```

Then open:

```bat
Overlay Studio.bat
```

The app stores machine-specific settings, counters, logs, and copied media locally.
Those runtime files are excluded from git.

## Build the desktop app

Close the visible Overlay Studio window, then run:

```bat
build-app.bat
```

The script builds a one-file Windows application, stops old processes belonging to this
project's packaged executable, and replaces the root `Overlay Studio.exe`.

## Project layout

- `overlay_studio.pyw`: native WebView desktop shell and Python bridge
- `studio/`: desktop interface
- `overlay-studio.html`: Dancing GIF and Spotify browser sources
- `overlays/win-loss.html`: Match Record browser source
- `assets/`: bundled default media
- `user-assets/`: copied custom dance and resting media
- `larpdog-server/`: local HTTP, websocket, system-audio, and media-session service

Server configuration and standalone development details are in
[`larpdog-server/README.md`](larpdog-server/README.md).

## Troubleshooting

- **The cards say Offline:** Open **Server Controls** and choose **Start**.
- **OBS shows the old version:** Refresh the Browser Source cache or toggle the source.
- **Spotify is waiting for a song:** Start playback in the Spotify desktop app and make
  sure it appears in the Windows media controls.
- **A custom file cannot be selected:** Confirm its extension is listed under
  [Custom media](#custom-media).
- **The desktop window is blank:** Install or repair the Microsoft Edge WebView2
  Runtime.
