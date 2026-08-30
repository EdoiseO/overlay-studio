import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const runtimeSource = fs.readFileSync(
  new URL("../assets/minecraft-time.js", import.meta.url),
  "utf8",
);

function makeHarness(ContextClass) {
  const stats = {
    gainNodes: 0,
    outputDisconnects: 0,
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
    ["minecraftTime", element()],
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
    MINECRAFT_TIME_TOOL: {
      overlayType: "minecraft-countdown-line",
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
  vm.createContext(sandbox);
  vm.runInContext(runtimeSource, sandbox, { filename: "minecraft-time.js" });
  return { tool: window.minecraftTimeTool, stats, document };
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
    const isOutput = this.stats.gainNodes === 1;
    return {
      gain: this.parameter,
      connect() {},
      disconnect: () => {
        if (isOutput) this.stats.outputDisconnects += 1;
      },
    };
  }

  createOscillator() {
    return {
      frequency: this.parameter,
      connect() {},
      start() {},
      stop() {},
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
  assert.equal(stats.outputDisconnects, 1);
  assert.equal(tool.activeSoundOutputCount, 0);
  assert.equal(document.documentElement.dataset.audioState, "running");
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
