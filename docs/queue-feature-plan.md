# Twitch Song-Request Queue — implementation plan

A **hybrid** chat-driven queue for the larpdog overlay: viewers request songs in Twitch chat, you moderate a self-managed display queue, and approved tracks can optionally be pushed to Spotify. The whole feature has a master on/off toggle, and requests can be opened/closed at runtime.

Built on the current `main` architecture (GSMTC now-playing, aiohttp + `/ws`, overlay URL-param layouts). The now-playing path stays **read-only and auth-free**; only the optional Spotify *push* adds auth.

---

## States to model (get these names straight first)

- **Disabled** — feature off entirely (`queue.enabled:false` or `!queue off`). Worker doesn't run; overlay panel hidden. This is your master toggle.
- **Open** — accepting `!sr` requests.
- **Closed** — not accepting new requests, but the existing queue stays visible (`!queue close`).

Keep "disabled" and "closed" distinct — they look similar but mean different things to the overlay.

---

## Layer 1 — Config (`queue` block + toggle)

```json
"queue": {
  "enabled": true,
  "platform": "twitch",
  "channel": "yourchannel",
  "command": "!sr",
  "open_on_start": true,
  "max_size": 20,
  "per_user_limit": 2,
  "cooldown_seconds": 30,
  "require_approval": true,
  "auto_push_to_spotify": false,
  "blocklist": []
}
```

`enabled` is the master switch (checked at startup and by `!queue on/off`). `require_approval` + `auto_push_to_spotify` are what make it "hybrid": requests land as **pending**, a mod approves, and only then (if `auto_push_to_spotify`) does it go to Spotify.

---

## Layer 2 — `ChatQueueWorker` (Twitch IRC)

A new async worker in the same shape as `MediaSessionWorker` (asyncio task, started from `on_startup` when `queue.enabled`).

- Connect to `wss://irc-ws.chat.twitch.tv:443`. **Reading is auth-free**: `NICK justinfan<random>`, then `CAP REQ :twitch.tv/tags twitch.tv/commands` (tags give you badges, `mod`, `user-id`, `display-name`), then `JOIN #channel`.
- Respond to `PING` with `PONG`; handle Twitch `RECONNECT`; reconnect with backoff on drop.
- Parse `PRIVMSG`:
  - Viewer `!sr <query>` → attempt add (limits/cooldown/blocklist/open checks).
  - Mod/broadcaster (from badge tags): `!queue open|close`, `!queue on|off`, `!skip`, `!remove <n>`, `!clear`, `!approve <n>`.
- On any queue change → broadcast to the hub (Layer 4).

> Reading chat needs no token. *Replying* in chat ("@user added!") would need a bot account + `chat:write` token — skip it for v1; the overlay is your feedback channel. Note it as optional Phase 2.

**Identity:** key `per_user_limit` and cooldown on the Twitch **`user-id`** tag, never the display name (names change / can be spoofed via display vs login).

---

## Layer 3 — Queue state

Each item:

```
{ id, query, title?, artist?, requestedBy, userId, requestedAt,
  status: "pending" | "approved" | "playing" | "done", spotifyUri? }
```

Enforce on add: queue **open**, `max_size`, `per_user_limit`, `cooldown_seconds`, dedupe, and **blocklist word-filter on the query text before it is ever broadcast** (so offensive text never reaches the overlay or Spotify). With `require_approval`, `!sr` creates `pending`; `!approve` → `approved`; if `auto_push_to_spotify`, approval triggers the Spotify push (Layer 6).

The **display queue is the source of truth** — Spotify's queue is fire-and-forget (add-only, you can't reorder/remove it via API).

---

## Layer 4 — Server wiring (small change to `ClientHub`)

`ClientHub` currently caches only `_last_track` and replays it on connect (main.py ~103–115). Generalize it to cache the **last message per type** so a freshly-added OBS source gets both now-playing *and* the current queue:

```python
self._last_by_type: dict[str, dict] = {}
# in broadcast(): self._last_by_type[message["type"]] = message
# in add(): replay every cached message (track, queue, …)
```

Then `ChatQueueWorker` just calls `hub.broadcast({"type":"queue", "open":bool, "items":[…], "updatedAt":…})`. Start the worker in `on_startup` only when `queue.enabled`.

---

## Layer 5 — Overlay (`?asset=queue` + a `queue` handler)

- Add a `queue` layout alongside `dog|player|both` (main overlay ~line 287) so the queue can be its own OBS browser source (`http://127.0.0.1:8474/?asset=queue`).
- In `ws.onmessage` (the switch at ~line 526, next to `audio`/`track`), add `else if (msg.type === "queue")` → render the list: "Up next", requester names, status badges. Reuse the glass-card CSS and `setTrackLine()` marquee for long titles.
- Hide the panel when `disabled` or empty; show a subtle "Requests closed" when `open:false`.

This keeps the websocket contract additive — existing dog/player sources are untouched.

---

## Layer 6 — Spotify push (the optional hybrid half)

A **separate, scoped** PKCE client used only when `auto_push_to_spotify` is on — kept entirely apart from the GSMTC now-playing read path:

- Scopes: `user-modify-playback-state` (+ `user-read-playback-state` to confirm an active device).
- On `!approve`: `GET /v1/search?type=track&q=<query>` → take the top match → `POST /v1/me/player/queue?uri=<uri>` → mark item queued, fill `title`/`artist` from the search result.
- Constraints to handle gracefully: **Premium required**, an **active device** must exist (Spotify desktop playing counts), and the API is **add-only**. On failure (no device / not premium), leave the item in the display queue and log — don't crash.

Bonus: even in display-only mode you can use the **search (read)** call to resolve `!sr bohemian rhapsody` into a real title + album art for a nicer overlay. Since the hybrid path already has the Spotify client, reuse it — just gate it behind the same flag so a no-auth install still works (showing the raw query text).

---

## Moderation & safety (build in from day one)

A public command that puts text on your stream is an abuse vector. Non-negotiables: blocklist filter, `per_user_limit`, cooldown, `max_size`, dedupe; mod/broadcaster-only control commands (check badge tags); the `require_approval` gate so nothing hits stream/Spotify without a mod's OK. Use `user-id` for identity.

---

## Test plan

- **Diagnostic first** (mirror `check-media-session.py`): `check-twitch-chat.py` connects anonymously, joins the channel, and prints parsed `!sr` commands. Get IRC working in isolation before wiring it into the server.
- **Unit (pure, no network):** command parser + tag parsing (mod/broadcaster), limit/cooldown/dedupe/blocklist, queue state transitions, "open vs closed vs disabled."
- **Integration:** feed fake IRC lines → assert queue state + the `{type:"queue"}` payload; PING→PONG; reconnect.
- **Overlay:** `?asset=queue` renders and updates on ws messages; hides when disabled/empty; long-title marquee.
- **Hybrid:** mock Spotify search/add; approve→push; simulate "no active device" / "not premium" → graceful.
- **Toggle:** `enabled:false` → worker never starts, panel hidden; `!queue close` → requests rejected, queue still shown; runtime `!queue on/off`.

---

## Suggested order

1. Config block + `ChatQueueWorker` (Twitch read) + `check-twitch-chat.py`.
2. Queue state + moderation + `ClientHub` generalization + `{type:"queue"}` broadcast.
3. Overlay `?asset=queue` panel + `queue` ws handler.
4. (Opt-in) Spotify PKCE push behind `auto_push_to_spotify`; reuse search to prettify titles.

Phases 1–3 are fully local and auth-free. Phase 4 is the only part that re-adds OAuth, and it stays behind a flag.

## Decisions to lock before coding

- `user-id` (not display name) for per-user limits.
- Does the display queue resolve real titles via Spotify search (prettier, needs a token) or show raw chat text (zero-auth)? Hybrid users get search for free.
- Reply-in-chat (needs a bot token) or overlay-only feedback for v1.
- Auto-advance: when a track finishes, does the queue auto-pop the next, or do you advance manually? (GSMTC can tell you when playback stops.)
