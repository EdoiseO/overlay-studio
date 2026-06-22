# larpdog stream overlay

Beat-reactive OBS browser-source overlay plus a local Windows companion server.

- `larpdog-overlay.html` is the visual overlay.
- `assets/dancing-dog.gif` is shown while music is playing.
- `assets/resting-dog.png` is shown when no track is playing.
- `larpdog-server/` serves the overlay, captures system audio through WASAPI loopback, and sends Spotify now-playing data over a local websocket.

Start with `larpdog-server/README.md`.
