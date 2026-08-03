const MAX_DANCE_PROFILES = 5;
const PREVIEW_ZOOM_MIN = 0.25;
const PREVIEW_ZOOM_MAX = 3;
const PREVIEW_ZOOM_STEP = 0.1;
const PREVIEW_MIN_VISIBLE = 48;

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
  goalPillKey: "",
  rivalsSettingsKey: "",
  customizerPreviewTimer: null,
  customizerPreviewReady: false,
  customizerPreviewExpanded: false,
  customizerPreviewZoom: 1,
  customizerPreviewPan: { x: 0, y: 0 },
  customizerPreviewDrag: null,
  customizerPreviewSource: "",
  customizerPreviewPoppedOut: false,
  customizerPreviewWindowSource: "",
  customizerPreviewWindowSyncPending: false,
  customizerPreviewWindowDraft: null,
  customizerResizeObserver: null,
  customizerBaseline: null,
  customizerDirty: false,
  confirmUnsavedChanges: true,
  pendingUnsavedAction: null,
  pendingUnsavedSource: null,
  unsavedDecisionBusy: false,
  pendingDeleteAsset: null,
  pendingRemoveInstanceId: null,
  pendingRenameInstanceId: null,
  overlayDragInstanceId: null,
  overlayDropTargetId: null,
  overlayDropAfter: false,
  overlayOrderSaving: false,
  socialGroupedBase: null,
};

const byId = (id) => document.getElementById(id);
const isGoalOverlayType = (type) => (
  type === "goal"
  || type === "goal-bar"
  || type === "goal-pill"
);
const GOAL_PILL_PRESETS = new Set([
  "f0b04a",
  "4ecdc4",
  "f07c6a",
  "a08ef0",
  "a8d66e",
  "82b7e8",
]);
const RIVALS_TIER_NAMES = Object.freeze({
  bronze: "Bronze",
  silver: "Silver",
  gold: "Gold",
  platinum: "Platinum",
  diamond: "Diamond",
  grandmaster: "Grandmaster",
  celestial: "Celestial",
  eternity: "Eternity",
  "one-above-all": "One Above All",
});
const CURRENCY_OPTIONS = [
  ["US Dollar ($)", "$"],
  ["Australian Dollar (A$)", "A$"],
  ["Bitcoin (BTC)", "\u20bf"],
  ["Brazilian Real (R$)", "R$"],
  ["Canadian Dollar (C$)", "C$"],
  ["Chinese Yuan (CN\u00a5)", "CN\u00a5"],
  ["Danish Krone (kr)", "kr"],
  ["Euro (EUR)", "\u20ac"],
  ["Indian Rupee (INR)", "\u20b9"],
  ["Japanese Yen (JPY)", "\u00a5"],
  ["Mexican Peso (MX$)", "MX$"],
  ["New Zealand Dollar (NZ$)", "NZ$"],
  ["Norwegian Krone (NOK)", "NOK"],
  ["Pound Sterling (GBP)", "\u00a3"],
  ["South African Rand (R)", "R"],
  ["South Korean Won (KRW)", "\u20a9"],
  ["Swedish Krona (SEK)", "SEK"],
  ["Swiss Franc (CHF)", "CHF"],
];
const SOCIAL_PLATFORMS = [
  { id: "twitch", name: "Twitch", mark: "T", color: "#9146FF" },
  { id: "youtube", name: "YouTube", mark: "YT", color: "#FF0000" },
  { id: "instagram", name: "Instagram", mark: "IG", color: "#E1306C" },
  { id: "x", name: "X", mark: "X", color: "#101014" },
  { id: "twitter", name: "Twitter", mark: "TW", color: "#1D9BF0" },
  {
    id: "tiktok",
    name: "TikTok",
    mark: "TT",
    color: "#25F4EE",
    surface: "#F6F7FB",
    ink: "#101014",
    shadow: "-1px -1px #25F4EE, 1px 1px #FE2C55",
  },
  { id: "discord", name: "Discord", mark: "D", color: "#5865F2" },
  { id: "kick", name: "Kick", mark: "K", color: "#53FC18", ink: "#101014" },
  { id: "facebook", name: "Facebook", mark: "F", color: "#1877F2" },
  { id: "snapchat", name: "Snapchat", mark: "S", color: "#FFFC00", ink: "#101014" },
  { id: "telegram", name: "Telegram", mark: "TG", color: "#2AABEE" },
  { id: "whatsapp", name: "WhatsApp", mark: "WA", color: "#25D366" },
  { id: "linkedin", name: "LinkedIn", mark: "IN", color: "#0A66C2" },
  { id: "threads", name: "Threads", mark: "@", color: "#101014" },
  { id: "bluesky", name: "Bluesky", mark: "BS", color: "#0085FF" },
  { id: "reddit", name: "Reddit", mark: "R", color: "#FF4500" },
];
const SOCIAL_GROUPED_LIMITS = Object.freeze({ groups: 6, platforms: 6 });
const SOCIAL_GROUPED_PRESETS = Object.freeze({
  sticker: Object.freeze({
    logoOutline: 2,
    edgeWidth: 1,
    textOutline: 2,
    textEdgeWidth: 1,
    merge: 3,
    textGap: -3,
    groupGap: -2,
    weight: 800,
    shadow: true,
  }),
  clean: Object.freeze({
    logoOutline: 1.25,
    edgeWidth: 0.5,
    textOutline: 1.25,
    textEdgeWidth: 0.5,
    merge: 1,
    textGap: 1,
    groupGap: 0,
    weight: 800,
    shadow: false,
  }),
  bold: Object.freeze({
    logoOutline: 3.5,
    edgeWidth: 1.5,
    textOutline: 3.5,
    textEdgeWidth: 1.5,
    merge: 4,
    textGap: -4,
    groupGap: -3,
    weight: 900,
    shadow: true,
  }),
});
const CUSTOMIZER_VIEW_IDS = new Set([
  "danceView",
  "spotifyView",
  "flowView",
  "goalView",
  "goalBarView",
  "goalPillView",
  "socialView",
  "socialGroupedView",
  "counterView",
  "rivalsRankView",
]);
const CUSTOMIZER_SPLIT_MEDIA = window.matchMedia("(min-width: 961px)");

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

function activeViewId() {
  return document.querySelector(".view.active")?.id || "libraryView";
}

function customizerDraftKey(instance = activeInstance()) {
  const draft = customizerDraft(instance);
  return draft ? JSON.stringify(draft) : null;
}

function renderCustomizerDirtyState() {
  const activeView = document.querySelector(".detail-view.active");
  const customizerActive =
    activeView && CUSTOMIZER_VIEW_IDS.has(activeView.id);
  const badge = byId("customizerDirtyBadge");
  if (customizerActive && app.customizerDirty) {
    const heading = activeView.querySelector(".detail-heading");
    const title = heading?.querySelector(".detail-title")
      || heading?.querySelector("h1");
    if (title) title.insertAdjacentElement("afterend", badge);
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }

  const dock = byId("customizerPreviewDock");
  dock.classList.toggle("has-unsaved", app.customizerDirty);
  byId("customizerPreviewStatus").textContent = app.state?.running
    ? (app.customizerDirty ? "UNSAVED" : "SAVED")
    : "OFFLINE";
  byId("customizerPreviewSaveButton").disabled =
    !customizerActive || !app.customizerDirty || app.busy;
}

function setCustomizerDirty(dirty) {
  const next = Boolean(dirty);
  if (app.customizerDirty === next) {
    renderCustomizerDirtyState();
    return;
  }
  app.customizerDirty = next;
  renderCustomizerDirtyState();
  callApi("set_unsaved_changes", next).catch(() => {});
}

function rememberSavedCustomizer() {
  app.customizerBaseline = customizerDraftKey();
  setCustomizerDirty(false);
}

function refreshCustomizerDirty() {
  if (
    app.customizerBaseline === null
    || !CUSTOMIZER_VIEW_IDS.has(activeViewId())
  ) return;
  setCustomizerDirty(customizerDraftKey() !== app.customizerBaseline);
}

function scheduleCustomizerChange(delay = 70) {
  scheduleCustomizerDraft(delay);
  queueMicrotask(refreshCustomizerDirty);
}

async function setConfirmUnsavedChanges(enabled) {
  const selected = Boolean(enabled);
  app.confirmUnsavedChanges = selected;
  if (app.state) app.state.confirmUnsavedChanges = selected;
  byId("confirmUnsavedChangesSetting").checked = selected;
  try {
    const result = await callApi("set_confirm_unsaved_changes", selected);
    if (!result.ok) throw new Error("Preference could not be saved");
    return true;
  } catch (error) {
    app.confirmUnsavedChanges = !selected;
    if (app.state) app.state.confirmUnsavedChanges = !selected;
    byId("confirmUnsavedChangesSetting").checked = !selected;
    showToast(String(error.message || error));
    return false;
  }
}

function finishUnsavedAction(action) {
  app.pendingUnsavedAction = null;
  app.pendingUnsavedSource = null;
  action?.();
}

function requestUnsavedAction(action, source = "navigation") {
  if (!app.customizerDirty || !app.confirmUnsavedChanges) {
    setCustomizerDirty(false);
    app.customizerBaseline = null;
    action();
    return;
  }
  app.pendingUnsavedAction = action;
  app.pendingUnsavedSource = source;
  byId("dontWarnUnsavedChanges").checked = false;
  const dialog = byId("unsavedChangesDialog");
  if (!dialog.open) dialog.showModal();
}

function navigateToView(viewId) {
  const currentView = activeViewId();
  if (viewId === currentView) return;
  const leavingCustomizer =
    CUSTOMIZER_VIEW_IDS.has(currentView)
    && !CUSTOMIZER_VIEW_IDS.has(viewId);
  if (leavingCustomizer) {
    requestUnsavedAction(() => showView(viewId));
  } else {
    showView(viewId);
  }
}

async function saveActiveCustomizer() {
  const instance = activeInstance();
  if (!instance) return false;
  if (
    instance.type === "larpdog-dance"
    || instance.type === "spotify"
    || instance.type === "now-playing-flow"
    || instance.type === "social"
    || instance.type === "social-rotator"
    || instance.type === "social-grouped"
  ) {
    return saveOverlaySettings();
  }
  if (instance.type === "goal") {
    return sendGoal(gatherGoalSettings(), "Goal saved and applied");
  }
  if (instance.type === "goal-bar") {
    return sendGoal(gatherGoalBarSettings(), "Goal Bar saved and applied");
  }
  if (instance.type === "goal-pill") {
    return sendGoal(gatherGoalPillSettings(), "Goal Pill saved and applied");
  }
  if (instance.type === "rivals-rank") {
    return sendRivals(
      gatherRivalsSettings(),
      "Rivals Rank saved and applied",
      { hydrate: true, remember: true },
    );
  }
  if (instance.type === "win-loss") {
    return sendCounter({
      title: byId("counterTitle").value,
      accent: byId("counterAccent").value.slice(1),
    });
  }
  return false;
}

async function saveCustomizerFromPreview(instanceId = null) {
  const instance = activeInstance();
  if (!instance || (instanceId && instance.id !== instanceId)) {
    showToast("Open this overlay in Studio before saving");
    return false;
  }
  if (!app.customizerDirty) {
    showToast("Preview is already saved");
    return true;
  }
  const button = byId("customizerPreviewSaveButton");
  button.disabled = true;
  try {
    return await saveActiveCustomizer();
  } finally {
    renderCustomizerDirtyState();
  }
}

async function applyDontWarnPreference() {
  if (!byId("dontWarnUnsavedChanges").checked) return true;
  return setConfirmUnsavedChanges(false);
}

async function resolveUnsavedChanges(choice) {
  if (app.unsavedDecisionBusy) return;
  const dialog = byId("unsavedChangesDialog");
  const action = app.pendingUnsavedAction;
  const source = app.pendingUnsavedSource;
  app.unsavedDecisionBusy = true;
  dialog.querySelectorAll("button").forEach((button) => {
    button.disabled = true;
  });
  try {
    if (choice === "save" && !(await saveActiveCustomizer())) return;
    if (choice === "discard") {
      setCustomizerDirty(false);
      app.customizerBaseline = null;
    }
    await applyDontWarnPreference();
    dialog.close();
    if (choice === "keep") {
      finishUnsavedAction(null);
      if (source === "close") {
        callApi("cancel_close_request").catch(() => {});
      }
      return;
    }
    finishUnsavedAction(action);
  } finally {
    app.unsavedDecisionBusy = false;
    dialog.querySelectorAll("button").forEach((button) => {
      button.disabled = false;
    });
  }
}

function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
    view.classList.toggle(
      "has-customizer-preview",
      view.id === viewId && CUSTOMIZER_VIEW_IDS.has(viewId),
    );
  });
  if (CUSTOMIZER_VIEW_IDS.has(viewId)) {
    requestAnimationFrame(() => {
      renderCustomizerPreview();
      setCustomizerPreviewExpanded(true);
    });
  } else {
    hideCustomizerPreview();
  }
  renderCustomizerDirtyState();
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

function rangeDecimalPlaces(value) {
  const fraction = String(value ?? "").split(".")[1] || "";
  return Math.min(6, fraction.length);
}

function rangePrecision(slider) {
  return Math.max(
    rangeDecimalPlaces(slider.step),
    rangeDecimalPlaces(slider.min),
  );
}

function formatRangeValue(slider, value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return numeric.toFixed(rangePrecision(slider));
}

function normalizeRangeValue(slider, value) {
  const minimum = Number(slider.min);
  const maximum = Number(slider.max);
  const numeric = Number(value);
  const fallback = Number(slider.value) || (Number.isFinite(minimum) ? minimum : 0);
  if (!Number.isFinite(numeric)) return fallback;
  let normalized = numeric;
  if (Number.isFinite(minimum)) normalized = Math.max(minimum, normalized);
  if (Number.isFinite(maximum)) normalized = Math.min(maximum, normalized);
  const step = Number(slider.step);
  if (Number.isFinite(step) && step > 0) {
    const base = Number.isFinite(minimum) ? minimum : 0;
    normalized = base + Math.round((normalized - base) / step) * step;
  }
  if (Number.isFinite(minimum)) normalized = Math.max(minimum, normalized);
  if (Number.isFinite(maximum)) normalized = Math.min(maximum, normalized);
  return Number(normalized.toFixed(rangePrecision(slider)));
}

function rangeEditorValueIsValid(editor, slider) {
  if (!editor.value.trim()) return false;
  const numeric = Number(editor.value);
  if (!Number.isFinite(numeric)) return false;
  const minimum = Number(slider.min);
  const maximum = Number(slider.max);
  if (Number.isFinite(minimum) && numeric < minimum) return false;
  if (Number.isFinite(maximum) && numeric > maximum) return false;
  const step = Number(slider.step);
  if (!Number.isFinite(step) || step <= 0) return true;
  const base = Number.isFinite(minimum) ? minimum : 0;
  const steps = (numeric - base) / step;
  return Math.abs(steps - Math.round(steps)) < 1e-7;
}

function initializeRangeControls() {
  const labels = [...document.querySelectorAll("label[for]")];
  document.querySelectorAll(".range-control").forEach((control) => {
    const slider = control.querySelector('input[type="range"]');
    const output = control.querySelector("output");
    if (!slider || !output || control.dataset.rangeEnhanced === "true") return;
    control.dataset.rangeEnhanced = "true";

    const track = document.createElement("div");
    track.className = "range-track";
    slider.replaceWith(track);
    track.append(slider);

    const limits = document.createElement("div");
    limits.className = "range-limits";
    limits.id = `${slider.id}Limits`;
    const minimum = document.createElement("span");
    minimum.textContent = `Min ${Number(slider.min)}`;
    const maximum = document.createElement("span");
    maximum.textContent = `Max ${Number(slider.max)}`;
    limits.append(minimum, maximum);
    track.append(limits);
    slider.setAttribute("aria-describedby", limits.id);

    const label = labels.find((candidate) => candidate.htmlFor === slider.id);
    const editor = document.createElement("input");
    editor.type = "number";
    editor.className = "range-value-input";
    editor.id = output.id;
    editor.min = slider.min;
    editor.max = slider.max;
    editor.step = slider.step;
    editor.inputMode = "decimal";
    editor.value = output.value || formatRangeValue(slider, slider.value);
    editor.dataset.customizerPassive = "";
    editor.setAttribute(
      "aria-label",
      `${label?.textContent.trim() || "Slider"} value`,
    );
    editor.title = `Enter a value from ${slider.min} to ${slider.max}`;
    output.replaceWith(editor);

    const syncEditor = () => {
      editor.value = formatRangeValue(slider, slider.value);
      editor.removeAttribute("aria-invalid");
    };
    const commitEditor = () => {
      slider.value = String(normalizeRangeValue(slider, editor.value));
      syncEditor();
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    };

    slider.addEventListener("input", syncEditor);
    editor.addEventListener("focus", () => editor.select());
    editor.addEventListener("input", () => {
      const valid = rangeEditorValueIsValid(editor, slider);
      if (valid) editor.removeAttribute("aria-invalid");
      else editor.setAttribute("aria-invalid", "true");
      if (!valid) return;
      slider.value = editor.value;
      scheduleCustomizerChange(0);
    });
    editor.addEventListener("change", commitEditor);
    editor.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commitEditor();
        editor.blur();
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        syncEditor();
        editor.blur();
      }
    });
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

function customizerPreviewUrl(instance) {
  const source = studioPreviewUrl(instance);
  if (!source) return "";
  const url = new URL(source);
  url.searchParams.set("customizer", "1");
  return url.toString();
}

function catalogPreviewUrl(manifest) {
  if (!manifest || !app.state?.baseUrl) return "";
  const url = new URL(manifest.route.replace(/^\//, ""), app.state.baseUrl);
  url.searchParams.set("preview", "studio");
  url.searchParams.set("catalog", "1");
  if (isGoalOverlayType(manifest.type)) {
    url.searchParams.set("current", "64");
    url.searchParams.set("target", "100");
    url.searchParams.set("demo", "off");
  }
  return url.toString();
}

function materializeInstanceConfig(instance) {
  const root = app.state?.config || {};
  const materialized = {};
  [
    "dance",
    "spotify",
    "flow",
    "audio",
    "nowPlaying",
    "social",
    "socialGrouped",
  ].forEach((key) => {
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

function customizerPreviewGeometry() {
  const frame = byId("customizerPreviewFrame");
  const stage = byId("customizerPreviewStage");
  const manifest = manifestFor(activeInstance()?.type);
  if (
    !frame
    || !stage
    || !manifest
    || stage.clientWidth <= 0
    || stage.clientHeight <= 0
  ) return null;
  const width = Number(manifest.canvas?.w) || 1;
  const height = Number(manifest.canvas?.h) || 1;
  const baseScale = Math.min(
    stage.clientWidth / width,
    stage.clientHeight / height,
  ) * 0.88;
  return { frame, stage, width, height, baseScale };
}

function clampCustomizerPreviewPan(geometry) {
  if (!geometry) return;
  const scale = geometry.baseScale * app.customizerPreviewZoom;
  const maxX = Math.max(
    0,
    (geometry.stage.clientWidth + geometry.width * scale) / 2
      - PREVIEW_MIN_VISIBLE,
  );
  const maxY = Math.max(
    0,
    (geometry.stage.clientHeight + geometry.height * scale) / 2
      - PREVIEW_MIN_VISIBLE,
  );
  app.customizerPreviewPan.x = Math.max(
    -maxX,
    Math.min(maxX, app.customizerPreviewPan.x),
  );
  app.customizerPreviewPan.y = Math.max(
    -maxY,
    Math.min(maxY, app.customizerPreviewPan.y),
  );
}

function fitCustomizerPreview() {
  const geometry = customizerPreviewGeometry();
  if (!geometry) return false;
  clampCustomizerPreviewPan(geometry);
  const scale = geometry.baseScale * app.customizerPreviewZoom;
  geometry.frame.style.width = `${geometry.width}px`;
  geometry.frame.style.height = `${geometry.height}px`;
  geometry.frame.style.left = `${geometry.stage.clientWidth / 2 + app.customizerPreviewPan.x}px`;
  geometry.frame.style.top = `${geometry.stage.clientHeight / 2 + app.customizerPreviewPan.y}px`;
  geometry.frame.style.transform = `translate(-50%, -50%) scale(${scale})`;
  byId("customizerPreviewZoomResetButton").textContent =
    `${Math.round(app.customizerPreviewZoom * 100)}%`;
  return true;
}

function setCustomizerPreviewZoom(value, clientX = null, clientY = null) {
  const geometry = customizerPreviewGeometry();
  if (!geometry) return;
  const previous = app.customizerPreviewZoom;
  const next = Math.max(
    PREVIEW_ZOOM_MIN,
    Math.min(PREVIEW_ZOOM_MAX, Math.round(Number(value) * 10) / 10),
  );
  if (!Number.isFinite(next) || next === previous) return;
  const rect = geometry.stage.getBoundingClientRect();
  const originX = Number.isFinite(clientX)
    ? clientX - rect.left - rect.width / 2
    : 0;
  const originY = Number.isFinite(clientY)
    ? clientY - rect.top - rect.height / 2
    : 0;
  const ratio = next / previous;
  app.customizerPreviewPan.x =
    originX - (originX - app.customizerPreviewPan.x) * ratio;
  app.customizerPreviewPan.y =
    originY - (originY - app.customizerPreviewPan.y) * ratio;
  app.customizerPreviewZoom = next;
  fitCustomizerPreview();
}

function resetCustomizerPreviewViewport() {
  app.customizerPreviewZoom = 1;
  app.customizerPreviewPan = { x: 0, y: 0 };
  app.customizerPreviewDrag = null;
  byId("customizerPreviewStage")?.classList.remove("dragging");
  fitCustomizerPreview();
}

function resetCustomizerPreviewZoom() {
  app.customizerPreviewZoom = 1;
  fitCustomizerPreview();
}

function customizerDraft(instance) {
  if (!instance) return null;
  if (
    instance.type === "larpdog-dance"
    || instance.type === "spotify"
    || instance.type === "now-playing-flow"
  ) {
    return { config: gatherConfig() };
  }
  if (instance.type === "social" || instance.type === "social-rotator") {
    return { config: { social: gatherSocialSettings() } };
  }
  if (instance.type === "social-grouped") {
    return { config: { socialGrouped: gatherSocialGroupedSettings() } };
  }
  if (instance.type === "goal") {
    return { state: gatherGoalSettings() };
  }
  if (instance.type === "goal-bar") {
    return { state: gatherGoalBarSettings() };
  }
  if (instance.type === "goal-pill") {
    return { state: gatherGoalPillSettings() };
  }
  if (instance.type === "rivals-rank") {
    return { config: { rivals: gatherRivalsSettings() } };
  }
  if (instance.type === "win-loss") {
    const saved =
      app.state?.counters?.[instance.id]
      || app.state?.counter
      || {};
    return {
      state: {
        wins: Math.max(0, Number(saved.wins) || 0),
        losses: Math.max(0, Number(saved.losses) || 0),
        title: byId("counterTitle").value,
        accent: byId("counterAccent").value.slice(1),
      },
    };
  }
  return null;
}

function postCustomizerDraft() {
  const dock = byId("customizerPreviewDock");
  const frame = byId("customizerPreviewFrame");
  const instance = activeInstance();
  if (dock.hidden || !instance) return;
  const payload = customizerDraft(instance);
  if (!payload) return;
  if (app.customizerPreviewReady && frame.contentWindow) {
    let targetOrigin;
    try {
      targetOrigin = new URL(app.state?.baseUrl || "").origin;
    } catch {
      targetOrigin = null;
    }
    if (targetOrigin) {
      frame.contentWindow.postMessage(
        {
          type: "overlay-studio-draft",
          overlayType: instance.type,
          instanceId: instance.id,
          ...payload,
        },
        targetOrigin,
      );
    }
  }
  syncCustomizerPreviewWindow({
    type: "overlay-studio-draft",
    overlayType: instance.type,
    instanceId: instance.id,
    ...payload,
  });
}

function scheduleCustomizerDraft(delay = 70) {
  if (byId("customizerPreviewDock").hidden) return;
  clearTimeout(app.customizerPreviewTimer);
  app.customizerPreviewTimer = setTimeout(postCustomizerDraft, delay);
}

function setCustomizerPreviewExpanded(expanded) {
  const dock = byId("customizerPreviewDock");
  const button = byId("customizerPreviewExpandButton");
  const next = Boolean(
    expanded && !dock.hidden && CUSTOMIZER_SPLIT_MEDIA.matches,
  );
  app.customizerPreviewExpanded = next;
  document.body.classList.toggle("customizer-preview-expanded", next);
  dock.classList.toggle("expanded", next);
  button.setAttribute("aria-expanded", String(next));
  button.setAttribute(
    "aria-label",
    next ? "Collapse live draft" : "Expand live draft",
  );
  button.title = next ? "Collapse live draft" : "Expand live draft";
  requestAnimationFrame(resetCustomizerPreviewViewport);
}

async function syncCustomizerPreviewWindow(payload) {
  if (
    !app.customizerPreviewPoppedOut
    || app.customizerPreviewWindowSource
      !== customizerPreviewUrl(activeInstance())
  ) return;
  app.customizerPreviewWindowDraft = payload;
  if (app.customizerPreviewWindowSyncPending) return;
  app.customizerPreviewWindowSyncPending = true;
  try {
    while (
      app.customizerPreviewPoppedOut
      && app.customizerPreviewWindowDraft
    ) {
      const next = app.customizerPreviewWindowDraft;
      app.customizerPreviewWindowDraft = null;
      const result = await callApi("update_preview_window", next);
      if (!result?.open) {
        app.customizerPreviewPoppedOut = false;
        app.customizerPreviewWindowSource = "";
        app.customizerPreviewWindowDraft = null;
      }
    }
  } catch {
    app.customizerPreviewPoppedOut = false;
    app.customizerPreviewWindowSource = "";
    app.customizerPreviewWindowDraft = null;
  } finally {
    app.customizerPreviewWindowSyncPending = false;
  }
}

async function openCustomizerPreviewWindow() {
  const instance = activeInstance();
  const manifest = manifestFor(instance?.type);
  const source = instance ? customizerPreviewUrl(instance) : "";
  if (!instance || !manifest || !source || !app.state?.running) {
    showToast("Start the overlay server to open the preview window");
    return;
  }
  const payload = customizerDraft(instance);
  if (!payload) return;
  const draft = {
    type: "overlay-studio-draft",
    overlayType: instance.type,
    instanceId: instance.id,
    ...payload,
  };
  try {
    const result = await callApi(
      "open_preview_window",
      source,
      instance.name,
      manifest.canvas.w,
      manifest.canvas.h,
      draft,
    );
    if (!result?.ok) {
      showToast(result?.detail || "Preview window could not be opened");
      return;
    }
    app.customizerPreviewPoppedOut = true;
    app.customizerPreviewWindowSource = source;
    showToast(result.reused ? "Preview window updated" : "Preview window opened");
  } catch (error) {
    showToast(String(error.message || error));
  }
}

function hideCustomizerPreview() {
  const dock = byId("customizerPreviewDock");
  const frame = byId("customizerPreviewFrame");
  clearTimeout(app.customizerPreviewTimer);
  app.customizerPreviewReady = false;
  setCustomizerPreviewExpanded(false);
  resetCustomizerPreviewViewport();
  app.customizerPreviewSource = "";
  dock.hidden = true;
  updatePreview(frame, "", false);
}

function renderCustomizerPreview(state = app.state) {
  const activeView = document.querySelector(".detail-view.active");
  const instance = activeInstance();
  const manifest = manifestFor(instance?.type);
  if (
    !activeView
    || !CUSTOMIZER_VIEW_IDS.has(activeView.id)
    || !instance
    || !manifest
  ) {
    hideCustomizerPreview();
    return;
  }
  const dock = byId("customizerPreviewDock");
  const frame = byId("customizerPreviewFrame");
  const source = customizerPreviewUrl(instance);
  dock.hidden = false;
  [
    "customizerPreviewZoomOutButton",
    "customizerPreviewZoomResetButton",
    "customizerPreviewZoomInButton",
    "customizerPreviewRecenterButton",
    "customizerPreviewPopoutButton",
  ].forEach((id) => {
    byId(id).disabled = !state?.running;
  });
  byId("customizerPreviewName").textContent = instance.name;
  renderCustomizerDirtyState();
  frame.title = `Live ${instance.name} customization preview`;
  const desired = state?.running ? source : "";
  if (frame.dataset.source !== desired) {
    app.customizerPreviewReady = false;
    if (app.customizerPreviewSource !== desired) {
      app.customizerPreviewSource = desired;
      resetCustomizerPreviewViewport();
    }
  }
  updatePreview(frame, source, Boolean(state?.running));
  requestAnimationFrame(fitCustomizerPreview);
}

function fitCardPreviewHost(host) {
  const frame = host?.querySelector("iframe");
  const instanceId = host?.closest(".overlay-card")?.dataset.instanceId;
  const overlayType = host?.closest(".catalog-item")?.dataset.overlayType;
  const manifest = overlayType
    ? manifestFor(overlayType)
    : manifestFor(instanceById(instanceId)?.type);
  fitCardPreview(frame, manifest);
}

const cardPreviewObserver = new ResizeObserver((entries) => {
  entries.forEach((entry) => fitCardPreviewHost(entry.target));
});

const catalogPreviewObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    const frame = entry.target.querySelector("iframe");
    if (!frame || frame.dataset.loaded === "true") return;
    frame.dataset.loaded = "true";
    updatePreview(frame, frame.dataset.previewUrl || "", app.state?.running);
  });
}, {
  root: byId("catalogGrid"),
  rootMargin: "120px 0px",
});

function clearCatalogPreviews() {
  byId("catalogGrid").querySelectorAll(".catalog-preview").forEach((host) => {
    catalogPreviewObserver.unobserve(host);
    cardPreviewObserver.unobserve(host);
    const frame = host.querySelector("iframe");
    if (frame) {
      frame.dataset.loaded = "false";
      updatePreview(frame, "", false);
    }
  });
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

function createCardDragHandle(instance) {
  const handle = document.createElement("button");
  handle.type = "button";
  handle.className = "card-drag-handle";
  handle.draggable = true;
  handle.dataset.dragInstance = instance.id;
  handle.title = "Drag to reorder";
  handle.setAttribute(
    "aria-label",
    `Move ${instance.name}. Drag or use the arrow keys to reorder.`,
  );
  const grip = document.createElement("span");
  grip.className = "card-drag-grip";
  grip.setAttribute("aria-hidden", "true");
  for (let index = 0; index < 6; index += 1) {
    grip.append(document.createElement("i"));
  }
  handle.append(grip);
  return handle;
}

function createOverlayCard(instance, running, canReorder) {
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
  if (canReorder) card.append(createCardDragHandle(instance));
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
  const installed = instances();
  installed.forEach((instance) => {
    const card = createOverlayCard(instance, state.running, installed.length > 1);
    if (card) grid.append(card);
  });
  grid.append(createAddCard());
  const count = installed.length;
  byId("overlayCount").textContent = `${count} installed`;
}

function overlayOrderIds() {
  return instances().map((instance) => instance.id);
}

function clearOverlayDropTarget() {
  const grid = byId("overlayGrid");
  grid.querySelectorAll(".drop-before, .drop-after").forEach((card) => {
    card.classList.remove("drop-before", "drop-after");
  });
  app.overlayDropTargetId = null;
  app.overlayDropAfter = false;
}

function finishOverlayCardDrag() {
  const grid = byId("overlayGrid");
  grid.classList.remove("is-reordering");
  grid.querySelectorAll(".is-dragging").forEach((card) => {
    card.classList.remove("is-dragging");
  });
  clearOverlayDropTarget();
  app.overlayDragInstanceId = null;
}

function reorderedOverlayIds(draggedId, targetId, dropAfter) {
  const current = overlayOrderIds();
  if (!current.includes(draggedId) || targetId === draggedId) return current;
  const reordered = current.filter((instanceId) => instanceId !== draggedId);
  if (!targetId) {
    reordered.push(draggedId);
    return reordered;
  }
  const targetIndex = reordered.indexOf(targetId);
  if (targetIndex < 0) return current;
  reordered.splice(targetIndex + (dropAfter ? 1 : 0), 0, draggedId);
  return reordered;
}

function focusOverlayDragHandle(instanceId) {
  const handle = [...byId("overlayGrid").querySelectorAll("[data-drag-instance]")]
    .find((candidate) => candidate.dataset.dragInstance === instanceId);
  handle?.focus();
}

async function persistOverlayOrder(orderedIds, focusInstanceId = null) {
  const current = overlayOrderIds();
  if (
    app.overlayOrderSaving
    || orderedIds.length !== current.length
    || orderedIds.every((instanceId, index) => instanceId === current[index])
  ) {
    if (focusInstanceId) focusOverlayDragHandle(focusInstanceId);
    return;
  }
  app.overlayOrderSaving = true;
  try {
    const result = await callApi("reorder_overlay_instances", orderedIds);
    if (!result.ok) {
      showToast(result.detail || "Overlay order could not be saved");
      return;
    }
    app.libraryKey = "";
    renderState(result.state, false);
    logActivity("Overlay order saved");
    showToast("Overlay order saved");
  } catch (error) {
    showToast(String(error.message || error));
  } finally {
    app.overlayOrderSaving = false;
    if (focusInstanceId) {
      requestAnimationFrame(() => focusOverlayDragHandle(focusInstanceId));
    }
  }
}

function beginOverlayCardDrag(event) {
  const handle = event.target.closest("[data-drag-instance]");
  if (!handle || app.overlayOrderSaving) {
    event.preventDefault();
    return;
  }
  const card = handle.closest(".overlay-card");
  app.overlayDragInstanceId = handle.dataset.dragInstance;
  app.overlayDropTargetId = app.overlayDragInstanceId;
  byId("overlayGrid").classList.add("is-reordering");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", app.overlayDragInstanceId);
  if (card) event.dataTransfer.setDragImage(card, card.offsetWidth - 20, 20);
  requestAnimationFrame(() => card?.classList.add("is-dragging"));
}

function updateOverlayDropTarget(event) {
  if (!app.overlayDragInstanceId) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  clearOverlayDropTarget();
  const grid = byId("overlayGrid");
  const target = event.target.closest(".overlay-card");
  if (!target || target.classList.contains("add-card")) {
    const addCard = grid.querySelector(".add-card");
    addCard?.classList.add("drop-before");
    return;
  }
  const targetId = target.dataset.instanceId;
  app.overlayDropTargetId = targetId;
  if (targetId === app.overlayDragInstanceId) return;
  const bounds = target.getBoundingClientRect();
  app.overlayDropAfter = event.clientX >= bounds.left + (bounds.width / 2);
  target.classList.add(app.overlayDropAfter ? "drop-after" : "drop-before");
}

function dropOverlayCard(event) {
  if (!app.overlayDragInstanceId) return;
  event.preventDefault();
  const draggedId = app.overlayDragInstanceId;
  const orderedIds = reorderedOverlayIds(
    draggedId,
    app.overlayDropTargetId,
    app.overlayDropAfter,
  );
  finishOverlayCardDrag();
  persistOverlayOrder(orderedIds, draggedId);
}

function moveOverlayCardWithKeyboard(event) {
  const handle = event.target.closest("[data-drag-instance]");
  if (!handle || app.overlayOrderSaving) return;
  const keys = new Set([
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "ArrowDown",
    "Home",
    "End",
  ]);
  if (!keys.has(event.key)) return;
  event.preventDefault();
  const current = overlayOrderIds();
  const sourceIndex = current.indexOf(handle.dataset.dragInstance);
  if (sourceIndex < 0) return;
  const columns = Math.max(
    1,
    getComputedStyle(byId("overlayGrid"))
      .gridTemplateColumns.trim().split(/\s+/).length,
  );
  const destinations = {
    ArrowLeft: sourceIndex - 1,
    ArrowRight: sourceIndex + 1,
    ArrowUp: sourceIndex - columns,
    ArrowDown: sourceIndex + columns,
    Home: 0,
    End: current.length - 1,
  };
  const destination = Math.max(
    0,
    Math.min(current.length - 1, destinations[event.key]),
  );
  if (destination === sourceIndex) return;
  const reordered = [...current];
  const [moved] = reordered.splice(sourceIndex, 1);
  reordered.splice(destination, 0, moved);
  persistOverlayOrder(reordered, moved);
}

function renderCatalog() {
  const grid = byId("catalogGrid");
  clearCatalogPreviews();
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
    item.dataset.overlayType = manifest.type;
    const preview = document.createElement("div");
    preview.className = "live-preview catalog-preview";
    const frame = document.createElement("iframe");
    frame.title = `${manifest.name} preview`;
    frame.tabIndex = -1;
    frame.loading = "lazy";
    frame.dataset.loaded = "false";
    frame.dataset.previewUrl = catalogPreviewUrl(manifest);
    frame.dataset.source = "";
    frame.src = "about:blank";
    frame.addEventListener("load", () => fitCardPreview(frame, manifest));
    const offline = document.createElement("span");
    offline.className = "preview-offline";
    offline.textContent = "OFFLINE";
    preview.append(frame, offline);
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
    item.append(preview, identity, add, description);
    grid.append(item);
    cardPreviewObserver.observe(preview);
    catalogPreviewObserver.observe(preview);
    requestAnimationFrame(() => fitCardPreview(frame, manifest));
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
  } else if (instance.type === "goal-pill") {
    byId("goalPillDetailName").textContent = instance.name;
    byId("goalPillSourceLabel").textContent = instance.name;
    byId("goalPillUrl").value = source;
  } else if (
    instance.type === "social"
    || instance.type === "social-rotator"
  ) {
    byId("socialTypeLabel").textContent =
      instance.type === "social" ? "SOCIAL BAR" : "SOCIAL ROTATOR";
    byId("socialDetailName").textContent = instance.name;
    byId("socialSourceLabel").textContent = instance.name;
    byId("socialUrl").value = source;
  } else if (instance.type === "social-grouped") {
    byId("socialGroupedDetailName").textContent = instance.name;
    byId("socialGroupedSourceLabel").textContent = instance.name;
    byId("socialGroupedUrl").value = source;
  } else if (instance.type === "rivals-rank") {
    byId("rivalsRankDetailName").textContent = instance.name;
    byId("rivalsRankSourceLabel").textContent = instance.name;
    byId("rivalsRankUrl").value = source;
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
    rememberSavedCustomizer();
    scheduleCustomizerDraft();
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
  renderCustomizerPreview(state);
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

function initializeCurrencySelects() {
  document.querySelectorAll("[data-currency-select]").forEach((select) => {
    select.replaceChildren();
    CURRENCY_OPTIONS.forEach(([label, symbol]) => {
      const option = document.createElement("option");
      option.value = symbol;
      option.textContent = label;
      select.append(option);
    });
  });
}

function setCurrencySymbol(id, symbol) {
  const select = byId(id);
  const selected = String(symbol || "$").slice(0, 4) || "$";
  select.querySelector("[data-saved-currency]")?.remove();
  if (![...select.options].some((option) => option.value === selected)) {
    const option = document.createElement("option");
    option.value = selected;
    option.textContent = `Saved currency (${selected})`;
    option.dataset.savedCurrency = "true";
    select.append(option);
  }
  select.value = selected;
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
  setCurrencySymbol("goalSymbol", goal.symbol);
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
  const vertical = byId("goalBarLayout").value === "vertical";
  byId("goalBarWidth").disabled = vertical;
  byId("goalBarIcon").disabled = !vertical;
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
  setCurrencySymbol("goalBarSymbol", goal.symbol);
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

function syncGoalPillFormat() {
  byId("goalPillSymbol").disabled =
    byId("goalPillFormat").value !== "currency";
}

function renderGoalPill(goal, force = false) {
  if (!goal) return;
  const key = JSON.stringify(goal);
  if (!force && key === app.goalPillKey) return;
  app.goalPillKey = key;
  byId("goalPillLabel").value = goal.label || "Tip goal";
  byId("goalPillCurrent").value = Number(goal.current) || 0;
  byId("goalPillTarget").value = Math.max(0.01, Number(goal.target) || 100);
  byId("goalPillFormat").value =
    goal.format === "number" ? "number" : "currency";
  setCurrencySymbol("goalPillSymbol", goal.symbol);
  byId("goalPillSize").value = goal.size || "full";
  byId("goalPillIcon").value = goal.icon || "tips";
  byId("goalPillCorners").value = goal.corners || "round";
  byId("goalPillWidth").value = Number(goal.width) || 560;
  byId("goalPillWidthOutput").value = String(Number(goal.width) || 560);
  setColor("goalPillColor", goal.color || "f0b04a");
  setColor("goalPillShellColor", goal.shellColor || "1a1f2c");
  setColor("goalPillTrack", goal.track || "0f131c");
  setColor("goalPillLabelColor", goal.labelColor || "f0f4fa");
  const accent = String(goal.color || "f0b04a").toLowerCase();
  byId("goalPillPreset").value =
    GOAL_PILL_PRESETS.has(accent) ? accent : "custom";
  byId("goalPillFont").value = goal.font || "sans";
  byId("goalPillWeight").value = String(goal.weight || 700);
  byId("goalPillScale").value = Number(goal.scale) || 1;
  byId("goalPillScaleOutput").value = Number(goal.scale || 1).toFixed(2);
  byId("goalPillGlow").value = Number(goal.glow) || 0;
  byId("goalPillGlowOutput").value = Number(goal.glow || 0).toFixed(2);
  syncGoalPillFormat();
}

function rivalsVisualState(state) {
  return {
    label: state?.label || "This session",
    showName: state?.showName !== false,
    shellColor: state?.shellColor || "141418",
    textColor: state?.textColor || "ffffff",
    accentColor: state?.accentColor || "f6f7fb",
    winColor: state?.winColor || "5fd97a",
    lossColor: state?.lossColor || "ff5f6d",
    font: state?.font || "display",
    weight: Number(state?.weight) || 800,
    scale: Number(state?.scale) || 1,
    corners: Number.isFinite(Number(state?.corners))
      ? Number(state.corners)
      : 18,
    glow: Number.isFinite(Number(state?.glow)) ? Number(state.glow) : 1,
  };
}

function renderRivals(state, linked = false, force = false, poll = null) {
  const resolved = state || app.state?.rivalsDefaults || {};
  const visual = rivalsVisualState(resolved);
  const settingsKey = JSON.stringify(visual);
  if (force || (!app.customizerDirty && settingsKey !== app.rivalsSettingsKey)) {
    app.rivalsSettingsKey = settingsKey;
    byId("rivalsLabel").value = visual.label;
    byId("rivalsShowName").checked = visual.showName;
    setColor("rivalsShellColor", visual.shellColor);
    setColor("rivalsTextColor", visual.textColor);
    setColor("rivalsAccentColor", visual.accentColor);
    setColor("rivalsWinColor", visual.winColor);
    setColor("rivalsLossColor", visual.lossColor);
    byId("rivalsFont").value = visual.font;
    byId("rivalsWeight").value = String(visual.weight);
    byId("rivalsScale").value = visual.scale;
    byId("rivalsScaleOutput").value = visual.scale.toFixed(2);
    byId("rivalsCorners").value = visual.corners;
    byId("rivalsCornersOutput").value = String(visual.corners);
    byId("rivalsGlow").value = visual.glow;
    byId("rivalsGlowOutput").value = visual.glow.toFixed(2);
  }

  const tier = RIVALS_TIER_NAMES[resolved.tier] || "Bronze";
  const division = ["eternity", "one-above-all"].includes(resolved.tier)
    ? ""
    : ` ${Math.max(1, Math.min(3, Number(resolved.division) || 3))}`;
  const score = Math.max(0, Number(resolved.score) || 0);
  const scoreText = Number.isInteger(score) ? String(score) : score.toFixed(2);
  const linkStatus = byId("rivalsLinkStatus");
  const pollStatus = String(poll?.status || "");
  linkStatus.dataset.syncStatus = linked ? pollStatus : "unlinked";
  linkStatus.title = pollStatus === "error" ? String(poll?.detail || "") : "";
  if (!linked) {
    linkStatus.textContent = "No account linked";
  } else if (pollStatus === "error") {
    linkStatus.textContent = "Linked; update unavailable";
  } else if (pollStatus === "waiting") {
    linkStatus.textContent = "Linked; waiting for update";
  } else {
    linkStatus.textContent =
      `Linked${resolved.playerName ? ` as ${resolved.playerName}` : ""}`;
  }
  byId("rivalsCurrentRank").textContent = `${tier}${division} | ${scoreText} RS`;
  const wins = Math.max(0, Math.round(Number(resolved.sessionWins) || 0));
  const losses = Math.max(0, Math.round(Number(resolved.sessionLosses) || 0));
  byId("rivalsSessionRecord").textContent =
    `${wins} ${wins === 1 ? "win" : "wins"} | `
    + `${losses} ${losses === 1 ? "loss" : "losses"}`;
  byId("resetRivalsSessionButton").disabled = !linked || app.busy;
}

function renderSocialAccounts(accounts, overlayType) {
  const byPlatform = new Map(
    (Array.isArray(accounts) ? accounts : []).map((account) => [
      account.platform,
      account,
    ]),
  );
  const grid = byId("socialPlatformGrid");
  grid.replaceChildren();
  SOCIAL_PLATFORMS.forEach((platform) => {
    const account = byPlatform.get(platform.id) || {
      platform: platform.id,
      enabled: false,
      handle: "yourname",
    };
    if (!account.enabled) return;
    const row = document.createElement("div");
    row.className = "social-platform-row";
    row.dataset.socialPlatform = platform.id;

    const mark = document.createElement("span");
    mark.className = "social-platform-mark";
    mark.textContent = platform.mark;
    mark.style.setProperty(
      "--platform-color",
      platform.surface || platform.color,
    );
    if (platform.ink) mark.style.setProperty("--platform-ink", platform.ink);
    if (platform.shadow) {
      mark.style.setProperty("--platform-shadow", platform.shadow);
    }

    const name = document.createElement("span");
    name.className = "social-platform-name";
    name.textContent = platform.name;

    const handle = document.createElement("input");
    handle.type = "text";
    handle.value = account.handle || "";
    handle.maxLength = 64;
    handle.autocomplete = "off";
    handle.placeholder = "yourname";
    handle.dataset.socialHandle = platform.id;
    handle.setAttribute("aria-label", `${platform.name} handle`);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "social-remove-button";
    remove.dataset.socialRemove = platform.id;
    remove.setAttribute("aria-label", `Remove ${platform.name}`);
    remove.title = `Remove ${platform.name}`;
    remove.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 6h18"></path>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
        <path d="M10 11v6"></path>
        <path d="M14 11v6"></path>
      </svg>
    `;
    row.append(mark, name, handle, remove);
    grid.append(row);
  });
  updateSocialSelectionState(overlayType);
}

function socialRows() {
  return [...byId("socialPlatformGrid").querySelectorAll(
    "[data-social-platform]",
  )];
}

function socialHandleFromInput(value, limit = 64) {
  const original = String(value || "").trim();
  if (!original) return "";
  let candidate = original;
  const looksLikeLink =
    /^[a-z][a-z0-9+.-]*:\/\//i.test(original)
    || /^(?:www\.)?[^/\s]+\.[a-z]{2,}(?:\/|$)/i.test(original);
  if (looksLikeLink) {
    try {
      const url = new URL(
        /^[a-z][a-z0-9+.-]*:\/\//i.test(original)
          ? original
          : `https://${original}`,
      );
      const parts = decodeURIComponent(url.pathname)
        .split("/")
        .map((part) => part.trim())
        .filter(Boolean);
      candidate = parts.at(-1) || "";
    } catch {
      candidate = original;
    }
  }
  return candidate.replace(/^@+/, "").trim().slice(0, limit);
}

function refreshSocialPlatformOptions(overlayType = activeInstance()?.type) {
  const select = byId("socialPlatformSelect");
  const previous = select.value;
  const selected = new Set(
    socialRows().map((row) => row.dataset.socialPlatform),
  );
  const available = SOCIAL_PLATFORMS.filter(
    (platform) => !selected.has(platform.id),
  );
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a platform";
  select.append(placeholder);
  available.forEach((platform) => {
    const option = document.createElement("option");
    option.value = platform.id;
    option.textContent = platform.name;
    select.append(option);
  });
  if (available.some((platform) => platform.id === previous)) {
    select.value = previous;
  }
  const atBarLimit = overlayType === "social" && selected.size >= 8;
  const unavailable = available.length === 0 || atBarLimit;
  select.disabled = unavailable;
  byId("socialHandleInput").disabled = unavailable;
  byId("socialAddButton").disabled = unavailable || !select.value;
  byId("socialEmptyState").hidden = selected.size !== 0;
}

function updateSocialSelectionState(overlayType = activeInstance()?.type) {
  const count = socialRows().length;
  byId("socialSelectionCount").textContent =
    `${count} account${count === 1 ? "" : "s"}`;
  byId("socialSelectionLimit").textContent =
    overlayType === "social"
      ? "Up to 8 accounts"
      : "Each platform can be added once";
  refreshSocialPlatformOptions(overlayType);
}

function addSocialAccount() {
  const instance = activeInstance();
  const platformId = byId("socialPlatformSelect").value;
  const platform = SOCIAL_PLATFORMS.find((item) => item.id === platformId);
  if (!platform) {
    showToast("Choose a platform first");
    return;
  }
  if (instance?.type === "social" && socialRows().length >= 8) {
    showToast("Social Bar supports up to 8 accounts");
    return;
  }
  const handle = socialHandleFromInput(byId("socialHandleInput").value);
  if (!handle) {
    showToast("Enter a handle or profile link");
    byId("socialHandleInput").focus();
    return;
  }
  const accounts = socialRows().map((row) => ({
    platform: row.dataset.socialPlatform,
    enabled: true,
    handle: row.querySelector("[data-social-handle]")?.value || "",
  }));
  accounts.push({ platform: platform.id, enabled: true, handle });
  renderSocialAccounts(accounts, instance?.type);
  byId("socialHandleInput").value = "";
  byId("socialPlatformSelect").focus();
  scheduleCustomizerChange(0);
}

function renderSocial(social, overlayType = activeInstance()?.type) {
  const config = social || app.state?.defaults?.social || {};
  const rotator = overlayType === "social-rotator";
  document.querySelectorAll("[data-social-bar-only]").forEach((element) => {
    element.hidden = rotator;
  });
  document.querySelectorAll("[data-social-rotator-only]").forEach((element) => {
    element.hidden = !rotator;
  });
  renderSocialAccounts(config.accounts, overlayType);
  byId("socialIconShape").value = config.iconShape || "rounded";
  byId("socialIconBackground").checked = config.iconBackground !== false;
  byId("socialIconShape").disabled = !byId("socialIconBackground").checked;
  byId("socialSize").value = config.size || "medium";
  byId("socialScale").value = Number(config.scale) || 1;
  byId("socialScaleOutput").value = Number(config.scale || 1).toFixed(2);
  byId("socialLayout").value = config.layout || "sticker";
  byId("socialMode").value = config.mode || "individual";
  byId("socialSharedName").value = config.sharedName || "";
  byId("socialHeading").value = config.heading || "Stay connected";
  byId("socialAlign").value = config.align || "center";
  byId("socialOutline").value = Number(config.outline) || 0;
  byId("socialOutlineOutput").value = String(Number(config.outline) || 0);
  byId("socialRotatorShape").value = config.rotatorShape || "capsule";
  byId("socialTransition").value = config.transition || "slide";
  byId("socialCycle").value = Number(config.cycle) || 4;
  byId("socialCycleOutput").value = Number(config.cycle || 4).toFixed(1);
  byId("socialPrefix").value = config.prefix ?? "@";
  byId("socialShowPlatform").checked = config.showPlatform !== false;
  byId("socialTimer").checked = config.timer !== false;
  byId("socialBrand").checked = config.brand !== false;
  setColor("socialColor", config.color || "f6f7fb");
  setColor("socialShellColor", config.shellColor || "141418");
  setColor("socialTextColor", config.textColor || "ffffff");
  byId("socialFont").value = config.font || "display";
  byId("socialWeight").value = String(config.weight || 800);
}

function gatherSocialSettings() {
  const selected = new Map(
    socialRows().map((row) => [
      row.dataset.socialPlatform,
      row.querySelector("[data-social-handle]")?.value || "",
    ]),
  );
  const accounts = SOCIAL_PLATFORMS.map((platform) => {
    return {
      platform: platform.id,
      enabled: selected.has(platform.id),
      handle: socialHandleFromInput(selected.get(platform.id) || ""),
    };
  });
  return {
    accounts,
    layout: byId("socialLayout").value,
    mode: byId("socialMode").value,
    sharedName: byId("socialSharedName").value,
    heading: byId("socialHeading").value,
    align: byId("socialAlign").value,
    iconShape: byId("socialIconShape").value,
    iconBackground: byId("socialIconBackground").checked,
    size: byId("socialSize").value,
    brand: byId("socialBrand").checked,
    color: byId("socialColor").value.slice(1),
    shellColor: byId("socialShellColor").value.slice(1),
    textColor: byId("socialTextColor").value.slice(1),
    font: byId("socialFont").value,
    weight: Number(byId("socialWeight").value),
    outline: Number(byId("socialOutline").value),
    scale: Number(byId("socialScale").value),
    cycle: Number(byId("socialCycle").value),
    rotatorShape: byId("socialRotatorShape").value,
    transition: byId("socialTransition").value,
    prefix: byId("socialPrefix").value,
    timer: byId("socialTimer").checked,
    showPlatform: byId("socialShowPlatform").checked,
  };
}

function parseSocialGroupedGroups(value) {
  const groups = [];
  String(value || "")
    .split(",")
    .slice(0, SOCIAL_GROUPED_LIMITS.groups)
    .forEach((chunk) => {
      const separator = chunk.indexOf(":");
      const platformText = separator >= 0 ? chunk.slice(0, separator) : chunk;
      const handle = separator >= 0 ? chunk.slice(separator + 1) : "";
      const platforms = [];
      platformText.split(/[+|]/).forEach((id) => {
        const platformId = id.trim().toLowerCase();
        if (
          SOCIAL_PLATFORMS.some((platform) => platform.id === platformId)
          && !platforms.includes(platformId)
          && platforms.length < SOCIAL_GROUPED_LIMITS.platforms
        ) {
          platforms.push(platformId);
        }
      });
      if (platforms.length) {
        groups.push({ platforms, handle: handle.trim().slice(0, 128) });
      }
    });
  return groups.length
    ? groups
    : [{ platforms: ["twitch", "youtube"], handle: "yourname" }];
}

function socialGroupedGroupsFromEditor() {
  return [...byId("socialGroupedList").querySelectorAll(
    "[data-social-grouped-row]",
  )].map((row) => ({
    platforms: [...row.querySelectorAll("[data-social-grouped-platform]")]
      .map((chip) => chip.dataset.socialGroupedPlatform)
      .filter(Boolean)
      .slice(0, SOCIAL_GROUPED_LIMITS.platforms),
    handle: String(
      row.querySelector("[data-social-grouped-handle]")?.value || "",
    ).slice(0, 128),
  })).filter((group) => group.platforms.length);
}

function createSocialGroupedMark(platform) {
  const mark = document.createElement("span");
  mark.className = "social-grouped-platform-mark";
  mark.textContent = platform.mark;
  mark.style.setProperty(
    "--platform-color",
    platform.surface || platform.color,
  );
  if (platform.ink) mark.style.setProperty("--platform-ink", platform.ink);
  if (platform.shadow) {
    mark.style.setProperty("--platform-shadow", platform.shadow);
  }
  return mark;
}

function populateSocialGroupedPlatformSelect() {
  const select = byId("socialGroupedPlatformSelect");
  const previous = select.value;
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a platform";
  select.append(placeholder);
  SOCIAL_PLATFORMS.forEach((platform) => {
    const option = document.createElement("option");
    option.value = platform.id;
    option.textContent = platform.name;
    select.append(option);
  });
  if (SOCIAL_PLATFORMS.some((platform) => platform.id === previous)) {
    select.value = previous;
  }
}

function updateSocialGroupedQuickAddState(groups = socialGroupedGroupsFromEditor()) {
  const select = byId("socialGroupedPlatformSelect");
  const handle = byId("socialGroupedHandleInput");
  const accountCount = groups.reduce(
    (total, group) => total + group.platforms.length,
    0,
  );
  byId("socialGroupedAccountCount").textContent =
    `${accountCount} account${accountCount === 1 ? "" : "s"}`;
  byId("socialGroupedAddButton").disabled =
    !select.value || !String(handle.value || "").trim();
}

function addSocialGroupedAccount() {
  const platformId = byId("socialGroupedPlatformSelect").value;
  const platform = SOCIAL_PLATFORMS.find((item) => item.id === platformId);
  if (!platform) {
    showToast("Choose a platform first");
    return;
  }
  const handleInput = byId("socialGroupedHandleInput");
  const handle = socialHandleFromInput(handleInput.value, 128);
  if (!handle) {
    showToast("Enter a handle or profile link");
    handleInput.focus();
    return;
  }

  const groups = socialGroupedGroupsFromEditor();
  const handleKey = handle.toLocaleLowerCase();
  const matchingGroup = groups.find((group) => (
    socialHandleFromInput(group.handle, 128).toLocaleLowerCase() === handleKey
  ));
  if (matchingGroup) {
    if (matchingGroup.platforms.includes(platform.id)) {
      showToast(`${platform.name} already uses this handle`);
      return;
    }
    if (matchingGroup.platforms.length >= SOCIAL_GROUPED_LIMITS.platforms) {
      showToast("This group already has the maximum number of platforms");
      return;
    }
    matchingGroup.platforms.push(platform.id);
  } else {
    if (groups.length >= SOCIAL_GROUPED_LIMITS.groups) {
      showToast("Social Grouped supports up to 6 handles");
      return;
    }
    groups.push({ platforms: [platform.id], handle });
  }

  renderSocialGroupedGroups(groups);
  byId("socialGroupedPlatformSelect").value = "";
  updateSocialGroupedQuickAddState(groups);
  byId("socialGroupedPlatformSelect").focus();
  scheduleCustomizerChange(0);
}

function renderSocialGroupedGroups(groups) {
  const normalized = (Array.isArray(groups) ? groups : [])
    .slice(0, SOCIAL_GROUPED_LIMITS.groups);
  if (!normalized.length) {
    normalized.push({ platforms: ["twitch", "youtube"], handle: "yourname" });
  }
  const list = byId("socialGroupedList");
  list.replaceChildren();

  normalized.forEach((group, index) => {
    const platforms = group.platforms
      .map((id) => SOCIAL_PLATFORMS.find((platform) => platform.id === id))
      .filter(Boolean)
      .slice(0, SOCIAL_GROUPED_LIMITS.platforms);
    if (!platforms.length) return;

    const row = document.createElement("section");
    row.className = "social-grouped-row";
    row.dataset.socialGroupedRow = String(index);

    const heading = document.createElement("div");
    heading.className = "social-grouped-row-heading";
    const title = document.createElement("strong");
    title.textContent = `Group ${index + 1}`;
    const summary = document.createElement("span");
    summary.textContent = `${platforms.length} platform${platforms.length === 1 ? "" : "s"}`;
    const removeGroup = document.createElement("button");
    removeGroup.type = "button";
    removeGroup.className = "social-grouped-delete";
    removeGroup.dataset.socialGroupedRemoveGroup = String(index);
    removeGroup.disabled = normalized.length === 1;
    removeGroup.setAttribute("aria-label", `Delete group ${index + 1}`);
    removeGroup.title = normalized.length === 1
      ? "At least one group is required"
      : `Delete group ${index + 1}`;
    removeGroup.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 6h18"></path>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
        <path d="M10 11v6"></path>
        <path d="M14 11v6"></path>
      </svg>
    `;
    heading.append(title, summary, removeGroup);

    const platformArea = document.createElement("div");
    platformArea.className = "social-grouped-platform-area";
    const chips = document.createElement("div");
    chips.className = "social-grouped-platforms";
    platforms.forEach((platform) => {
      const chip = document.createElement("span");
      chip.className = "social-grouped-chip";
      chip.dataset.socialGroupedPlatform = platform.id;
      const name = document.createElement("span");
      name.textContent = platform.name;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.dataset.socialGroupedRemovePlatform = platform.id;
      remove.disabled = platforms.length === 1;
      remove.textContent = "\u00d7";
      remove.setAttribute("aria-label", `Remove ${platform.name} from group ${index + 1}`);
      remove.title = platforms.length === 1
        ? "A group needs at least one platform"
        : `Remove ${platform.name}`;
      chip.append(createSocialGroupedMark(platform), name, remove);
      chips.append(chip);
    });

    const addPlatform = document.createElement("select");
    addPlatform.dataset.socialGroupedAddPlatform = String(index);
    addPlatform.setAttribute("aria-label", `Add platform to group ${index + 1}`);
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = platforms.length >= SOCIAL_GROUPED_LIMITS.platforms
      ? "Platform limit reached"
      : "Add platform...";
    addPlatform.append(placeholder);
    const selected = new Set(platforms.map((platform) => platform.id));
    SOCIAL_PLATFORMS
      .filter((platform) => !selected.has(platform.id))
      .forEach((platform) => {
        const option = document.createElement("option");
        option.value = platform.id;
        option.textContent = platform.name;
        addPlatform.append(option);
      });
    addPlatform.disabled = platforms.length >= SOCIAL_GROUPED_LIMITS.platforms;
    platformArea.append(chips, addPlatform);

    const handleLabel = document.createElement("label");
    handleLabel.className = "social-grouped-handle";
    const handleTitle = document.createElement("span");
    handleTitle.textContent = "Shared handle";
    const handle = document.createElement("input");
    handle.type = "text";
    handle.value = String(group.handle || "").slice(0, 128);
    handle.maxLength = 128;
    handle.autocomplete = "off";
    handle.placeholder = "yourname";
    handle.dataset.socialGroupedHandle = String(index);
    handleLabel.append(handleTitle, handle);

    row.append(heading, platformArea, handleLabel);
    list.append(row);
  });

  const count = list.querySelectorAll("[data-social-grouped-row]").length;
  byId("socialGroupedCount").textContent =
    `${count} group${count === 1 ? "" : "s"}`;
  byId("addSocialGroupButton").disabled =
    count >= SOCIAL_GROUPED_LIMITS.groups;
  updateSocialGroupedQuickAddState(normalized);
}

function setSocialGroupedRange(name, value, precision = 2) {
  const input = byId(`socialGrouped${name}`);
  const output = byId(`socialGrouped${name}Output`);
  const numeric = Number(value);
  input.value = Number.isFinite(numeric) ? numeric : input.min || 0;
  output.value = Number(input.value).toFixed(precision);
}

function setSocialGroupedModeControls(id, enabled) {
  const section = byId(id);
  section.hidden = !enabled;
  section.querySelectorAll("input, select").forEach((control) => {
    control.disabled = !enabled;
  });
}

function syncSocialGroupedModeControls() {
  const tile = byId("socialGroupedTile").checked;
  const split = tile || byId("socialGroupedSeparate").checked;
  setSocialGroupedModeControls("socialGroupedSplitLayoutControls", split);
  setSocialGroupedModeControls("socialGroupedTileFineTuningSection", tile);
}

function renderSocialGrouped(socialGrouped) {
  const defaults = app.state?.defaults?.socialGrouped || {};
  const config = { ...defaults, ...(socialGrouped || {}) };
  app.socialGroupedBase = structuredClone(config);
  renderSocialGroupedGroups(parseSocialGroupedGroups(config.groups));
  byId("socialGroupedPreset").value = config.preset || "sticker";
  byId("socialGroupedSeparate").checked = config.separate === true;
  byId("socialGroupedTile").checked = config.tile === true;
  byId("socialGroupedShape").value = config.shape || "squircle";
  byId("socialGroupedTextSide").value = config.textSide || "right";
  byId("socialGroupedTextCase").value = config.textCase || "none";
  byId("socialGroupedPrefix").value = config.prefix ?? "@";
  byId("socialGroupedFont").value = config.font || "montserrat";
  byId("socialGroupedWeight").value = String(config.weight || 800);
  byId("socialGroupedSize").value = config.size || "medium";
  byId("socialGroupedAlign").value = config.align || "center";
  byId("socialGroupedDirection").value = config.direction || "horizontal";
  byId("socialGroupedWrap").checked = config.wrap !== false;
  byId("socialGroupedLabel").value = config.label || "";
  byId("socialGroupedEqualHeight").checked = config.equalHeight !== false;
  byId("socialGroupedBrand").checked = config.brand !== false;
  byId("socialGroupedJoin").value = config.join || "round";
  byId("socialGroupedShadow").checked = config.shadow !== false;
  setSocialGroupedRange("Scale", config.scale ?? 1);
  setSocialGroupedRange("Merge", config.merge ?? 3, 1);
  setSocialGroupedRange("TextGap", config.textGap ?? -3, 1);
  setSocialGroupedRange("GroupGap", config.groupGap ?? -2, 1);
  setSocialGroupedRange("TextNudge", config.textNudge ?? 0);
  setSocialGroupedRange("LetterSpacing", config.letterSpacing ?? -0.3, 1);
  setSocialGroupedRange("LogoHeight", config.logoHeight ?? 19, 1);
  setSocialGroupedRange("TextSize", config.textSize ?? 20, 1);
  setSocialGroupedRange("LabelSize", config.labelSize ?? 8, 1);
  setSocialGroupedRange("LabelGap", config.labelGap ?? 0, 1);
  setSocialGroupedRange("Padding", config.padding ?? 18, 1);
  setSocialGroupedRange("Gap", config.gap ?? 26, 1);
  setSocialGroupedRange("Round", config.round ?? 0.3);
  setSocialGroupedRange("Overlap", config.overlap ?? 20, 1);
  setSocialGroupedRange("NameGap", config.nameGap ?? 6, 1);
  setSocialGroupedRange("Outline", config.outline ?? 4);
  setSocialGroupedRange("TileOutline", config.tileOutline ?? 3);
  setSocialGroupedRange("LogoOutline", config.logoOutline ?? 2);
  setSocialGroupedRange("TextOutline", config.textOutline ?? 2);
  setSocialGroupedRange("EdgeWidth", config.edgeWidth ?? 1);
  setSocialGroupedRange("TextEdgeWidth", config.textEdgeWidth ?? 1);
  setSocialGroupedRange("OutlineOpacity", config.outlineOpacity ?? 1);
  setSocialGroupedRange("ShadowX", config.shadowX ?? 0, 1);
  setSocialGroupedRange("ShadowY", config.shadowY ?? 3, 1);
  setSocialGroupedRange("ShadowBlur", config.shadowBlur ?? 5, 1);
  setSocialGroupedRange("ShadowOpacity", config.shadowOpacity ?? 0.45);
  setColor("socialGroupedBaseColor", config.color || "ffffff");
  setColor("socialGroupedOuterColor", config.tileEdge || "ffffff");
  setColor("socialGroupedEdgeColor", config.edgeColor || "000000");
  setColor("socialGroupedLegacyTextEdgeColor", config.textEdge || "000000");
  setColor("socialGroupedTextColor", config.textColor || "ffffff");
  setColor(
    "socialGroupedTextOuterColor",
    config.textOutlineColor || config.tileEdge || "ffffff",
  );
  setColor(
    "socialGroupedTextEdgeColor",
    config.textEdgeColor || config.edgeColor || "000000",
  );
  setColor(
    "socialGroupedLabelColor",
    config.labelColor || config.textColor || "ffffff",
  );
  setColor("socialGroupedShadowColor", config.shadowColor || "000000");
  syncSocialGroupedModeControls();
}

function gatherSocialGroupedSettings() {
  const groups = socialGroupedGroupsFromEditor()
    .slice(0, SOCIAL_GROUPED_LIMITS.groups)
    .map((group) => {
      const handle = group.handle
        .replaceAll(",", " ")
        .replace(/[\u0000-\u001f\u007f]/g, "")
        .trim()
        .slice(0, 128);
      return `${group.platforms.join("+")}:${handle}`;
    })
    .join(",");
  return {
    ...(app.socialGroupedBase || app.state?.defaults?.socialGrouped || {}),
    groups,
    prefix: byId("socialGroupedPrefix").value.slice(0, 8),
    preset: byId("socialGroupedPreset").value,
    separate: byId("socialGroupedSeparate").checked,
    tile: byId("socialGroupedTile").checked,
    shape: byId("socialGroupedShape").value,
    round: Number(byId("socialGroupedRound").value),
    textSide: byId("socialGroupedTextSide").value,
    textCase: byId("socialGroupedTextCase").value,
    font: byId("socialGroupedFont").value,
    weight: Number(byId("socialGroupedWeight").value),
    size: byId("socialGroupedSize").value,
    scale: Number(byId("socialGroupedScale").value),
    merge: Number(byId("socialGroupedMerge").value),
    textGap: Number(byId("socialGroupedTextGap").value),
    groupGap: Number(byId("socialGroupedGroupGap").value),
    overlap: Number(byId("socialGroupedOverlap").value),
    nameGap: Number(byId("socialGroupedNameGap").value),
    textNudge: Number(byId("socialGroupedTextNudge").value),
    letterSpacing: Number(byId("socialGroupedLetterSpacing").value),
    logoHeight: Number(byId("socialGroupedLogoHeight").value),
    textSize: Number(byId("socialGroupedTextSize").value),
    equalHeight: byId("socialGroupedEqualHeight").checked,
    brand: byId("socialGroupedBrand").checked,
    logoOutline: Number(byId("socialGroupedLogoOutline").value),
    textOutline: Number(byId("socialGroupedTextOutline").value),
    edgeWidth: Number(byId("socialGroupedEdgeWidth").value),
    textEdgeWidth: Number(byId("socialGroupedTextEdgeWidth").value),
    join: byId("socialGroupedJoin").value,
    outlineOpacity: Number(byId("socialGroupedOutlineOpacity").value),
    color: byId("socialGroupedBaseColor").value.slice(1),
    tileEdge: byId("socialGroupedOuterColor").value.slice(1),
    edgeColor: byId("socialGroupedEdgeColor").value.slice(1),
    textEdge: byId("socialGroupedLegacyTextEdgeColor").value.slice(1),
    textColor: byId("socialGroupedTextColor").value.slice(1),
    textOutlineColor: byId("socialGroupedTextOuterColor").value.slice(1),
    textEdgeColor: byId("socialGroupedTextEdgeColor").value.slice(1),
    outline: Number(byId("socialGroupedOutline").value),
    tileOutline: Number(byId("socialGroupedTileOutline").value),
    gap: Number(byId("socialGroupedGap").value),
    align: byId("socialGroupedAlign").value,
    label: byId("socialGroupedLabel").value.slice(0, 64),
    labelSize: Number(byId("socialGroupedLabelSize").value),
    labelGap: Number(byId("socialGroupedLabelGap").value),
    labelColor: byId("socialGroupedLabelColor").value.slice(1),
    direction: byId("socialGroupedDirection").value,
    wrap: byId("socialGroupedWrap").checked,
    padding: Number(byId("socialGroupedPadding").value),
    shadow: byId("socialGroupedShadow").checked,
    shadowX: Number(byId("socialGroupedShadowX").value),
    shadowY: Number(byId("socialGroupedShadowY").value),
    shadowBlur: Number(byId("socialGroupedShadowBlur").value),
    shadowColor: byId("socialGroupedShadowColor").value.slice(1),
    shadowOpacity: Number(byId("socialGroupedShadowOpacity").value),
  };
}

function applySocialGroupedPreset(preset) {
  const values = SOCIAL_GROUPED_PRESETS[preset];
  if (!values) return;
  renderSocialGrouped({
    ...gatherSocialGroupedSettings(),
    ...values,
    preset,
  });
  scheduleCustomizerChange(0);
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
  if (
    activeInstance()?.type === "social"
    || activeInstance()?.type === "social-rotator"
  ) {
    renderSocial(config.social, activeInstance().type);
  } else if (activeInstance()?.type === "social-grouped") {
    renderSocialGrouped(config.socialGrouped);
  }
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
  app.confirmUnsavedChanges = state.confirmUnsavedChanges !== false;
  byId("confirmUnsavedChangesSetting").checked =
    app.confirmUnsavedChanges;
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
  renderGoalPill(
    selected?.type === "goal-pill"
      ? state.goals?.[selected.id]
      : state.goalPillDefaults,
  );
  renderRivals(
    selected?.type === "rivals-rank"
      ? state.rivals?.[selected.id]
      : state.rivalsDefaults,
    selected?.type === "rivals-rank"
      ? state.rivalsLinked?.[selected.id] === true
      : false,
    false,
    selected?.type === "rivals-rank"
      ? state.rivalsPolls?.[selected.id]
      : null,
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
  scheduleCustomizerChange();
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
    scheduleCustomizerChange();
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
    let submitted;
    if (instance.type === "social" || instance.type === "social-rotator") {
      submitted = { social: gatherSocialSettings() };
    } else if (instance.type === "social-grouped") {
      submitted = { socialGrouped: gatherSocialGroupedSettings() };
    } else {
      submitted = gatherConfig();
    }
    const result = await callApi(
      "save_overlay_settings",
      submitted,
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
    rememberSavedCustomizer();
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
  if (!instance || instance.type !== "win-loss") return false;
  try {
    const result = await callApi("update_counter", payload, instance.id);
    if (!result.ok) {
      showToast(result.detail || "Counter update failed");
      return false;
    }
    app.state.counters = app.state.counters || {};
    app.state.counters[instance.id] = result.counter;
    renderCounter(result.counter);
    rememberSavedCustomizer();
    logActivity(`Match record updated: ${result.counter.wins} wins, ${result.counter.losses} losses`);
    return true;
  } catch (error) {
    showToast(String(error.message || error));
    return false;
  }
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

function gatherGoalPillSettings() {
  return {
    label: byId("goalPillLabel").value,
    current: Number(byId("goalPillCurrent").value),
    target: Number(byId("goalPillTarget").value),
    format: byId("goalPillFormat").value,
    symbol: byId("goalPillSymbol").value,
    size: byId("goalPillSize").value,
    icon: byId("goalPillIcon").value,
    corners: byId("goalPillCorners").value,
    width: Number(byId("goalPillWidth").value),
    color: byId("goalPillColor").value.slice(1),
    shellColor: byId("goalPillShellColor").value.slice(1),
    track: byId("goalPillTrack").value.slice(1),
    labelColor: byId("goalPillLabelColor").value.slice(1),
    font: byId("goalPillFont").value,
    weight: Number(byId("goalPillWeight").value),
    scale: Number(byId("goalPillScale").value),
    glow: Number(byId("goalPillGlow").value),
  };
}

function gatherRivalsSettings() {
  return {
    label: byId("rivalsLabel").value,
    showName: byId("rivalsShowName").checked,
    shellColor: byId("rivalsShellColor").value.slice(1),
    textColor: byId("rivalsTextColor").value.slice(1),
    accentColor: byId("rivalsAccentColor").value.slice(1),
    winColor: byId("rivalsWinColor").value.slice(1),
    lossColor: byId("rivalsLossColor").value.slice(1),
    font: byId("rivalsFont").value,
    weight: Number(byId("rivalsWeight").value),
    scale: Number(byId("rivalsScale").value),
    corners: Number(byId("rivalsCorners").value),
    glow: Number(byId("rivalsGlow").value),
  };
}

async function sendRivals(payload, message, options = {}) {
  const instance = activeInstance();
  if (!instance || instance.type !== "rivals-rank" || app.busy) return false;
  app.busy = true;
  renderRivals(
    app.state?.rivals?.[instance.id],
    app.state?.rivalsLinked?.[instance.id] === true,
    false,
    app.state?.rivalsPolls?.[instance.id],
  );
  try {
    const result = await callApi("update_rivals", payload, instance.id);
    if (!result.ok) {
      showToast(result.detail || "Rivals Rank update failed");
      return false;
    }
    app.state.rivals = app.state.rivals || {};
    app.state.rivalsLinked = app.state.rivalsLinked || {};
    app.state.rivalsPolls = app.state.rivalsPolls || {};
    app.state.rivals[instance.id] = result.rivals;
    app.state.rivalsLinked[instance.id] = result.linked === true;
    app.state.rivalsPolls[instance.id] = result.poll || {};
    renderRivals(
      result.rivals,
      result.linked,
      options.hydrate === true,
      result.poll,
    );
    logActivity(message);
    showToast(message);
    if (options.remember) rememberSavedCustomizer();
    return true;
  } catch (error) {
    showToast(String(error.message || error));
    return false;
  } finally {
    app.busy = false;
    renderRivals(
      app.state?.rivals?.[instance.id],
      app.state?.rivalsLinked?.[instance.id] === true,
      false,
      app.state?.rivalsPolls?.[instance.id],
    );
  }
}

async function linkRivalsAccount() {
  const uid = byId("rivalsUid").value.trim();
  if (!uid) {
    showToast("Enter a Rivals Data player ID or profile URL");
    byId("rivalsUid").focus();
    return;
  }
  const linked = await sendRivals(
    { uid },
    "Rivals Data account linked",
  );
  if (linked) byId("rivalsUid").value = "";
}

async function sendGoal(payload, message = "Goal updated") {
  const instance = activeInstance();
  if (!instance || !isGoalOverlayType(instance.type) || app.busy) return false;
  app.busy = true;
  try {
    const result = await callApi("update_goal", payload, instance.id);
    if (!result.ok) {
      showToast(result.detail || "Goal update failed");
      return false;
    }
    app.state.goals = app.state.goals || {};
    app.state.goals[instance.id] = result.goal;
    if (instance.type === "goal-bar") {
      app.goalBarKey = "";
      renderGoalBar(result.goal);
    } else if (instance.type === "goal-pill") {
      app.goalPillKey = "";
      renderGoalPill(result.goal);
    } else {
      app.goalKey = "";
      renderGoal(result.goal);
    }
    logActivity(
      `${message}: ${result.goal.current} of ${result.goal.target}`,
    );
    showToast(message);
    rememberSavedCustomizer();
    return true;
  } catch (error) {
    showToast(String(error.message || error));
    return false;
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

function openInstanceSettings(instanceId, skipWarning = false) {
  const instance = instanceById(instanceId);
  const manifest = manifestFor(instance?.type);
  if (!instance || !manifest?.studioView) return;
  const switchingCustomizer =
    CUSTOMIZER_VIEW_IDS.has(activeViewId())
    && app.activeInstanceId !== instance.id;
  if (!skipWarning && switchingCustomizer && app.customizerDirty) {
    requestUnsavedAction(
      () => openInstanceSettings(instanceId, true),
    );
    return;
  }
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
  } else if (instance.type === "goal-pill") {
    app.goalPillKey = "";
    renderGoalPill(
      app.state?.goals?.[instance.id] || app.state?.goalPillDefaults,
      true,
    );
  } else if (instance.type === "rivals-rank") {
    app.rivalsSettingsKey = "";
    byId("rivalsUid").value = "";
    renderRivals(
      app.state?.rivals?.[instance.id] || app.state?.rivalsDefaults,
      app.state?.rivalsLinked?.[instance.id] === true,
      true,
      app.state?.rivalsPolls?.[instance.id],
    );
  } else if (
    instance.type === "social"
    || instance.type === "social-rotator"
  ) {
    renderSocial(
      materializeInstanceConfig(instance).social,
      instance.type,
    );
  } else if (instance.type === "social-grouped") {
    renderSocialGrouped(
      materializeInstanceConfig(instance).socialGrouped,
    );
  }
  showView(manifest.studioView);
  rememberSavedCustomizer();
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
  initializeRangeControls();
  initializeCurrencySelects();
  bindDanceDropZone();
  populateSocialGroupedPlatformSelect();
  const customizerFrame = byId("customizerPreviewFrame");
  const customizerStage = byId("customizerPreviewStage");
  customizerFrame.addEventListener("load", () => {
    app.customizerPreviewReady =
      Boolean(customizerFrame.dataset.source)
      && customizerFrame.src !== "about:blank";
    fitCustomizerPreview();
    if (app.customizerPreviewReady) scheduleCustomizerDraft(0);
  });
  app.customizerResizeObserver = new ResizeObserver(fitCustomizerPreview);
  app.customizerResizeObserver.observe(byId("customizerPreviewStage"));
  CUSTOMIZER_SPLIT_MEDIA.addEventListener("change", (event) => {
    if (!event.matches) setCustomizerPreviewExpanded(false);
  });
  byId("customizerPreviewExpandButton").addEventListener("click", () => {
    setCustomizerPreviewExpanded(!app.customizerPreviewExpanded);
  });
  byId("customizerPreviewPopoutButton").addEventListener(
    "click",
    openCustomizerPreviewWindow,
  );
  byId("customizerPreviewZoomOutButton").addEventListener("click", () => {
    setCustomizerPreviewZoom(app.customizerPreviewZoom - PREVIEW_ZOOM_STEP);
  });
  byId("customizerPreviewZoomInButton").addEventListener("click", () => {
    setCustomizerPreviewZoom(app.customizerPreviewZoom + PREVIEW_ZOOM_STEP);
  });
  byId("customizerPreviewZoomResetButton").addEventListener(
    "click",
    resetCustomizerPreviewZoom,
  );
  byId("customizerPreviewRecenterButton").addEventListener(
    "click",
    resetCustomizerPreviewViewport,
  );
  byId("customizerPreviewSaveButton").addEventListener(
    "click",
    () => saveCustomizerFromPreview(),
  );
  customizerStage.addEventListener("wheel", (event) => {
    if (!app.customizerPreviewReady) return;
    event.preventDefault();
    setCustomizerPreviewZoom(
      app.customizerPreviewZoom
        + (event.deltaY < 0 ? PREVIEW_ZOOM_STEP : -PREVIEW_ZOOM_STEP),
      event.clientX,
      event.clientY,
    );
  }, { passive: false });
  customizerStage.addEventListener("pointerdown", (event) => {
    if (!app.customizerPreviewReady || event.button !== 0) return;
    event.preventDefault();
    app.customizerPreviewDrag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panX: app.customizerPreviewPan.x,
      panY: app.customizerPreviewPan.y,
      moved: false,
    };
    customizerStage.classList.add("dragging");
    customizerStage.setPointerCapture(event.pointerId);
  });
  customizerStage.addEventListener("pointermove", (event) => {
    const drag = app.customizerPreviewDrag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    drag.moved ||= Math.hypot(deltaX, deltaY) > 3;
    app.customizerPreviewPan.x = drag.panX + deltaX;
    app.customizerPreviewPan.y = drag.panY + deltaY;
    fitCustomizerPreview();
  });
  const finishCustomizerPreviewDrag = (event) => {
    const drag = app.customizerPreviewDrag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    app.customizerPreviewDrag = null;
    customizerStage.classList.remove("dragging");
    if (customizerStage.hasPointerCapture(event.pointerId)) {
      customizerStage.releasePointerCapture(event.pointerId);
    }
    if (!drag.moved && !app.customizerPreviewExpanded) {
      setCustomizerPreviewExpanded(true);
    }
  };
  customizerStage.addEventListener("pointerup", finishCustomizerPreviewDrag);
  customizerStage.addEventListener("pointercancel", finishCustomizerPreviewDrag);
  customizerStage.addEventListener("lostpointercapture", () => {
    app.customizerPreviewDrag = null;
    customizerStage.classList.remove("dragging");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && app.customizerPreviewExpanded) {
      setCustomizerPreviewExpanded(false);
    }
  });
  const scheduleFromCustomizerEvent = (event) => {
    if (
      event.target.closest(".detail-view.active.has-customizer-preview")
      && !event.target.closest("[data-customizer-passive]")
    ) {
      scheduleCustomizerChange();
    }
  };
  document.addEventListener("input", scheduleFromCustomizerEvent);
  document.addEventListener("change", scheduleFromCustomizerEvent);
  document.addEventListener("click", scheduleFromCustomizerEvent);

  byId("menuButton").addEventListener("click", () => setDrawer(true));
  byId("closeDrawerButton").addEventListener("click", () => setDrawer(false));
  byId("drawerScrim").addEventListener("click", () => setDrawer(false));

  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => navigateToView(button.dataset.viewTarget));
  });
  document.querySelectorAll(".library-button").forEach((button) => {
    button.addEventListener("click", () => navigateToView("libraryView"));
  });
  document.querySelectorAll("[data-drawer-view]").forEach((button) => {
    button.addEventListener("click", () => {
      navigateToView(button.dataset.drawerView);
      setDrawer(false);
    });
  });

  byId("headerServerButton").addEventListener("click", () => {
    if (app.state?.running) navigateToView("serverView");
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
  byId("goalPillWidth").addEventListener("input", () => {
    byId("goalPillWidthOutput").value = byId("goalPillWidth").value;
  });
  byId("goalPillScale").addEventListener("input", () => {
    byId("goalPillScaleOutput").value =
      Number(byId("goalPillScale").value).toFixed(2);
  });
  byId("goalPillGlow").addEventListener("input", () => {
    byId("goalPillGlowOutput").value =
      Number(byId("goalPillGlow").value).toFixed(2);
  });
  byId("rivalsScale").addEventListener("input", () => {
    byId("rivalsScaleOutput").value =
      Number(byId("rivalsScale").value).toFixed(2);
  });
  byId("rivalsCorners").addEventListener("input", () => {
    byId("rivalsCornersOutput").value = byId("rivalsCorners").value;
  });
  byId("rivalsGlow").addEventListener("input", () => {
    byId("rivalsGlowOutput").value =
      Number(byId("rivalsGlow").value).toFixed(2);
  });
  byId("socialScale").addEventListener("input", () => {
    byId("socialScaleOutput").value =
      Number(byId("socialScale").value).toFixed(2);
  });
  byId("socialOutline").addEventListener("input", () => {
    byId("socialOutlineOutput").value = byId("socialOutline").value;
  });
  byId("socialIconBackground").addEventListener("change", () => {
    byId("socialIconShape").disabled = !byId("socialIconBackground").checked;
  });
  byId("socialCycle").addEventListener("input", () => {
    byId("socialCycleOutput").value =
      Number(byId("socialCycle").value).toFixed(1);
  });
  [
    ["Scale", 2],
    ["Merge", 1],
    ["TextGap", 1],
    ["GroupGap", 1],
    ["TextNudge", 2],
    ["LetterSpacing", 1],
    ["LogoHeight", 1],
    ["TextSize", 1],
    ["LabelSize", 1],
    ["LabelGap", 1],
    ["Padding", 1],
    ["Gap", 1],
    ["Round", 2],
    ["Overlap", 1],
    ["NameGap", 1],
    ["Outline", 2],
    ["TileOutline", 2],
    ["LogoOutline", 2],
    ["TextOutline", 2],
    ["EdgeWidth", 2],
    ["TextEdgeWidth", 2],
    ["OutlineOpacity", 2],
    ["ShadowX", 1],
    ["ShadowY", 1],
    ["ShadowBlur", 1],
    ["ShadowOpacity", 2],
  ].forEach(([name, precision]) => {
    byId(`socialGrouped${name}`).addEventListener("input", () => {
      byId(`socialGrouped${name}Output`).value =
        Number(byId(`socialGrouped${name}`).value).toFixed(precision);
    });
  });
  ["socialGroupedTile", "socialGroupedSeparate"].forEach((id) => {
    byId(id).addEventListener("change", syncSocialGroupedModeControls);
  });
  byId("socialGroupedPreset").addEventListener("change", (event) => {
    applySocialGroupedPreset(event.target.value);
  });
  const socialGroupedView = byId("socialGroupedView");
  const markSocialGroupedCustom = (event) => {
    if (
      event.target.id === "socialGroupedPreset"
      || event.target.closest("#socialGroupedList")
      || event.target.closest("#socialGroupedQuickAdd")
    ) return;
    byId("socialGroupedPreset").value = "custom";
  };
  socialGroupedView.addEventListener("input", markSocialGroupedCustom);
  socialGroupedView.addEventListener("change", markSocialGroupedCustom);
  byId("socialGroupedPlatformSelect").addEventListener("change", () => {
    updateSocialGroupedQuickAddState();
  });
  byId("socialGroupedHandleInput").addEventListener("input", () => {
    updateSocialGroupedQuickAddState();
  });
  byId("socialGroupedHandleInput").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    addSocialGroupedAccount();
  });
  byId("socialGroupedAddButton").addEventListener(
    "click",
    addSocialGroupedAccount,
  );
  byId("addSocialGroupButton").addEventListener("click", () => {
    const groups = socialGroupedGroupsFromEditor();
    if (groups.length >= SOCIAL_GROUPED_LIMITS.groups) return;
    const used = new Set(groups.flatMap((group) => group.platforms));
    const platform = SOCIAL_PLATFORMS.find((item) => !used.has(item.id))
      || SOCIAL_PLATFORMS[0];
    groups.push({ platforms: [platform.id], handle: "yourname" });
    renderSocialGroupedGroups(groups);
    scheduleCustomizerChange(0);
  });
  byId("socialGroupedList").addEventListener("change", (event) => {
    const select = event.target.closest("[data-social-grouped-add-platform]");
    if (!select?.value) return;
    const groups = socialGroupedGroupsFromEditor();
    const index = Number(select.dataset.socialGroupedAddPlatform);
    if (
      !groups[index]
      || groups[index].platforms.length >= SOCIAL_GROUPED_LIMITS.platforms
      || groups[index].platforms.includes(select.value)
    ) return;
    groups[index].platforms.push(select.value);
    renderSocialGroupedGroups(groups);
    scheduleCustomizerChange(0);
  });
  byId("socialGroupedList").addEventListener("click", (event) => {
    const row = event.target.closest("[data-social-grouped-row]");
    if (!row) return;
    const index = Number(row.dataset.socialGroupedRow);
    const groups = socialGroupedGroupsFromEditor();
    const removeGroup = event.target.closest("[data-social-grouped-remove-group]");
    if (removeGroup && groups.length > 1) {
      groups.splice(index, 1);
      renderSocialGroupedGroups(groups);
      scheduleCustomizerChange(0);
      return;
    }
    const removePlatform = event.target.closest(
      "[data-social-grouped-remove-platform]",
    );
    if (!removePlatform || !groups[index] || groups[index].platforms.length <= 1) {
      return;
    }
    groups[index].platforms = groups[index].platforms.filter(
      (id) => id !== removePlatform.dataset.socialGroupedRemovePlatform,
    );
    renderSocialGroupedGroups(groups);
    scheduleCustomizerChange(0);
  });
  byId("socialPlatformSelect").addEventListener("change", () => {
    byId("socialAddButton").disabled = !byId("socialPlatformSelect").value;
  });
  byId("socialAddButton").addEventListener("click", addSocialAccount);
  byId("socialHandleInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addSocialAccount();
    }
  });
  byId("socialPlatformGrid").addEventListener("click", (event) => {
    const remove = event.target.closest("[data-social-remove]");
    if (!remove) return;
    const platform = SOCIAL_PLATFORMS.find(
      (item) => item.id === remove.dataset.socialRemove,
    );
    remove.closest("[data-social-platform]")?.remove();
    updateSocialSelectionState(activeInstance()?.type);
    scheduleCustomizerChange(0);
    showToast(`${platform?.name || "Social account"} removed`);
  });
  byId("goalFormat").addEventListener("change", syncGoalFormat);
  byId("goalBarFormat").addEventListener("change", syncGoalBarFormat);
  byId("goalBarLayout").addEventListener("change", syncGoalBarLayout);
  byId("goalPillFormat").addEventListener("change", syncGoalPillFormat);
  byId("goalPillPreset").addEventListener("change", () => {
    const preset = byId("goalPillPreset").value;
    if (preset !== "custom") setColor("goalPillColor", preset);
  });
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
    "goalPillColor",
    "goalPillShellColor",
    "goalPillTrack",
    "goalPillLabelColor",
    "rivalsShellColor",
    "rivalsTextColor",
    "rivalsAccentColor",
    "rivalsWinColor",
    "rivalsLossColor",
    "socialColor",
    "socialShellColor",
    "socialTextColor",
    "socialGroupedOuterColor",
    "socialGroupedEdgeColor",
    "socialGroupedTextColor",
    "socialGroupedTextOuterColor",
    "socialGroupedTextEdgeColor",
    "socialGroupedLabelColor",
    "socialGroupedBaseColor",
    "socialGroupedLegacyTextEdgeColor",
    "socialGroupedShadowColor",
  ].forEach((id) => {
    byId(id).addEventListener("input", () => updateColorLabel(id));
  });
  byId("goalPillColor").addEventListener("input", () => {
    const accent = byId("goalPillColor").value.slice(1).toLowerCase();
    byId("goalPillPreset").value =
      GOAL_PILL_PRESETS.has(accent) ? accent : "custom";
  });

  byId("saveDanceButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveSpotifyButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveFlowButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveSocialButton").addEventListener("click", () => saveOverlaySettings());
  byId("saveSocialGroupedButton").addEventListener(
    "click",
    () => saveOverlaySettings(),
  );
  byId("saveGoalSettingsButton").addEventListener("click", () => {
    sendGoal(gatherGoalSettings(), "Goal saved and applied");
  });
  byId("saveGoalBarSettingsButton").addEventListener("click", () => {
    sendGoal(gatherGoalBarSettings(), "Goal Bar saved and applied");
  });
  byId("saveGoalPillSettingsButton").addEventListener("click", () => {
    sendGoal(gatherGoalPillSettings(), "Goal Pill saved and applied");
  });
  byId("saveRivalsSettingsButton").addEventListener("click", () => {
    sendRivals(
      gatherRivalsSettings(),
      "Rivals Rank saved and applied",
      { hydrate: true, remember: true },
    );
  });
  byId("linkRivalsAccountButton").addEventListener(
    "click",
    linkRivalsAccount,
  );
  byId("rivalsUid").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    linkRivalsAccount();
  });
  byId("resetRivalsSessionButton").addEventListener("click", () => {
    sendRivals({ action: "reset-session" }, "Rivals session reset");
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
  byId("resetSocialButton").addEventListener("click", () => {
    renderSocial(app.state.defaults.social, activeInstance()?.type);
    logActivity("Social fields reset; save to apply");
  });
  byId("resetSocialGroupedButton").addEventListener("click", () => {
    renderSocialGrouped(app.state.defaults.socialGrouped);
    scheduleCustomizerChange(0);
    logActivity("Grouped social fields reset; save to apply");
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
  byId("resetGoalPillFieldsButton").addEventListener("click", () => {
    const instance = activeInstance();
    const current =
      app.state?.goals?.[instance?.id]
      || app.state?.goalPillDefaults;
    renderGoalPill(app.state?.goalPillDefaults, true);
    app.goalPillKey = JSON.stringify(current || {});
    logActivity("Goal Pill fields reset; save to apply");
  });
  byId("resetRivalsFieldsButton").addEventListener("click", () => {
    const instance = activeInstance();
    const current =
      app.state?.rivals?.[instance?.id]
      || app.state?.rivalsDefaults
      || {};
    renderRivals(
      { ...current, ...rivalsVisualState(app.state?.rivalsDefaults) },
      app.state?.rivalsLinked?.[instance?.id] === true,
      true,
      app.state?.rivalsPolls?.[instance?.id],
    );
    logActivity("Rivals Rank fields reset; save to apply");
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
  document.querySelectorAll("[data-goal-pill-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.goalPillAction;
      const payload = { action };
      if (action === "add" || action === "subtract") {
        payload.amount = Number(byId("goalPillStep").value);
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
  byId("confirmUnsavedChangesSetting").addEventListener("change", (event) => {
    setConfirmUnsavedChanges(event.target.checked);
  });

  const overlayGrid = byId("overlayGrid");
  overlayGrid.addEventListener("dragstart", beginOverlayCardDrag);
  overlayGrid.addEventListener("dragover", updateOverlayDropTarget);
  overlayGrid.addEventListener("drop", dropOverlayCard);
  overlayGrid.addEventListener("dragend", finishOverlayCardDrag);
  overlayGrid.addEventListener("keydown", moveOverlayCardWithKeyboard);
  overlayGrid.addEventListener("dragleave", (event) => {
    if (!overlayGrid.contains(event.relatedTarget)) clearOverlayDropTarget();
  });
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
  const addOverlayDialog = byId("addOverlayDialog");
  byId("closeAddDialog").addEventListener("click", () => addOverlayDialog.close());
  addOverlayDialog.addEventListener("close", clearCatalogPreviews);

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

  const unsavedChangesDialog = byId("unsavedChangesDialog");
  byId("keepEditingButton").addEventListener("click", () => {
    resolveUnsavedChanges("keep");
  });
  byId("discardChangesButton").addEventListener("click", () => {
    resolveUnsavedChanges("discard");
  });
  byId("saveUnsavedChangesButton").addEventListener("click", () => {
    resolveUnsavedChanges("save");
  });
  unsavedChangesDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    resolveUnsavedChanges("keep");
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
window.overlayStudioSavePreviewDraft = saveCustomizerFromPreview;
window.overlayStudioRequestClose = () => {
  requestUnsavedAction(
    () => callApi("close_window").catch(() => {}),
    "close",
  );
};
