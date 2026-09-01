(() => {
  "use strict";

  const definition = window.PIXEL_TIME_TOOL || {};
  const overlayType = String(definition.overlayType || "");
  const kind = String(definition.kind || "clock");
  const lineLayout = definition.layout === "line";
  const query = new URLSearchParams(location.search);
  const instanceId = query.get("i") || "";
  const customizerMode = query.get("customizer") === "1";
  const catalogMode = query.get("catalog") === "1";
  if (query.get("preview") === "studio" || location.protocol === "file:") {
    document.documentElement.classList.add("overlay-studio-preview");
  }

  const tool = document.getElementById("pixelTime");
  const label = document.getElementById("timeLabel");
  const zone = document.getElementById("timeZone");
  const value = document.getElementById("timeValue");
  const detail = document.getElementById("timeDetail");
  const mode = document.getElementById("timeMode");

  const defaults = {
    clock: {
      label: "LOCAL TIME",
      timezone: "local",
      timezoneLabel: "",
      hour12: true,
      showSeconds: true,
      showDate: true,
    },
    countdown: {
      label: "STARTING IN",
      durationSeconds: 600,
      remainingMs: 600000,
      running: false,
      startedAt: 0,
      finishText: "TIME'S UP",
      showTenths: false,
      soundEnabled: true,
      soundPreset: "challenge-complete",
      customSound: "",
      soundVolume: .8,
    },
    stopwatch: {
      label: "TIME SPENT",
      elapsedMs: 0,
      running: false,
      startedAt: 0,
      showTenths: false,
    },
  }[kind] || {};

  let state = {
    accentColor: "70b237",
    shellColor: "292725",
    textColor: "fffbed",
    showLabel: true,
    scale: 1,
    glow: lineLayout ? 0 : .7,
    digitShadow: lineLayout ? 0 : 1,
    ...defaults,
  };
  let audioContext = null;
  let completionObservedRunning = false;
  let completionSoundPlayed = false;
  let soundPlayCount = 0;
  const completionSoundBuffers = new Map();
  const completionSoundLoads = new Map();
  const activeSoundOutputs = new Set();
  const AUDIO_RESUME_TIMEOUT_MS = 500;
  const COMPLETION_SOUND_URL = "/local-assets/countdown-completion.ogg";
  const MAX_COMPLETION_SOUND_BYTES = 5 * 1024 * 1024;

  const clamp = (number, minimum, maximum) => Math.max(
    minimum,
    Math.min(maximum, Number.isFinite(Number(number)) ? Number(number) : minimum),
  );
  const color = (candidate, fallback) => {
    const normalized = String(candidate || "").trim().replace(/^#/, "");
    return /^[0-9a-f]{6}$/i.test(normalized) ? normalized.toLowerCase() : fallback;
  };
  const text = (candidate, fallback, maximum, allowEmpty = false) => {
    const normalized = String(candidate ?? fallback).trim().replace(/\s+/g, " ").slice(0, maximum);
    return normalized || (allowEmpty ? "" : fallback);
  };
  const boolean = (candidate, fallback) => (
    typeof candidate === "boolean" ? candidate : fallback
  );
  const customSoundPath = candidate => {
    const normalized = String(candidate || "").trim().replaceAll("\\", "/");
    return /^user-assets\/sounds\/[A-Za-z0-9][A-Za-z0-9._-]{0,95}\.(?:mp3|ogg|wav)$/i
      .test(normalized)
      ? normalized
      : "";
  };
  const timezoneChoices = new Set([
    "local",
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
  ]);

  function normalize(patch = {}) {
    const next = { ...state, ...(patch && typeof patch === "object" ? patch : {}) };
    const common = {
      label: text(next.label, defaults.label, 32),
      accentColor: color(next.accentColor, "70b237"),
      shellColor: color(next.shellColor, "292725"),
      textColor: color(next.textColor, "fffbed"),
      showLabel: boolean(next.showLabel, true),
      scale: clamp(next.scale, .5, 1.25),
      glow: clamp(next.glow, 0, 2),
      digitShadow: clamp(next.digitShadow, 0, 1),
    };
    if (kind === "clock") {
      const timezone = String(next.timezone || "local");
      return {
        ...common,
        timezone: timezoneChoices.has(timezone) ? timezone : "local",
        timezoneLabel: text(next.timezoneLabel, "", 16, true),
        hour12: boolean(next.hour12, true),
        showSeconds: boolean(next.showSeconds, true),
        showDate: boolean(next.showDate, true),
      };
    }
    const runtime = {
      ...common,
      running: boolean(next.running, false),
      startedAt: Math.max(0, Math.round(Number(next.startedAt) || 0)),
      showTenths: boolean(next.showTenths, false),
    };
    if (kind === "countdown") {
      const durationSeconds = Math.round(clamp(next.durationSeconds, 1, 359999));
      return {
        ...runtime,
        durationSeconds,
        remainingMs: Math.round(clamp(next.remainingMs, 0, durationSeconds * 1000)),
        finishText: text(next.finishText, "TIME'S UP", 24),
        soundEnabled: boolean(next.soundEnabled, true),
        soundPreset: ["block-chime", "challenge-complete", "custom"]
          .includes(next.soundPreset)
          ? next.soundPreset
          : "challenge-complete",
        customSound: customSoundPath(next.customSound),
        soundVolume: clamp(next.soundVolume, 0, 1),
      };
    }
    return {
      ...runtime,
      elapsedMs: Math.round(clamp(next.elapsedMs, 0, 359999000)),
    };
  }

  function applyAppearance() {
    const root = document.documentElement;
    const accent = color(state.accentColor, "70b237");
    const rgb = [0, 2, 4].map(index => parseInt(accent.slice(index, index + 2), 16));
    root.style.setProperty("--accent", `#${accent}`);
    root.style.setProperty("--accent-rgb", rgb.join(", "));
    root.style.setProperty("--shell", `#${color(state.shellColor, "292725")}`);
    root.style.setProperty("--ink", `#${color(state.textColor, "fffbed")}`);
    root.style.setProperty("--scale", String(state.scale));
    root.style.setProperty("--glow", String(state.glow));
    root.style.setProperty("--digit-shadow", String(state.digitShadow));
    tool.classList.toggle("no-label", !state.showLabel);
    tool.classList.toggle(
      "compact-timer",
      lineLayout && kind !== "clock" && !state.showLabel,
    );
    label.textContent = state.label;
  }

  function timeZoneOptions(extra = {}) {
    return {
      ...(state.timezone === "local" ? {} : { timeZone: state.timezone }),
      ...extra,
    };
  }

  function clockZone(now) {
    if (state.timezoneLabel) return state.timezoneLabel.toUpperCase();
    try {
      const part = new Intl.DateTimeFormat("en-US", timeZoneOptions({
        timeZoneName: "short",
      })).formatToParts(now).find(item => item.type === "timeZoneName");
      return String(part?.value || "LOCAL").toUpperCase();
    } catch {
      return "LOCAL";
    }
  }

  function renderClock(now) {
    let parts;
    try {
      parts = new Intl.DateTimeFormat("en-US", timeZoneOptions({
        hour: "numeric",
        minute: "2-digit",
        ...(state.showSeconds ? { second: "2-digit" } : {}),
        hour12: state.hour12,
      })).formatToParts(now);
    } catch {
      parts = new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        minute: "2-digit",
        second: state.showSeconds ? "2-digit" : undefined,
        hour12: state.hour12,
      }).formatToParts(now);
    }
    const period = parts.find(part => part.type === "dayPeriod")?.value || "";
    const digits = parts
      .filter(part => ["hour", "minute", "second", "literal"].includes(part.type))
      .map(part => part.value.replace(/\s+/g, ""))
      .join("")
      .replace(/\s+/g, "");
    value.replaceChildren(document.createTextNode(digits));
    if (period) {
      const suffix = document.createElement("span");
      suffix.className = "period";
      suffix.textContent = period;
      value.append(suffix);
    }
    zone.textContent = clockZone(now);
    mode.textContent = state.hour12 ? "12-HOUR" : "24-HOUR";
    if (state.showDate) {
      try {
        detail.textContent = new Intl.DateTimeFormat("en-US", timeZoneOptions({
          weekday: "short",
          month: "short",
          day: "numeric",
        })).format(now).toUpperCase();
      } catch {
        detail.textContent = now.toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
        }).toUpperCase();
      }
    } else {
      detail.textContent = lineLayout ? "" : "CURRENT TIME";
    }
    tool.classList.remove("complete");
  }

  function effectiveMilliseconds(now) {
    if (!state.running) {
      return kind === "countdown" ? state.remainingMs : state.elapsedMs;
    }
    const delta = Math.max(0, now.getTime() - state.startedAt);
    return kind === "countdown"
      ? Math.max(0, state.remainingMs - delta)
      : Math.min(359999000, state.elapsedMs + delta);
  }

  function timerMarkup(milliseconds) {
    const totalTenths = Math.max(0, Math.floor(milliseconds / 100));
    const totalSeconds = Math.floor(totalTenths / 10);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor(totalSeconds / 60) % 60;
    const seconds = totalSeconds % 60;
    const digits = [hours, minutes, seconds]
      .map(number => String(number).padStart(2, "0"))
      .join(":");
    value.replaceChildren(document.createTextNode(digits));
    if (state.showTenths) {
      const tenths = document.createElement("span");
      tenths.className = "tenths";
      tenths.textContent = `.${totalTenths % 10}`;
      value.append(tenths);
    }
  }

  function reportAudioState(value = audioContext?.state || "uninitialized") {
    document.documentElement.dataset.audioState = value;
    document.documentElement.dataset.audioOutputCount = String(
      activeSoundOutputs.size,
    );
  }

  async function ensureAudioContextRunning(AudioContextClass) {
    if (!audioContext || audioContext.state === "closed") {
      audioContext = new AudioContextClass();
      audioContext.onstatechange = () => reportAudioState();
    }
    if (audioContext.state !== "running" && typeof audioContext.resume === "function") {
      await new Promise(resolve => {
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          resolve();
        };
        const timeout = setTimeout(finish, AUDIO_RESUME_TIMEOUT_MS);
        Promise.resolve(audioContext.resume()).then(finish, finish);
      });
    }
    reportAudioState();
    return audioContext.state === "running";
  }

  async function loadCompletionSoundBuffer(soundUrl) {
    if (!soundUrl) return null;
    if (completionSoundBuffers.has(soundUrl)) {
      return completionSoundBuffers.get(soundUrl);
    }
    if (completionSoundLoads.has(soundUrl)) {
      return completionSoundLoads.get(soundUrl);
    }
    if (
      !audioContext
      || typeof audioContext.decodeAudioData !== "function"
      || typeof fetch !== "function"
    ) return null;
    const pending = (async () => {
      try {
        const response = await fetch(soundUrl, {
          cache: "force-cache",
          credentials: "same-origin",
        });
        if (!response.ok) return null;
        const declaredSize = Number(response.headers?.get?.("Content-Length") || 0);
        if (declaredSize > MAX_COMPLETION_SOUND_BYTES) return null;
        const encoded = await response.arrayBuffer();
        if (encoded.byteLength > MAX_COMPLETION_SOUND_BYTES) return null;
        const decoded = await audioContext.decodeAudioData(encoded.slice(0));
        if (!decoded) return null;
        if (completionSoundBuffers.size >= 4) completionSoundBuffers.clear();
        completionSoundBuffers.set(soundUrl, decoded);
        return decoded;
      } catch {
        return null;
      } finally {
        completionSoundLoads.delete(soundUrl);
      }
    })();
    completionSoundLoads.set(soundUrl, pending);
    return pending;
  }

  async function playCompletionSound(force = false, override = {}) {
    const playbackState = normalize({
      ...state,
      ...(override && typeof override === "object" ? override : {}),
    });
    if (
      kind !== "countdown"
      || (!force && !playbackState.soundEnabled)
    ) return false;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      reportAudioState("unavailable");
      return false;
    }
    let releaseOutput = null;
    try {
      if (!await ensureAudioContextRunning(AudioContextClass)) return false;
      const selectedCustomSound = customSoundPath(playbackState.customSound);
      const soundUrl = playbackState.soundPreset === "challenge-complete"
        ? COMPLETION_SOUND_URL
        : (
          playbackState.soundPreset === "custom"
            ? (selectedCustomSound ? `/${selectedCustomSound}` : "")
            : ""
        );
      const decodedBuffer = await loadCompletionSoundBuffer(soundUrl);
      const start = audioContext.currentTime + .025;
      const output = audioContext.createGain();
      activeSoundOutputs.add(output);
      reportAudioState();
      let cleanupTimer = null;
      let outputReleased = false;
      releaseOutput = () => {
        if (outputReleased) return;
        outputReleased = true;
        if (cleanupTimer !== null) clearTimeout(cleanupTimer);
        try { output.disconnect(); } catch { /* The node may already be detached. */ }
        activeSoundOutputs.delete(output);
        reportAudioState();
      };
      const volume = clamp(playbackState.soundVolume, 0, 1);
      if (
        decodedBuffer
        && typeof audioContext.createBufferSource === "function"
      ) {
        const source = audioContext.createBufferSource();
        source.buffer = decodedBuffer;
        output.gain.setValueAtTime(Math.max(.0001, volume * .6), start);
        source.connect(output);
        output.connect(audioContext.destination);
        source.addEventListener("ended", releaseOutput, { once: true });
        cleanupTimer = setTimeout(
          releaseOutput,
          Math.max(1_500, Math.ceil((Number(decodedBuffer.duration) + 1) * 1000)),
        );
        source.start(start);
        document.documentElement.dataset.soundPreset = playbackState.soundPreset;
        soundPlayCount += 1;
        document.documentElement.dataset.soundPlayCount = String(soundPlayCount);
        reportAudioState();
        return true;
      }

      cleanupTimer = setTimeout(releaseOutput, 1_500);
      output.gain.setValueAtTime(Math.max(.0001, volume * .14), start);
      output.gain.exponentialRampToValueAtTime(.0001, start + .94);
      output.connect(audioContext.destination);
      let finalOscillator = null;
      [
        { frequency: 523.25, delay: 0, duration: .2 },
        { frequency: 659.25, delay: .12, duration: .22 },
        { frequency: 783.99, delay: .27, duration: .26 },
        { frequency: 1046.5, delay: .46, duration: .42 },
      ].forEach(note => {
        const oscillator = audioContext.createOscillator();
        const envelope = audioContext.createGain();
        const noteStart = start + note.delay;
        const noteEnd = noteStart + note.duration;
        oscillator.type = "square";
        oscillator.frequency.setValueAtTime(note.frequency, noteStart);
        envelope.gain.setValueAtTime(.0001, noteStart);
        envelope.gain.exponentialRampToValueAtTime(1, noteStart + .012);
        envelope.gain.exponentialRampToValueAtTime(.0001, noteEnd);
        oscillator.connect(envelope);
        envelope.connect(output);
        oscillator.start(noteStart);
        oscillator.stop(noteEnd + .02);
        finalOscillator = oscillator;
      });
      finalOscillator?.addEventListener(
        "ended",
        releaseOutput,
        { once: true },
      );
      document.documentElement.dataset.soundPreset = "block-chime";
      soundPlayCount += 1;
      document.documentElement.dataset.soundPlayCount = String(soundPlayCount);
      reportAudioState();
      return true;
    } catch {
      releaseOutput?.();
      reportAudioState("failed");
      return false;
    }
  }

  function renderTimer(now) {
    const milliseconds = effectiveMilliseconds(now);
    const finished = kind === "countdown" && milliseconds <= 0;
    const compactTimer = lineLayout && !state.showLabel;
    if (kind === "countdown") {
      if (!finished && state.running) {
        completionObservedRunning = true;
        completionSoundPlayed = false;
      } else if (
        finished
        && completionObservedRunning
        && !completionSoundPlayed
      ) {
        completionSoundPlayed = true;
        void playCompletionSound();
      } else if (
        !finished
        && !state.running
        && milliseconds >= state.durationSeconds * 1000
      ) {
        completionObservedRunning = false;
        completionSoundPlayed = false;
      }
    }
    timerMarkup(milliseconds);
    mode.textContent = kind === "countdown" ? "COUNTDOWN" : "STOPWATCH";
    if (finished && compactTimer) {
      zone.textContent = "";
      detail.textContent = "";
    } else if (compactTimer) {
      zone.textContent = "";
      detail.textContent = kind === "countdown" ? "TIME REMAINING" : "TIME ELAPSED";
    } else if (finished) {
      zone.textContent = state.finishText;
      detail.textContent = "COMPLETE";
    } else if (state.running) {
      zone.textContent = "RUNNING";
      detail.textContent = kind === "countdown" ? "TIME REMAINING" : "ELAPSED TIME";
    } else {
      zone.textContent = milliseconds > 0 ? "PAUSED" : "READY";
      detail.textContent = kind === "countdown" ? "TIME REMAINING" : "ELAPSED TIME";
    }
    tool.classList.toggle("complete", finished);
  }

  function render() {
    const now = new Date();
    if (kind === "clock") renderClock(now);
    else renderTimer(now);
  }

  function setState(patch = {}) {
    state = normalize(patch);
    applyAppearance();
    render();
  }

  function scheduleTick() {
    const delay = kind === "clock"
      ? (state.showSeconds ? 200 : 1000)
      : (state.showTenths ? 50 : 200);
    setTimeout(() => {
      render();
      scheduleTick();
    }, delay);
  }

  if (customizerMode) {
    window.addEventListener("message", event => {
      const message = event.data;
      if (
        event.source === window.parent
        && message?.type === "overlay-studio-test-sound"
        && message.overlayType === overlayType
        && String(message.instanceId || "") === instanceId
      ) {
        setState(message.state || {});
        const source = event.source;
        const origin = event.origin;
        void playCompletionSound(true).then(ok => {
          source?.postMessage(
            {
              type: "overlay-studio-test-sound-result",
              requestId: String(message.requestId || ""),
              overlayType,
              instanceId,
              ok,
              audioState: document.documentElement.dataset.audioState,
              soundPreset: document.documentElement.dataset.soundPreset,
            },
            origin,
          );
        });
        return;
      }
      if (
        event.source !== window.parent
        || message?.type !== "overlay-studio-draft"
        || message.overlayType !== overlayType
        || String(message.instanceId || "") !== instanceId
      ) return;
      setState(message.state || {});
    });
  }

  function connect() {
    if (location.protocol === "file:" || !("WebSocket" in window)) return;
    let socket;
    try {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${location.host}/ws`);
    } catch { return; }
    socket.onmessage = event => {
      if (typeof event.data !== "string" || event.data.length > 64 * 1024) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (
        message?.type === "time-tool-sound"
        && message.overlayType === overlayType
        && String(message.instanceId || "") === instanceId
      ) {
        void playCompletionSound(true, message.state || {});
        return;
      }
      if (
        message?.type !== "time-tool"
        || message.overlayType !== overlayType
        || String(message.instanceId || "") !== instanceId
      ) return;
      setState(message.state || {});
    };
    socket.onclose = () => setTimeout(connect, 2000);
  }

  async function loadInstalledState() {
    if (!instanceId || location.protocol === "file:") return;
    try {
      const response = await fetch(`/api/time-tool?i=${encodeURIComponent(instanceId)}`, {
        cache: "no-store",
      });
      if (!response.ok) return;
      setState(await response.json());
    } catch {
      // Defaults keep the preview useful while the local server reconnects.
    }
  }

  const demoSeconds = catalogMode && query.has("demoSeconds")
    ? Math.round(clamp(query.get("demoSeconds"), 1, 359999))
    : null;
  const demoRunning = catalogMode && query.get("demoRunning") === "1";
  const demoMinimal = catalogMode && query.get("demoMinimal") === "1";
  if (catalogMode && kind === "stopwatch") {
    state = {
      ...state,
      elapsedMs: demoSeconds === null ? 5_025_000 : demoSeconds * 1000,
      running: demoRunning,
      startedAt: demoRunning ? Date.now() : 0,
      showLabel: demoMinimal ? false : state.showLabel,
    };
  } else if (catalogMode && kind === "countdown") {
    const durationSeconds = demoSeconds === null ? 185 : demoSeconds;
    state = {
      ...state,
      durationSeconds,
      remainingMs: durationSeconds * 1000,
      running: demoRunning,
      startedAt: demoRunning ? Date.now() : 0,
      showLabel: demoMinimal ? false : state.showLabel,
    };
  }
  setState(state);
  if (kind === "countdown") {
    document.documentElement.dataset.soundPlayCount = "0";
    document.documentElement.dataset.audioState = "uninitialized";
    document.documentElement.dataset.audioOutputCount = "0";
    document.documentElement.dataset.soundPreset = "uninitialized";
    document.addEventListener("pointerdown", () => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!audioContext && AudioContextClass) {
        try {
          audioContext = new AudioContextClass();
          audioContext.onstatechange = () => reportAudioState();
        } catch {
          reportAudioState("failed");
        }
      }
      if (audioContext?.state === "suspended") {
        void audioContext.resume().then(
          () => reportAudioState(),
          () => reportAudioState(),
        );
      }
    });
  }
  scheduleTick();
  if (!customizerMode && !catalogMode) {
    loadInstalledState();
    connect();
  }
  window.pixelTimeTool = {
    get state() { return { ...state }; },
    get soundPlayCount() { return soundPlayCount; },
    get audioState() { return audioContext?.state || "uninitialized"; },
    get activeSoundOutputCount() { return activeSoundOutputs.size; },
    setState,
    testSound: () => playCompletionSound(true),
  };
})();
