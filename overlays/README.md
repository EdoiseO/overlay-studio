# Overlay page contract

Every dedicated overlay is a transparent, centered object. OBS owns its final screen
position and size.

## Drop-in discovery

Create an overlay at `overlays/<type>.html`. The type must match:

```text
[A-Za-z0-9][A-Za-z0-9_-]*
```

The server automatically exposes `overlays/alerts.html` at:

```text
http://127.0.0.1:8473/overlays/alerts
```

Each file must contain one JSON manifest. Files with missing, malformed, or invalid
manifests are skipped by `GET /api/overlays` without affecting the server.

```html
<script type="application/json" id="overlay-manifest">
{
  "name": "Alerts",
  "description": "Displays local stream alerts.",
  "category": "stream",
  "canvas": { "w": 800, "h": 400 },
  "settings": [],
  "studioView": "",
  "exportable": false
}
</script>
```

Manifest fields:

| Field | Rules |
| --- | --- |
| `name` | Required display name, up to 80 characters. |
| `description` | Required catalog description, up to 240 characters. |
| `category` | Required identifier using letters, numbers, `_`, or `-`. |
| `canvas.w`, `canvas.h` | Required integers from 100 through 4096. |
| `settings` | Optional list of setting identifiers. Unknown settings remain inert. |
| `studioView` | Optional existing Studio view ID. Leave empty when no customizer exists. |
| `exportable` | Optional literal `true` only for deterministic static overlays with the PNG renderer contract below. Defaults to `false`. |

The filename supplies the manifest `type` and route. Do not duplicate them in JSON.
Adding a valid local file is enough for it to appear in **Browse overlays**; no Studio
HTML, JavaScript, or CSS registration is needed.

## Instances

**My overlays** contains instances. Multiple instances can use the same type and keep
different names and settings. Studio appends a strict instance ID to the source URL:

```text
http://127.0.0.1:8473/overlays/alerts?i=alerts-2
```

Read `i` with `URLSearchParams` when an overlay has instance-specific HTTP or websocket
state. Ignore addressed websocket messages whose `instanceId` does not match. Existing
source URLs without `i` remain legacy-compatible.

## Surface template

Use the shared surface classes:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Overlay name</title>
  <script type="application/json" id="overlay-manifest">
  {
    "name": "Overlay name",
    "description": "Short catalog description.",
    "category": "stream",
    "canvas": { "w": 800, "h": 400 },
    "settings": []
  }
  </script>
  <link rel="stylesheet" href="/assets/overlay-surface.css">
</head>
<body class="overlay-surface">
  <main class="overlay-content">
    <!-- One self-contained overlay object -->
  </main>
  <script>
    if (new URLSearchParams(location.search).get("preview") === "studio") {
      document.documentElement.classList.add("overlay-studio-preview");
    }
  </script>
</body>
</html>
```

Keep overlay content in normal document flow. Do not anchor it to a stream corner or
build a full scene inside the page. Give the OBS Browser Source a canvas comfortably
larger than the object, then position that source in OBS.

## Static PNG export contract

PNG export is opt-in. Set the manifest's `exportable` field to the literal value `true`
only when freezing the current visual cannot misrepresent live state. Static branding
overlays qualify; timers, media metadata, rotating content, counters, goals, ranks, and
other live or animated overlays do not. Studio never infers eligibility from category.

An exportable page must load the shared renderer and register its visible artwork:

```html
<script src="/assets/overlay-png-export.js"></script>
<script>
  window.OverlayPngExport.register({
    overlayType: "alerts",
    instanceId,
    target: () => document.getElementById("alertArtwork"),
    padding: () => ({ top: 12, right: 12, bottom: 12, left: 12 }),
  });
</script>
```

The target must be one deterministic DOM element containing every visual that belongs
in the image. Padding must include the overlay's maximum glow, keyline, and shadow
extent. The renderer temporarily neutralizes `--scale` and `--fit-scale`, embeds used
local fonts and images, preserves transparency, refuses clipped effects or unsafe output
dimensions, and accepts only `256`, `512`, or `1024` pixel output heights. Do not add a
second writer or browser download path; Studio validates each returned PNG and writes it
under `user-assets/exports/<instance-id>/` through the desktop bridge.

## Built-in social overlays

`social.html`, `social-rotator.html`, `social-grouped.html`, and
`platform-badge.html` read their platform metadata and inline vector paths from
`assets/social-platforms.js`. Social Bar, Social Rotator, and Platform Badge use the
shared vector glyph factory. Social Grouped deliberately keeps its own single-SVG,
three-layer renderer so overlapping logo and text outlines merge into one sticker
instead of separate outlined tiles.

Built-in social marks are vector-only; no PNG logo directory is loaded at runtime.
Icon backgrounds and shapes are drawn by the overlay around the centered vector path,
and branded modes use the colors, layers, and gradients in the shared metadata. The
`accounts` setting is an ordered list of platform, enabled, and handle values. Social
Bar accepts up to eight enabled platforms; Social Rotator accepts all supported
platforms. Both deliberately render an empty transparent source when no account is
enabled.

Use the shared `socialView` customizer for selection, colors, fonts, icon shapes, scale,
and live drafts. Bar-specific controls choose the row layout, shared-handle mode,
alignment, heading, and outline. Rotator-specific controls choose the shell shape,
transition, interval, prefix, timer, and platform label.

## Rivals Rank overlay

`rivals-rank.html` reads public per-instance state from `/api/rivals?i=...` and listens
only for addressed `rivals` websocket messages. Account IDs and match cursors belong in
the server-side `rivals_store.py` record; never add them to the manifest, query string,
customizer draft, HTTP response, or websocket payload. Eternity and One Above All share
`assets/ranks/eternity-oaa.png` until separate approved artwork is available.

## Platform Badge overlay

Platform Badge uses its dedicated `platformBadgeView` customizer for one platform,
handle, optional prefix, brand or custom nameplate color, width, height, corners, scale,
font, and weight. Width is a safe minimum, so long handles expand the nameplate instead
of being truncated. Handle ink is always computed from the active nameplate color rather
than stored as a user setting.
