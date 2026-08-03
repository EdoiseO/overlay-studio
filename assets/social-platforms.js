(() => {
  "use strict";

  const ORDER = [
    "twitch", "youtube", "instagram", "x", "twitter", "tiktok",
    "discord", "kick", "facebook", "snapchat", "telegram", "whatsapp",
    "linkedin", "threads", "bluesky", "reddit",
  ];
  const PLATFORMS = {
    twitch:    { name: "Twitch", color: "#9146ff", symbolAsset: "/assets/social-icons/twitch-symbol.png", symbolAssetBare: true, path: "M3 3h18v10.5l-5 5h-3.5L9 21v-2.5H3zM9 7h2v5H9zm5 0h2v5h-2z" },
    youtube:   { name: "YouTube", color: "#ff0000", tileAsset: "/assets/social-icons/youtube-tile.png", wide: true, scale: .94, path: "M23 12s0-3.7-.5-5.4a2.8 2.8 0 0 0-2-2C18.8 4 12 4 12 4s-6.8 0-8.5.6a2.8 2.8 0 0 0-2 2C1 8.3 1 12 1 12s0 3.7.5 5.4a2.8 2.8 0 0 0 2 2C5.2 20 12 20 12 20s6.8 0 8.5-.6a2.8 2.8 0 0 0 2-2C23 15.7 23 12 23 12zM10 15.5v-7l6 3.5z" },
    instagram: {
      name: "Instagram",
      color: "#e1306c",
      tileAsset: "/assets/social-icons/instagram-tile.png",
      scale: .93,
      path: "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zm5 5.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 2a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zm5.8-3.9a1.3 1.3 0 1 0 0 2.6 1.3 1.3 0 0 0 0-2.6z",
      grouped: {
        cssGradient: "linear-gradient(145deg,#4f5bd5 0%,#962fbf 28%,#d62976 52%,#fa7e1e 76%,#feda75 100%)",
        gradient: [[0,"#4f5bd5"],[.28,"#962fbf"],[.52,"#d62976"],[.76,"#fa7e1e"],[1,"#feda75"]],
        details: [
          { d: "M8 5h8a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3z", stroke: 1.8 },
          { d: "M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z", stroke: 1.8 },
          { d: "M17.25 6.35a1.15 1.15 0 1 1 0 2.3 1.15 1.15 0 0 1 0-2.3z", fill: true },
        ],
        path: "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5z",
      },
    },
    x:         { name: "X", color: "#101014", bare: "#ffffff", symbolAsset: "/assets/social-icons/x-symbol.png", scale: .88, path: "M3 3h4.5l4.2 5.7L16.8 3H21l-6.8 8.2L21.4 21h-4.5l-4.6-6.2L7 21H2.8l7.2-8.6z" },
    twitter:   { name: "Twitter", color: "#1d9bf0", dx: .2, dy: .35, scale: .94, path: "M22 5.9c-.7.3-1.5.5-2.3.6a4 4 0 0 0 1.8-2.2c-.8.5-1.7.8-2.6 1a4 4 0 0 0-6.9 3.7A11.4 11.4 0 0 1 3.8 4.6a4 4 0 0 0 1.2 5.4c-.6 0-1.2-.2-1.8-.5a4 4 0 0 0 3.2 4 4 4 0 0 1-1.8.1 4 4 0 0 0 3.7 2.8A8 8 0 0 1 2 18.1a11.3 11.3 0 0 0 6.1 1.8c7.4 0 11.4-6.1 11.4-11.4v-.5c.8-.6 1.5-1.3 2-2.1z" },
    tiktok:    { name: "TikTok", color: "#25f4ee", surface: "#f6f7fb", ink: "#101014", symbolAsset: "/assets/social-icons/tiktok-symbol.png", symbolAssetBare: true, layers: [{ color: "#25f4ee", dx: -1.15, dy: -.7 }, { color: "#fe2c55", dx: 1.15, dy: .7 }, { color: "#101014", bareColor: "#ffffff" }], dx: -1.25, dy: .5, scale: .82, path: "M14.5 2h3.1a5.9 5.9 0 0 0 4.4 4.6v3.2a9 9 0 0 1-4.3-1.3v6a6.6 6.6 0 1 1-5.7-6.5v3.3a3.4 3.4 0 1 0 2.5 3.2z" },
    discord:   { name: "Discord", color: "#5865f2", symbolAsset: "/assets/social-icons/discord-symbol.png", symbolAssetBare: true, dy: .85, scale: .92, path: "M19.3 5.4A16 16 0 0 0 15.5 4l-.3.5a12 12 0 0 1 3 1.5 14 14 0 0 0-12.4 0 12 12 0 0 1 3-1.5L8.5 4a16 16 0 0 0-3.8 1.4C2.3 9 1.7 12.5 2 16a16 16 0 0 0 4.8 2.4l.9-1.4a10 10 0 0 1-1.6-.8l.4-.3a11.4 11.4 0 0 0 9 0l.4.3a10 10 0 0 1-1.6.8l.9 1.4A16 16 0 0 0 22 16c.4-4-.6-7.5-2.7-10.6zM9 14.4a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4zm6 0a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4z" },
    kick:      { name: "Kick", color: "#53fc18", ink: "#101014", symbolAsset: "/assets/social-icons/kick-symbol.png", symbolAssetBare: true, tileAsset: "/assets/social-icons/kick-tile.png", scale: .88, path: "M3 3h6v6h3V6h3V3h6v9h-3v3h3v6h-6v-3h-3v-3H9v6H3z" },
    facebook:  { name: "Facebook", color: "#1877f2", tileAsset: "/assets/social-icons/facebook-round.png", dy: .1, scale: .94, path: "M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z" },
    snapchat:  { name: "Snapchat", color: "#fffc00", ink: "#101014", grouped: { tileInk: "#ffffff", tileStroke: "#101014" }, dy: .9, scale: .9, path: "M12 3c2.6 0 4.4 1.9 4.4 4.4v1.9c.5.2 1-.2 1.5-.1.6.2.4 1-.2 1.4-.5.3-1.1.5-1.1.9 0 .9 2 2.6 3.3 3 .3.1.4.4.2.7-.4.6-1.6.8-2.1 1-.3.1-.3.5-.4.9-.1.3-.3.4-.7.3-.6-.1-1.5-.2-2.3.1-.7.4-1.3 1.4-2.2 1.4s-1.5-1-2.2-1.4c-.8-.3-1.7-.2-2.3-.1-.4.1-.6 0-.7-.3-.1-.4-.1-.8-.4-.9-.5-.2-1.7-.4-2.1-1-.2-.3-.1-.6.2-.7 1.3-.4 3.3-2.1 3.3-3 0-.4-.6-.6-1.1-.9-.6-.4-.8-1.2-.2-1.4.5-.1 1 .3 1.5.1V7.4C7.6 4.9 9.4 3 12 3z" },
    telegram:  { name: "Telegram", color: "#2aabee", tileAsset: "/assets/social-icons/telegram-round.png", dx: .65, scale: .92, path: "M21.9 4.3 18.7 20c-.2 1-.9 1.3-1.8.8l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.1L18.2 6c.4-.4-.1-.6-.6-.2L6.1 13.1l-4.9-1.5c-1-.3-1-1 .2-1.5l19.1-7.4c.9-.3 1.6.2 1.4 1.6z" },
    whatsapp:  { name: "WhatsApp", color: "#25d366", tileAsset: "/assets/social-icons/whatsapp-tile.png", scale: .92, path: "M12 2a10 10 0 0 0-8.6 15L2 22l5.2-1.4A10 10 0 1 0 12 2zm0 2a8 8 0 1 1-4.2 14.8l-.3-.2-2.5.7.7-2.4-.2-.3A8 8 0 0 1 12 4zm-3 4c-.3 0-.7.1-1 .5-.4.4-1 1-1 2.3s1 2.6 1.2 2.8c.1.2 2 3.1 4.9 4.2 2.4.9 2.9.7 3.4.7.5-.1 1.6-.7 1.9-1.3.2-.7.2-1.2.1-1.3l-.6-.3-1.9-.9c-.3-.1-.5-.2-.7.1l-.9 1.1c-.2.2-.3.3-.6.1a8 8 0 0 1-2.4-1.5 9 9 0 0 1-1.6-2c-.2-.3 0-.5.1-.6l.5-.6.3-.5v-.5l-.9-2.1c-.2-.5-.4-.5-.6-.5z" },
    linkedin:  { name: "LinkedIn", color: "#0a66c2", tileAsset: "/assets/social-icons/linkedin-tile.png", dx: -.35, dy: -.15, scale: .9, path: "M4.9 3.5a2.4 2.4 0 1 1 0 4.9 2.4 2.4 0 0 1 0-4.9zM3 9.5h4v11H3zm7 0h3.8v1.5h.1a4.2 4.2 0 0 1 3.8-2c4 0 4.8 2.6 4.8 6v5.5h-4v-4.9c0-1.2 0-2.7-1.7-2.7s-2 1.3-2 2.6v5H10z" },
    threads:   { name: "Threads", color: "#101014", bare: "#ffffff", symbolAsset: "/assets/social-icons/threads-symbol.png", tileAsset: "/assets/social-icons/threads-tile.png", dx: -.6, scale: .9, path: "M12.2 2C6.9 2 3.5 5.6 3.5 12s3.4 10 8.7 10c4.5 0 7.4-2.5 8.1-6.1l-2.4-.5c-.5 2.4-2.4 4.1-5.7 4.1-3.7 0-6-2.6-6-7.5s2.3-7.5 6-7.5c3 0 4.9 1.4 5.5 3.6-1-.4-2.1-.6-3.4-.6-3.2 0-5.3 1.6-5.3 4.1 0 2.4 1.9 4 4.6 4 2.9 0 4.7-1.8 5-4.8h.1c.7 1 1 2.3 1 3.6l2.3-.1c0-5.9-3.4-9.3-8.8-9.3zm.3 8.9c1.2 0 2.2.2 3 .5-.2 2-1.4 3.1-3.2 3.1-1.4 0-2.3-.7-2.3-1.8s1-1.8 2.5-1.8z" },
    bluesky:   { name: "Bluesky", color: "#0085ff", symbolAsset: "/assets/social-icons/bluesky-symbol.png", symbolAssetBare: true, tileAsset: "/assets/social-icons/bluesky-tile.png", dx: 2, dy: 2.2, scale: .95, path: "M12 10.8C10.9 8.7 7.9 4.7 5.1 3 2.4 1.4 1.4 2.3 1.4 4.2c0 1.9 1 6.4 1.7 7.6.7 1.2 2.1 1.6 3.4 1.4-2 .3-3.8 1-1.5 3.6 2.5 2.9 3.5-.6 4-2.4l1-2.6 1 2.6c.5 1.8 1.5 5.3 4 2.4 2.3-2.6.5-3.3-1.5-3.6 1.3.2 2.7-.2 3.4-1.4.7-1.2 1.7-5.7 1.7-7.6 0-1.9-1-2.8-3.7-1.2-2.8 1.7-5.8 5.7-6.9 7.8z" },
    reddit:    { name: "Reddit", color: "#ff4500", tileAsset: "/assets/social-icons/reddit-tile.png", dx: .7, dy: .4, scale: .89, path: "M22 11.2a2.4 2.4 0 0 0-4.1-1.7 11.7 11.7 0 0 0-5.8-1.8l1-4.6 3.2.7a1.9 1.9 0 1 0 .2-1.6l-3.9-.8a.6.6 0 0 0-.7.5l-1.2 5.6a11.7 11.7 0 0 0-5.9 1.8A2.4 2.4 0 1 0 2 14.4a4 4 0 0 0 0 .8c0 3.6 4.2 6.5 9.4 6.5s9.4-2.9 9.4-6.5a4 4 0 0 0 0-.8 2.4 2.4 0 0 0 1.2-3.2zM9.1 14.9a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4zm7.3 2.6c-1.2 1.2-3.5 1.3-4.2 1.3s-3-.1-4.2-1.3a.5.5 0 0 1 .7-.7c.8.8 2.4 1 3.5 1s2.8-.2 3.5-1a.5.5 0 0 1 .7.7zm-1.5-2.6a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4z" },
  };
  const ALIASES = {
    ig: "instagram", yt: "youtube", tt: "tiktok", fb: "facebook",
    snap: "snapchat", tg: "telegram", wa: "whatsapp", li: "linkedin",
    tweet: "twitter",
  };
  const FONTS = {
    montserrat: '"Montserrat", "Segoe UI", system-ui, sans-serif',
    poppins: '"Poppins", "Segoe UI", system-ui, sans-serif',
    archivo: '"Archivo Black", "Segoe UI", system-ui, sans-serif',
    nunito: '"Nunito", "Segoe UI", system-ui, sans-serif',
    anton: '"Anton", "Bahnschrift", system-ui, sans-serif',
    sans: '"Segoe UI", system-ui, sans-serif',
    display: '"Bahnschrift", "Segoe UI Semibold", system-ui, sans-serif',
    round: '"Fredoka", "Segoe UI", system-ui, sans-serif',
    mono: '"Cascadia Mono", Consolas, monospace',
    serif: 'Georgia, "Times New Roman", serif',
  };
  const DEFAULTS = {
    accounts: ORDER.map(platform => ({
      platform,
      enabled: ["twitch", "youtube", "instagram", "tiktok"].includes(platform),
      handle: "yourname",
    })),
    layout: "sticker", mode: "individual", sharedName: "",
    heading: "Stay connected", align: "center", iconShape: "rounded",
    iconBackground: true, size: "medium", brand: true, color: "f6f7fb",
    shellColor: "141418", textColor: "ffffff", font: "display",
    weight: 800, outline: 3, scale: 1, cycle: 4,
    rotatorShape: "capsule", transition: "slide", prefix: "@",
    timer: true, showPlatform: true,
  };
  const CHOICES = {
    layout: new Set(["sticker", "flat", "compact", "stacked", "fused"]),
    mode: new Set(["individual", "shared"]),
    align: new Set(["left", "center", "right"]),
    iconShape: new Set(["rounded", "circle", "square", "diamond", "hex"]),
    size: new Set(["small", "medium", "large"]),
    font: new Set(Object.keys(FONTS)),
    rotatorShape: new Set(["capsule", "rounded", "square", "cut"]),
    transition: new Set(["slide", "fade", "flip"]),
  };
  const ACCOUNT_LIMITS = {
    social: 8,
    "social-rotator": 12,
  };
  const clamp = (value, minimum, maximum, fallback) => {
    const numeric = Number(value);
    return Math.max(minimum, Math.min(maximum, Number.isFinite(numeric) ? numeric : fallback));
  };
  const hex = (value, fallback) => {
    const candidate = String(value || "").trim().replace(/^#/, "").toLowerCase();
    return /^[0-9a-f]{6}$/.test(candidate) ? candidate : fallback;
  };
  const choice = (value, key) => {
    const candidate = String(value || "").trim().toLowerCase();
    return CHOICES[key].has(candidate) ? candidate : DEFAULTS[key];
  };
  const bool = (value, fallback) => (
    typeof value === "boolean" ? value : fallback
  );
  const short = (value, maximum, fallback = "") => {
    const candidate = String(value ?? "").replace(/\s+/g, " ").trim();
    return (candidate || fallback).slice(0, maximum);
  };
  const contrast = value => {
    const candidate = String(value || "").replace(/^#/, "");
    if (!/^[0-9a-f]{6}$/i.test(candidate)) return "#ffffff";
    const channels = [0, 2, 4].map(offset => parseInt(candidate.slice(offset, offset + 2), 16));
    const luminance = channels[0] * .299 + channels[1] * .587 + channels[2] * .114;
    return luminance > 165 ? "#101014" : "#ffffff";
  };

  function normalizeAccounts(raw, overlayType) {
    const supplied = Array.isArray(raw) ? raw : DEFAULTS.accounts;
    const byPlatform = new Map();
    supplied.slice(0, ORDER.length).forEach(item => {
      if (!item || typeof item !== "object") return;
      const platform = String(item.platform || "").toLowerCase();
      if (!PLATFORMS[platform] || byPlatform.has(platform)) return;
      const icon = String(item.icon || "").trim();
      byPlatform.set(platform, {
        platform,
        enabled: Boolean(item.enabled),
        handle: short(String(item.handle ?? "").replace(/^@+/, ""), 64),
        icon: icon && !/^[a-z]+:/i.test(icon) && !icon.includes("..") ? icon.slice(0, 256) : "",
      });
    });
    const limit = ACCOUNT_LIMITS[overlayType] || ORDER.length;
    let enabled = 0;
    return ORDER.map(platform => {
      const account = byPlatform.get(platform) || {
        platform, enabled: false, handle: "yourname", icon: "",
      };
      let selected = account.enabled;
      if (selected && enabled >= limit) selected = false;
      if (selected) enabled += 1;
      return { ...account, enabled: selected };
    });
  }

  function normalize(raw, overlayType) {
    const source = raw && typeof raw === "object" ? raw : {};
    return {
      accounts: normalizeAccounts(source.accounts, overlayType),
      layout: choice(source.layout, "layout"),
      mode: choice(source.mode, "mode"),
      sharedName: short(source.sharedName, 64),
      heading: short(source.heading, 32, DEFAULTS.heading),
      align: choice(source.align, "align"),
      iconShape: choice(source.iconShape, "iconShape"),
      iconBackground: bool(
        source.iconBackground,
        DEFAULTS.iconBackground,
      ),
      size: choice(source.size, "size"),
      brand: bool(source.brand, DEFAULTS.brand),
      color: hex(source.color, DEFAULTS.color),
      shellColor: hex(source.shellColor, DEFAULTS.shellColor),
      textColor: hex(source.textColor, DEFAULTS.textColor),
      font: choice(source.font, "font"),
      weight: Math.round(clamp(source.weight, 300, 900, DEFAULTS.weight)),
      outline: Math.round(clamp(source.outline, 0, 8, DEFAULTS.outline)),
      scale: clamp(source.scale, .5, 2, DEFAULTS.scale),
      cycle: clamp(source.cycle, 1.5, 30, DEFAULTS.cycle),
      rotatorShape: choice(source.rotatorShape, "rotatorShape"),
      transition: choice(source.transition, "transition"),
      prefix: source.prefix === undefined
        ? DEFAULTS.prefix
        : short(source.prefix, 4),
      timer: bool(source.timer, DEFAULTS.timer),
      showPlatform: bool(source.showPlatform, DEFAULTS.showPlatform),
    };
  }

  function queryOverrides(query, overlayType) {
    const result = {};
    const accountChunks = query.get("accounts");
    const accounts = [];
    if (accountChunks !== null) {
      accountChunks.split(",").slice(0, ORDER.length).forEach(chunk => {
        const parts = chunk.split(":").map(part => part.trim());
        const platform = ALIASES[(parts[0] || "").toLowerCase()] || (parts[0] || "").toLowerCase();
        if (!PLATFORMS[platform]) return;
        accounts.push({
          platform, enabled: true, handle: parts[1] || "", icon: parts[2] || "",
        });
      });
    } else {
      ORDER.forEach(platform => {
        const handle = query.get(platform);
        if (handle !== null) accounts.push({ platform, enabled: true, handle });
      });
    }
    if (accounts.length) {
      result.accounts = ORDER.map(platform => (
        accounts.find(account => account.platform === platform)
        || { platform, enabled: false, handle: "yourname" }
      ));
    }
    const scalarKeys = [
      "layout", "mode", "sharedName", "heading", "align", "iconShape",
      "size", "color", "shellColor", "textColor", "font", "weight",
      "outline", "scale", "cycle", "rotatorShape", "transition", "prefix",
    ];
    scalarKeys.forEach(key => {
      if (query.has(key)) result[key] = query.get(key);
    });
    if (query.has("style") && !query.has("rotatorShape")) {
      result.rotatorShape = query.get("style") === "plain" ? "square" : query.get("style");
    }
    ["brand", "iconBackground", "timer", "showPlatform"].forEach(key => {
      if (!query.has(key)) return;
      result[key] = !["off", "false", "0"].includes(String(query.get(key)).toLowerCase());
    });
    return result;
  }

  async function load(instanceId, overlayType, query) {
    let saved = DEFAULTS;
    if (instanceId && location.protocol !== "file:") {
      try {
        const response = await fetch(`/api/config?i=${encodeURIComponent(instanceId)}`, {
          cache: "no-store",
        });
        if (response.ok) {
          const payload = await response.json();
          if (payload.social && typeof payload.social === "object") saved = payload.social;
        }
      } catch {}
    }
    const overrides = queryOverrides(query, overlayType);
    const hasQueryOverride = [
      "accounts", ...ORDER, "layout", "mode", "sharedName", "heading",
      "align", "iconShape", "iconBackground", "size", "brand", "color", "shellColor",
      "textColor", "font", "weight", "outline", "scale", "cycle",
      "rotatorShape", "transition", "prefix", "timer", "showPlatform", "style",
    ].some(key => query.has(key));
    return normalize(
      hasQueryOverride ? { ...saved, ...overrides } : saved,
      overlayType,
    );
  }

  function createVectorGlyph(meta, branded, bare) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.setAttribute("aria-hidden", "true");
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const dx = Number(meta.dx) || 0;
    const dy = Number(meta.dy) || 0;
    const scale = Number(meta.scale) || 1;
    group.setAttribute(
      "transform",
      `translate(${12 + dx} ${12 + dy}) scale(${scale}) translate(-12 -12)`,
    );
    const layers = branded && Array.isArray(meta.layers)
      ? meta.layers
      : [{}];
    layers.forEach(layer => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("fill-rule", "evenodd");
      path.setAttribute("clip-rule", "evenodd");
      path.setAttribute("d", meta.path);
      const layerColor = bare && layer.bareColor
        ? layer.bareColor
        : layer.color;
      if (layerColor) path.setAttribute("fill", layerColor);
      const layerDx = Number(layer.dx) || 0;
      const layerDy = Number(layer.dy) || 0;
      if (layerDx || layerDy) {
        path.setAttribute("transform", `translate(${layerDx} ${layerDy})`);
      }
      group.append(path);
    });
    svg.append(group);
    return svg;
  }

  function createGlyph(platform, branded = true, bare = false, assetKind = "") {
    const meta = PLATFORMS[platform];
    if (!meta) return document.createTextNode("");
    const asset = branded && assetKind === "tile"
      ? meta.tileAsset
      : branded && assetKind === "symbol" && meta.symbolAssetBare
        ? meta.symbolAsset
        : "";
    if (!asset) return createVectorGlyph(meta, branded, bare);

    const image = new Image();
    image.alt = "";
    image.decoding = "async";
    image.draggable = false;
    image.dataset.socialAssetKind = assetKind;
    image.src = asset;
    image.addEventListener("error", () => {
      image.replaceWith(createVectorGlyph(meta, branded, bare));
    }, { once: true });
    return image;
  }

  function listen(instanceId, overlayType, onConfig) {
    const customizerMode =
      new URLSearchParams(location.search).get("customizer") === "1";
    if (customizerMode) {
      window.addEventListener("message", event => {
        if (
          event.source !== window.parent
          || event.data?.type !== "overlay-studio-draft"
          || event.data?.overlayType !== overlayType
          || String(event.data?.instanceId || "") !== instanceId
          || !event.data?.config?.social
        ) return;
        onConfig(normalize(event.data.config.social, overlayType));
      });
    }
    if (location.protocol === "file:" || !("WebSocket" in window)) return;
    const connect = () => {
      let socket;
      try {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        socket = new WebSocket(`${protocol}//${location.host}/ws`);
      } catch {
        setTimeout(connect, 2000);
        return;
      }
      socket.onmessage = event => {
        if (typeof event.data !== "string" || event.data.length > 64 * 1024) return;
        let message;
        try { message = JSON.parse(event.data); } catch { return; }
        if (
          message?.type === "config"
          && String(message.instanceId || "") === instanceId
          && message.config?.social
        ) {
          onConfig(normalize(message.config.social, overlayType));
        }
      };
      socket.onclose = () => setTimeout(connect, 2000);
    };
    connect();
  }

  function deepFreeze(value, seen = new WeakSet()) {
    if (
      value === null
      || (typeof value !== "object" && typeof value !== "function")
      || seen.has(value)
    ) return value;
    seen.add(value);
    for (const key of Reflect.ownKeys(value)) {
      deepFreeze(value[key], seen);
    }
    return Object.freeze(value);
  }

  window.OverlaySocial = deepFreeze({
    ORDER,
    PLATFORMS,
    ALIASES,
    FONTS,
    DEFAULTS,
    ACCOUNT_LIMITS,
    normalize,
    load,
    createGlyph,
    contrast,
    listen,
  });
})();
