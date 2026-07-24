const app = {
  state: null,
  busy: false,
  initialized: false,
  pollPending: false,
  toastTimer: null,
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
  };
}

function updatePreview(iframe, url, running) {
  const desired = running ? url : "";
  if (iframe.dataset.source === desired) return;
  iframe.dataset.source = desired;
  iframe.src = desired || "about:blank";
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
  };
  Object.entries(urlBindings).forEach(([id, kind]) => {
    byId(id).value = app.urls[kind];
  });

  updatePreview(byId("dancePreview"), `${app.urls.dance}?preview=studio`, state.running);
  updatePreview(byId("spotifyPreview"), `${app.urls.spotify}?preview=studio`, state.running);
  updatePreview(byId("counterPreview"), `${app.urls.counter}?preview=studio`, state.running);
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
  byId("dancePosition").value = config.dance.position;
  byId("danceGif").value = config.dance.gif;
  byId("danceRest").value = config.dance.rest;
  byId("danceScale").value = config.dance.scale;
  byId("sensitivity").value = config.audio.sensitivity;
  byId("sensitivityOutput").value = Number(config.audio.sensitivity).toFixed(2);
  byId("fallbackBpm").value = config.nowPlaying.fallbackBpm;

  byId("spotifyPosition").value = config.spotify.position;
  byId("spotifyScale").value = config.spotify.scale;
  byId("playerWidth").value = config.spotify.cardWidth;
  byId("colorMode").value = config.spotify.colorMode;
  setColor("colorA", config.spotify.colors.a);
  setColor("colorB", config.spotify.colors.b);
  setColor("colorC", config.spotify.colors.c);
}

function gatherConfig() {
  return {
    dance: {
      gif: byId("danceGif").value,
      rest: byId("danceRest").value,
      position: byId("dancePosition").value,
      scale: Number(byId("danceScale").value),
    },
    spotify: {
      position: byId("spotifyPosition").value,
      scale: Number(byId("spotifyScale").value),
      cardWidth: Number(byId("playerWidth").value),
      colorMode: byId("colorMode").value,
      colors: {
        a: byId("colorA").value.slice(1),
        b: byId("colorB").value.slice(1),
        c: byId("colorC").value.slice(1),
      },
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
  app.state = state;
  setTheme(state.theme);
  renderServerState(state);
  renderCounter(state.counter);
  if (hydrate) fillConfig(state.config);
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
  byId(kind === "gif" ? "danceGif" : "danceRest").value = result.path;
  logActivity(`${kind === "gif" ? "Dance GIF" : "Resting image"} selected: ${result.name}`);
}

async function saveOverlaySettings() {
  if (app.busy) return;
  app.busy = true;
  try {
    const result = await callApi("save_overlay_settings", gatherConfig());
    fillConfig(result.config);
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

  document.querySelectorAll("[data-copy-source]").forEach((button) => {
    button.addEventListener("click", () => copySource(button.dataset.copySource));
  });
  document.querySelectorAll("[data-open-source]").forEach((button) => {
    button.addEventListener("click", () => callApi("open_url", app.urls[button.dataset.openSource]));
  });

  document.querySelectorAll("[data-choose-asset]").forEach((button) => {
    button.addEventListener("click", () => chooseAsset(button.dataset.chooseAsset));
  });
  document.querySelectorAll("[data-default-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      const kind = button.dataset.defaultAsset;
      byId(kind === "gif" ? "danceGif" : "danceRest").value =
        app.state.defaults.dance[kind];
    });
  });

  byId("sensitivity").addEventListener("input", () => {
    byId("sensitivityOutput").value = Number(byId("sensitivity").value).toFixed(2);
  });
  ["colorA", "colorB", "colorC", "counterAccent"].forEach((id) => {
    byId(id).addEventListener("input", () => updateColorLabel(id));
  });

  byId("saveDanceButton").addEventListener("click", saveOverlaySettings);
  byId("saveSpotifyButton").addEventListener("click", saveOverlaySettings);
  byId("resetDanceButton").addEventListener("click", () => {
    const defaults = app.state.defaults;
    byId("dancePosition").value = defaults.dance.position;
    byId("danceGif").value = defaults.dance.gif;
    byId("danceRest").value = defaults.dance.rest;
    byId("danceScale").value = defaults.dance.scale;
    byId("sensitivity").value = defaults.audio.sensitivity;
    byId("sensitivityOutput").value = Number(defaults.audio.sensitivity).toFixed(2);
    byId("fallbackBpm").value = defaults.nowPlaying.fallbackBpm;
    logActivity("Dance fields reset; save to apply");
  });
  byId("resetSpotifyButton").addEventListener("click", () => {
    const defaults = app.state.defaults.spotify;
    byId("spotifyPosition").value = defaults.position;
    byId("spotifyScale").value = defaults.scale;
    byId("playerWidth").value = defaults.cardWidth;
    byId("colorMode").value = defaults.colorMode;
    setColor("colorA", defaults.colors.a);
    setColor("colorB", defaults.colors.b);
    setColor("colorC", defaults.colors.c);
    logActivity("Spotify fields reset; save to apply");
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
