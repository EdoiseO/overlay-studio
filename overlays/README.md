# Overlay page contract

Every dedicated overlay is a transparent, centered object. OBS owns its final screen
position and size.

Create future overlays as `overlays/<name>.html`. The server automatically exposes a
safe filename such as `overlays/alerts.html` at:

```text
http://127.0.0.1:8473/overlays/alerts
```

Use the shared surface classes:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/assets/overlay-surface.css">
  <title>Overlay name</title>
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
