# larpdog stream overlay

Beat-reactive OBS browser-source overlay plus a local Windows companion server.

## Quickstart

1. Open `larpdog-server` and run `install.bat`.
2. Run `run.bat`, then open `http://127.0.0.1:8473/`.
3. In OBS, add a Browser Source using one of these URLs:

```text
http://127.0.0.1:8473/
http://127.0.0.1:8473/?asset=dog
http://127.0.0.1:8473/?asset=player
```

## Customizing

- Drop custom character files into `user-assets/`.
- Use `?dog=user-assets/dancing.webm&rest=user-assets/resting.png` for custom animations.
- Use `?colorMode=fixed&a=00ffd0&b=ffd24a&c=ff4d9d` for fixed overlay colors.

## Project layout

- `larpdog-overlay.html` is the visual overlay.
- `assets/dancing-dog.gif` is shown while music is playing.
- `assets/resting-dog.png` is shown when no track is playing.
- `user-assets/` is where streamers can drop custom local character files.
- `larpdog-server/` serves the overlay, captures system audio through WASAPI loopback, and sends Spotify now-playing data over a local websocket.

More setup detail lives in `larpdog-server/README.md`.
