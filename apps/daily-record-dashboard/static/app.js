"use strict";

const WORLD_WIDTH = 6000;
const WORLD_HEIGHT = 4000;
const state = {
  date: "",
  today: "",
  document: emptyDocument(),
  selectedId: null,
  mode: "select",
  action: null,
  dirty: false,
  saving: false,
  revision: 0,
  previewDirty: false,
  pendingUploads: 0,
  saveTimer: null,
  loadToken: 0,
  recentDates: [],
  undoStack: [],
  spaceDown: false,
  lastWorldPoint: {x: 260, y: 220},
  idCounter: 0,
  clientId: `client-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`}`.replace(/[^A-Za-z0-9_-]/g, ""),
  syncId: "",
  remoteSyncing: false,
  syncPolling: false,
  syncConflict: false,
  focusMode: false,
  activeTouches: new Map(),
  pinch: null,
  suppressTouchAction: false,
};

const elements = {
  saveState: document.getElementById("saveState"),
  saveText: document.getElementById("saveText"),
  previousDay: document.getElementById("previousDay"),
  nextDay: document.getElementById("nextDay"),
  dateInput: document.getElementById("dateInput"),
  dateLabel: document.getElementById("dateLabel"),
  todayButton: document.getElementById("todayButton"),
  friendlyDate: document.getElementById("friendlyDate"),
  selectTool: document.getElementById("selectTool"),
  textTool: document.getElementById("textTool"),
  penTool: document.getElementById("penTool"),
  eraserTool: document.getElementById("eraserTool"),
  imageUploadButton: document.getElementById("imageUploadButton"),
  imageUploadInput: document.getElementById("imageUploadInput"),
  drawingColor: document.getElementById("drawingColor"),
  drawingWidth: document.getElementById("drawingWidth"),
  sendBackward: document.getElementById("sendBackward"),
  bringForward: document.getElementById("bringForward"),
  undoButton: document.getElementById("undoButton"),
  zoomOut: document.getElementById("zoomOut"),
  zoomIn: document.getElementById("zoomIn"),
  fitView: document.getElementById("fitView"),
  focusCanvas: document.getElementById("focusCanvas"),
  zoomText: document.getElementById("zoomText"),
  canvasViewport: document.getElementById("canvasViewport"),
  canvasWorld: document.getElementById("canvasWorld"),
  strokeLayer: document.getElementById("strokeLayer"),
  elementsLayer: document.getElementById("elementsLayer"),
  canvasHint: document.getElementById("canvasHint"),
  selectionHint: document.getElementById("selectionHint"),
  recentDates: document.getElementById("recentDates"),
  toast: document.getElementById("toast"),
};

function emptyDocument() {
  return {
    elements: [],
    strokes: [],
    camera: {x: 70, y: 60, zoom: 1},
    preview_asset: "",
  };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function createId(prefix) {
  state.idCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${state.idCounter.toString(36)}`;
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 4200);
}

function setSaveState(kind, text) {
  elements.saveState.dataset.state = kind;
  elements.saveText.textContent = text;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error("记录服务返回了无法识别的内容。");
  }
  if (!response.ok || !payload.ok) {
    const error = new Error(payload.error || "操作失败。");
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function localDateText(value) {
  const parsed = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(parsed);
}

function shortDateText(value) {
  const parsed = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("zh-CN", {month: "short", day: "numeric"}).format(parsed);
}

function offsetDate(value, days) {
  const parsed = new Date(`${value}T12:00:00`);
  parsed.setDate(parsed.getDate() + days);
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function normalizeDocument(canvas) {
  if (!canvas || typeof canvas !== "object") return emptyDocument();
  const normalized = emptyDocument();
  normalized.elements = (Array.isArray(canvas.elements) ? canvas.elements : [])
    .filter((item) => item && (item.type === "text" || item.type === "image"))
    .map((item, index) => {
      const base = {
        id: String(item.id || createId("node")),
        type: item.type,
        x: Number(item.x || 0),
        y: Number(item.y || 0),
        w: Number(item.w || 320),
        h: Number(item.h || 140),
        z: Number(item.z ?? index),
      };
      if (item.type === "text") return {...base, text: String(item.text || "")};
      return {
        ...base,
        asset: String(item.asset || ""),
        aspect: Number(item.aspect || (base.w / base.h) || 1),
      };
    });
  normalized.strokes = (Array.isArray(canvas.strokes) ? canvas.strokes : [])
    .filter((stroke) => stroke && Array.isArray(stroke.points))
    .map((stroke) => ({
      id: String(stroke.id || createId("stroke")),
      color: String(stroke.color || "#1f7465"),
      width: Number(stroke.width || 6),
      points: stroke.points.map((point) => [Number(point[0]), Number(point[1])]),
    }));
  if (canvas.camera && typeof canvas.camera === "object") {
    normalized.camera = {
      x: Number(canvas.camera.x || 0),
      y: Number(canvas.camera.y || 0),
      zoom: clamp(Number(canvas.camera.zoom || 1), 0.15, 4),
    };
  }
  normalized.preview_asset = String(canvas.preview_asset || "");
  return normalized;
}

function migrateBlocks(blocks) {
  const migrated = emptyDocument();
  let y = 180;
  let z = 1;
  for (const block of Array.isArray(blocks) ? blocks : []) {
    if (block?.type === "text") {
      const text = String(block.text || "");
      const lines = Math.max(3, text.split("\n").length + 1);
      const height = clamp(lines * 34, 110, 620);
      migrated.elements.push({
        id: createId("text"), type: "text", x: 180, y, w: 560, h: height, z: z++, text,
      });
      y += height + 52;
    } else if (block?.asset) {
      migrated.elements.push({
        id: createId("image"), type: "image", x: 180, y, w: 640, h: 420, z: z++,
        asset: String(block.asset), aspect: 640 / 420, _needsAspect: true,
      });
      y += 472;
    }
  }
  migrated.elements = migrated.elements.filter((item) => item.type !== "text" || item.text.trim());
  return migrated;
}

function hasContent(documentValue = state.document) {
  return documentValue.strokes.length > 0 || documentValue.elements.some((item) => (
    item.type === "image" || (item.type === "text" && item.text.trim())
  ));
}

function markDirty(previewNeeded = true) {
  state.dirty = true;
  state.revision += 1;
  state.previewDirty = state.previewDirty || previewNeeded;
  if (state.syncConflict) {
    setSaveState("error", "等待刷新");
    return;
  }
  setSaveState("dirty", "等待保存");
  syncEmptyHint();
  window.clearTimeout(state.saveTimer);
  state.saveTimer = window.setTimeout(() => saveNote().catch(reportError), 800);
}

function cameraStorageKey(dayText) {
  return `daily-dashboard-camera:${dayText}`;
}

function normalizedCamera(value, fallback = {x: 70, y: 60, zoom: 1}) {
  if (!value || typeof value !== "object") return clone(fallback);
  const x = Number(value.x);
  const y = Number(value.y);
  const zoom = Number(value.zoom);
  if (![x, y, zoom].every(Number.isFinite)) return clone(fallback);
  return {x, y, zoom: clamp(zoom, 0.15, 4)};
}

function loadLocalCamera(dayText, fallback) {
  try {
    const saved = localStorage.getItem(cameraStorageKey(dayText));
    return saved ? normalizedCamera(JSON.parse(saved), fallback) : normalizedCamera(fallback);
  } catch (_error) {
    return normalizedCamera(fallback);
  }
}

function persistCamera() {
  if (!state.date) return;
  try {
    localStorage.setItem(cameraStorageKey(state.date), JSON.stringify(state.document.camera));
  } catch (_error) {
    // The canvas still works when browser storage is unavailable.
  }
}

function pushUndo() {
  state.undoStack.push({
    elements: clone(state.document.elements),
    strokes: clone(state.document.strokes),
  });
  if (state.undoStack.length > 35) state.undoStack.shift();
  updateToolbar();
}

function undo() {
  const previous = state.undoStack.pop();
  if (!previous) return;
  state.document.elements = previous.elements;
  state.document.strokes = previous.strokes;
  state.selectedId = null;
  renderContent();
  markDirty(true);
}

function maxZ() {
  return state.document.elements.reduce((maximum, item) => Math.max(maximum, item.z || 0), 0);
}

function selectedElement() {
  return state.document.elements.find((item) => item.id === state.selectedId) || null;
}

function setSelected(id) {
  state.selectedId = id;
  for (const node of elements.elementsLayer.querySelectorAll(".canvas-item")) {
    node.classList.toggle("selected", node.dataset.id === id);
  }
  updateToolbar();
}

function updateToolbar() {
  const modeButtons = {
    select: elements.selectTool,
    text: elements.textTool,
    pen: elements.penTool,
    eraser: elements.eraserTool,
  };
  for (const [mode, button] of Object.entries(modeButtons)) {
    button.classList.toggle("active", state.mode === mode);
  }
  for (const mode of ["select", "text", "pen", "eraser"]) {
    elements.canvasViewport.classList.toggle(`mode-${mode}`, state.mode === mode);
  }
  elements.canvasViewport.classList.toggle("is-panning", state.action?.type === "pan");
  const selected = Boolean(selectedElement());
  elements.sendBackward.disabled = !selected;
  elements.bringForward.disabled = !selected;
  elements.undoButton.disabled = state.undoStack.length === 0;
  elements.drawingColor.disabled = state.mode !== "pen";
  elements.drawingWidth.disabled = !["pen", "eraser"].includes(state.mode);
  elements.selectionHint.textContent = selected ? "已选中，可拖动或缩放" : "当前没有选中对象";
}

function setMode(mode) {
  state.mode = mode;
  state.action = null;
  if (mode !== "select") setSelected(null);
  updateToolbar();
  elements.canvasViewport.focus({preventScroll: true});
}

function syncEmptyHint() {
  elements.canvasViewport.classList.toggle("has-content", hasContent());
}

function applyCamera({persist = true} = {}) {
  const camera = state.document.camera;
  elements.canvasWorld.style.transform = `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})`;
  elements.canvasViewport.style.setProperty("--grid-size", `${32 * camera.zoom}px`);
  elements.canvasViewport.style.setProperty("--grid-x", `${camera.x}px`);
  elements.canvasViewport.style.setProperty("--grid-y", `${camera.y}px`);
  elements.zoomText.textContent = `${Math.round(camera.zoom * 100)}%`;
  if (persist) persistCamera();
}

function worldPointFromEvent(event) {
  const rect = elements.canvasViewport.getBoundingClientRect();
  const camera = state.document.camera;
  return {
    x: (event.clientX - rect.left - camera.x) / camera.zoom,
    y: (event.clientY - rect.top - camera.y) / camera.zoom,
  };
}

function viewportCenterWorldPoint() {
  const rect = elements.canvasViewport.getBoundingClientRect();
  const camera = state.document.camera;
  return {
    x: (rect.width / 2 - camera.x) / camera.zoom,
    y: (rect.height / 2 - camera.y) / camera.zoom,
  };
}

function strokePath(points) {
  if (!points.length) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point[0]} ${point[1]}`).join(" ");
}

function renderStrokes() {
  elements.strokeLayer.replaceChildren();
  const namespace = "http://www.w3.org/2000/svg";
  for (const stroke of state.document.strokes) {
    if (stroke.points.length === 1) {
      const circle = document.createElementNS(namespace, "circle");
      circle.setAttribute("cx", String(stroke.points[0][0]));
      circle.setAttribute("cy", String(stroke.points[0][1]));
      circle.setAttribute("r", String(stroke.width / 2));
      circle.setAttribute("fill", stroke.color);
      elements.strokeLayer.appendChild(circle);
      continue;
    }
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("d", strokePath(stroke.points));
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", stroke.color);
    path.setAttribute("stroke-width", String(stroke.width));
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    elements.strokeLayer.appendChild(path);
  }
}

function applyElementFrame(node, item) {
  node.style.left = `${item.x}px`;
  node.style.top = `${item.y}px`;
  node.style.width = `${item.w}px`;
  node.style.height = `${item.h}px`;
  node.style.zIndex = String(item.z || 0);
}

function createHandle(className, text, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = text;
  button.setAttribute("aria-label", label);
  return button;
}

function renderElements() {
  elements.elementsLayer.replaceChildren();
  const ordered = [...state.document.elements].sort((a, b) => (a.z || 0) - (b.z || 0));
  for (const item of ordered) {
    const node = document.createElement("article");
    node.className = `canvas-item ${item.type}-item${item.id === state.selectedId ? " selected" : ""}`;
    node.dataset.id = item.id;
    applyElementFrame(node, item);

    if (item.type === "text") {
      const textarea = document.createElement("textarea");
      textarea.value = item.text;
      textarea.placeholder = "在这里输入……";
      textarea.spellcheck = false;
      textarea.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        setSelected(item.id);
      });
      textarea.addEventListener("focus", () => {
        if (!textarea.dataset.undoReady) {
          pushUndo();
          textarea.dataset.undoReady = "1";
        }
        setSelected(item.id);
      });
      textarea.addEventListener("blur", () => {
        delete textarea.dataset.undoReady;
      });
      textarea.addEventListener("input", () => {
        item.text = textarea.value;
        markDirty(true);
      });
      node.appendChild(textarea);
    } else {
      const image = document.createElement("img");
      image.src = `/data/${item.asset}`;
      image.alt = "画布中的图片";
      image.draggable = false;
      image.addEventListener("load", () => {
        if (!item._needsAspect || !image.naturalWidth || !image.naturalHeight) return;
        item.aspect = image.naturalWidth / image.naturalHeight;
        item.h = item.w / item.aspect;
        delete item._needsAspect;
        applyElementFrame(node, item);
      });
      node.appendChild(image);
      node.addEventListener("pointerdown", (event) => startMove(event, item.id));
    }

    const move = createHandle("move-handle", "✥", "拖动对象");
    move.addEventListener("pointerdown", (event) => startMove(event, item.id));
    const resize = createHandle("resize-handle", "", "调整大小");
    resize.addEventListener("pointerdown", (event) => startResize(event, item.id));
    const remove = createHandle("delete-handle", "×", "删除对象");
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteElement(item.id);
    });
    node.append(move, resize, remove);
    node.addEventListener("click", (event) => {
      event.stopPropagation();
      setSelected(item.id);
    });
    elements.elementsLayer.appendChild(node);
  }
}

function renderContent() {
  renderStrokes();
  renderElements();
  applyCamera();
  syncEmptyHint();
  updateToolbar();
}

function focusTextElement(id) {
  window.requestAnimationFrame(() => {
    const textarea = elements.elementsLayer.querySelector(`[data-id="${id}"] textarea`);
    if (!textarea) return;
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  });
}

function createTextAt(point) {
  pushUndo();
  const item = {
    id: createId("text"),
    type: "text",
    x: clamp(point.x, 0, WORLD_WIDTH - 360),
    y: clamp(point.y, 0, WORLD_HEIGHT - 160),
    w: 360,
    h: 150,
    z: maxZ() + 1,
    text: "",
  };
  state.document.elements.push(item);
  state.selectedId = item.id;
  state.mode = "select";
  renderElements();
  updateToolbar();
  markDirty(true);
  focusTextElement(item.id);
}

function deleteElement(id) {
  if (!state.document.elements.some((item) => item.id === id)) return;
  pushUndo();
  state.document.elements = state.document.elements.filter((item) => item.id !== id);
  state.selectedId = null;
  renderElements();
  updateToolbar();
  markDirty(true);
}

function startMove(event, id) {
  if (state.mode !== "select") return;
  event.preventDefault();
  event.stopPropagation();
  const item = state.document.elements.find((candidate) => candidate.id === id);
  if (!item) return;
  pushUndo();
  setSelected(id);
  const point = worldPointFromEvent(event);
  state.action = {type: "move", id, start: point, original: {x: item.x, y: item.y}};
  elements.canvasViewport.setPointerCapture(event.pointerId);
}

function startResize(event, id) {
  event.preventDefault();
  event.stopPropagation();
  const item = state.document.elements.find((candidate) => candidate.id === id);
  if (!item) return;
  pushUndo();
  setSelected(id);
  const point = worldPointFromEvent(event);
  state.action = {
    type: "resize",
    id,
    start: point,
    original: {w: item.w, h: item.h},
  };
  elements.canvasViewport.setPointerCapture(event.pointerId);
}

function startStroke(event) {
  pushUndo();
  const point = worldPointFromEvent(event);
  const stroke = {
    id: createId("stroke"),
    color: elements.drawingColor.value,
    width: Number(elements.drawingWidth.value) / state.document.camera.zoom,
    points: [[point.x, point.y]],
  };
  state.document.strokes.push(stroke);
  state.action = {type: "stroke", stroke};
  elements.canvasViewport.setPointerCapture(event.pointerId);
  renderStrokes();
}

function distanceToSegment(point, start, end) {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  if (dx === 0 && dy === 0) return Math.hypot(point.x - start[0], point.y - start[1]);
  const t = clamp(((point.x - start[0]) * dx + (point.y - start[1]) * dy) / (dx * dx + dy * dy), 0, 1);
  return Math.hypot(point.x - (start[0] + t * dx), point.y - (start[1] + t * dy));
}

function strokeIsHit(stroke, point, radius) {
  if (stroke.points.length === 1) {
    return Math.hypot(point.x - stroke.points[0][0], point.y - stroke.points[0][1]) <= radius;
  }
  for (let index = 1; index < stroke.points.length; index += 1) {
    if (distanceToSegment(point, stroke.points[index - 1], stroke.points[index]) <= radius) return true;
  }
  return false;
}

function eraseAt(point) {
  const radius = Number(elements.drawingWidth.value) * 2.4 / state.document.camera.zoom;
  const remaining = state.document.strokes.filter((stroke) => !strokeIsHit(stroke, point, radius));
  if (remaining.length === state.document.strokes.length) return false;
  state.document.strokes = remaining;
  renderStrokes();
  return true;
}

function startErase(event) {
  pushUndo();
  state.action = {type: "erase", changed: false};
  elements.canvasViewport.setPointerCapture(event.pointerId);
  state.action.changed = eraseAt(worldPointFromEvent(event));
}

function startPan(event) {
  const camera = state.document.camera;
  state.action = {
    type: "pan",
    start: {x: event.clientX, y: event.clientY},
    original: {x: camera.x, y: camera.y},
  };
  elements.canvasViewport.setPointerCapture(event.pointerId);
  updateToolbar();
}

function localPoint(clientX, clientY) {
  const rect = elements.canvasViewport.getBoundingClientRect();
  return {x: clientX - rect.left, y: clientY - rect.top};
}

function touchPair() {
  return Array.from(state.activeTouches.values()).slice(0, 2);
}

function touchGeometry(points) {
  const first = points[0];
  const second = points[1];
  return {
    midpoint: {
      x: (first.clientX + second.clientX) / 2,
      y: (first.clientY + second.clientY) / 2,
    },
    distance: Math.max(8, Math.hypot(second.clientX - first.clientX, second.clientY - first.clientY)),
  };
}

function cancelActionForPinch() {
  const action = state.action;
  if (!action) return;
  if (action.type === "stroke") {
    state.document.strokes = state.document.strokes.filter((stroke) => stroke.id !== action.stroke.id);
    state.undoStack.pop();
    renderStrokes();
  } else if (action.type === "erase") {
    const previous = state.undoStack.pop();
    if (previous) {
      state.document.elements = previous.elements;
      state.document.strokes = previous.strokes;
      renderContent();
    }
  }
  state.action = null;
  updateToolbar();
}

function beginPinch() {
  const points = touchPair();
  if (points.length < 2) return;
  cancelActionForPinch();
  const geometry = touchGeometry(points);
  const midpoint = localPoint(geometry.midpoint.x, geometry.midpoint.y);
  const camera = state.document.camera;
  state.pinch = {
    startDistance: geometry.distance,
    startZoom: camera.zoom,
    anchor: {
      x: (midpoint.x - camera.x) / camera.zoom,
      y: (midpoint.y - camera.y) / camera.zoom,
    },
  };
  state.suppressTouchAction = true;
}

function updatePinch() {
  const points = touchPair();
  if (!state.pinch || points.length < 2) return;
  const geometry = touchGeometry(points);
  const midpoint = localPoint(geometry.midpoint.x, geometry.midpoint.y);
  const zoom = clamp(
    state.pinch.startZoom * geometry.distance / state.pinch.startDistance,
    0.15,
    4,
  );
  state.document.camera.zoom = zoom;
  state.document.camera.x = midpoint.x - state.pinch.anchor.x * zoom;
  state.document.camera.y = midpoint.y - state.pinch.anchor.y * zoom;
  applyCamera({persist: false});
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 760px)").matches;
}

function setFocusMode(active, anchorWorld = null) {
  const previousRect = elements.canvasViewport.getBoundingClientRect();
  const camera = state.document.camera;
  const anchor = anchorWorld || {
    x: (previousRect.width / 2 - camera.x) / camera.zoom,
    y: (previousRect.height / 2 - camera.y) / camera.zoom,
  };
  state.focusMode = active;
  document.body.classList.toggle("canvas-focus", active);
  elements.focusCanvas.textContent = active ? "退出全屏" : "全屏画布";
  elements.focusCanvas.setAttribute("aria-pressed", String(active));
  window.requestAnimationFrame(() => {
    const rect = elements.canvasViewport.getBoundingClientRect();
    state.document.camera.x = rect.width / 2 - anchor.x * camera.zoom;
    state.document.camera.y = rect.height / 2 - anchor.y * camera.zoom;
    applyCamera();
    elements.canvasViewport.focus({preventScroll: true});
  });
}

function handleMobileFocusCapture(event) {
  if (event.pointerType !== "touch" || state.focusMode || !isMobileLayout()) return;
  const anchor = worldPointFromEvent(event);
  event.preventDefault();
  event.stopPropagation();
  setFocusMode(true, anchor);
}

function handleViewportPointerDown(event) {
  if (event.pointerType === "touch") {
    state.activeTouches.set(event.pointerId, {clientX: event.clientX, clientY: event.clientY});
    elements.canvasViewport.setPointerCapture(event.pointerId);
    if (state.activeTouches.size >= 2) {
      event.preventDefault();
      beginPinch();
      return;
    }
    if (state.suppressTouchAction) return;
  }
  state.lastWorldPoint = worldPointFromEvent(event);
  if (event.button === 1 || state.spaceDown) {
    event.preventDefault();
    startPan(event);
    return;
  }
  if (event.button !== 0) return;
  if (event.pointerType === "touch" && state.focusMode && state.mode === "select") {
    event.preventDefault();
    startPan(event);
    return;
  }
  if (state.mode === "pen") {
    event.preventDefault();
    startStroke(event);
    return;
  }
  if (state.mode === "eraser") {
    event.preventDefault();
    startErase(event);
    return;
  }
  if (state.mode === "text") {
    event.preventDefault();
    createTextAt(state.lastWorldPoint);
    return;
  }
  setSelected(null);
}

function handleViewportPointerMove(event) {
  if (event.pointerType === "touch" && state.activeTouches.has(event.pointerId)) {
    state.activeTouches.set(event.pointerId, {clientX: event.clientX, clientY: event.clientY});
    if (state.pinch) {
      event.preventDefault();
      updatePinch();
      return;
    }
    if (state.suppressTouchAction) return;
  }
  state.lastWorldPoint = worldPointFromEvent(event);
  if (!state.action) return;
  const action = state.action;
  if (action.type === "move") {
    const item = state.document.elements.find((candidate) => candidate.id === action.id);
    if (!item) return;
    const point = worldPointFromEvent(event);
    item.x = clamp(action.original.x + point.x - action.start.x, 0, WORLD_WIDTH - item.w);
    item.y = clamp(action.original.y + point.y - action.start.y, 0, WORLD_HEIGHT - item.h);
    const node = elements.elementsLayer.querySelector(`[data-id="${item.id}"]`);
    if (node) applyElementFrame(node, item);
    return;
  }
  if (action.type === "resize") {
    const item = state.document.elements.find((candidate) => candidate.id === action.id);
    if (!item) return;
    const point = worldPointFromEvent(event);
    const width = clamp(action.original.w + point.x - action.start.x, 80, WORLD_WIDTH - item.x);
    item.w = width;
    item.h = item.type === "image"
      ? clamp(width / Math.max(0.02, item.aspect), 50, WORLD_HEIGHT - item.y)
      : clamp(action.original.h + point.y - action.start.y, 60, WORLD_HEIGHT - item.y);
    const node = elements.elementsLayer.querySelector(`[data-id="${item.id}"]`);
    if (node) applyElementFrame(node, item);
    return;
  }
  if (action.type === "stroke") {
    const point = worldPointFromEvent(event);
    const previous = action.stroke.points[action.stroke.points.length - 1];
    if (Math.hypot(point.x - previous[0], point.y - previous[1]) < 1.5 / state.document.camera.zoom) return;
    action.stroke.points.push([point.x, point.y]);
    renderStrokes();
    return;
  }
  if (action.type === "erase") {
    action.changed = eraseAt(worldPointFromEvent(event)) || action.changed;
    return;
  }
  if (action.type === "pan") {
    state.document.camera.x = action.original.x + event.clientX - action.start.x;
    state.document.camera.y = action.original.y + event.clientY - action.start.y;
    applyCamera({persist: false});
  }
}

function handleViewportPointerUp(event) {
  if (event.pointerType === "touch") {
    state.activeTouches.delete(event.pointerId);
    if (state.pinch) {
      state.pinch = null;
      state.suppressTouchAction = state.activeTouches.size > 0;
      persistCamera();
      if (elements.canvasViewport.hasPointerCapture(event.pointerId)) {
        elements.canvasViewport.releasePointerCapture(event.pointerId);
      }
      return;
    }
    if (state.suppressTouchAction) {
      state.suppressTouchAction = state.activeTouches.size > 0;
      if (elements.canvasViewport.hasPointerCapture(event.pointerId)) {
        elements.canvasViewport.releasePointerCapture(event.pointerId);
      }
      return;
    }
  }
  if (!state.action) return;
  const action = state.action;
  state.action = null;
  if (elements.canvasViewport.hasPointerCapture(event.pointerId)) {
    elements.canvasViewport.releasePointerCapture(event.pointerId);
  }
  if (["move", "resize", "stroke"].includes(action.type)) markDirty(true);
  if (action.type === "pan") persistCamera();
  if (action.type === "erase") {
    if (action.changed) markDirty(true);
    else state.undoStack.pop();
  }
  updateToolbar();
}

function zoomAt(clientX, clientY, factor) {
  const rect = elements.canvasViewport.getBoundingClientRect();
  const camera = state.document.camera;
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  const worldX = (localX - camera.x) / camera.zoom;
  const worldY = (localY - camera.y) / camera.zoom;
  const nextZoom = clamp(camera.zoom * factor, 0.15, 4);
  camera.x = localX - worldX * nextZoom;
  camera.y = localY - worldY * nextZoom;
  camera.zoom = nextZoom;
  applyCamera();
}

function handleWheel(event) {
  event.preventDefault();
  zoomAt(event.clientX, event.clientY, Math.exp(-event.deltaY * 0.0015));
}

function contentBounds(documentValue = state.document) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const include = (x, y) => {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  };
  for (const item of documentValue.elements) {
    if (item.type === "text" && !item.text.trim()) continue;
    include(item.x, item.y);
    include(item.x + item.w, item.y + item.h);
  }
  for (const stroke of documentValue.strokes) {
    for (const point of stroke.points) include(point[0], point[1]);
  }
  if (!Number.isFinite(minX)) return null;
  return {minX, minY, maxX, maxY};
}

function fitContent() {
  const bounds = contentBounds();
  const rect = elements.canvasViewport.getBoundingClientRect();
  if (!bounds) {
    state.document.camera = {x: 70, y: 60, zoom: 1};
  } else {
    const width = Math.max(200, bounds.maxX - bounds.minX);
    const height = Math.max(150, bounds.maxY - bounds.minY);
    const zoom = clamp(Math.min((rect.width - 100) / width, (rect.height - 100) / height), 0.15, 1.5);
    state.document.camera.zoom = zoom;
    state.document.camera.x = (rect.width - width * zoom) / 2 - bounds.minX * zoom;
    state.document.camera.y = (rect.height - height * zoom) / 2 - bounds.minY * zoom;
  }
  applyCamera();
}

function moveLayer(direction) {
  const item = selectedElement();
  if (!item) return;
  pushUndo();
  if (direction > 0) item.z = maxZ() + 1;
  else item.z = Math.max(0, Math.min(...state.document.elements.map((candidate) => candidate.z || 0)) - 1);
  renderElements();
  markDirty(true);
}

async function uploadImage(blob, dayText) {
  return api(`/api/image?date=${encodeURIComponent(dayText)}`, {
    method: "POST",
    headers: {"Content-Type": blob.type || "application/octet-stream"},
    body: blob,
  });
}

async function imageDimensions(file) {
  if ("createImageBitmap" in window) {
    const bitmap = await createImageBitmap(file);
    const result = {width: bitmap.width, height: bitmap.height};
    bitmap.close();
    return result;
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = reject;
      image.src = url;
    });
    return {width: image.naturalWidth, height: image.naturalHeight};
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function pasteImages(files, insertionPoint = state.lastWorldPoint) {
  if (!files.length) return;
  const pasteDate = state.date;
  const insertion = {...insertionPoint};
  state.pendingUploads += 1;
  setSaveState("saving", files.length > 1 ? `正在加入 ${files.length} 张图片` : "正在加入图片");
  try {
    const added = [];
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      const [uploaded, dimensions] = await Promise.all([
        uploadImage(file, pasteDate),
        imageDimensions(file),
      ]);
      const aspect = dimensions.width / Math.max(1, dimensions.height);
      const width = clamp(dimensions.width, 180, 680);
      const height = width / aspect;
      added.push({
        id: createId("image"),
        type: "image",
        x: clamp(insertion.x + index * 35, 0, WORLD_WIDTH - width),
        y: clamp(insertion.y + index * 35, 0, WORLD_HEIGHT - height),
        w: width,
        h: height,
        z: maxZ() + index + 1,
        asset: uploaded.asset,
        aspect,
      });
    }
    if (pasteDate !== state.date) return;
    pushUndo();
    state.document.elements.push(...added);
    state.selectedId = added[added.length - 1]?.id || null;
    renderElements();
    updateToolbar();
    markDirty(true);
    await saveNote();
  } finally {
    state.pendingUploads -= 1;
  }
}

function loadImageAsset(asset) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = `/data/${asset}`;
  });
}

function wrapText(context, text, x, y, width, lineHeight) {
  let cursorY = y;
  for (const paragraph of text.split("\n")) {
    if (!paragraph) {
      cursorY += lineHeight;
      continue;
    }
    let line = "";
    for (const character of paragraph) {
      const candidate = line + character;
      if (line && context.measureText(candidate).width > width) {
        context.fillText(line, x, cursorY);
        cursorY += lineHeight;
        line = character;
      } else {
        line = candidate;
      }
    }
    if (line) context.fillText(line, x, cursorY);
    cursorY += lineHeight;
  }
}

async function buildPreviewBlob(documentValue) {
  const bounds = contentBounds(documentValue);
  if (!bounds) return null;
  const padding = 55;
  const worldWidth = Math.max(320, bounds.maxX - bounds.minX + padding * 2);
  const worldHeight = Math.max(240, bounds.maxY - bounds.minY + padding * 2);
  const scale = Math.min(1, 1800 / worldWidth, 1400 / worldHeight);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(320, Math.ceil(worldWidth * scale));
  canvas.height = Math.max(240, Math.ceil(worldHeight * scale));
  const context = canvas.getContext("2d");
  context.fillStyle = "#fffefb";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.setTransform(
    scale, 0, 0, scale,
    (-bounds.minX + padding) * scale,
    (-bounds.minY + padding) * scale,
  );

  for (const stroke of documentValue.strokes) {
    if (!stroke.points.length) continue;
    if (stroke.points.length === 1) {
      context.beginPath();
      context.arc(stroke.points[0][0], stroke.points[0][1], stroke.width / 2, 0, Math.PI * 2);
      context.fillStyle = stroke.color;
      context.fill();
      continue;
    }
    context.beginPath();
    context.moveTo(stroke.points[0][0], stroke.points[0][1]);
    for (const point of stroke.points.slice(1)) context.lineTo(point[0], point[1]);
    context.strokeStyle = stroke.color;
    context.lineWidth = stroke.width;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.stroke();
  }

  const ordered = [...documentValue.elements].sort((a, b) => (a.z || 0) - (b.z || 0));
  for (const item of ordered) {
    if (item.type === "image") {
      try {
        const image = await loadImageAsset(item.asset);
        context.fillStyle = "#ffffff";
        context.fillRect(item.x, item.y, item.w, item.h);
        context.drawImage(image, item.x, item.y, item.w, item.h);
      } catch (_error) {
        context.fillStyle = "#eeeae2";
        context.fillRect(item.x, item.y, item.w, item.h);
      }
    } else if (item.text.trim()) {
      context.fillStyle = "rgba(255,254,251,0.9)";
      context.fillRect(item.x, item.y, item.w, item.h);
      context.fillStyle = "#252c2a";
      context.font = '18px "Microsoft YaHei", sans-serif';
      context.textBaseline = "top";
      wrapText(context, item.text, item.x + 12, item.y + 12, item.w - 24, 28);
    }
  }
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("画布预览生成失败。")), "image/png");
  });
}

async function saveNote() {
  window.clearTimeout(state.saveTimer);
  if (!state.dirty || state.saving || !state.date || state.syncConflict) return;
  state.saving = true;
  setSaveState("saving", "正在保存");
  const savingDate = state.date;
  const savingRevision = state.revision;
  const previewNeeded = state.previewDirty;
  const savingDocument = clone(state.document);
  savingDocument.camera = {x: 70, y: 60, zoom: 1};
  try {
    if (previewNeeded) {
      const preview = await buildPreviewBlob(savingDocument);
      if (savingRevision !== state.revision || savingDate !== state.date) return;
      if (preview) {
        const uploaded = await api(`/api/canvas-preview?date=${encodeURIComponent(savingDate)}`, {
          method: "POST",
          headers: {"Content-Type": "image/png"},
          body: preview,
        });
        savingDocument.preview_asset = uploaded.asset;
      } else {
        savingDocument.preview_asset = "";
      }
    }
    if (savingRevision !== state.revision || savingDate !== state.date) return;
    const payload = await api("/api/note", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        date: savingDate,
        canvas: savingDocument,
        base_sync_id: state.syncId,
        source_client_id: state.clientId,
      }),
    });
    if (savingDate === state.date) state.syncId = String(payload.sync_id || "");
    if (savingDate === state.date && savingRevision === state.revision) {
      state.document.preview_asset = savingDocument.preview_asset;
      state.dirty = false;
      state.previewDirty = false;
      const time = new Date(payload.updated_at).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
      setSaveState("saved", `${time} 已保存`);
    }
    await loadRecentDates();
  } catch (error) {
    if (error.status === 409) {
      state.syncConflict = true;
      window.clearTimeout(state.saveTimer);
      setSaveState("error", "另一设备有更新");
    }
    throw error;
  } finally {
    state.saving = false;
    if (state.dirty && !state.syncConflict && savingDate === state.date) {
      state.saveTimer = window.setTimeout(() => saveNote().catch(reportError), 350);
    }
  }
}

async function flushCurrentNote() {
  if (state.syncConflict) throw new Error("另一台设备已经更新了当前日期，请刷新页面后继续。");
  if (!state.dirty) return;
  await saveNote();
  while (state.saving) await new Promise((resolve) => window.setTimeout(resolve, 40));
  if (state.dirty) await saveNote();
}

async function loadNote(dayText) {
  if (!dayText || dayText === state.date) return;
  while (state.pendingUploads > 0) await new Promise((resolve) => window.setTimeout(resolve, 40));
  await flushCurrentNote();
  const token = ++state.loadToken;
  setSaveState("saving", "正在打开");
  const payload = await api(`/api/note?date=${encodeURIComponent(dayText)}`);
  if (token !== state.loadToken) return;
  state.date = dayText;
  state.document = payload.canvas ? normalizeDocument(payload.canvas) : migrateBlocks(payload.blocks);
  state.document.camera = loadLocalCamera(dayText, state.document.camera);
  state.syncId = String(payload.sync_id || "");
  state.selectedId = null;
  state.mode = "select";
  state.action = null;
  state.dirty = false;
  state.previewDirty = false;
  state.revision = 0;
  state.undoStack = [];
  state.syncConflict = false;
  elements.dateInput.value = dayText;
  elements.dateLabel.textContent = dayText === state.today ? "今天" : shortDateText(dayText);
  elements.friendlyDate.textContent = localDateText(dayText);
  renderContent();
  setSaveState("saved", payload.updated_at ? "内容已载入" : "还没有记录");
  renderRecentDates();
}

async function applyRemoteNote(dayText, expectedSyncId) {
  if (state.remoteSyncing || dayText !== state.date) return;
  state.remoteSyncing = true;
  try {
    const payload = await api(`/api/note?date=${encodeURIComponent(dayText)}`);
    if (dayText !== state.date) return;
    if (expectedSyncId && payload.sync_id && payload.sync_id !== expectedSyncId) {
      // A newer save arrived while this request was in flight; use the newest response.
    }
    const localCamera = clone(state.document.camera);
    state.document = payload.canvas ? normalizeDocument(payload.canvas) : migrateBlocks(payload.blocks);
    state.document.camera = localCamera;
    state.syncId = String(payload.sync_id || "");
    state.selectedId = null;
    state.action = null;
    state.dirty = false;
    state.previewDirty = false;
    state.revision = 0;
    state.undoStack = [];
    renderContent();
    setSaveState("saved", "另一设备内容已同步");
    await loadRecentDates();
  } finally {
    state.remoteSyncing = false;
  }
}

async function checkForRemoteChanges() {
  if (!state.date || state.syncPolling || state.remoteSyncing || document.hidden) return;
  state.syncPolling = true;
  const checkingDate = state.date;
  try {
    const payload = await api(`/api/note-version?date=${encodeURIComponent(checkingDate)}`);
    if (checkingDate !== state.date) return;
    const remoteSyncId = String(payload.sync_id || "");
    if (remoteSyncId === state.syncId || (!remoteSyncId && !state.syncId)) return;
    if (state.dirty || state.saving || state.action || state.pendingUploads > 0) {
      if (!state.syncConflict) {
        state.syncConflict = true;
        window.clearTimeout(state.saveTimer);
        setSaveState("error", "另一设备有更新");
        showToast("另一台设备刚刚更新了这一天。为避免覆盖，已暂停本机保存，请刷新页面后继续。");
      }
      return;
    }
    await applyRemoteNote(checkingDate, remoteSyncId);
  } catch (error) {
    console.warn("同步检查暂时失败", error);
  } finally {
    state.syncPolling = false;
  }
}

async function loadRecentDates() {
  const payload = await api("/api/dates");
  state.recentDates = payload.dates || [];
  renderRecentDates();
}

function renderRecentDates() {
  elements.recentDates.replaceChildren();
  if (!state.recentDates.length) {
    const empty = document.createElement("span");
    empty.className = "recent-empty";
    empty.textContent = "保存第一条记录后，这里会出现日期。";
    elements.recentDates.appendChild(empty);
    return;
  }
  for (const dayText of state.recentDates.slice(0, 14)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `recent-date${dayText === state.date ? " active" : ""}`;
    button.textContent = dayText === state.today ? "今天" : shortDateText(dayText);
    button.title = dayText;
    button.addEventListener("click", () => loadNote(dayText).catch(reportError));
    elements.recentDates.appendChild(button);
  }
}

function reportError(error) {
  console.error(error);
  setSaveState("error", "保存失败");
  showToast(error.message || String(error));
}

function isTypingTarget(target) {
  return target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement;
}

function bindEvents() {
  elements.dateInput.addEventListener("change", () => loadNote(elements.dateInput.value).catch(reportError));
  elements.previousDay.addEventListener("click", () => loadNote(offsetDate(state.date, -1)).catch(reportError));
  elements.nextDay.addEventListener("click", () => loadNote(offsetDate(state.date, 1)).catch(reportError));
  elements.todayButton.addEventListener("click", () => loadNote(state.today).catch(reportError));

  elements.selectTool.addEventListener("click", () => setMode("select"));
  elements.textTool.addEventListener("click", () => setMode("text"));
  elements.penTool.addEventListener("click", () => setMode("pen"));
  elements.eraserTool.addEventListener("click", () => setMode("eraser"));
  elements.imageUploadButton.addEventListener("click", () => elements.imageUploadInput.click());
  elements.imageUploadInput.addEventListener("change", (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) return;
    const insertion = viewportCenterWorldPoint();
    state.lastWorldPoint = insertion;
    pasteImages(files, insertion).catch(reportError);
  });
  elements.undoButton.addEventListener("click", undo);
  elements.sendBackward.addEventListener("click", () => moveLayer(-1));
  elements.bringForward.addEventListener("click", () => moveLayer(1));

  elements.zoomOut.addEventListener("click", () => {
    const rect = elements.canvasViewport.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 0.82);
  });
  elements.zoomIn.addEventListener("click", () => {
    const rect = elements.canvasViewport.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.22);
  });
  elements.fitView.addEventListener("click", fitContent);
  elements.focusCanvas.addEventListener("click", () => setFocusMode(!state.focusMode));

  elements.canvasViewport.addEventListener("pointerdown", handleMobileFocusCapture, {capture: true});
  elements.canvasViewport.addEventListener("pointerdown", handleViewportPointerDown);
  elements.canvasViewport.addEventListener("pointermove", handleViewportPointerMove);
  elements.canvasViewport.addEventListener("pointerup", handleViewportPointerUp);
  elements.canvasViewport.addEventListener("pointercancel", handleViewportPointerUp);
  elements.canvasViewport.addEventListener("wheel", handleWheel, {passive: false});
  elements.canvasViewport.addEventListener("dblclick", (event) => {
    if (event.target.closest?.(".canvas-item")) return;
    createTextAt(worldPointFromEvent(event));
  });

  document.addEventListener("paste", (event) => {
    const files = Array.from(event.clipboardData?.items || [])
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (!files.length) return;
    event.preventDefault();
    pasteImages(files).catch(reportError);
  });

  document.addEventListener("keydown", (event) => {
    if (event.code === "Space" && !isTypingTarget(event.target)) {
      state.spaceDown = true;
      event.preventDefault();
    }
    if (isTypingTarget(event.target)) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      undo();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveNote().catch(reportError);
      return;
    }
    if ((event.key === "Delete" || event.key === "Backspace") && state.selectedId) {
      event.preventDefault();
      deleteElement(state.selectedId);
      return;
    }
    if (event.key === "Escape" && state.focusMode) {
      setFocusMode(false);
      return;
    }
    if (event.key === "Escape") setMode("select");
  });
  document.addEventListener("keyup", (event) => {
    if (event.code === "Space") state.spaceDown = false;
  });
  window.addEventListener("blur", () => {
    state.spaceDown = false;
  });
  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty && state.pendingUploads === 0) return;
    event.preventDefault();
    event.returnValue = "";
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) checkForRemoteChanges();
  });
}

async function boot() {
  bindEvents();
  const status = await api("/api/status");
  state.today = status.today;
  await loadRecentDates();
  await loadNote(state.today);
  window.setInterval(checkForRemoteChanges, 900);
}

boot().catch(reportError);
