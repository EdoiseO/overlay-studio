# larpdog overlay — customization & sharing roadmap

A plan to evolve the personal overlay into something other **Windows streamers** can install and customize — custom character animations and custom colors — without editing code. Scoped to keep the existing standalone overlay and the WASAPI loopback server as the main path.

---

## What you already have (reuse, don't rebuild)

- **URL-param engine** in `larpdog-overlay.html` (`Q = new URLSearchParams`) — every setting is already overridable by `?param`.
- **Asset overrides already exist:** `DANCING_DOG_SRC = Q.get("dog") || dogImg.src` and `RESTING_DOG_SRC = Q.get("rest") || "assets/resting-dog.png"`. Custom images are 80% done.
- **Color engine:** `extractPalette()` → `applyPalette()` sets `--a-rgb/--b-rgb/--c-rgb`, auto-sampled from album art or the dog. Just no manual override yet.
- **Server:** aiohttp app in `create_app()` with `/` (overlay), `/assets` static, `/ws` websocket (audio + track push), `/callback` (Spotify PKCE), `/health`.
- **Distribution:** `install.bat`, `run.bat`, `build-exe.bat`, PyInstaller spec.

Design principle for everything below: **the standalone overlay must keep working without the server**, and existing URLs must keep working. The settings page is a friendly layer on top of the param system, not a replacement.

---

## Phase 1 — Custom animations (small, ship first)

**1.1 Serve a user folder.** In `create_app()`, mirror the existing `/assets` route:

```python
user_assets = base_dir.parent / "user-assets"   # next to the overlay
user_assets.mkdir(exist_ok=True)
app.router.add_static("/user-assets", user_assets, show_index=False)
```

Then anyone drops a file in `user-assets/` and uses `?dog=user-assets/mydog.webm`.

**1.2 Support better formats than GIF.** GIF is heavy (your dog is 1.1 MB) and only has 1-bit (hard-edged) transparency. Add a tiny resolver in the overlay that swaps `<img>` for `<video>` when the source is a video, so streamers can use clean-alpha assets:

```js
function isVideo(src){ return /\.(webm|mov|mp4)(\?|$)/i.test(src); }
// if isVideo(DANCING_DOG_SRC): replace #dog <img> with a muted autoplay loop <video>
```

Recommend (in docs) **transparent WebM (VP9/AV1 alpha)** for smooth edges + small size, with **animated WebP / APNG** as lighter drop-in alternatives to GIF. Export reference for users:

```
ffmpeg -i in.mov -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 out.webm
```

**1.3 Colour sampling for custom assets.** `extractPalette()` taints the canvas on cross-origin images and returns null. Local files you serve are same-origin, so sampling works and no CORS header is needed.

> **Superseded:** an earlier version of this plan suggested adding `Access-Control-Allow-Origin: *` to static responses so remote `?dog=https://…` assets could be sampled. That middleware was added and has since been **removed** — it let any website read guessed `/user-assets/` URLs and sample their pixels, which is not worth enabling palette extraction for remote assets. Remote assets simply fall back to the default palette (already handled gracefully).

**Acceptance:** drop a `.webm`/`.gif` in `user-assets/`, load `?dog=user-assets/x.webm&rest=user-assets/y.png`, and the dog renders and recolors the card. Remote media still renders but falls back to the default palette.

---

## Phase 2 — Color controls (small)

**2.1 Hex params.** Add `?a=ff4d9d&b=ffd24a&c=5ee0ff` feeding the existing CSS vars via a helper:

```js
const hexToRgb = h => { const n = parseInt(h.replace('#',''),16);
  return [(n>>16)&255,(n>>8)&255,n&255]; };
```

**2.2 `colorMode` param** to define precedence explicitly:

| `colorMode` | Behavior |
|---|---|
| `auto` (default) | Current behavior — recolor from album art, fall back to dog palette. |
| `fixed` | Always use the user's `?a/?b/?c`, ignore album art. |
| `art` | Use art when present, else the user's colors (not the dog). |

Wire it into `applyArtwork()`/`applyPalette()` — when `fixed`, skip the art sampler entirely.

**Acceptance:** `?colorMode=fixed&a=00ffd0&b=...` locks the palette regardless of what's playing.

---

## Phase 3 — Settings control panel (the real "others can use it" unlock)

Most streamers won't hand-edit URLs. Add `settings.html`, served at `/settings`, that writes config and previews live.

**3.1 Controls:** asset pickers (upload), color pickers + auto/fixed toggle, position, scale, card width, sensitivity, fallback BPM, now-playing source/mode. Embed a live `<iframe src="/?...">` preview.

**3.2 Persist via server config (recommended over URL-only).**

- New file `overlay-config.json` — **separate from `config.json`** (which holds the Spotify secret). This one is safe to share/commit as an example.
- New endpoints: `GET /api/config` and `POST /api/config` (read/write `overlay-config.json`).
- On POST, broadcast over the existing websocket so the live OBS source updates instantly — extend the `ws.onmessage` switch with a `config` case:

```js
} else if (msg.type === "config") { applyConfig(msg.config); }
```

- Overlay loads `/api/config` on startup and merges: **defaults → server config → URL params** (URL params win, so per-source overrides like `?asset=dog` still work).

**3.3 Upload endpoint.** `POST /api/assets` (multipart). Since other people will run this:

- Allowlist extensions: `gif, webp, apng, png, webm`.
- Cap size (e.g. 10 MB).
- Sanitize/slugify the filename — **reject path traversal** (`..`, slashes), never trust the client name.
- Save to `user-assets/`, return the served URL.

**3.4 "Copy OBS URL" buttons** for each source: `/?asset=dog`, `/?asset=player`, `/` (both).

**Acceptance:** a non-technical user opens `/settings`, uploads a gif, picks colors, clicks save, and the OBS source updates without touching a URL.

---

## Phase 4 — Distribution & onboarding (Windows)

- **`LICENSE`** — add MIT (currently "all rights reserved" by default, which blocks the reuse you want).
- **README rewrite** — a 3-step quickstart: `install.bat` → open `/settings` → add the OBS browser source. Include a screenshot/gif.
- **First-run UX** — `run.bat` already creates `config.json`; also auto-open `/settings` on first launch.
- **GitHub Releases** — attach the built `larpdog-server.exe` (+ `config.example.json`, overlay, assets) and a separate `overlay-only.zip` for people who just want the standalone overlay (no server).
- **Spotify onboarding doc** — per-user app, PKCE (no secret, already done), redirect URI `http://127.0.0.1:8473/callback`, with screenshots.
- **Versioning** — tag releases, keep a short changelog.

---

## Proposed `overlay-config.json` schema

```json
{
  "appearance": {
    "asset": "both",
    "dog": "user-assets/dancing.webm",
    "rest": "user-assets/resting.png",
    "position": "bottom-left",
    "scale": 1.0,
    "cardWidth": 335,
    "colorMode": "auto",
    "colors": { "a": "ff4d9d", "b": "ffd24a", "c": "5ee0ff" }
  },
  "audio":      { "enabled": true, "sensitivity": 1.0 },
  "nowPlaying": { "mode": "spotify", "fallbackBpm": 120 }
}
```

Each key maps to an existing `CONFIG` field / param, so the settings page just reads/writes this and the overlay's merge logic does the rest.

---

## Suggested order & sizing

1. **Phase 1 + 2** — half a day, independently shippable, immediately delivers custom animations + colors.
2. **Phase 3** — the big one (settings page + `/api/config` + uploads). The actual "anyone can use it" milestone.
3. **Phase 4** — polish; do `LICENSE` + README first since they're tiny and unblock sharing.

## Decisions to lock before Phase 3

- **Config precedence** — confirm defaults → server config → URL params (recommended).
- **Asset storage** — `user-assets/` gitignored (user content) vs committed sample. Recommend gitignored.
- **Profiles** — one shared config vs per-source profiles (dog vs player). Start with one shared config + per-source URL overrides.
- **Keep secrets separate** — `config.json` (Spotify secret, gitignored) stays distinct from `overlay-config.json` (shareable).
