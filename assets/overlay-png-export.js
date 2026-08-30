(() => {
  "use strict";

  const REQUEST_TYPE = "overlay-studio-export-request";
  const RESULT_TYPE = "overlay-studio-export-result";
  const OUTPUT_HEIGHTS = new Set([256, 512, 1024]);
  const MAX_OUTPUT_WIDTH = 8192;
  const MAX_OUTPUT_PIXELS = 12 * 1024 * 1024;
  const XHTML_NS = "http://www.w3.org/1999/xhtml";
  const scriptUrl = document.currentScript?.src || "/assets/overlay-png-export.js";
  const fontCssUrl = new URL("./fonts/overlay-fonts.css", scriptUrl).href;
  const bundledFamilies = [
    "Anton",
    "Archivo Black",
    "Fredoka",
    "Minecraftia",
    "Montserrat",
    "Nunito",
    "Poppins",
  ];

  let registration = null;
  let fontCssPromise = null;
  const dataUrlCache = new Map();

  const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));

  function boundedText(value, maximum = 220) {
    return String(value || "")
      .replace(/[\u0000-\u001f\u007f]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, maximum);
  }

  function normalizePadding(value) {
    const source = value && typeof value === "object" ? value : {};
    const side = name => {
      const numeric = Number(source[name]);
      return Math.max(4, Math.min(512, Number.isFinite(numeric) ? numeric : 12));
    };
    return {
      top: side("top"),
      right: side("right"),
      bottom: side("bottom"),
      left: side("left"),
    };
  }

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("A required asset could not be read"));
      reader.readAsDataURL(blob);
    });
  }

  async function fetchDataUrl(url) {
    const absolute = new URL(url, location.href).href;
    if (absolute.startsWith("data:")) return absolute;
    if (!dataUrlCache.has(absolute)) {
      dataUrlCache.set(absolute, (async () => {
        const response = await fetch(absolute, { cache: "force-cache" });
        if (!response.ok) {
          throw new Error(`A required export asset returned ${response.status}`);
        }
        return blobToDataUrl(await response.blob());
      })());
    }
    return dataUrlCache.get(absolute);
  }

  async function fontCssFor(target) {
    const usedFamilies = new Set();
    for (const element of [target, ...target.querySelectorAll("*")]) {
      const family = getComputedStyle(element).fontFamily.toLowerCase();
      for (const bundled of bundledFamilies) {
        if (family.includes(bundled.toLowerCase())) usedFamilies.add(bundled);
      }
    }
    if (!usedFamilies.size) return "";

    if (!fontCssPromise) {
      fontCssPromise = fetch(fontCssUrl, { cache: "force-cache" }).then(response => {
        if (!response.ok) throw new Error("The local font bundle is unavailable");
        return response.text();
      });
    }
    const source = await fontCssPromise;
    const blocks = source.match(/@font-face\s*\{[^}]*\}/g) || [];
    const selected = blocks.filter(block => {
      const family = block.match(/font-family:\s*['\"]([^'\"]+)['\"]/i)?.[1];
      return family && usedFamilies.has(family);
    });

    return (await Promise.all(selected.map(async block => {
      let inlined = block;
      const matches = [
        ...block.matchAll(/url\(([^)]+\.(?:woff2?|ttf|otf))\)/gi),
      ];
      for (const match of matches) {
        const relative = match[1].trim().replace(/^['\"]|['\"]$/g, "");
        const absolute = new URL(relative, fontCssUrl).href;
        inlined = inlined.replace(match[0], `url(${await fetchDataUrl(absolute)})`);
      }
      return inlined;
    }))).join("\n");
  }

  function inlineComputedStyles(source, clone) {
    const sourceElements = [source, ...source.querySelectorAll("*")];
    const cloneElements = [clone, ...clone.querySelectorAll("*")];
    if (sourceElements.length !== cloneElements.length) {
      throw new Error("The overlay changed while it was being prepared");
    }
    sourceElements.forEach((element, index) => {
      const computed = getComputedStyle(element);
      const cloneStyle = cloneElements[index].style;
      for (let propertyIndex = 0; propertyIndex < computed.length; propertyIndex += 1) {
        const property = computed[propertyIndex];
        cloneStyle.setProperty(
          property,
          computed.getPropertyValue(property),
          computed.getPropertyPriority(property),
        );
      }
    });
  }

  async function inlineImages(source, clone) {
    const sourceImages = [...source.querySelectorAll("img")];
    const cloneImages = [...clone.querySelectorAll("img")];
    for (let index = 0; index < sourceImages.length; index += 1) {
      const original = sourceImages[index];
      const copy = cloneImages[index];
      if (!copy) throw new Error("An overlay image changed during export");
      const sourceUrl = original.currentSrc || original.src;
      if (!sourceUrl) continue;
      try {
        copy.src = await fetchDataUrl(sourceUrl);
        copy.removeAttribute("srcset");
      } catch {
        throw new Error("An overlay image could not be embedded safely");
      }
    }
  }

  function loadSvg(svgText) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("The browser could not rasterize this overlay"));
      image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgText)}`;
    });
  }

  function alphaRowHasContent(pixels, width, row) {
    const start = row * width * 4 + 3;
    const end = start + width * 4;
    for (let offset = start; offset < end; offset += 4) {
      if (pixels[offset] !== 0) return true;
    }
    return false;
  }

  function alphaColumnHasContent(pixels, width, height, column) {
    for (let row = 0; row < height; row += 1) {
      if (pixels[(row * width + column) * 4 + 3] !== 0) return true;
    }
    return false;
  }

  function horizontalAlphaBounds(context, width, height) {
    const pixels = context.getImageData(0, 0, width, height).data;
    const touchesEdge = (
      alphaRowHasContent(pixels, width, 0)
      || alphaRowHasContent(pixels, width, height - 1)
      || alphaColumnHasContent(pixels, width, height, 0)
      || alphaColumnHasContent(pixels, width, height, width - 1)
    );
    if (touchesEdge) return { minX: 0, maxX: width - 1, touchesEdge: true };

    let minX = -1;
    for (let column = 1; column < width - 1; column += 1) {
      if (alphaColumnHasContent(pixels, width, height, column)) {
        minX = column;
        break;
      }
    }
    if (minX < 0) return null;

    let maxX = minX;
    for (let column = width - 2; column > minX; column -= 1) {
      if (alphaColumnHasContent(pixels, width, height, column)) {
        maxX = column;
        break;
      }
    }
    return { minX, maxX, touchesEdge: false };
  }

  async function capture(targetHeight) {
    if (!registration) throw new Error("This overlay is not ready for PNG export");
    if (!OUTPUT_HEIGHTS.has(targetHeight)) throw new Error("Unsupported export height");

    const rootStyle = document.documentElement.style;
    const previousScale = rootStyle.getPropertyValue("--scale");
    const previousFitScale = rootStyle.getPropertyValue("--fit-scale");
    let restoreAdapter = null;
    try {
      rootStyle.setProperty("--scale", "1");
      rootStyle.setProperty("--fit-scale", "1");
      restoreAdapter = registration.prepare?.() || null;
      await nextFrame();
      rootStyle.setProperty("--fit-scale", "1");
      await nextFrame();
      if (document.fonts?.ready) await document.fonts.ready;

      const target = registration.target();
      if (!(target instanceof Element) || target.closest("[hidden]")) {
        throw new Error("There is nothing visible to export");
      }
      const rect = target.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) {
        throw new Error("There is nothing visible to export");
      }

      const padding = normalizePadding(registration.padding?.());
      const designWidth = Math.ceil(rect.width + padding.left + padding.right);
      const designHeight = Math.ceil(rect.height + padding.top + padding.bottom);
      const outputWidth = Math.max(1, Math.round(designWidth * targetHeight / designHeight));
      if (
        outputWidth > MAX_OUTPUT_WIDTH
        || outputWidth * targetHeight > MAX_OUTPUT_PIXELS
      ) {
        throw new Error("This export is too wide. Reduce its content or output height");
      }

      const clone = target.cloneNode(true);
      inlineComputedStyles(target, clone);
      await inlineImages(target, clone);
      clone.setAttribute("xmlns", XHTML_NS);
      clone.style.setProperty("transform", "none");
      clone.style.setProperty("transform-origin", "center");
      clone.style.setProperty("margin", "0");
      clone.style.setProperty("width", `${rect.width}px`);
      clone.style.setProperty("height", `${rect.height}px`);

      const embeddedFonts = await fontCssFor(target);
      const serialized = new XMLSerializer().serializeToString(clone);
      const svg = [
        `<svg xmlns="http://www.w3.org/2000/svg" width="${designWidth}" height="${designHeight}" viewBox="0 0 ${designWidth} ${designHeight}">`,
        `<foreignObject x="0" y="0" width="${designWidth}" height="${designHeight}">`,
        `<div xmlns="${XHTML_NS}" style="position:relative;width:${designWidth}px;height:${designHeight}px;overflow:visible;">`,
        `<style>${embeddedFonts}*{animation:none!important;transition:none!important;}</style>`,
        `<div style="position:absolute;left:${padding.left}px;top:${padding.top}px;overflow:visible;">${serialized}</div>`,
        "</div></foreignObject></svg>",
      ].join("");

      const image = await loadSvg(svg);
      const canvas = document.createElement("canvas");
      canvas.width = outputWidth;
      canvas.height = targetHeight;
      const context = canvas.getContext("2d", { alpha: true, willReadFrequently: true });
      if (!context) throw new Error("The browser could not create an export canvas");
      context.clearRect(0, 0, outputWidth, targetHeight);
      context.drawImage(image, 0, 0, outputWidth, targetHeight);

      const bounds = horizontalAlphaBounds(context, outputWidth, targetHeight);
      if (!bounds) throw new Error("The exported overlay is fully transparent");
      if (bounds.touchesEdge) {
        throw new Error("An effect reaches the export edge. Reduce the effect size");
      }

      const safety = Math.max(2, Math.ceil(targetHeight * .008));
      const cropLeft = Math.max(0, bounds.minX - safety);
      const cropRight = Math.min(outputWidth - 1, bounds.maxX + safety);
      const cropWidth = cropRight - cropLeft + 1;
      const cropped = document.createElement("canvas");
      cropped.width = cropWidth;
      cropped.height = targetHeight;
      const croppedContext = cropped.getContext("2d", { alpha: true });
      if (!croppedContext) throw new Error("The browser could not finish the export");
      croppedContext.drawImage(
        canvas,
        cropLeft,
        0,
        cropWidth,
        targetHeight,
        0,
        0,
        cropWidth,
        targetHeight,
      );
      return {
        png: cropped.toDataURL("image/png"),
        width: cropWidth,
        height: targetHeight,
      };
    } finally {
      if (typeof restoreAdapter === "function") restoreAdapter();
      if (previousScale) rootStyle.setProperty("--scale", previousScale);
      else rootStyle.removeProperty("--scale");
      if (previousFitScale) rootStyle.setProperty("--fit-scale", previousFitScale);
      else rootStyle.removeProperty("--fit-scale");
    }
  }

  function register(options) {
    if (
      !options
      || typeof options.target !== "function"
      || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(String(options.overlayType || ""))
    ) {
      throw new TypeError("Invalid PNG export registration");
    }
    registration = {
      overlayType: String(options.overlayType),
      instanceId: String(options.instanceId || "").slice(0, 80),
      target: options.target,
      padding: typeof options.padding === "function" ? options.padding : null,
      prepare: typeof options.prepare === "function" ? options.prepare : null,
    };
  }

  addEventListener("message", async event => {
    const request = event.data;
    if (
      event.source !== window.parent
      || request?.type !== REQUEST_TYPE
      || !registration
      || request.overlayType !== registration.overlayType
      || String(request.instanceId || "") !== registration.instanceId
      || !/^[a-z0-9-]{8,80}$/.test(String(request.requestId || ""))
    ) return;

    const response = {
      type: RESULT_TYPE,
      requestId: request.requestId,
      overlayType: registration.overlayType,
      instanceId: registration.instanceId,
    };
    try {
      Object.assign(response, { ok: true, ...await capture(Number(request.targetHeight)) });
    } catch (error) {
      Object.assign(response, {
        ok: false,
        detail: boundedText(error?.message || "PNG export failed"),
      });
    }
    window.parent.postMessage(response, event.origin);
  });

  window.OverlayPngExport = Object.freeze({
    register,
    exportCurrent: ({ targetHeight = 512 } = {}) => capture(Number(targetHeight)),
  });
})();
