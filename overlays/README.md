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
  "studioView": ""
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
