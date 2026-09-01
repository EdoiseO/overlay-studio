import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const runtimeSource = fs.readFileSync(
  new URL("../assets/pixel-time.js", import.meta.url),
  "utf8",
);

function makeHarness(ContextClass, { fetchImpl } = {}) {
  const stats = {
    gainNodes: 0,
    outputDisconnects: 0,
    oscillatorNodes: 0,
    bufferSources: 0,
    fetchCalls: 0,
    decodeCalls: 0,
  };
  const timers = new Map();
  let nextTimer = 1;
  const setTimeout = (callback, delay) => {
    const id = nextTimer++;
    if (delay === 500) queueMicrotask(callback);
    else timers.set(id, callback);
    return id;
  };
  const clearTimeout = id => timers.delete(id);
  const parameter = {
    setValueAtTime() {},
    exponentialRampToValueAtTime() {},
  };

  class Context extends ContextClass {
    constructor() {
      super(stats, parameter);
    }
  }

  const classList = { add() {}, remove() {}, toggle() {} };
  const element = () => ({
    classList,
    style: { setProperty() {} },
    textContent: "",
    replaceChildren() {},
    append() {},
  });
  const elements = new Map([
    ["pixelTime", element()],
    ["timeLabel", element()],
    ["timeZone", element()],
    ["timeValue", element()],
    ["timeDetail", element()],
    ["timeMode", element()],
  ]);
  const document = {
    documentElement: {
      classList,
      dataset: {},
      style: { setProperty() {} },
    },
    getElementById: id => elements.get(id),
    createTextNode: text => ({ textContent: text }),
    createElement: () => element(),
    addEventListener() {},
  };
  const location = {
    search: "?customizer=1&i=audio-test",
    protocol: "file:",
    host: "127.0.0.1",
  };
  const window = {
    PIXEL_TIME_TOOL: {
      overlayType: "pixel-countdown-line",
      kind: "countdown",
      layout: "line",
    },
    AudioContext: Context,
    webkitAudioContext: null,
    parent: { postMessage() {} },
    addEventListener() {},
  };
  const sandbox = {
    window,
    document,
    location,
    URLSearchParams,
    Intl,
    Date,
    Promise,
    queueMicrotask,
    setTimeout,
    clearTimeout,
    console,
  };
  if (fetchImpl) {
    sandbox.fetch = async (...args) => {
      stats.fetchCalls += 1;
      return fetchImpl(...args);
    };
  }
  vm.createContext(sandbox);
  vm.runInContext(runtimeSource, sandbox, { filename: "pixel-time.js" });
  return { tool: window.pixelTimeTool, stats, document };
}

class RunningContext {
  constructor(stats, parameter) {
    this.stats = stats;
    this.parameter = parameter;
    this.state = "running";
    this.currentTime = 1;
    this.destination = {};
  }

  createGain() {
    this.stats.gainNodes += 1;
    return {
      gain: this.parameter,
      connect() {},
      disconnect: () => {
        this.stats.outputDisconnects += 1;
      },
    };
  }

  createOscillator() {
    this.stats.oscillatorNodes += 1;
    return {
      frequency: this.parameter,
      connect() {},
      start() {},
      stop() {},
      addEventListener: (_type, callback) => queueMicrotask(callback),
    };
  }
}

class SampleContext extends RunningContext {
  async decodeAudioData() {
    this.stats.decodeCalls += 1;
    return { duration: 0.75 };
  }

  createBufferSource() {
    this.stats.bufferSources += 1;
    return {
      buffer: null,
      connect() {},
      start() {},
      addEventListener: (_type, callback) => queueMicrotask(callback),
    };
  }
}

class BlockedContext extends RunningContext {
  constructor(...args) {
    super(...args);
    this.state = "suspended";
  }

  async resume() {
    // A browser may resolve resume() while still requiring a user gesture.
  }
}

class FailedContext extends RunningContext {
  createOscillator() {
    throw new Error("oscillator creation failed");
  }
}

{
  const { tool, stats, document } = makeHarness(RunningContext);
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(tool.soundPlayCount, 1);
  assert.equal(stats.gainNodes, 5);
  assert.equal(stats.oscillatorNodes, 4);
  assert.equal(stats.outputDisconnects, 1);
  assert.equal(tool.activeSoundOutputCount, 0);
  assert.equal(document.documentElement.dataset.audioState, "running");
  assert.equal(document.documentElement.dataset.soundPreset, "block-chime");
}

{
  const fetchImpl = async () => ({
    ok: true,
    headers: { get: () => "32" },
    arrayBuffer: async () => new ArrayBuffer(32),
  });
  const { tool, stats, document } = makeHarness(
    SampleContext,
    { fetchImpl },
  );
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(tool.soundPlayCount, 2);
  assert.equal(stats.fetchCalls, 1);
  assert.equal(stats.decodeCalls, 1);
  assert.equal(stats.bufferSources, 2);
  assert.equal(stats.oscillatorNodes, 0);
  assert.equal(stats.gainNodes, 2);
  assert.equal(stats.outputDisconnects, 2);
  assert.equal(tool.activeSoundOutputCount, 0);
  assert.equal(document.documentElement.dataset.soundPreset, "challenge-complete");
}

{
  const { tool, stats, document } = makeHarness(
    SampleContext,
    { fetchImpl: async () => ({ ok: false }) },
  );
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(stats.fetchCalls, 2);
  assert.equal(stats.decodeCalls, 0);
  assert.equal(stats.oscillatorNodes, 8);
  assert.equal(document.documentElement.dataset.soundPreset, "block-chime");
}

{
  let requestedUrl = "";
  const { tool, stats, document } = makeHarness(
    SampleContext,
    {
      fetchImpl: async url => {
        requestedUrl = url;
        return {
          ok: true,
          headers: { get: () => "48" },
          arrayBuffer: async () => new ArrayBuffer(48),
        };
      },
    },
  );
  tool.setState({
    soundPreset: "custom",
    customSound: "user-assets/sounds/raid-alert.ogg",
  });
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(requestedUrl, "/user-assets/sounds/raid-alert.ogg");
  assert.equal(stats.fetchCalls, 1);
  assert.equal(stats.bufferSources, 1);
  assert.equal(stats.oscillatorNodes, 0);
  assert.equal(document.documentElement.dataset.soundPreset, "custom");
}

{
  const { tool, stats, document } = makeHarness(
    SampleContext,
    { fetchImpl: async () => { throw new Error("should not fetch"); } },
  );
  tool.setState({
    soundPreset: "custom",
    customSound: "https://example.com/tracker.mp3",
  });
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(stats.fetchCalls, 0);
  assert.equal(stats.oscillatorNodes, 4);
  assert.equal(document.documentElement.dataset.soundPreset, "block-chime");
}

{
  const { tool, stats, document } = makeHarness(
    SampleContext,
    { fetchImpl: async () => { throw new Error("should not fetch"); } },
  );
  tool.setState({ soundPreset: "block-chime" });
  assert.equal(await tool.testSound(), true);
  await Promise.resolve();
  assert.equal(stats.fetchCalls, 0);
  assert.equal(stats.oscillatorNodes, 4);
  assert.equal(document.documentElement.dataset.soundPreset, "block-chime");
}

{
  const { tool, stats, document } = makeHarness(BlockedContext);
  assert.equal(await tool.testSound(), false);
  assert.equal(tool.soundPlayCount, 0);
  assert.equal(stats.gainNodes, 0);
  assert.equal(stats.outputDisconnects, 0);
  assert.equal(tool.activeSoundOutputCount, 0);
  assert.equal(document.documentElement.dataset.audioState, "suspended");
}

{
  const { tool, stats, document } = makeHarness(FailedContext);
  assert.equal(await tool.testSound(), false);
  assert.equal(tool.soundPlayCount, 0);
  assert.equal(stats.gainNodes, 1);
  assert.equal(stats.outputDisconnects, 1);
  assert.equal(tool.activeSoundOutputCount, 0);
  assert.equal(document.documentElement.dataset.audioState, "failed");
}
