const MAX_DANCE_PROFILES = 5;

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
  danceProfiles: [],
  activeDanceProfileId: null,
  danceProfileDialogMode: null,
  mediaLibraryKey: "",
  libraryKey: "",
  goalKey: "",
  goalBarKey: "",
  pendingDeleteAsset: null,
  pendingRemoveInstanceId: null,
  pendingRenameInstanceId: null,
};

const byId = (id) => document.getElementById(id);
const isGoalOverlayType = (type) => type === "goal" || type === "goal-bar";

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
  if (!host || !manifest || host.clientWidth <= 0 || host.clientHeight <= 0) {
    return false;
  }
  const width = manifest.canvas.w;
  const height = manifest.canvas.h;
  const scale = Math.min(
    host.clientWidth / width,
    host.clientHeight / height,
  ) * 0.88;
  frame.style.width = `${width}px`;
  frame.style.height = `${height}px`;
  frame.style.transform = `translate(-50%, -50%) scale(${scale})`;
  return true;
}

function fitCardPreviewHost(host) {
  const frame = host?.querySelector("iframe");
  const instanceId = host?.closest(".overlay-card")?.dataset.instanceId;
  fitCardPreview(frame, manifestFor(instanceById(instanceId)?.type));
}

const cardPreviewObserver = new ResizeObserver((entries) => {
  entries.forEach((entry) => fitCardPreviewHost(entry.target));
});

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
  frame.addEventListener("load", () => fitCardPreview(frame, manifest));
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
  cardPreviewObserver.observe(livePreview);
  requestAnimationFrame(() => {
    if (!fitCardPreview(frame, manifest)) {
      requestAnimationFrame(() => fitCardPreview(frame, manifest));
    }
  });
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
  grid.querySelectorAll(".live-preview").forEach((host) => {
    cardPreviewObserver.unobserve(host);
  });
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
  } else if (instance.type === "goal") {
    byId("goalDetailName").textContent = instance.name;
    byId("goalSourceLabel").textContent = instance.name;
    byId("goalUrl").value = source;
  } else if (instance.type === "goal-bar") {
    byId("goalBarDetailName").textContent = instance.name;
    byId("goalBarSourceLabel").textContent = instance.name;
    byId("goalBarUrl").value = source;
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

function activeDanceProfile() {
  return app.danceProfiles.find(
    (profile) => profile.id === app.activeDanceProfileId,
  ) || app.danceProfiles[0] || null;
}

function captureDanceProfile(profile) {
  const dancePool = [...app.danceSelection];
  const primaryDance =
    dancePool[0] || app.state?.defaults?.dance?.gif || "assets/dancing-dog.gif";
  return {
    ...structuredClone(profile || {}),
    mode: app.danceMode,
    gif: primaryDance,
    pool: dancePool.length ? dancePool : [primaryDance],
    rest: byId("danceRest").value,
    position:
      profile?.position
      || app.state?.defaults?.dance?.position
      || "bottom-left",
    scale: Number(byId("danceScale").value),
    sensitivity: Number(byId("sensitivity").value),
    fallbackBpm: Number(byId("fallbackBpm").value),
  };
}

function syncActiveDanceProfile() {
  const index = app.danceProfiles.findIndex(
    (profile) => profile.id === app.activeDanceProfileId,
  );
  if (index < 0) return;
  app.danceProfiles[index] = captureDanceProfile(app.danceProfiles[index]);
}

function loadDanceProfile(profile) {
  if (!profile) return;
  app.danceMode = profile.mode === "random" ? "random" : "single";
  const pool = Array.isArray(profile.pool) && profile.pool.length
    ? profile.pool
    : [profile.gif];
  app.danceSelection = new Set(
    app.danceMode === "random" ? pool : [profile.gif || pool[0]],
  );
  byId("danceGif").value = profile.gif || pool[0] || "";
  byId("danceRest").value = profile.rest || "";
  byId("danceScale").value = profile.scale;
  byId("sensitivity").value = profile.sensitivity;
  byId("sensitivityOutput").value = Number(profile.sensitivity).toFixed(2);
  byId("fallbackBpm").value = profile.fallbackBpm;
  renderMediaLibraries();
}

function renderDanceProfileControls() {
  const select = byId("danceProfileSelect");
  select.replaceChildren();
  app.danceProfiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.name;
    option.selected = profile.id === app.activeDanceProfileId;
    select.append(option);
  });
  byId("danceProfileCount").textContent =
    `${app.danceProfiles.length} of ${MAX_DANCE_PROFILES}`;
  select.disabled = app.busy || !app.danceProfiles.length;
  byId("addDanceProfileButton").disabled =
    app.busy || app.danceProfiles.length >= MAX_DANCE_PROFILES;
  byId("renameDanceProfileButton").disabled =
    app.busy || !app.danceProfiles.length;
  byId("deleteDanceProfileButton").disabled =
    app.busy || app.danceProfiles.length <= 1;
}

function hydrateDanceProfiles(config) {
  const supplied = Array.isArray(config.dance.profiles)
    ? config.dance.profiles.slice(0, MAX_DANCE_PROFILES)
    : [];
  app.danceProfiles = supplied.length
    ? structuredClone(supplied)
    : [{
      id: "default",
      name: "Default",
      mode: config.dance.mode,
      gif: config.dance.gif,
      pool: config.dance.pool,
      rest: config.dance.rest,
      position: config.dance.position,
      scale: config.dance.scale,
      sensitivity: config.audio.sensitivity,
      fallbackBpm: config.nowPlaying.fallbackBpm,
    }];
  app.activeDanceProfileId = app.danceProfiles.some(
    (profile) => profile.id === config.dance.activeProfileId,
  )
    ? config.dance.activeProfileId
    : app.danceProfiles[0].id;
  loadDanceProfile(activeDanceProfile());
  renderDanceProfileControls();
}

function nextDanceProfileId() {
  let suffix = 2;
  while (app.danceProfiles.some((profile) => profile.id === `profile-${suffix}`)) {
    suffix += 1;
  }
  return `profile-${suffix}`;
}

async function switchDanceProfile(profileId) {
  if (app.busy || profileId === app.activeDanceProfileId) return;
  syncActiveDanceProfile();
  const previousProfiles = structuredClone(app.danceProfiles);
  const previousProfileId = app.activeDanceProfileId;
  const selected = app.danceProfiles.find((profile) => profile.id === profileId);
  if (!selected) {
    renderDanceProfileControls();
    return;
  }
  app.activeDanceProfileId = selected.id;
  loadDanceProfile(selected);
  renderDanceProfileControls();
  const saved = await saveOverlaySettings({
    successMessage: `${selected.name} applied`,
    activityMessage: `Dance profile switched: ${selected.name}`,
  });
  if (!saved) {
    app.danceProfiles = previousProfiles;
    app.activeDanceProfileId = previousProfileId;
    loadDanceProfile(activeDanceProfile());
    renderDanceProfileControls();
  }
}

function openDanceProfileDialog(mode) {
  if (app.busy) return;
  const current = activeDanceProfile();
  if (mode === "create" && app.danceProfiles.length >= MAX_DANCE_PROFILES) {
    showToast("Dance profile limit reached");
    return;
  }
  if (mode === "rename" && !current) return;
  app.danceProfileDialogMode = mode;
  byId("danceProfileDialogTitle").textContent =
    mode === "create" ? "New dance profile" : "Rename dance profile";
  byId("danceProfileNameInput").value =
    mode === "create" ? `Profile ${app.danceProfiles.length + 1}` : current.name;
  byId("danceProfileDialog").showModal();
  requestAnimationFrame(() => {
    byId("danceProfileNameInput").focus();
    byId("danceProfileNameInput").select();
  });
}

async function saveDanceProfileDialog() {
  const mode = app.danceProfileDialogMode;
  const name = byId("danceProfileNameInput").value.trim();
  if (!mode || !name || app.busy) return;
  syncActiveDanceProfile();
  const previousProfiles = structuredClone(app.danceProfiles);
  const previousProfileId = app.activeDanceProfileId;
  if (mode === "create") {
    if (app.danceProfiles.length >= MAX_DANCE_PROFILES) {
      showToast("Dance profile limit reached");
      return;
    }
    const created = {
      ...structuredClone(activeDanceProfile()),
      id: nextDanceProfileId(),
      name,
    };
    app.danceProfiles.push(created);
    app.activeDanceProfileId = created.id;
    loadDanceProfile(created);
  } else {
    const current = activeDanceProfile();
    if (!current) return;
    current.name = name;
  }
  renderDanceProfileControls();
  byId("danceProfileDialog").close();
  const saved = await saveOverlaySettings({
    successMessage: mode === "create" ? "Profile created" : "Profile renamed",
    activityMessage:
      mode === "create"
        ? `Dance profile created: ${name}`
        : `Dance profile renamed: ${name}`,
  });
  if (!saved) {
    app.danceProfiles = previousProfiles;
    app.activeDanceProfileId = previousProfileId;
    loadDanceProfile(activeDanceProfile());
    renderDanceProfileControls();
  }
}

function requestDeleteDanceProfile() {
  const profile = activeDanceProfile();
  if (!profile || app.danceProfiles.length <= 1 || app.busy) return;
  byId("deleteDanceProfileName").textContent = profile.name;
  byId("deleteDanceProfileDialog").showModal();
}

async function deleteDanceProfile() {
  const profile = activeDanceProfile();
  if (!profile || app.danceProfiles.length <= 1 || app.busy) return;
  syncActiveDanceProfile();
  const previousProfiles = structuredClone(app.danceProfiles);
  const previousProfileId = app.activeDanceProfileId;
  const deletedIndex = app.danceProfiles.findIndex(
    (candidate) => candidate.id === profile.id,
  );
  app.danceProfiles.splice(deletedIndex, 1);
  const nextProfile =
    app.danceProfiles[Math.min(deletedIndex, app.danceProfiles.length - 1)];
  app.activeDanceProfileId = nextProfile.id;
  loadDanceProfile(nextProfile);
  renderDanceProfileControls();
  byId("deleteDanceProfileDialog").close();
  const saved = await saveOverlaySettings({
    successMessage: "Profile deleted",
    activityMessage: `Dance profile deleted: ${profile.name}`,
  });
  if (!saved) {
    app.danceProfiles = previousProfiles;
    app.activeDanceProfileId = previousProfileId;
    loadDanceProfile(activeDanceProfile());
    renderDanceProfileControls();
  }
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
    const selectedInstance = activeInstance();
    fillConfig(
      selectedInstance
        ? materializeInstanceConfig(selectedInstance)
        : result.config,
    );
    byId("deleteMediaDialog").close();
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

function syncGoalFormat() {
  byId("goalSymbol").disabled = byId("goalFormat").value !== "currency";
}

function renderGoal(goal, force = false) {
  if (!goal) return;
  const key = JSON.stringify(goal);
  if (!force && key === app.goalKey) return;
  app.goalKey = key;
  byId("goalLabel").value = goal.label || "Tip goal";
  byId("goalCurrent").value = Number(goal.current) || 0;
  byId("goalTarget").value = Math.max(0.01, Number(goal.target) || 50);
  byId("goalFormat").value = goal.format === "number" ? "number" : "currency";
  byId("goalSymbol").value = goal.symbol || "$";
  setColor("goalColor", goal.color || "ffe2a0");
  setColor("goalTrack", goal.track || "3c3028");
  setColor("goalLabelColor", goal.labelColor || "f5e3be");
  byId("goalFont").value = goal.font || "serif";
  byId("goalWeight").value = String(goal.weight || 500);
  byId("goalParticles").checked = goal.particles !== false;
  byId("goalPercent").checked = goal.percent !== false;
  byId("goalScale").value = Number(goal.scale) || 1;
  byId("goalScaleOutput").value = Number(goal.scale || 1).toFixed(2);
  byId("goalGlow").value = Number(goal.glow) || 0;
  byId("goalGlowOutput").value = Number(goal.glow || 0).toFixed(2);
  syncGoalFormat();
}

function syncGoalBarFormat() {
  byId("goalBarSymbol").disabled = byId("goalBarFormat").value !== "currency";
}

function syncGoalBarLayout() {
  byId("goalBarWidth").disabled = byId("goalBarLayout").value === "vertical";
}

function renderGoalBar(goal, force = false) {
  if (!goal) return;
  const key = JSON.stringify(goal);
  if (!force && key === app.goalBarKey) return;
  app.goalBarKey = key;
  byId("goalBarLabel").value = goal.label || "Followers";
  byId("goalBarCurrent").value = Number(goal.current) || 0;
  byId("goalBarTarget").value = Math.max(0.01, Number(goal.target) || 100);
  byId("goalBarFormat").value = goal.format === "currency" ? "currency" : "number";
  byId("goalBarSymbol").value = goal.symbol || "$";
  byId("goalBarLayout").value = goal.layout || "horizontal";
  byId("goalBarSize").value = goal.size || "full";
  byId("goalBarShell").value = goal.shell || "on";
  byId("goalBarIcon").value = goal.icon || "followers";
  byId("goalBarCorners").value = goal.corners || "round";
  byId("goalBarWidth").value = Number(goal.width) || 640;
  byId("goalBarWidthOutput").value = String(Number(goal.width) || 640);
  setColor("goalBarColor", goal.color || "c8f57a");
  setColor("goalBarShellColor", goal.shellColor || "18181b");
  setColor("goalBarTrack", goal.track || "0a0a0c");
  setColor("goalBarLabelColor", goal.labelColor || "f4f6f2");
  byId("goalBarFont").value = goal.font || "sans";
  byId("goalBarWeight").value = String(goal.weight || 700);
  byId("goalBarScale").value = Number(goal.scale) || 1;
  byId("goalBarScaleOutput").value = Number(goal.scale || 1).toFixed(2);
  byId("goalBarGlow").value = Number(goal.glow) || 0;
  byId("goalBarGlowOutput").value = Number(goal.glow || 0).toFixed(2);
  byId("goalBarTiltX").value = Number(goal.tiltX) || 0;
  byId("goalBarTiltXOutput").value = String(Number(goal.tiltX) || 0);
  byId("goalBarTiltY").value = Number(goal.tiltY) || 0;
  byId("goalBarTiltYOutput").value = String(Number(goal.tiltY) || 0);
  syncGoalBarFormat();
  syncGoalBarLayout();
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
  hydrateDanceProfiles(config);

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
  syncActiveDanceProfile();
  const profile = activeDanceProfile();
  const dancePool = Array.isArray(profile?.pool) ? profile.pool : [];
  const primaryDance =
    profile?.gif
    || dancePool[0]
    || app.state?.defaults?.dance?.gif
    || "assets/dancing-dog.gif";
  return {
    dance: {
      name: byId("danceName").value,
      activeProfileId: profile?.id || "default",
      profiles: structuredClone(app.danceProfiles),
      mode: profile?.mode || "single",
      gif: primaryDance,
      pool: dancePool.length ? dancePool : [primaryDance],
      rest: profile?.rest || byId("danceRest").value,
      position:
        profile?.position
        || app.state?.config?.dance?.position
        || app.state?.defaults?.dance?.position
        || "bottom-left",
      scale: Number(profile?.scale ?? byId("danceScale").value),
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
      sensitivity: Number(profile?.sensitivity ?? byId("sensitivity").value),
    },
    nowPlaying: {
      fallbackBpm: Number(profile?.fallbackBpm ?? byId("fallbackBpm").value),
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
  renderGoal(
    selected?.type === "goal"
      ? state.goals?.[selected.id]
      : state.goal,
  );
  renderGoalBar(
    selected?.type === "goal-bar"
      ? state.goals?.[selected.id]
      : state.goalBarDefaults,
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

async function saveOverlaySettings(options = {}) {
  if (app.busy) return false;
  const instance = activeInstance();
  if (!instance) {
    showToast("Choose an overlay instance first");
    return false;
  }
  app.busy = true;
  renderDanceProfileControls();
  try {
    const result = await callApi(
      "save_overlay_settings",
      gatherConfig(),
      instance.id,
    );
    if (!result.ok) {
      showToast(result.detail || "Settings could not be saved");
      return false;
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
    logActivity(
      options.activityMessage
      || (result.applied ? "Settings saved and applied" : "Settings saved"),
    );
    showToast(
      options.successMessage
      || (result.applied ? "Saved and applied" : "Saved"),
    );
    return true;
  } catch (error) {
    showToast(String(error.message || error));
    return false;
  } finally {
    app.busy = false;
    renderDanceProfileControls();
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

function gatherGoalSettings() {
  return {
    label: byId("goalLabel").value,
    current: Number(byId("goalCurrent").value),
    target: Number(byId("goalTarget").value),
    format: byId("goalFormat").value,
    symbol: byId("goalSymbol").value,
    color: byId("goalColor").value.slice(1),
    track: byId("goalTrack").value.slice(1),
    labelColor: byId("goalLabelColor").value.slice(1),
    font: byId("goalFont").value,
    weight: Number(byId("goalWeight").value),
    particles: byId("goalParticles").checked,
    percent: byId("goalPercent").checked,
    scale: Number(byId("goalScale").value),
    glow: Number(byId("goalGlow").value),
  };
}

function gatherGoalBarSettings() {
  return {
    label: byId("goalBarLabel").value,
    current: Number(byId("goalBarCurrent").value),
    target: Number(byId("goalBarTarget").value),
    format: byId("goalBarFormat").value,
    symbol: byId("goalBarSymbol").value,
    layout: byId("goalBarLayout").value,
    size: byId("goalBarSize").value,
    shell: byId("goalBarShell").value,
    icon: byId("goalBarIcon").value,
    corners: byId("goalBarCorners").value,
    width: Number(byId("goalBarWidth").value),
    color: byId("goalBarColor").value.slice(1),
    shellColor: byId("goalBarShellColor").value.slice(1),
    track: byId("goalBarTrack").value.slice(1),
    labelColor: byId("goalBarLabelColor").value.slice(1),
    font: byId("goalBarFont").value,
    weight: Number(byId("goalBarWeight").value),
    scale: Number(byId("goalBarScale").value),
    glow: Number(byId("goalBarGlow").value),
    tiltX: Number(byId("goalBarTiltX").value),
    tiltY: Number(byId("goalBarTiltY").value),
  };
}

async function sendGoal(payload, message = "Goal updated") {
  const instance = activeInstance();
  if (!instance || !isGoalOverlayType(instance.type) || app.busy) return;
  app.busy = true;
  try {
    const result = await callApi("update_goal", payload, instance.id);
    if (!result.ok) {
      showToast(result.detail || "Goal update failed");
      return;
    }
    app.state.goals = app.state.goals || {};
    app.state.goals[instance.id] = result.goal;
    if (instance.type === "goal-bar") {
      app.goalBarKey = "";
      renderGoalBar(result.goal);
    } else {
      app.goalKey = "";
      renderGoal(result.goal);
    }
    logActivity(
      `${message}: ${result.goal.current} of ${result.goal.target}`,
    );
    showToast(message);
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.busy = false;
  }
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
  } else if (instance.type === "goal") {
    app.goalKey = "";
    renderGoal(app.state?.goals?.[instance.id] || app.state?.goal, true);
  } else if (instance.type === "goal-bar") {
    app.goalBarKey = "";
    renderGoalBar(
      app.state?.goals?.[instance.id] || app.state?.goalBarDefaults,
      true,
    );
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
  byId("danceProfileSelect").addEventListener("change", (event) => {
    switchDanceProfile(event.target.value);
  });
  byId("addDanceProfileButton").addEventListener("click", () => {
    openDanceProfileDialog("create");
  });
  byId("renameDanceProfileButton").addEventListener("click", () => {
    openDanceProfileDialog("rename");
  });
  byId("deleteDanceProfileButton").addEventListener(
    "click",
    requestDeleteDanceProfile,
  );

  byId("sensitivity").addEventListener("input", () => {
    byId("sensitivityOutput").value = Number(byId("sensitivity").value).toFixed(2);
  });
  byId("flowGlow").addEventListener("input", () => {
    byId("flowGlowOutput").value = Number(byId("flowGlow").value).toFixed(2);
  });
  byId("goalScale").addEventListener("input", () => {
    byId("goalScaleOutput").value = Number(byId("goalScale").value).toFixed(2);
  });
  byId("goalGlow").addEventListener("input", () => {
    byId("goalGlowOutput").value = Number(byId("goalGlow").value).toFixed(2);
  });
  byId("goalBarWidth").addEventListener("input", () => {
    byId("goalBarWidthOutput").value = byId("goalBarWidth").value;
  });
  byId("goalBarScale").addEventListener("input", () => {
    byId("goalBarScaleOutput").value = Number(byId("goalBarScale").value).toFixed(2);
  });
  byId("goalBarGlow").addEventListener("input", () => {
    byId("goalBarGlowOutput").value = Number(byId("goalBarGlow").value).toFixed(2);
  });
  byId("goalBarTiltX").addEventListener("input", () => {
    byId("goalBarTiltXOutput").value = byId("goalBarTiltX").value;
  });
  byId("goalBarTiltY").addEventListener("input", () => {
    byId("goalBarTiltYOutput").value = byId("goalBarTiltY").value;
  });
  byId("goalFormat").addEventListener("change", syncGoalFormat);
  byId("goalBarFormat").addEventListener("change", syncGoalBarFormat);
  byId("goalBarLayout").addEventListener("change", syncGoalBarLayout);
  [
    "colorA",
    "colorB",
    "colorC",
    "counterAccent",
    "goalColor",
    "goalTrack",
    "goalLabelColor",
    "goalBarColor",
    "goalBarShellColor",
    "goalBarTrack",
    "goalBarLabelColor",
  ].forEach((id) => {
    byId(id).addEventListener("input", () => updateColorLabel(id));
  });

  byId("saveDanceButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveSpotifyButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveFlowButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveGoalSettingsButton").addEventListener("click", () => {
    sendGoal(gatherGoalSettings(), "Goal saved and applied");
  });
  byId("saveGoalBarSettingsButton").addEventListener("click", () => {
    sendGoal(gatherGoalBarSettings(), "Goal Bar saved and applied");
  });
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
  byId("resetGoalFieldsButton").addEventListener("click", () => {
    const instance = activeInstance();
    const current =
      app.state?.goals?.[instance?.id]
      || app.state?.goal
      || app.state?.goalDefaults;
    renderGoal(app.state?.goalDefaults, true);
    app.goalKey = JSON.stringify(current || {});
    logActivity("Goal fields reset; save to apply");
  });
  byId("resetGoalBarFieldsButton").addEventListener("click", () => {
    const instance = activeInstance();
    const current =
      app.state?.goals?.[instance?.id]
      || app.state?.goalBarDefaults;
    renderGoalBar(app.state?.goalBarDefaults, true);
    app.goalBarKey = JSON.stringify(current || {});
    logActivity("Goal Bar fields reset; save to apply");
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
  document.querySelectorAll("[data-goal-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.goalAction;
      const payload = { action };
      if (action === "add" || action === "subtract") {
        payload.amount = Number(byId("goalStep").value);
      }
      const labels = {
        add: "Progress added",
        subtract: "Progress subtracted",
        complete: "Goal completed",
        reset: "Goal reset",
      };
      sendGoal(payload, labels[action] || "Goal updated");
    });
  });
  document.querySelectorAll("[data-goal-bar-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.goalBarAction;
      const payload = { action };
      if (action === "add" || action === "subtract") {
        payload.amount = Number(byId("goalBarStep").value);
      }
      const labels = {
        add: "Progress added",
        subtract: "Progress subtracted",
        complete: "Goal completed",
        reset: "Goal reset",
      };
      sendGoal(payload, labels[action] || "Goal updated");
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

  const danceProfileDialog = byId("danceProfileDialog");
  byId("cancelDanceProfile").addEventListener("click", () => {
    danceProfileDialog.close();
  });
  byId("confirmDanceProfile").addEventListener("click", saveDanceProfileDialog);
  byId("danceProfileNameInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveDanceProfileDialog();
  });
  danceProfileDialog.addEventListener("close", () => {
    app.danceProfileDialogMode = null;
  });

  const deleteDanceProfileDialog = byId("deleteDanceProfileDialog");
  byId("cancelDeleteDanceProfile").addEventListener("click", () => {
    deleteDanceProfileDialog.close();
  });
  byId("confirmDeleteDanceProfile").addEventListener(
    "click",
    deleteDanceProfile,
  );

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
    document.querySelectorAll(".live-preview").forEach(fitCardPreviewHost);
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
