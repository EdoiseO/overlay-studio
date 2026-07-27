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
| **Now Playing Flow** | Presents the current media-session artwork with audio-reactive progress bars. |
| **Goal Widget** | Tracks tip, subscriber, follower, or custom goals with a glowing progress ring. |
| **Goal Bar** | Tracks the same kinds of goals with horizontal, vertical, shelled, and bare progress-bar layouts. |
| **Goal Pill** | Tracks goals in a compact rounded pill with an icon badge, live value, and proportional fill. |

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
6. Use the starting canvas size listed under [OBS source URLs](#obs-source-urls),
   then position the Browser Source in OBS.

`Overlay Studio.bat` launches `Overlay Studio.exe` when the packaged build is present.
If it is missing, the launcher uses the local Python environment instead.

The overlay server starts automatically. Closing the desktop window leaves the server
running so active OBS sources do not disappear. To shut everything down, open
**Server Controls** and choose **Stop** before closing Overlay Studio.

## Overlay library

**My overlays** is a four-column, instance-based library. It can contain multiple
copies of the same local overlay type with independent names, URLs, settings, and
addressed state. Select **Add overlay** to open **Browse overlays**, which is generated
from manifests embedded in local `overlays/*.html` files. Every catalog entry includes
a live scaled preview; previews load only near the visible scroll area and unload when
Browse overlays closes.

Clicking an instance preview opens a larger live preview with actions to:

- copy the OBS browser-source URL;
- open the source in a browser;
- enter the overlay's customization page.

These previews render the same live pages used by OBS. The dark preview background is
only added inside Overlay Studio; the OBS sources remain transparent.

Every customization page also keeps a compact live draft preview beside its controls.
Text, number, color, layout, media, and slider changes appear there immediately without
writing to the server. OBS and the installed library preview continue using the saved
settings until **Save** is selected. Edited drafts are marked **Unsaved** and prompt
for **Save**, **Discard**, or **Keep editing** when leaving the customizer or closing
the app. The warning can be disabled from the prompt and restored under
**Settings > Editing**. Leaving the customization page unloads the draft preview to
release its browser resources. The form scrolls independently from the preview; click
the live draft to expand it and press `Esc` to return to the editor.

Each card can copy its OBS URL, be renamed without changing that URL, or be removed
from My overlays. Removing an instance does not delete its local overlay type, which
remains available in Browse overlays.

## Now Playing Flow

Open **Now Playing Flow** to customize its library name, size, and artwork-colored
glow. It intentionally shows only the current track. Spotify queue cards can be added
after account authorization is introduced through the Connections area in Settings.
Saving applies the new appearance to connected Studio previews and OBS browser sources
without changing their URL.

## Goal Widget

Add **Goal Widget** from Browse overlays to track a tip, subscriber, follower, or
custom numeric goal. Its Studio page controls the label, current and target values,
currency or plain-number formatting, colors, font, particles, percentage, scale, and
glow. The circular fill tracks `current / target` proportionally and caps visually at
100 percent. Progress is stored independently for every Goal Widget instance and is
restored when Overlay Studio restarts. Every goal editor uses the same currency menu;
typing while it is focused jumps to currencies by name, such as `C` for Canadian Dollar.

## Goal Bar

Add **Goal Bar** for a compact follower, tip, subscription, bits, or custom progress
display. Its Studio page controls horizontal or vertical orientation, three bar sizes,
shell visibility, icon, corners, width, palette, type, glow, scale, and bounded
perspective tilt. Horizontal bars omit the icon badge for a cleaner label row; vertical
bars can use the follower, tip, subscription, or bits icon. Each Goal Bar keeps progress
and appearance independently from Goal Widgets and other Goal Bar instances.

## Goal Pill

Add **Goal Pill** for a compact tip, follower, subscription, bits, or custom goal.
Its Studio page includes live progress controls plus bounded size, width, scale, glow,
corners, icon, font, and color settings. The fill is proportional to `current / target`,
including a fully empty track at zero. Every Goal Pill instance stores its own progress
and appearance.

## Custom media

Open **Dancing GIF** and give it a personal overlay name such as **Dancing Cats**. Use
the resting and dancing media libraries to preview and select imported assets. Dancing
media can use one fixed selection or a random pool that chooses a new dance each time
the song changes while preserving that dance across pause and resume. Overlay Studio
copies imported files into `user-assets/`, so
moving or deleting the original file does not break the overlay. Imported media can be
removed with the trash button on its library tile; built-in media is protected. Dancing
and resting imports are stored separately, so deleting one cannot remove the other.
File signatures are checked during import. If selected media later becomes unavailable
or cannot be decoded, the overlay keeps the current image and automatically tries
another dance or the built-in resting image.

Each Dancing GIF instance can keep up to five named profiles. A profile remembers its
resting image, dancing selection or random pool, scale, beat sensitivity, and fallback
BPM. Choose a profile from the dropdown to save the current profile and apply the
selected one to connected Studio previews and OBS sources. Existing configurations are
migrated into a `Default` profile automatically. Deleting a profile does not delete its
imported media, and the final remaining profile is protected.

GIFs, animated images, and videos up to 25 MB can also be dragged directly onto the
**Dancing media** library. Windows `.url` Internet shortcuts to public HTTPS media are
also supported, including media pages that publish a direct Open Graph image or video.
Overlay Studio downloads and validates the real file before importing it. Use **Add
media** for larger local files.

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
http://127.0.0.1:8473/overlays/now-playing-flow
http://127.0.0.1:8473/overlays/goal
http://127.0.0.1:8473/overlays/goal-bar
http://127.0.0.1:8473/overlays/goal-pill
```

Those unqualified URLs remain supported for existing OBS scenes. New library instances
include a validated `i` query parameter, for example:

```text
http://127.0.0.1:8473/overlays/win-loss?i=ranked
```

Each dedicated page centers one transparent overlay object. Position the Browser
Source itself in OBS instead of anchoring content to a corner inside the webpage.
Useful starting canvas sizes at scale `1.0` are:

```text
Dancing GIF      520 x 420
Spotify Overlay  620 x 360
Match Record     900 x 320
Now Playing Flow 760 x 420
Goal Widget      460 x 520
Goal Bar         860 x 560
Goal Pill        720 x 220
```

Increase the Browser Source canvas if you raise an overlay's scale. Existing combined
overlay links and explicit `?pos=bottom-left`, `bottom-right`, `top-left`, or
`top-right` query parameters retain the old full-canvas positioning behavior.

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

## Goal automation

Chat tools can update a Goal Widget, Goal Bar, or Goal Pill by sending JSON to `POST /api/goal`
with the instance's `i` query parameter. Supported actions are:

```text
add
subtract
reset
complete
```

PowerShell example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"action":"add","amount":5}' `
  -Uri "http://127.0.0.1:8473/api/goal?i=goal"
```

The endpoint also accepts direct settings such as `label`, `current`, `target`,
`format`, `symbol`, `color`, `font`, `scale`, and `glow`. Goal Bar adds `layout`,
`size`, `shell`, `icon`, `corners`, `width`, `shellColor`, `track`, `labelColor`,
`tiltX`, and `tiltY`. Goal Pill uses `size`, `icon`, `corners`, `width`,
`shellColor`, `track`, and `labelColor`. Values are normalized and bounded before
being saved.

For compatibility with the original Goal Widget, omitting `?i=` reads or updates a
separate legacy ring state. It does not modify any installed overlay instance. New
automation should always include the intended instance ID.

All mutating `/api/` requests must use `Content-Type: application/json`. Browser-based
automation must run from the same local Overlay Studio origin; desktop and chat tools
without browser `Origin` headers continue to work through the loopback address.

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
- `overlays/`: standalone overlay pages and the
  [future-overlay authoring guide](overlays/README.md)
- `assets/`: bundled default media and the shared centered-surface stylesheet
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
