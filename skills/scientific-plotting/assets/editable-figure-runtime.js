/* Scientific Plotting editable-figure interaction runtime.
 * Figure-specific adapters own data, scales, scientific geometry, and annotations.
 * This runtime owns repeatable viewport interaction and export/editor helpers.
 */
(function attachScientificFigureRuntime(global) {
  "use strict";

  const VERSION = "1.0.0";
  const DEFAULT_TRANSIENT_SELECTORS = [
    ".sf-transient",
    ".layout-selected",
    "[data-sf-editor-only]",
    "[data-sf-interaction-surface]",
  ];

  function resolveElement(value, root = document) {
    if (!value) return null;
    return typeof value === "string" ? root.querySelector(value) : value;
  }

  function finiteView(view) {
    const keys = ["xMin", "xMax", "yMin", "yMax"];
    if (!view || !keys.every(key => Number.isFinite(Number(view[key])))) {
      throw new Error("A finite {xMin, xMax, yMin, yMax} view is required.");
    }
    const normalized = Object.fromEntries(keys.map(key => [key, Number(view[key])]));
    if (normalized.xMax <= normalized.xMin || normalized.yMax <= normalized.yMin) {
      throw new Error("View maxima must be greater than minima.");
    }
    return normalized;
  }

  function finiteBounds(bounds) {
    const keys = ["left", "right", "top", "bottom"];
    if (!bounds || !keys.every(key => Number.isFinite(Number(bounds[key])))) {
      throw new Error("Finite plot bounds are required.");
    }
    const normalized = Object.fromEntries(keys.map(key => [key, Number(bounds[key])]));
    if (normalized.right <= normalized.left || normalized.bottom <= normalized.top) {
      throw new Error("Plot bounds must have positive width and height.");
    }
    return normalized;
  }

  function copyView(view) {
    return {xMin: view.xMin, xMax: view.xMax, yMin: view.yMin, yMax: view.yMax};
  }

  function cloneState(state) {
    return typeof structuredClone === "function"
      ? structuredClone(state)
      : JSON.parse(JSON.stringify(state));
  }

  function clampView(view, fullView) {
    const next = copyView(view);
    const fullXSpan = fullView.xMax - fullView.xMin;
    const fullYSpan = fullView.yMax - fullView.yMin;
    const xSpan = Math.min(next.xMax - next.xMin, fullXSpan);
    const ySpan = Math.min(next.yMax - next.yMin, fullYSpan);

    if (next.xMin < fullView.xMin) {
      next.xMin = fullView.xMin;
      next.xMax = next.xMin + xSpan;
    }
    if (next.xMax > fullView.xMax) {
      next.xMax = fullView.xMax;
      next.xMin = next.xMax - xSpan;
    }
    if (next.yMin < fullView.yMin) {
      next.yMin = fullView.yMin;
      next.yMax = next.yMin + ySpan;
    }
    if (next.yMax > fullView.yMax) {
      next.yMax = fullView.yMax;
      next.yMin = next.yMax - ySpan;
    }
    return next;
  }

  function clientToSvg(surface, event) {
    const svg = surface.ownerSVGElement;
    if (svg?.createSVGPoint && surface.getScreenCTM) {
      const matrix = surface.getScreenCTM();
      if (matrix) {
        const point = svg.createSVGPoint();
        point.x = event.clientX;
        point.y = event.clientY;
        return point.matrixTransform(matrix.inverse());
      }
    }
    const box = surface.getBoundingClientRect();
    const viewBox = svg?.viewBox?.baseVal;
    const width = viewBox?.width || box.width;
    const height = viewBox?.height || box.height;
    return {
      x: (event.clientX - box.left) / box.width * width,
      y: (event.clientY - box.top) / box.height * height,
    };
  }

  function createController(options) {
    const root = resolveElement(options.root) || document;
    const surface = resolveElement(options.surface, root);
    const brush = resolveElement(options.brush, root);
    if (!surface) throw new Error("ScientificFigureRuntime requires an interaction surface.");

    const bounds = finiteBounds(options.plotBounds);
    const fullView = finiteView(options.fullView);
    const hooks = options.hooks || {};
    const transforms = options.transforms || {};
    const clampToFullView = options.clampToFullView !== false;
    const minimumDrag = Number(options.minimumDrag ?? 5);
    let view = finiteView(options.initialView || fullView);
    let pointerMode = options.pointerMode === "pan" ? "pan" : "zoom";
    let enabled = true;
    let drag = null;

    const actionElements = new Map();
    root.querySelectorAll?.("[data-sf-action]").forEach(element => {
      actionElements.set(element.getAttribute("data-sf-action"), element);
    });

    function svgPoint(event) {
      return options.clientToPlot?.(event) || clientToSvg(surface, event);
    }

    function plotToData(point, sourceView = view) {
      if (transforms.plotToData) {
        return transforms.plotToData({point, view: copyView(sourceView), bounds: {...bounds}});
      }
      return {
        x: sourceView.xMin + (point.x - bounds.left) / (bounds.right - bounds.left) * (sourceView.xMax - sourceView.xMin),
        y: sourceView.yMax - (point.y - bounds.top) / (bounds.bottom - bounds.top) * (sourceView.yMax - sourceView.yMin),
      };
    }

    function insidePlot(point) {
      return point.x >= bounds.left && point.x <= bounds.right && point.y >= bounds.top && point.y <= bounds.bottom;
    }

    function applyView(candidate, reason) {
      let next = finiteView(candidate);
      if (clampToFullView) next = clampView(next, fullView);
      const hookResult = hooks.beforeViewChange?.({next: copyView(next), current: copyView(view), reason});
      if (hookResult === false) return false;
      if (hookResult && hookResult !== true) next = finiteView(hookResult);
      view = next;
      hooks.viewChanged?.({view: copyView(view), reason});
      return true;
    }

    function zoomAt(point, factor, reason = "zoom") {
      if (!enabled || !insidePlot(point)) return false;
      if (transforms.zoomView) {
        return applyView(
          transforms.zoomView({point, factor, view: copyView(view), bounds: {...bounds}}),
          reason,
        );
      }
      const anchor = plotToData(point);
      const xMin = anchor.x - (anchor.x - view.xMin) * factor;
      const xMax = anchor.x + (view.xMax - anchor.x) * factor;
      const yMin = anchor.y - (anchor.y - view.yMin) * factor;
      const yMax = anchor.y + (view.yMax - anchor.y) * factor;
      return applyView({xMin, xMax, yMin, yMax}, reason);
    }

    function setPointerMode(mode) {
      if (!['zoom', 'pan'].includes(mode)) throw new Error(`Unknown pointer mode: ${mode}`);
      pointerMode = mode;
      syncUi();
      hooks.modeChanged?.({pointerMode, enabled});
    }

    function syncUi() {
      const zoomButton = actionElements.get("box-zoom");
      const panButton = actionElements.get("pan");
      zoomButton?.setAttribute("aria-pressed", String(enabled && pointerMode === "zoom"));
      panButton?.setAttribute("aria-pressed", String(enabled && pointerMode === "pan"));
      for (const action of ["box-zoom", "pan", "zoom-in", "zoom-out", "reset-view"]) {
        const element = actionElements.get(action);
        if (element) element.disabled = !enabled;
      }
      surface.classList.toggle("sf-pan-mode", enabled && pointerMode === "pan");
      surface.classList.toggle("sf-runtime-disabled", !enabled);
    }

    function setEnabled(nextEnabled) {
      enabled = Boolean(nextEnabled);
      drag = null;
      hideBrush();
      if (!enabled) hooks.clearInspection?.();
      syncUi();
      hooks.modeChanged?.({pointerMode, enabled});
    }

    function showBrush(start, end) {
      if (!brush) return;
      brush.setAttribute("x", Math.min(start.x, end.x));
      brush.setAttribute("y", Math.min(start.y, end.y));
      brush.setAttribute("width", Math.abs(end.x - start.x));
      brush.setAttribute("height", Math.abs(end.y - start.y));
      brush.setAttribute("visibility", "visible");
    }

    function hideBrush() {
      brush?.setAttribute("visibility", "hidden");
    }

    function onWheel(event) {
      if (!enabled) return;
      const point = svgPoint(event);
      if (!insidePlot(point)) return;
      event.preventDefault();
      const factor = Math.exp(Math.max(-1.2, Math.min(1.2, event.deltaY * 0.0015)));
      zoomAt(point, factor, "wheel");
    }

    function onPointerDown(event) {
      if (!enabled || event.button !== 0) return;
      const point = svgPoint(event);
      if (!insidePlot(point)) return;
      event.preventDefault();
      drag = {start: point, last: point, startView: copyView(view), pointerId: event.pointerId};
      surface.setPointerCapture?.(event.pointerId);
      if (pointerMode === "zoom") showBrush(point, point);
    }

    function onPointerMove(event) {
      const point = svgPoint(event);
      if (!drag) {
        if (!enabled || !insidePlot(point)) return;
        const result = hooks.inspect?.({plot: point, data: plotToData(point), view: copyView(view)});
        if (result == null) hooks.clearInspection?.();
        else hooks.renderInspection?.(result, {plot: point, view: copyView(view)});
        return;
      }
      event.preventDefault();
      drag.last = point;
      if (pointerMode === "zoom") {
        showBrush(drag.start, point);
        return;
      }
      if (transforms.panView) {
        applyView(
          transforms.panView({
            start: drag.start,
            current: point,
            startView: copyView(drag.startView),
            bounds: {...bounds},
          }),
          "pan",
        );
        return;
      }
      const xSpan = drag.startView.xMax - drag.startView.xMin;
      const ySpan = drag.startView.yMax - drag.startView.yMin;
      const dx = (point.x - drag.start.x) / (bounds.right - bounds.left) * xSpan;
      const dy = (point.y - drag.start.y) / (bounds.bottom - bounds.top) * ySpan;
      applyView({
        xMin: drag.startView.xMin - dx,
        xMax: drag.startView.xMax - dx,
        yMin: drag.startView.yMin + dy,
        yMax: drag.startView.yMax + dy,
      }, "pan");
    }

    function onPointerUp(event) {
      if (!drag) return;
      const completed = drag;
      drag = null;
      surface.releasePointerCapture?.(completed.pointerId);
      if (pointerMode !== "zoom") return;
      hideBrush();
      const left = Math.max(bounds.left, Math.min(completed.start.x, completed.last.x));
      const right = Math.min(bounds.right, Math.max(completed.start.x, completed.last.x));
      const top = Math.max(bounds.top, Math.min(completed.start.y, completed.last.y));
      const bottom = Math.min(bounds.bottom, Math.max(completed.start.y, completed.last.y));
      if (right - left < minimumDrag || bottom - top < minimumDrag) return;
      if (transforms.boxView) {
        applyView(
          transforms.boxView({
            rectangle: {left, right, top, bottom},
            startView: copyView(completed.startView),
            bounds: {...bounds},
          }),
          "box-zoom",
        );
        hooks.clearInspection?.();
        return;
      }
      const low = plotToData({x: left, y: bottom}, completed.startView);
      const high = plotToData({x: right, y: top}, completed.startView);
      applyView({xMin: low.x, xMax: high.x, yMin: low.y, yMax: high.y}, "box-zoom");
      hooks.clearInspection?.();
    }

    function onPointerLeave() {
      if (!drag) hooks.clearInspection?.();
    }

    function bindAction(name, handler) {
      actionElements.get(name)?.addEventListener("click", handler);
    }

    surface.addEventListener("wheel", onWheel, {passive: false});
    surface.addEventListener("pointerdown", onPointerDown);
    surface.addEventListener("pointermove", onPointerMove);
    surface.addEventListener("pointerup", onPointerUp);
    surface.addEventListener("pointercancel", onPointerUp);
    surface.addEventListener("pointerleave", onPointerLeave);
    bindAction("box-zoom", () => setPointerMode("zoom"));
    bindAction("pan", () => setPointerMode("pan"));
    bindAction("zoom-in", () => zoomAt({x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2}, 0.8, "button-zoom-in"));
    bindAction("zoom-out", () => zoomAt({x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2}, 1.25, "button-zoom-out"));
    bindAction("reset-view", () => applyView(fullView, "reset"));
    syncUi();

    return Object.freeze({
      version: VERSION,
      getView: () => copyView(view),
      getPointerMode: () => pointerMode,
      isEnabled: () => enabled,
      setView: (next, reason = "adapter") => applyView(next, reason),
      resetView: () => applyView(fullView, "reset"),
      setPointerMode,
      setEnabled,
      zoomAt,
      plotToData,
    });
  }

  function createStateStore(storageKey, version = 1) {
    if (!storageKey) throw new Error("A figure-specific storage key is required.");
    return Object.freeze({
      load() {
        try {
          const payload = JSON.parse(localStorage.getItem(storageKey) || "null");
          return payload?.version === version ? payload.state : null;
        } catch (_error) {
          localStorage.removeItem(storageKey);
          return null;
        }
      },
      save(state) {
        localStorage.setItem(storageKey, JSON.stringify({version, state}));
      },
      clear() {
        localStorage.removeItem(storageKey);
      },
    });
  }

  function createHistory(limit = 30) {
    const entries = [];
    return Object.freeze({
      push(state) {
        entries.push(cloneState(state));
        while (entries.length > limit) entries.shift();
      },
      undo() {
        return entries.length ? entries.pop() : null;
      },
      clear() {
        entries.length = 0;
      },
      size() {
        return entries.length;
      },
    });
  }

  function safeBox(element) {
    try {
      const box = element?.getBBox?.();
      return box && [box.x, box.y, box.width, box.height].every(Number.isFinite) ? box : null;
    } catch (_error) {
      return null;
    }
  }

  function placeHorizontalAxisTitle({title, tickLabels, gapEm = 0.3, fontSizePx, offsetY = 0}) {
    const titleElement = resolveElement(title);
    const labels = Array.from(tickLabels || [])
      .map(value => resolveElement(value))
      .filter(Boolean);
    const titleBox = safeBox(titleElement);
    const tickBoxes = labels.map(safeBox).filter(Boolean);
    if (!titleElement || !titleBox || !tickBoxes.length) return false;
    const baseline = Number(titleElement.getAttribute("y")) || 0;
    const baselineFromTop = baseline - titleBox.y;
    const tickBottom = Math.max(...tickBoxes.map(box => box.y + box.height));
    const nextBaseline = tickBottom + Number(gapEm) * Number(fontSizePx) + baselineFromTop + Number(offsetY);
    titleElement.setAttribute("y", nextBaseline.toFixed(2));
    titleElement.setAttribute("data-gap-method", "bbox");
    titleElement.setAttribute("data-gap-em", String(gapEm));
    return true;
  }

  function sanitizeSvg(svg, extraSelectors = []) {
    const copy = svg.cloneNode(true);
    for (const selector of [...DEFAULT_TRANSIENT_SELECTORS, ...extraSelectors]) {
      copy.querySelectorAll(selector).forEach(element => element.remove());
    }
    copy.querySelectorAll("[data-sf-selected], [data-sf-layout-role], [tabindex]").forEach(element => {
      element.removeAttribute("data-sf-selected");
      element.removeAttribute("data-sf-layout-role");
      element.removeAttribute("tabindex");
    });
    return copy;
  }

  global.ScientificFigureRuntime = Object.freeze({
    version: VERSION,
    createController,
    createHistory,
    createStateStore,
    placeHorizontalAxisTitle,
    sanitizeSvg,
  });
})(globalThis);
