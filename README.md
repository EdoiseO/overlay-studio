# larpdog stream overlay

Windows overlay library with local controls, persistent settings, and OBS browser sources.

<p align="center">
  <img src="assets/larpdog-demo.gif" alt="larpdog stream overlay demo" width="520">
</p>

## Quickstart

1. Open `Larpdog.bat`.
2. Click **Start**.
3. Copy the OBS URL from the app and use it in an OBS Browser Source.

The app shows whether the local server is running, opens a browser preview, and provides
separate URLs for the full overlay, dog, and player. Use the **Customize** tab to choose
character files, layout, colors, scale, and beat sensitivity. Saved changes refresh
connected OBS overlays automatically.

If the Python environment is ever removed, run `larpdog-server\install.bat` once before
opening the control app again.

`Larpdog.bat` uses `Larpdog Control.exe` when a packaged build is present and otherwise
opens the Python desktop app directly.

## Overlay library

- **Larpdog Music** combines the dancing character, system-audio reaction, and
  Windows now-playing card.
- **Match Record** is a transparent win/loss banner with controls for wins, losses,
  title, and accent color.

The Match Record browser source is:

```text
http://127.0.0.1:8473/overlays/win-loss
```

Chat integrations can update it through `POST /api/win-loss` using the actions `win`,
`loss`, `undo-win`, `undo-loss`, and `reset`.

## Customizing

- Use **Browse** in the control app to choose dancing and resting character files.
- Character files are copied into `user-assets/`.
- Settings are stored in `larpdog-server/overlay-config.json`.

## Project layout

- `larpdog-overlay.html` is the visual overlay.
- `assets/dancing-dog.gif` is shown while music is playing.
- `assets/resting-dog.png` is shown when no track is playing.
- `user-assets/` is where streamers can drop custom local character files.
- `larpdog-server/` serves the overlay, captures system audio through WASAPI loopback, and sends Windows now-playing data over a local websocket.

More setup detail lives in `larpdog-server/README.md`.
