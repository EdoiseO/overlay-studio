const app = {
  state: null,
  busy: false,
  initialized: false,
  pollPending: false,
  toastTimer: null,
  previewInstanceId: null,
  activeInstanceId: null,
  danceMode: "single",
  danceSelection: new Set(),
  mediaLibraryKey: "",
  libraryKey: "",
  pendingDeleteAsset: null,
  pendingRemoveInstanceId: null,
  pendingRenameInstanceId: null,
};

const byId = (id) => document.getElementById(id);

function logActivity(message) {
  const log = byId("activityLog");
  const row = document.createElement("div");
  const timestamp = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  row.textContent = `${timestamp}  ${message}`;
  log.append(row);
  while (log.children.length > 30) log.firstElementChild.remove();
  log.scrollTop = log.scrollHeight;
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(app.toastTimer);
  app.toastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
}

async function callApi(method, ...args) {
  if (!window.pywebview?.api?.[method]) {
    throw new Error("Desktop connection is not ready");
  }
  return window.pywebview.api[method](...args);
}

function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
  });
}

function setDrawer(open) {
  document.body.classList.toggle("drawer-open", open);
  byId("settingsDrawer").setAttribute("aria-hidden", String(!open));
}

function setTheme(theme) {
  const selected = theme === "light" ? "light" : "dark";
  document.body.dataset.theme = selected;
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.classList.toggle("active", button.dataset.themeChoice === selected);
  });
}

function updatePreview(iframe, url, running) {
  const desired = running ? url : "";
  if (iframe.dataset.source === desired) return;
  iframe.dataset.source = desired;
  iframe.src = desired || "about:blank";
}

function instances() {
  return Object.values(app.state?.config?.instances || {});
}

function instanceById(instanceId) {
  return app.state?.config?.instances?.[instanceId] || null;
}

function manifestFor(overlayType) {
  return (app.state?.catalog || []).find((item) => item.type === overlayType) || null;
}

function activeInstance() {
  return instanceById(app.activeInstanceId);
}

function instanceUrl(instance) {
  const manifest = manifestFor(instance?.type);
  if (!instance || !manifest || !app.state?.baseUrl) return "";
  const url = new URL(manifest.route.replace(/^\//, ""), app.state.baseUrl);
  url.searchParams.set("i", instance.id);
  return url.toString();
}

function studioPreviewUrl(instance) {
  const source = instanceUrl(instance);
  if (!source) return "";
  const url = new URL(source);
  url.searchParams.set("preview", "studio");
  return url.toString();
}

function materializeInstanceConfig(instance) {
  const root = app.state?.config || {};
  const materialized = {};
  ["dance", "spotify", "flow", "audio", "nowPlaying"].forEach((key) => {
    materialized[key] = structuredClone(root[key] || {});
  });
  Object.entries(instance?.config || {}).forEach(([key, value]) => {
    materialized[key] = structuredClone(value);
  });
  return materialized;
}

function fitCardPreview(frame, manifest) {
  const host = frame?.parentElement;
  if (!host || !manifest) return;
  const width = manifest.canvas.w;
  const height = manifest.canvas.h;
  const scale = Math.min(
    host.clientWidth / width,
    host.clientHeight / height,
  ) * 0.88;
  frame.style.width = `${width}px`;
  frame.style.height = `${height}px`;
  frame.style.transform = `translate(-50%, -50%) scale(${scale})`;
}

function createCardAction(label, action, instanceId, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `card-action ${className}`.trim();
  button.textContent = label;
  button.dataset.instanceAction = action;
  button.dataset.instanceId = instanceId;
  return button;
}

function createOverlayCard(instance, running) {
  const manifest = manifestFor(instance.type);
  if (!manifest) return null;
  const card = document.createElement("article");
  card.className = "overlay-card";
  card.dataset.instanceId = instance.id;

  const previewButton = document.createElement("button");
  previewButton.type = "button";
  previewButton.className = "overlay-preview-button";
  previewButton.dataset.previewInstance = instance.id;
  previewButton.setAttribute("aria-label", `Preview ${instance.name}`);
  const livePreview = document.createElement("div");
  livePreview.className = "live-preview";
  const frame = document.createElement("iframe");
  frame.title = `Live ${instance.name} preview`;
  frame.tabIndex = -1;
  frame.dataset.source = running ? studioPreviewUrl(instance) : "";
  frame.src = frame.dataset.source || "about:blank";
  const offline = document.createElement("span");
  offline.className = "preview-offline";
  offline.textContent = "OFFLINE";
  livePreview.append(frame, offline);
  previewButton.append(livePreview);

  const copy = document.createElement("div");
  copy.className = "card-copy";
  const name = document.createElement("strong");
  name.textContent = instance.name;
  const description = document.createElement("span");
  description.textContent = manifest.description;
  const canvas = document.createElement("span");
  canvas.className = "canvas-size";
  canvas.textContent = `${manifest.canvas.w} x ${manifest.canvas.h} canvas`;
  const meta = document.createElement("div");
  meta.className = "card-meta-row";
  const status = document.createElement("small");
  const dot = document.createElement("i");
  dot.className = "status-dot";
  const statusText = document.createElement("b");
  statusText.textContent = running ? "RUNNING" : "OFFLINE";
  status.append(dot, statusText);
  meta.append(canvas, status);
  const actions = document.createElement("div");
  actions.className = "card-actions";
  actions.append(
    createCardAction("Copy", "copy", instance.id),
    createCardAction("Rename", "rename", instance.id),
    createCardAction("Remove", "remove", instance.id, "remove"),
  );
  copy.append(name, description, meta, actions);
  card.append(previewButton, copy);
  requestAnimationFrame(() => fitCardPreview(frame, manifest));
  return card;
}

function createAddCard() {
  const button = document.createElement("button");
  button.className = "overlay-card add-card";
  button.id = "addOverlayButton";
  button.type = "button";
  button.innerHTML = `
    <span class="add-mark" aria-hidden="true">+</span>
    <strong>Add overlay</strong>
  `;
  return button;
}

function renderLibrary(state) {
  const key = JSON.stringify({
    running: state.running,
    baseUrl: state.baseUrl,
    catalog: state.catalog,
    instances: state.config?.instances,
  });
  if (key === app.libraryKey) return;
  app.libraryKey = key;
  const grid = byId("overlayGrid");
  grid.replaceChildren();
  instances().forEach((instance) => {
    const card = createOverlayCard(instance, state.running);
    if (card) grid.append(card);
  });
  grid.append(createAddCard());
  const count = instances().length;
  byId("overlayCount").textContent = `${count} installed`;
}

function renderCatalog() {
  const grid = byId("catalogGrid");
  grid.replaceChildren();
  const catalog = app.state?.catalog || [];
  if (!catalog.length) {
    const empty = document.createElement("div");
    empty.className = "catalog-empty";
    empty.textContent = "No local overlays discovered";
    grid.append(empty);
    return;
  }
  catalog.forEach((manifest) => {
    const item = document.createElement("article");
    item.className = "catalog-item";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = manifest.name;
    const meta = document.createElement("span");
    meta.className = "catalog-meta";
    meta.textContent =
      `${manifest.category.toUpperCase()} / ${manifest.canvas.w} x ${manifest.canvas.h}`;
    identity.append(name, meta);
    const add = document.createElement("button");
    add.type = "button";
    add.className = "primary-button compact";
    add.textContent = "Add";
    add.dataset.addOverlayType = manifest.type;
    const description = document.createElement("p");
    description.textContent = manifest.description;
    item.append(identity, add, description);
    grid.append(item);
  });
}

function renderServerUrls() {
  const container = byId("serverOverlayUrls");
  container.replaceChildren();
  instances().forEach((instance) => {
    const row = document.createElement("div");
    row.className = "source-row";
    const label = document.createElement("label");
    label.textContent = instance.name;
    const input = document.createElement("input");
    input.readOnly = true;
    input.value = instanceUrl(instance);
    input.setAttribute("aria-label", `${instance.name} OBS URL`);
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "primary-button compact";
    copy.textContent = "Copy";
    copy.dataset.instanceAction = "copy";
    copy.dataset.instanceId = instance.id;
    const open = document.createElement("button");
    open.type = "button";
    open.className = "secondary-button compact";
    open.textContent = "Open";
    open.dataset.instanceAction = "open";
    open.dataset.instanceId = instance.id;
    row.append(label, input, copy, open);
    container.append(row);
  });
}

function renderActiveIdentity(instance) {
  if (!instance) return;
  const source = instanceUrl(instance);
  if (instance.type === "larpdog-dance") {
    byId("danceDetailName").textContent = instance.name;
    byId("danceSourceLabel").textContent = instance.name;
    byId("danceUrl").value = source;
  } else if (instance.type === "spotify") {
    byId("spotifyDetailName").textContent = instance.name;
    byId("spotifySourceLabel").textContent = instance.name;
    byId("spotifyUrl").value = source;
  } else if (instance.type === "win-loss") {
    byId("counterDetailName").textContent = instance.name;
    byId("counterSourceLabel").textContent = instance.name;
    byId("counterUrl").value = source;
  } else if (instance.type === "now-playing-flow") {
    byId("flowDetailName").textContent = instance.name;
    byId("flowSourceLabel").textContent = instance.name;
    byId("flowUrl").value = source;
  }
}

function mediaUrl(path) {
  const source = String(path || "");
  if (/^(?:https?:|data:|blob:)/i.test(source)) return source;
  const encoded = source
    .replaceAll("\\", "/")
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
  return new URL(encoded, app.state?.baseUrl || "http://127.0.0.1/").toString();
}

function createMediaChoice(asset, selected, multiple, onSelect, onDelete) {
  const item = document.createElement("div");
  item.className = "media-item";

  const choice = document.createElement("button");
  choice.type = "button";
  choice.className = "media-choice";
  choice.classList.toggle("selected", selected);
  choice.setAttribute("role", multiple ? "checkbox" : "radio");
  choice.setAttribute("aria-checked", String(selected));
  choice.setAttribute("aria-label", asset.name);
  choice.title = asset.name;

  const thumbnail = document.createElement("span");
  thumbnail.className = "media-thumbnail";
  const preview =
    asset.type === "video" ? document.createElement("video") : document.createElement("img");
  preview.src = mediaUrl(asset.path);
  preview.draggable = false;
  if (preview.tagName === "VIDEO") {
    preview.muted = true;
    preview.loop = true;
    preview.autoplay = true;
    preview.playsInline = true;
    preview.preload = "metadata";
  } else {
    preview.alt = "";
    preview.loading = "lazy";
  }
  preview.addEventListener("error", () => choice.classList.add("preview-failed"));
  thumbnail.append(preview);

  const name = document.createElement("span");
  name.className = "media-name";
  name.textContent = asset.name;
  const indicator = document.createElement("i");
  indicator.className = "media-selection";
  indicator.setAttribute("aria-hidden", "true");
  choice.append(thumbnail, name, indicator);
  choice.addEventListener("click", () => onSelect(asset.path));
  item.append(choice);

  if (asset.deletable) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "media-delete";
    deleteButton.setAttribute("aria-label", `Delete ${asset.name}`);
    deleteButton.title = `Delete ${asset.name}`;
    deleteButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 6h18"></path>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
        <path d="M10 11v6"></path>
        <path d="M14 11v6"></path>
      </svg>
    `;
    deleteButton.addEventListener("click", () => onDelete(asset));
    item.append(deleteButton);
  }
  return item;
}

function renderMediaLibraries() {
  const library = app.state?.mediaLibrary || { dancing: [], resting: [] };
  const restPath = byId("danceRest").value;
  const restGrid = byId("restMediaGrid");
  restGrid.replaceChildren();
  library.resting.forEach((asset) => {
    restGrid.append(
      createMediaChoice(
        asset,
        asset.path === restPath,
        false,
        (path) => {
          byId("danceRest").value = path;
          renderMediaLibraries();
        },
        (selectedAsset) => requestDeleteAsset(selectedAsset, "rest"),
      ),
    );
  });
  if (!library.resting.length) {
    const empty = document.createElement("span");
    empty.className = "media-empty";
    empty.textContent = "No resting images";
    restGrid.append(empty);
  }
  const selectedRest = library.resting.find((asset) => asset.path === restPath);
  byId("restSelectionName").textContent = selectedRest?.name || "No image selected";

  const multiple = app.danceMode === "random";
  const danceGrid = byId("danceMediaGrid");
  danceGrid.classList.toggle("multi-select", multiple);
  danceGrid.setAttribute("role", multiple ? "group" : "radiogroup");
  danceGrid.replaceChildren();
  library.dancing.forEach((asset) => {
    danceGrid.append(
      createMediaChoice(
        asset,
        app.danceSelection.has(asset.path),
        multiple,
        (path) => {
          if (multiple) {
            if (app.danceSelection.has(path)) {
              if (app.danceSelection.size === 1) {
                showToast("Keep at least one dance selected");
                return;
              }
              app.danceSelection.delete(path);
            } else {
              app.danceSelection.add(path);
            }
          } else {
            app.danceSelection = new Set([path]);
          }
          byId("danceGif").value = [...app.danceSelection][0] || "";
          renderMediaLibraries();
        },
        (selectedAsset) => requestDeleteAsset(selectedAsset, "gif"),
      ),
    );
  });
  if (!library.dancing.length) {
    const empty = document.createElement("span");
    empty.className = "media-empty";
    empty.textContent = "No dancing media";
    danceGrid.append(empty);
  }

  const count = app.danceSelection.size;
  byId("danceSelectionCount").textContent =
    app.danceMode === "random" ? `${count} selected for random play` : `${count} selected`;
  document.querySelectorAll("[data-dance-mode]").forEach((button) => {
    const active = button.dataset.danceMode === app.danceMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function setDanceMode(mode) {
  app.danceMode = mode === "random" ? "random" : "single";
  if (!app.danceSelection.size) {
    const fallback =
      app.state?.config?.dance?.gif || app.state?.defaults?.dance?.gif || "";
    if (fallback) app.danceSelection.add(fallback);
  }
  if (app.danceMode === "single" && app.danceSelection.size > 1) {
    app.danceSelection = new Set([[...app.danceSelection][0]]);
  }
  byId("danceGif").value = [...app.danceSelection][0] || "";
  renderMediaLibraries();
}

function requestDeleteAsset(asset, kind) {
  app.pendingDeleteAsset = { ...asset, kind };
  byId("deleteMediaName").textContent = asset.name;
  byId("deleteMediaDialog").showModal();
}

async function deletePendingAsset() {
  const asset = app.pendingDeleteAsset;
  if (!asset || app.busy) return;
  app.busy = true;
  byId("confirmDeleteMedia").disabled = true;
  try {
    const result = await callApi("delete_asset", asset.kind, asset.path);
    if (!result.ok) {
      showToast(result.detail || "Could not delete that media");
      return;
    }

    app.state.config = result.config;
    app.state.mediaLibrary = result.library;
    app.mediaLibraryKey = JSON.stringify(result.library);
    if (asset.kind === "gif") {
      app.danceSelection.delete(asset.path);
      if (!app.danceSelection.size) {
        app.danceSelection.add(result.config.dance.gif);
      }
      byId("danceGif").value = [...app.danceSelection][0];
    } else if (app.danceSelection.has(asset.path)) {
      app.danceSelection.delete(asset.path);
      result.config.dance.pool.forEach((path) => app.danceSelection.add(path));
      byId("danceGif").value = [...app.danceSelection][0];
    }
    if (byId("danceRest").value === asset.path) {
      byId("danceRest").value = result.config.dance.rest;
    }
    byId("deleteMediaDialog").close();
    renderMediaLibraries();
    logActivity(`Media deleted: ${result.name}`);
    showToast(`${result.name} deleted`);
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
    byId("confirmDeleteMedia").disabled = false;
  }
}

function resizeLargePreview() {
  const stage = document.querySelector(".large-preview-stage");
  const iframe = byId("largeOverlayPreview");
  const instance = instanceById(app.previewInstanceId);
  const manifest = manifestFor(instance?.type);
  if (!stage || !iframe || !manifest) return;
  const { w: width, h: height } = manifest.canvas;
  const scale = Math.min(stage.clientWidth / width, stage.clientHeight / height) * 0.9;
  iframe.style.width = `${width}px`;
  iframe.style.height = `${height}px`;
  iframe.style.left = `${(stage.clientWidth - width * scale) / 2}px`;
  iframe.style.top = `${(stage.clientHeight - height * scale) / 2}px`;
  iframe.style.transform = `scale(${scale})`;
}

function renderLargePreview(state) {
  const instance = instanceById(app.previewInstanceId);
  if (!instance) return;
  const iframe = byId("largeOverlayPreview");
  const url = instanceUrl(instance);
  updatePreview(iframe, studioPreviewUrl(instance), state.running);
  byId("overlayPreviewStatus").textContent = state.running ? "Live and running" : "Server offline";
  byId("copyPreviewUrlButton").disabled = !url;
  byId("openPreviewSourceButton").disabled = !state.running || !url;
  byId("overlayPreviewDialog").classList.toggle("server-running", state.running);
}

function openOverlayPreview(instanceId) {
  const instance = instanceById(instanceId);
  const manifest = manifestFor(instance?.type);
  if (!instance || !manifest) return;
  app.previewInstanceId = instance.id;
  byId("overlayPreviewType").textContent =
    `${manifest.name.toUpperCase()} / LIVE OBS PREVIEW`;
  byId("overlayPreviewTitle").textContent = instance.name;
  byId("largeOverlayPreview").title = `Live ${instance.name} preview`;
  byId("customizePreviewButton").hidden = !manifest.studioView;
  renderLargePreview(app.state || { running: false });
  byId("overlayPreviewDialog").showModal();
  requestAnimationFrame(resizeLargePreview);
}

function closeOverlayPreview() {
  const dialog = byId("overlayPreviewDialog");
  if (dialog.open) dialog.close();
}

function renderServerState(state) {
  document.body.classList.toggle("server-running", state.running);
  byId("headerStatusText").textContent = state.running ? "Running" : "Stopped";
  byId("headerServerButton").textContent = state.running ? "Server ready" : "Start server";
  byId("serverAddress").textContent = state.baseUrl;
  byId("serverState").textContent = state.running ? "Ready for OBS and Spotify" : "Not running";

  document.querySelectorAll(".overlay-card small b").forEach((label) => {
    label.textContent = state.running ? "RUNNING" : "OFFLINE";
  });
  document.querySelectorAll("[data-server-action]").forEach((button) => {
    const action = button.dataset.serverAction;
    button.disabled =
      app.busy ||
      (state.running && action === "start") ||
      (!state.running && action !== "start");
  });
  byId("headerServerButton").disabled = app.busy;

  renderLibrary(state);
  renderServerUrls();
  renderActiveIdentity(activeInstance());
  renderLargePreview(state);
}

function renderCounter(counter) {
  if (!counter) return;
  byId("winsValue").textContent = Math.max(0, Number(counter.wins) || 0);
  byId("lossesValue").textContent = Math.max(0, Number(counter.losses) || 0);
  byId("counterTitle").value = counter.title || "MARVEL RIVALS";
  setColor("counterAccent", counter.accent || "d7ff45");
}

function setColor(id, value) {
  const normalized = `#${String(value || "").replace("#", "").padEnd(6, "0").slice(0, 6)}`;
  const input = byId(id);
  input.value = normalized;
  updateColorLabel(id);
}

function updateColorLabel(id) {
  const input = byId(id);
  const label = byId(`${id}Label`);
  if (!input || !label) return;
  const value = input.value.toUpperCase();
  const red = parseInt(value.slice(1, 3), 16);
  const green = parseInt(value.slice(3, 5), 16);
  const blue = parseInt(value.slice(5, 7), 16);
  const luminance = (red * 299 + green * 587 + blue * 114) / 1000;
  label.textContent = value;
  label.parentElement.style.background = value;
  label.parentElement.style.color = luminance > 145 ? "#101416" : "#ffffff";
}

function fillConfig(config) {
  byId("danceName").value = config.dance.name;
  app.danceMode = config.dance.mode === "random" ? "random" : "single";
  app.danceSelection = new Set(
    app.danceMode === "random" ? config.dance.pool : [config.dance.gif],
  );
  byId("danceGif").value = config.dance.gif;
  byId("danceRest").value = config.dance.rest;
  byId("danceScale").value = config.dance.scale;
  byId("sensitivity").value = config.audio.sensitivity;
  byId("sensitivityOutput").value = Number(config.audio.sensitivity).toFixed(2);
  byId("fallbackBpm").value = config.nowPlaying.fallbackBpm;

  byId("spotifyScale").value = config.spotify.scale;
  byId("playerWidth").value = config.spotify.cardWidth;
  byId("colorMode").value = config.spotify.colorMode;
  setColor("colorA", config.spotify.colors.a);
  setColor("colorB", config.spotify.colors.b);
  setColor("colorC", config.spotify.colors.c);
  byId("flowName").value = config.flow.name;
  byId("flowScale").value = config.flow.scale;
  byId("flowGlow").value = config.flow.glow;
  byId("flowGlowOutput").value = Number(config.flow.glow).toFixed(2);
  renderMediaLibraries();
}

function gatherConfig() {
  const dancePool = [...app.danceSelection];
  const primaryDance =
    dancePool[0] || app.state?.defaults?.dance?.gif || "assets/dancing-dog.gif";
  return {
    dance: {
      name: byId("danceName").value,
      mode: app.danceMode,
      gif: primaryDance,
      pool: dancePool.length ? dancePool : [primaryDance],
      rest: byId("danceRest").value,
      position:
        app.state?.config?.dance?.position
        || app.state?.defaults?.dance?.position
        || "bottom-left",
      scale: Number(byId("danceScale").value),
    },
    spotify: {
      position:
        app.state?.config?.spotify?.position
        || app.state?.defaults?.spotify?.position
        || "bottom-left",
      scale: Number(byId("spotifyScale").value),
      cardWidth: Number(byId("playerWidth").value),
      colorMode: byId("colorMode").value,
      colors: {
        a: byId("colorA").value.slice(1),
        b: byId("colorB").value.slice(1),
        c: byId("colorC").value.slice(1),
      },
    },
    flow: {
      name: byId("flowName").value,
      scale: Number(byId("flowScale").value),
      glow: Number(byId("flowGlow").value),
    },
    audio: {
      enabled: true,
      sensitivity: Number(byId("sensitivity").value),
    },
    nowPlaying: {
      fallbackBpm: Number(byId("fallbackBpm").value),
    },
  };
}

function renderState(state, hydrate = false) {
  const mediaLibraryKey = JSON.stringify(state.mediaLibrary || {});
  const mediaLibraryChanged = mediaLibraryKey !== app.mediaLibraryKey;
  app.mediaLibraryKey = mediaLibraryKey;
  app.state = state;
  if (app.activeInstanceId && !instanceById(app.activeInstanceId)) {
    app.activeInstanceId = null;
  }
  setTheme(state.theme);
  renderServerState(state);
  const selected = activeInstance();
  renderCounter(
    selected?.type === "win-loss"
      ? state.counters?.[selected.id]
      : state.counter,
  );
  if (hydrate) {
    fillConfig(
      selected ? materializeInstanceConfig(selected) : state.config,
    );
  }
  else if (mediaLibraryChanged && byId("danceRest").value) renderMediaLibraries();
}

async function refreshState(hydrate = false) {
  if (app.pollPending) return;
  app.pollPending = true;
  try {
    const state = await callApi("get_state");
    renderState(state, hydrate);
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.pollPending = false;
  }
}

async function runServerAction(action) {
  if (app.busy) return;
  app.busy = true;
  if (app.state) renderServerState(app.state);
  logActivity(`${action[0].toUpperCase()}${action.slice(1)}ing overlay server`);
  try {
    const result = await callApi("server_action", action);
    renderState(result.state, false);
    logActivity(result.detail);
    if (!result.ok) showToast(result.detail);
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
    if (app.state) renderServerState(app.state);
  }
}

async function chooseAsset(kind) {
  const result = await callApi("choose_asset", kind);
  if (!result.ok) {
    if (!result.cancelled) showToast(result.detail || "Could not choose that file");
    return;
  }
  app.state.mediaLibrary = result.library;
  app.mediaLibraryKey = JSON.stringify(result.library);
  if (kind === "gif") {
    if (app.danceMode === "random") app.danceSelection.add(result.path);
    else app.danceSelection = new Set([result.path]);
    byId("danceGif").value = [...app.danceSelection][0];
  } else {
    byId("danceRest").value = result.path;
  }
  renderMediaLibraries();
  logActivity(`${kind === "gif" ? "Dance GIF" : "Resting image"} selected: ${result.name}`);
}

function readDroppedFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(new Error(`Could not read ${file.name}`)));
    reader.readAsDataURL(file);
  });
}

async function importDroppedDanceFiles(fileList) {
  if (app.busy) return;
  const allowed = new Set(["gif", "webp", "apng", "png", "webm", "mp4", "mov", "url"]);
  const files = [...fileList].filter((file) => {
    const extension = file.name.split(".").pop()?.toLowerCase();
    return extension && allowed.has(extension);
  });
  if (!files.length) {
    showToast("Drop supported media or an Internet shortcut");
    return;
  }

  app.busy = true;
  const imported = [];
  const failures = [];
  try {
    for (const file of files) {
      const extension = file.name.split(".").pop()?.toLowerCase();
      const maximumBytes = extension === "url" ? 64 * 1024 : 25 * 1024 * 1024;
      if (file.size > maximumBytes) {
        failures.push(
          extension === "url"
            ? `${file.name} is not a valid Internet shortcut`
            : `${file.name} is over 25 MB; use Add media`,
        );
        continue;
      }
      try {
        const dataUrl = await readDroppedFile(file);
        const result = await callApi("import_asset", "gif", file.name, dataUrl);
        if (!result.ok) {
          failures.push(result.detail || `Could not import ${file.name}`);
          continue;
        }
        app.state.mediaLibrary = result.library;
        app.mediaLibraryKey = JSON.stringify(result.library);
        imported.push(result);
      } catch (error) {
        failures.push(String(error.message || error));
      }
    }
  } finally {
    app.busy = false;
  }

  if (imported.length) {
    if (app.danceMode === "random") {
      imported.forEach((result) => app.danceSelection.add(result.path));
    } else {
      app.danceSelection = new Set([imported[0].path]);
    }
    byId("danceGif").value = [...app.danceSelection][0];
    renderMediaLibraries();
    imported.forEach((result) => logActivity(`Dancing media imported: ${result.name}`));
    showToast(`${imported.length} dancing ${imported.length === 1 ? "file" : "files"} imported`);
  } else {
    showToast(failures[0] || "No dancing media imported");
  }
  failures.forEach((message) => logActivity(message));
}

function bindDanceDropZone() {
  const target = byId("danceMediaDropZone");
  const containsFiles = (event) => [...(event.dataTransfer?.types || [])].includes("Files");
  document.addEventListener(
    "dragover",
    (event) => {
      if (containsFiles(event)) event.preventDefault();
    },
    true,
  );
  document.addEventListener(
    "drop",
    (event) => {
      if (containsFiles(event)) event.preventDefault();
    },
    true,
  );
  target.addEventListener("dragenter", (event) => {
    if (!containsFiles(event)) return;
    event.preventDefault();
    target.classList.add("drop-active");
  });
  target.addEventListener("dragover", (event) => {
    if (!containsFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    target.classList.add("drop-active");
  });
  target.addEventListener("dragleave", (event) => {
    if (!target.contains(event.relatedTarget)) target.classList.remove("drop-active");
  });
  target.addEventListener("drop", (event) => {
    target.classList.remove("drop-active");
    if (!containsFiles(event)) return;
    event.preventDefault();
    importDroppedDanceFiles(event.dataTransfer.files);
  });
}

async function saveOverlaySettings() {
  if (app.busy) return;
  const instance = activeInstance();
  if (!instance) {
    showToast("Choose an overlay instance first");
    return;
  }
  app.busy = true;
  try {
    const result = await callApi(
      "save_overlay_settings",
      gatherConfig(),
      instance.id,
    );
    if (!result.ok) {
      showToast(result.detail || "Settings could not be saved");
      return;
    }
    if (app.state) app.state.config = result.config;
    fillConfig(result.instanceConfig || materializeInstanceConfig(instance));
    const desiredName =
      instance.type === "larpdog-dance"
        ? byId("danceName").value
        : instance.type === "now-playing-flow"
          ? byId("flowName").value
          : instance.name;
    if (desiredName.trim() && desiredName.trim() !== instance.name) {
      const renamed = await callApi(
        "rename_overlay_instance",
        instance.id,
        desiredName,
      );
      if (renamed.ok) renderState(renamed.state, false);
    } else {
      app.libraryKey = "";
      renderServerState(app.state);
    }
    renderActiveIdentity(activeInstance());
    logActivity(result.applied ? "Settings saved and applied" : "Settings saved");
    showToast(result.applied ? "Saved and applied" : "Saved");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
}

async function sendCounter(payload) {
  const instance = activeInstance();
  if (!instance || instance.type !== "win-loss") return;
  const result = await callApi("update_counter", payload, instance.id);
  if (!result.ok) {
    showToast(result.detail || "Counter update failed");
    return;
  }
  app.state.counters = app.state.counters || {};
  app.state.counters[instance.id] = result.counter;
  renderCounter(result.counter);
  logActivity(`Match record updated: ${result.counter.wins} wins, ${result.counter.losses} losses`);
}

async function copySource(instanceId) {
  const instance = instanceById(instanceId);
  if (!instance) return;
  const result = await callApi("copy_text", instanceUrl(instance));
  if (result.ok) showToast("OBS URL copied");
  else showToast(result.detail || "Copy failed");
}

function openSource(instanceId) {
  const instance = instanceById(instanceId);
  if (instance) callApi("open_url", instanceUrl(instance));
}

function openInstanceSettings(instanceId) {
  const instance = instanceById(instanceId);
  const manifest = manifestFor(instance?.type);
  if (!instance || !manifest?.studioView) return;
  app.activeInstanceId = instance.id;
  fillConfig(materializeInstanceConfig(instance));
  renderActiveIdentity(instance);
  if (instance.type === "win-loss") {
    renderCounter(app.state?.counters?.[instance.id] || app.state?.counter);
  }
  showView(manifest.studioView);
}

async function addOverlayType(overlayType) {
  if (app.busy) return;
  app.busy = true;
  try {
    const result = await callApi("add_overlay_instance", overlayType);
    if (!result.ok) {
      showToast(result.detail || "Overlay could not be added");
      return;
    }
    app.libraryKey = "";
    renderState(result.state, false);
    logActivity(`Overlay added: ${instanceById(result.instanceId)?.name || overlayType}`);
    showToast("Overlay added");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
}

function requestRemoveOverlay(instanceId) {
  const instance = instanceById(instanceId);
  if (!instance) return;
  app.pendingRemoveInstanceId = instance.id;
  byId("removeOverlayName").textContent = instance.name;
  byId("removeOverlayDialog").showModal();
}

async function removePendingOverlay() {
  const instanceId = app.pendingRemoveInstanceId;
  if (!instanceId || app.busy) return;
  app.busy = true;
  try {
    const result = await callApi("remove_overlay_instance", instanceId);
    if (!result.ok) {
      showToast(result.detail || "Overlay could not be removed");
      return;
    }
    if (app.activeInstanceId === instanceId) app.activeInstanceId = null;
    app.libraryKey = "";
    byId("removeOverlayDialog").close();
    renderState(result.state, false);
    logActivity("Overlay removed");
    showToast("Overlay removed");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
}

function requestRenameOverlay(instanceId) {
  const instance = instanceById(instanceId);
  if (!instance) return;
  app.pendingRenameInstanceId = instance.id;
  byId("renameOverlayInput").value = instance.name;
  byId("renameOverlayDialog").showModal();
  requestAnimationFrame(() => {
    byId("renameOverlayInput").focus();
    byId("renameOverlayInput").select();
  });
}

async function renamePendingOverlay() {
  const instanceId = app.pendingRenameInstanceId;
  const name = byId("renameOverlayInput").value.trim();
  if (!instanceId || !name || app.busy) return;
  app.busy = true;
  try {
    const result = await callApi("rename_overlay_instance", instanceId, name);
    if (!result.ok) {
      showToast(result.detail || "Overlay could not be renamed");
      return;
    }
    app.libraryKey = "";
    byId("renameOverlayDialog").close();
    renderState(result.state, false);
    renderActiveIdentity(activeInstance());
    logActivity(`Overlay renamed: ${name}`);
    showToast("Overlay renamed");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
}

function handleInstanceAction(action, instanceId) {
  if (action === "copy") copySource(instanceId);
  else if (action === "open") openSource(instanceId);
  else if (action === "rename") requestRenameOverlay(instanceId);
  else if (action === "remove") requestRemoveOverlay(instanceId);
}

function bindEvents() {
  bindDanceDropZone();
  byId("menuButton").addEventListener("click", () => setDrawer(true));
  byId("closeDrawerButton").addEventListener("click", () => setDrawer(false));
  byId("drawerScrim").addEventListener("click", () => setDrawer(false));

  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewTarget));
  });
  document.querySelectorAll(".library-button").forEach((button) => {
    button.addEventListener("click", () => showView("libraryView"));
  });
  document.querySelectorAll("[data-drawer-view]").forEach((button) => {
    button.addEventListener("click", () => {
      showView(button.dataset.drawerView);
      setDrawer(false);
    });
  });

  byId("headerServerButton").addEventListener("click", () => {
    if (app.state?.running) showView("serverView");
    else runServerAction("start");
  });
  document.querySelectorAll("[data-server-action]").forEach((button) => {
    button.addEventListener("click", () => runServerAction(button.dataset.serverAction));
  });
  document.querySelectorAll("[data-open-folder]").forEach((button) => {
    button.addEventListener("click", () => callApi("open_folder", button.dataset.openFolder));
  });

  document.querySelectorAll("[data-copy-active]").forEach((button) => {
    button.addEventListener("click", () => copySource(app.activeInstanceId));
  });
  document.querySelectorAll("[data-open-active]").forEach((button) => {
    button.addEventListener("click", () => openSource(app.activeInstanceId));
  });

  document.querySelectorAll("[data-choose-asset]").forEach((button) => {
    button.addEventListener("click", () => chooseAsset(button.dataset.chooseAsset));
  });
  document.querySelectorAll("[data-dance-mode]").forEach((button) => {
    button.addEventListener("click", () => setDanceMode(button.dataset.danceMode));
  });

  byId("sensitivity").addEventListener("input", () => {
    byId("sensitivityOutput").value = Number(byId("sensitivity").value).toFixed(2);
  });
  byId("flowGlow").addEventListener("input", () => {
    byId("flowGlowOutput").value = Number(byId("flowGlow").value).toFixed(2);
  });
  ["colorA", "colorB", "colorC", "counterAccent"].forEach((id) => {
    byId(id).addEventListener("input", () => updateColorLabel(id));
  });

  byId("saveDanceButton").addEventListener("click", saveOverlaySettings);
  byId("saveSpotifyButton").addEventListener("click", saveOverlaySettings);
  byId("saveFlowButton").addEventListener("click", saveOverlaySettings);
  byId("resetDanceButton").addEventListener("click", () => {
    const defaults = app.state.defaults;
    byId("danceName").value = defaults.dance.name;
    app.danceMode = defaults.dance.mode;
    app.danceSelection = new Set(defaults.dance.pool);
    byId("danceGif").value = defaults.dance.gif;
    byId("danceRest").value = defaults.dance.rest;
    byId("danceScale").value = defaults.dance.scale;
    byId("sensitivity").value = defaults.audio.sensitivity;
    byId("sensitivityOutput").value = Number(defaults.audio.sensitivity).toFixed(2);
    byId("fallbackBpm").value = defaults.nowPlaying.fallbackBpm;
    renderMediaLibraries();
    logActivity("Dance fields reset; save to apply");
  });
  byId("resetSpotifyButton").addEventListener("click", () => {
    const defaults = app.state.defaults.spotify;
    byId("spotifyScale").value = defaults.scale;
    byId("playerWidth").value = defaults.cardWidth;
    byId("colorMode").value = defaults.colorMode;
    setColor("colorA", defaults.colors.a);
    setColor("colorB", defaults.colors.b);
    setColor("colorC", defaults.colors.c);
    logActivity("Spotify fields reset; save to apply");
  });
  byId("resetFlowButton").addEventListener("click", () => {
    const defaults = app.state.defaults.flow;
    byId("flowName").value = defaults.name;
    byId("flowScale").value = defaults.scale;
    byId("flowGlow").value = defaults.glow;
    byId("flowGlowOutput").value = Number(defaults.glow).toFixed(2);
    logActivity("Now Playing Flow fields reset; save to apply");
  });

  document.querySelectorAll("[data-counter-action]").forEach((button) => {
    button.addEventListener("click", () => sendCounter({ action: button.dataset.counterAction }));
  });
  document.querySelectorAll("[data-counter-reset]").forEach((button) => {
    button.addEventListener("click", () => sendCounter({ [button.dataset.counterReset]: 0 }));
  });
  byId("saveCounterSettings").addEventListener("click", () => {
    sendCounter({
      title: byId("counterTitle").value,
      accent: byId("counterAccent").value.slice(1),
    });
  });

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", async () => {
      const theme = button.dataset.themeChoice;
      setTheme(theme);
      await callApi("set_theme", theme);
    });
  });

  const overlayGrid = byId("overlayGrid");
  overlayGrid.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-preview-instance]");
    if (preview) {
      openOverlayPreview(preview.dataset.previewInstance);
      return;
    }
    const action = event.target.closest("[data-instance-action]");
    if (action) {
      handleInstanceAction(action.dataset.instanceAction, action.dataset.instanceId);
      return;
    }
    if (event.target.closest("#addOverlayButton")) {
      renderCatalog();
      byId("addOverlayDialog").showModal();
    }
  });
  byId("serverOverlayUrls").addEventListener("click", (event) => {
    const action = event.target.closest("[data-instance-action]");
    if (action) handleInstanceAction(action.dataset.instanceAction, action.dataset.instanceId);
  });
  byId("catalogGrid").addEventListener("click", (event) => {
    const add = event.target.closest("[data-add-overlay-type]");
    if (add) addOverlayType(add.dataset.addOverlayType);
  });
  byId("closeAddDialog").addEventListener("click", () => byId("addOverlayDialog").close());

  const removeOverlayDialog = byId("removeOverlayDialog");
  byId("cancelRemoveOverlay").addEventListener("click", () => removeOverlayDialog.close());
  byId("confirmRemoveOverlay").addEventListener("click", removePendingOverlay);
  removeOverlayDialog.addEventListener("close", () => {
    app.pendingRemoveInstanceId = null;
  });

  const renameOverlayDialog = byId("renameOverlayDialog");
  byId("cancelRenameOverlay").addEventListener("click", () => renameOverlayDialog.close());
  byId("confirmRenameOverlay").addEventListener("click", renamePendingOverlay);
  byId("renameOverlayInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") renamePendingOverlay();
  });
  renameOverlayDialog.addEventListener("close", () => {
    app.pendingRenameInstanceId = null;
  });

  const deleteMediaDialog = byId("deleteMediaDialog");
  byId("cancelDeleteMedia").addEventListener("click", () => deleteMediaDialog.close());
  byId("confirmDeleteMedia").addEventListener("click", deletePendingAsset);
  deleteMediaDialog.addEventListener("click", (event) => {
    if (event.target === deleteMediaDialog) deleteMediaDialog.close();
  });
  deleteMediaDialog.addEventListener("close", () => {
    app.pendingDeleteAsset = null;
  });

  const previewDialog = byId("overlayPreviewDialog");
  byId("closePreviewButton").addEventListener("click", closeOverlayPreview);
  byId("copyPreviewUrlButton").addEventListener("click", () => copySource(app.previewInstanceId));
  byId("openPreviewSourceButton").addEventListener("click", () => {
    openSource(app.previewInstanceId);
  });
  byId("customizePreviewButton").addEventListener("click", () => {
    const instanceId = app.previewInstanceId;
    closeOverlayPreview();
    openInstanceSettings(instanceId);
  });
  previewDialog.addEventListener("click", (event) => {
    if (event.target === previewDialog) closeOverlayPreview();
  });
  previewDialog.addEventListener("close", () => {
    app.previewInstanceId = null;
    updatePreview(byId("largeOverlayPreview"), "", false);
  });
  window.addEventListener("resize", () => {
    resizeLargePreview();
    document.querySelectorAll(".live-preview iframe").forEach((frame) => {
      const instance = instanceById(frame.closest(".overlay-card")?.dataset.instanceId);
      fitCardPreview(frame, manifestFor(instance?.type));
    });
  });
}

async function initialize() {
  if (app.initialized) return;
  app.initialized = true;
  bindEvents();
  logActivity("Overlay Studio opened");
  await refreshState(true);
  setInterval(() => refreshState(false), 2500);
}

function initializeWhenReady() {
  if (window.pywebview?.api?.get_state) {
    initialize();
    return;
  }
  setTimeout(initializeWhenReady, 100);
}

window.addEventListener("pywebviewready", initializeWhenReady);
initializeWhenReady();
window.overlayStudioRefresh = () => refreshState(false);
