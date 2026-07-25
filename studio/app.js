const app = {
  state: null,
  busy: false,
  initialized: false,
  pollPending: false,
  toastTimer: null,
  previewKind: null,
  danceMode: "single",
  danceSelection: new Set(),
  mediaLibraryKey: "",
  pendingDeleteAsset: null,
  urls: {},
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

function sourceUrls(baseUrl) {
  return {
    dance: `${baseUrl}overlays/larpdog-dance`,
    spotify: `${baseUrl}overlays/spotify`,
    counter: `${baseUrl}overlays/win-loss`,
    flow: `${baseUrl}overlays/now-playing-flow`,
  };
}

function updatePreview(iframe, url, running) {
  const desired = running ? url : "";
  if (iframe.dataset.source === desired) return;
  iframe.dataset.source = desired;
  iframe.src = desired || "about:blank";
}

const previewDetails = {
  dance: {
    title: "Dancing GIF",
    type: "DANCING GIF",
    view: "danceView",
    canvas: [520, 420],
  },
  spotify: {
    title: "Spotify Overlay",
    type: "SPOTIFY OVERLAY",
    view: "spotifyView",
    canvas: [620, 360],
  },
  counter: {
    title: "Match Record",
    type: "MATCH RECORD",
    view: "counterView",
    canvas: [900, 320],
  },
  flow: {
    title: "Now Playing Flow",
    type: "NOW PLAYING FLOW",
    view: "flowView",
    canvas: [760, 420],
  },
};

function getDanceName(config = app.state?.config) {
  const name = String(config?.dance?.name || "").trim();
  return name || previewDetails.dance.title;
}

function renderDanceIdentity(config) {
  const name = getDanceName(config);
  byId("danceCardName").textContent = name;
  byId("danceCard").setAttribute("aria-label", `Preview ${name}`);
  byId("dancePreview").title = `Live ${name} preview`;
  byId("danceDetailName").textContent = name;
  byId("serverDanceLabel").textContent = name;
  byId("danceSourceLabel").textContent = name;
  if (app.previewKind === "dance") {
    byId("overlayPreviewTitle").textContent = name;
  }
}

function getFlowName(config = app.state?.config) {
  const name = String(config?.flow?.name || "").trim();
  return name || previewDetails.flow.title;
}

function renderFlowIdentity(config) {
  const name = getFlowName(config);
  byId("flowCardName").textContent = name;
  byId("flowCard").setAttribute("aria-label", `Preview ${name}`);
  byId("flowPreview").title = `Live ${name} preview`;
  byId("flowDetailName").textContent = name;
  byId("serverFlowLabel").textContent = name;
  byId("flowSourceLabel").textContent = name;
  if (app.previewKind === "flow") {
    byId("overlayPreviewTitle").textContent = name;
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
  const canvas = previewDetails[app.previewKind]?.canvas;
  if (!stage || !iframe || !canvas) return;
  const [width, height] = canvas;
  const scale = Math.min(stage.clientWidth / width, stage.clientHeight / height) * 0.9;
  iframe.style.width = `${width}px`;
  iframe.style.height = `${height}px`;
  iframe.style.left = `${(stage.clientWidth - width * scale) / 2}px`;
  iframe.style.top = `${(stage.clientHeight - height * scale) / 2}px`;
  iframe.style.transform = `scale(${scale})`;
}

function renderLargePreview(state) {
  if (!app.previewKind) return;
  const iframe = byId("largeOverlayPreview");
  const url = app.urls[app.previewKind];
  updatePreview(iframe, url ? `${url}?preview=studio` : "", state.running);
  byId("overlayPreviewStatus").textContent = state.running ? "Live and running" : "Server offline";
  byId("copyPreviewUrlButton").disabled = !url;
  byId("openPreviewSourceButton").disabled = !state.running || !url;
  byId("overlayPreviewDialog").classList.toggle("server-running", state.running);
}

function openOverlayPreview(kind) {
  const details = previewDetails[kind];
  if (!details) return;
  app.previewKind = kind;
  const title =
    kind === "dance"
      ? getDanceName()
      : kind === "flow"
        ? getFlowName()
        : details.title;
  byId("overlayPreviewType").textContent = `${details.type} / LIVE OBS PREVIEW`;
  byId("overlayPreviewTitle").textContent = title;
  byId("largeOverlayPreview").title = `Live ${title} preview`;
  byId("customizePreviewButton").hidden = !details.view;
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

  app.urls = sourceUrls(state.baseUrl);
  const urlBindings = {
    serverDanceUrl: "dance",
    danceUrl: "dance",
    serverSpotifyUrl: "spotify",
    spotifyUrl: "spotify",
    serverCounterUrl: "counter",
    counterUrl: "counter",
    serverFlowUrl: "flow",
    flowUrl: "flow",
  };
  Object.entries(urlBindings).forEach(([id, kind]) => {
    byId(id).value = app.urls[kind];
  });

  updatePreview(byId("dancePreview"), `${app.urls.dance}?preview=studio`, state.running);
  updatePreview(byId("spotifyPreview"), `${app.urls.spotify}?preview=studio`, state.running);
  updatePreview(byId("counterPreview"), `${app.urls.counter}?preview=studio`, state.running);
  updatePreview(byId("flowPreview"), `${app.urls.flow}?preview=studio`, state.running);
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
  byId("flowSideCovers").value = config.flow.sideCovers;
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
      sideCovers: Number(byId("flowSideCovers").value),
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
  setTheme(state.theme);
  renderDanceIdentity(state.config);
  renderFlowIdentity(state.config);
  renderServerState(state);
  renderCounter(state.counter);
  if (hydrate) fillConfig(state.config);
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
  app.busy = true;
  try {
    const result = await callApi("save_overlay_settings", gatherConfig());
    if (app.state) app.state.config = result.config;
    fillConfig(result.config);
    renderDanceIdentity(result.config);
    renderFlowIdentity(result.config);
    logActivity(result.applied ? "Settings saved and applied" : "Settings saved");
    showToast(result.applied ? "Saved and applied" : "Saved");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
}

async function sendCounter(payload) {
  const result = await callApi("update_counter", payload);
  if (!result.ok) {
    showToast(result.detail || "Counter update failed");
    return;
  }
  renderCounter(result.counter);
  logActivity(`Match record updated: ${result.counter.wins} wins, ${result.counter.losses} losses`);
}

async function copySource(kind) {
  const result = await callApi("copy_text", app.urls[kind]);
  if (result.ok) showToast("OBS URL copied");
  else showToast(result.detail || "Copy failed");
}

function bindEvents() {
  bindDanceDropZone();
  byId("menuButton").addEventListener("click", () => setDrawer(true));
  byId("closeDrawerButton").addEventListener("click", () => setDrawer(false));
  byId("drawerScrim").addEventListener("click", () => setDrawer(false));

  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewTarget));
  });
  document.querySelectorAll("[data-preview-kind]").forEach((button) => {
    button.addEventListener("click", () => openOverlayPreview(button.dataset.previewKind));
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

  document.querySelectorAll("[data-copy-source]").forEach((button) => {
    button.addEventListener("click", () => copySource(button.dataset.copySource));
  });
  document.querySelectorAll("[data-open-source]").forEach((button) => {
    button.addEventListener("click", () => callApi("open_url", app.urls[button.dataset.openSource]));
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
    byId("flowSideCovers").value = defaults.sideCovers;
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

  byId("addOverlayButton").addEventListener("click", () => byId("addOverlayDialog").showModal());
  byId("closeAddDialog").addEventListener("click", () => byId("addOverlayDialog").close());

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
  byId("copyPreviewUrlButton").addEventListener("click", () => copySource(app.previewKind));
  byId("openPreviewSourceButton").addEventListener("click", () => {
    if (app.previewKind) callApi("open_url", app.urls[app.previewKind]);
  });
  byId("customizePreviewButton").addEventListener("click", () => {
    const details = previewDetails[app.previewKind];
    if (!details) return;
    closeOverlayPreview();
    showView(details.view);
  });
  previewDialog.addEventListener("click", (event) => {
    if (event.target === previewDialog) closeOverlayPreview();
  });
  previewDialog.addEventListener("close", () => {
    app.previewKind = null;
    updatePreview(byId("largeOverlayPreview"), "", false);
  });
  window.addEventListener("resize", resizeLargePreview);
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
