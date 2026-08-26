"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const htmlPath = process.argv[2] ?? path.join(__dirname, "fixtures", "editable-resonance.html");
const html = fs.readFileSync(htmlPath, "utf8");
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) throw new Error("Inline figure script not found");

class ElementStub {
  constructor(tagName = "div", id = "") {
    this.tagName = tagName;
    this.id = id;
    this.attributes = {};
    this.children = [];
    this.listeners = {};
    this.style = {};
    this.dataset = {};
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.classNames = new Set();
    this.classList = {
      add: (...names) => names.forEach(name => this.classNames.add(name)),
      remove: (...names) => names.forEach(name => this.classNames.delete(name)),
      toggle: (name, force) => {
        const enabled = force === undefined ? !this.classNames.has(name) : Boolean(force);
        if (enabled) this.classNames.add(name); else this.classNames.delete(name);
        return enabled;
      },
      contains: name => this.classNames.has(name),
    };
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this.children = [...children];
  }

  addEventListener(type, handler) {
    (this.listeners[type] ??= []).push(handler);
  }

  closest(selector) {
    if (selector.startsWith(".") && this.classList.contains(selector.slice(1))) return this;
    return null;
  }

  querySelectorAll(selector) {
    const selectors = selector.split(",").map(item => item.trim());
    const descendants = [];
    const visit = node => {
      for (const child of node.children) {
        descendants.push(child);
        visit(child);
      }
    };
    visit(this);
    return descendants.filter(element => selectors.some(item => {
      if (item.startsWith(".")) return element.classList.contains(item.slice(1));
      if (item.startsWith("#")) return element.id === item.slice(1);
      return false;
    }));
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  getBoundingClientRect() {
    return {left: 0, top: 0, width: 340, height: 220};
  }

  click() {}

  cloneNode(deep = false) {
    const clone = new ElementStub(this.tagName, this.id);
    clone.attributes = {...this.attributes};
    clone.style = {...this.style};
    clone.dataset = {...this.dataset};
    clone.textContent = this.textContent;
    clone.disabled = this.disabled;
    clone.hidden = this.hidden;
    clone.classNames = new Set(this.classNames);
    if (deep) clone.children = this.children.map(child => child.cloneNode(true));
    return clone;
  }
}

const elements = new Map();
const documentStub = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new ElementStub("div", id));
    return elements.get(id);
  },
  createElement(tagName) {
    return new ElementStub(tagName);
  },
  createElementNS(_namespace, tagName) {
    return new ElementStub(tagName);
  },
  querySelector(selector) {
    if (selector === ".workspace") return this.getElementById("workspace-stub");
    return null;
  },
  querySelectorAll(selector) {
    if (!selector.startsWith(".")) return [];
    const className = selector.slice(1);
    return Array.from(elements.values()).filter(element => element.classList.contains(className));
  },
};

const savedStorage = new Map();
const localStorageStub = {
  getItem(key) { return savedStorage.has(key) ? savedStorage.get(key) : null; },
  setItem(key, value) { savedStorage.set(key, String(value)); },
  removeItem(key) { savedStorage.delete(key); },
};

const context = {
  Blob,
  console,
  document: documentStub,
  localStorage: localStorageStub,
  setTimeout(callback) {
    callback();
    return 1;
  },
  URL: {
    createObjectURL() { return "blob:test"; },
    revokeObjectURL() {},
  },
  window: {},
  XMLSerializer: class {
    serializeToString(element) {
      return `<${element.tagName} width="${element.getAttribute("width")}" height="${element.getAttribute("height")}"></${element.tagName}>`;
    }
  },
};
vm.createContext(context);
vm.runInContext(match[1], context, {filename: htmlPath});

const api = context.window.__figureTest;
assert.ok(api, "Figure test API should exist");
assert.equal(api.getProfile().exportWidthMm, 90);
assert.equal(api.getState().profileId, "90mm-single");
assert.equal(api.getState().fontPt, 7);
assert.equal(api.getState().axisLabelPt, 8);
assert.equal(api.getState().titlePt, 9);
assert.equal(api.getState().legendPt, 7);
assert.equal(api.getState().hoverTitlePt, 7);
assert.equal(api.getState().hoverValuePt, 6);
assert.equal(api.getState().majorTickTarget, 6);
assert.equal(api.getState().axisTitleGapEmX, 0.3);
assert.equal(api.getState().axisTitleGapEmY, 0.2);
assert.equal(api.getState().fontFamily, 'Calibri, "Microsoft YaHei", sans-serif');
assert.equal(api.getState().title, "Synthetic resonance response");
assert.ok(!api.getState().title.includes("合成"), "Default title should not be bilingual");
assert.equal(api.getState().interactionMode, "zoom");
assert.equal(api.getState().uiMode, "inspect");
assert.equal(api.getState().layoutOffsets.title.x, 0);
assert.equal(api.getState().layoutOffsets.title.y, 0);
assert.equal(elements.get("box-zoom-mode").getAttribute("aria-pressed"), "true");
assert.equal(elements.get("pan-mode").getAttribute("aria-pressed"), "false");
assert.equal(elements.get("layout-edit-mode").getAttribute("aria-pressed"), "false");
assert.ok(!html.includes('id="clear-selection"'), "Transient hover must not need Clear selection");
assert.ok(!html.includes('id="selected-point"'), "Persistent point selection should not be present");
assert.ok(!html.includes('id="delivery-profile"'), "Formal HTML must not expose a delivery-profile selector");
assert.ok(!html.includes('"185mm-wide"'), "Formal HTML must embed only its selected delivery profile");
assert.ok(!html.includes('id="grid"'), "Figure must not render a grid group");
assert.ok(html.includes("#chart text { fill: #000; }"), "All SVG text should default to black");
assert.ok(html.includes('id="hover-guide-x" stroke="#217565" stroke-width="1.4" stroke-dasharray="5 4"'));
assert.equal(elements.get("raw-line").getAttribute("stroke-width"), String(4 / 3));
assert.equal(elements.get("markers").children.length, 11);
assert.deepEqual(Array.from(api.niceTicks(-640, 520, 6)), [-500, -250, 0, 250, 500]);
assert.ok(Array.from(api.niceTicks(-640, 520, 6)).every(value => value % 50 === 0));
assert.ok([5, 6].includes(Array.from(api.niceTicks(-640, 520, 6)).length));
assert.equal(elements.get("x-label").getAttribute("data-gap-em"), "0.3");
assert.equal(elements.get("y-label").getAttribute("data-gap-em"), "0.2");
const expectedXLabelY = 197 + 0.2 * 7 * 4 / 3 + 0.3 * 8 * 4 / 3 + 0.8 * 8 * 4 / 3;
assert.ok(Math.abs(Number(elements.get("x-label").getAttribute("y")) - expectedXLabelY) < 0.01);
for (const eventName of ["wheel", "pointerdown", "pointermove", "pointerup", "pointerleave", "keydown"]) {
  assert.ok(elements.get("interaction-surface").listeners[eventName]?.length, `Missing ${eventName} interaction`);
}
for (const buttonId of ["box-zoom-mode", "pan-mode", "zoom-in", "zoom-out", "reset-view"]) {
  assert.ok(elements.get(buttonId).listeners.click?.length, `Missing ${buttonId} action`);
}
for (const buttonId of ["layout-edit-mode", "toggle-editor-panel", "undo-edit", "apply-layout-edit"]) {
  assert.ok(elements.get(buttonId).listeners.click?.length, `Missing ${buttonId} direct-edit action`);
}

elements.get("layout-edit-mode").listeners.click[0]();
assert.equal(api.getState().uiMode, "layout");
assert.equal(elements.get("layout-edit-mode").getAttribute("aria-pressed"), "true");
assert.ok(elements.get("chart").classList.contains("edit-layout"));
assert.equal(elements.get("box-zoom-mode").disabled, true);
assert.match(elements.get("gesture-hint").textContent, /Scientific curves, points, axes, and ticks are locked/);
api.selectLayoutRole("title");
assert.equal(api.getSelectedLayoutRole(), "title");
assert.equal(elements.get("layout-inspector").hidden, false);
assert.match(elements.get("selected-layout-name").textContent, /Figure title/);
elements.get("layout-text").value = "Directly edited title";
elements.get("layout-font-size").value = "11";
elements.get("layout-offset-x").value = "4";
elements.get("layout-offset-y").value = "3";
elements.get("apply-layout-edit").listeners.click[0]();
assert.equal(api.getState().title, "Directly edited title");
assert.equal(api.getState().layoutFontOverrides.title, 11);
assert.equal(api.getState().layoutOffsets.title.x, 4);
assert.equal(api.getState().layoutOffsets.title.y, 3);
assert.equal(elements.get("plot-title").getAttribute("x"), "181.00");
assert.equal(elements.get("plot-title").getAttribute("y"), "20.00");
assert.ok(savedStorage.size > 0, "Direct edits should persist in browser storage");
api.setState({title: "Unsaved temporary title"});
assert.equal(api.restoreSavedState(), true);
assert.equal(api.getState().title, "Directly edited title");
assert.equal(api.getState().uiMode, "inspect", "Restored files should reopen in safe inspection mode");
assert.ok(api.getHistoryLength() > 0);
elements.get("undo-edit").listeners.click[0]();
assert.equal(api.getState().title, "Synthetic resonance response");
assert.equal(api.getState().layoutOffsets.title.x, 0);
assert.equal(api.getState().layoutOffsets.title.y, 0);

const titleElement = elements.get("plot-title");
titleElement.classList.add("layout-editable");
titleElement.dataset.layoutRole = "title";
elements.get("chart").listeners.pointerdown[0]({target: titleElement, clientX: 177, clientY: 17, pointerId: 4, preventDefault() {}});
elements.get("chart").listeners.pointermove[0]({target: titleElement, clientX: 187, clientY: 22, preventDefault() {}});
elements.get("chart").listeners.pointerup[0]({target: titleElement});
assert.ok(api.getState().layoutOffsets.title.x > 0);
assert.ok(api.getState().layoutOffsets.title.y > 0);
assert.match(elements.get("status").textContent, /moved and saved/);
elements.get("undo-edit").listeners.click[0]();
assert.equal(api.getState().layoutOffsets.title.x, 0);
assert.equal(api.getState().layoutOffsets.title.y, 0);

const rawElement = elements.get("raw-line");
rawElement.classList.add("scientific-locked");
rawElement.dataset.label = "Raw data curve (locked)";
const lockedOffsets = {...api.getState().layoutOffsets.title};
elements.get("chart").listeners.pointerdown[0]({target: rawElement, clientX: 180, clientY: 100});
assert.equal(api.getState().layoutOffsets.title.x, lockedOffsets.x);
assert.equal(api.getState().layoutOffsets.title.y, lockedOffsets.y);
assert.match(elements.get("status").textContent, /cannot be moved/);
elements.get("layout-edit-mode").listeners.click[0]();
assert.equal(api.getState().uiMode, "inspect");
assert.equal(elements.get("box-zoom-mode").disabled, false);
elements.get("pan-mode").listeners.click[0]();
assert.equal(api.getState().interactionMode, "pan");
assert.equal(elements.get("pan-mode").getAttribute("aria-pressed"), "true");
assert.ok(elements.get("interaction-surface").classList.contains("pan-mode"));
assert.match(elements.get("gesture-hint").textContent, /move both axes/);
elements.get("box-zoom-mode").listeners.click[0]();
assert.equal(api.getState().interactionMode, "zoom");
assert.ok(!elements.get("interaction-surface").classList.contains("pan-mode"));

api.setState({
  title: "Edited response",
  fontPt: 10,
  rawWidthPt: 2.2,
  markerPt: 8,
  screenWidth: 820,
  majorTickTarget: 5,
  axisTitleGapEmX: 0.5,
  axisTitleGapEmY: 0.4,
});
assert.equal(api.getState().title, "Edited response");
assert.equal(elements.get("plot-title").textContent, "Edited response");
assert.ok(Math.abs(parseFloat(elements.get("chart").style.fontSize) - 10 * 4 / 3) < 1e-9);
assert.ok(Math.abs(Number(elements.get("raw-line").getAttribute("stroke-width")) - 2.2 * 4 / 3) < 1e-9);
assert.equal(elements.get("markers").children.length, 11);
assert.equal(elements.get("figure-wrap").style.width, "min(100%, 820px)");
assert.equal(elements.get("x-label").getAttribute("data-gap-em"), "0.5");
assert.equal(elements.get("y-label").getAttribute("data-gap-em"), "0.4");

const surface = elements.get("interaction-surface");
surface.listeners.pointermove[0]({clientX: 186.5, clientY: 104.5, pointerType: "mouse"});
assert.notEqual(api.getHoverIndex(), null);
assert.equal(elements.get("hover-crosshair").getAttribute("visibility"), "visible");
assert.equal(elements.get("hover-tooltip").getAttribute("visibility"), "visible");
assert.match(elements.get("hover-readout").textContent, /Frequency: \d+\.\d{3} kHz; response: \d+\.\d{6}/);
assert.match(elements.get("hover-tooltip-value").textContent, /x \d+\.\d{3}; y \d+\.\d{6}/);
assert.ok(Math.abs(parseFloat(elements.get("hover-tooltip-series").style.fontSize) - 7 * 4 / 3) < 1e-9);
assert.ok(Math.abs(parseFloat(elements.get("hover-tooltip-value").style.fontSize) - 6 * 4 / 3) < 1e-9);
assert.ok(Number(elements.get("hover-tooltip-box").getAttribute("width")) <= 150);
assert.notEqual(elements.get("hover-guide-x").getAttribute("x1"), null);
assert.notEqual(elements.get("hover-guide-y").getAttribute("y1"), null);
surface.listeners.pointerleave[0]();
assert.equal(api.getHoverIndex(), null);
assert.equal(elements.get("hover-crosshair").getAttribute("visibility"), "hidden");
assert.equal(elements.get("hover-readout").textContent, "Hover over the curve to inspect a raw value.");

elements.get("export-svg").listeners.click[0]();
assert.equal(elements.get("status").textContent, "90 mm SVG exported.");

const fullXSpan = api.getState().xMax - api.getState().xMin;
const fullYSpan = api.getState().yMax - api.getState().yMin;
surface.listeners.pointerdown[0]({button: 0, clientX: 90, clientY: 55, pointerId: 1, preventDefault() {}});
surface.listeners.pointermove[0]({clientX: 270, clientY: 155, pointerType: "mouse", preventDefault() {}});
assert.equal(elements.get("box-zoom-rect").getAttribute("visibility"), "visible");
surface.listeners.pointerup[0]({clientX: 270, clientY: 155});
assert.equal(elements.get("box-zoom-rect").getAttribute("visibility"), "hidden");
assert.ok(api.getState().xMax - api.getState().xMin < fullXSpan);
assert.ok(api.getState().yMax - api.getState().yMin < fullYSpan);
const beforePan = [api.getState().xMin, api.getState().yMin];
elements.get("pan-mode").listeners.click[0]();
surface.listeners.pointerdown[0]({button: 0, clientX: 180, clientY: 100, pointerId: 2, preventDefault() {}});
surface.listeners.pointermove[0]({clientX: 195, clientY: 92, pointerType: "mouse", preventDefault() {}});
surface.listeners.pointerup[0]({clientX: 195, clientY: 92});
assert.notDeepEqual([api.getState().xMin, api.getState().yMin], beforePan);
api.resetView();
assert.deepEqual(
  [api.getState().xMin, api.getState().xMax, api.getState().yMin, api.getState().yMax],
  [0, 100, 0, 1.2]
);
surface.listeners.wheel[0]({clientX: 186.5, clientY: 104.5, deltaY: -1, preventDefault() {}});
assert.ok(api.getState().xMax - api.getState().xMin < 100);
assert.ok(api.getState().yMax - api.getState().yMin < 1.2);
api.resetView();

api.setState({title: "合成共振响应", xLabel: "频率 (kHz)", yLabel: "归一化响应"});
assert.equal(elements.get("plot-title").textContent, "合成共振响应");
assert.ok(!elements.get("plot-title").textContent.includes("Synthetic"));

const rawWidthControl = elements.get("raw-width");
rawWidthControl.value = "2.5";
rawWidthControl.listeners.input[0]({target: rawWidthControl});
assert.equal(api.getState().rawWidthPt, 2.5);

const tickControl = elements.get("major-ticks");
tickControl.value = "6";
tickControl.listeners.input[0]({target: tickControl});
assert.equal(api.getState().majorTickTarget, 6);

const xGapControl = elements.get("x-axis-title-gap");
xGapControl.value = "0.4";
xGapControl.listeners.input[0]({target: xGapControl});
assert.equal(api.getState().axisTitleGapEmX, 0.4);
const yGapControl = elements.get("y-axis-title-gap");
yGapControl.value = "0.2";
yGapControl.listeners.input[0]({target: yGapControl});
assert.equal(api.getState().axisTitleGapEmY, 0.2);

elements.get("export-svg").listeners.click[0]();
assert.equal(elements.get("status").textContent, "90 mm SVG exported.");
const exportRoot = new ElementStub("svg", "export-root");
const exportHover = new ElementStub("g", "hover-tooltip");
const exportTitle = new ElementStub("text", "export-title");
exportTitle.classList.add("layout-editable", "layout-selected");
exportTitle.setAttribute("data-layout-role", "title");
exportTitle.setAttribute("data-label", "Figure title");
exportTitle.setAttribute("tabindex", "0");
const exportCurve = new ElementStub("path", "export-curve");
exportCurve.classList.add("scientific-locked");
exportCurve.setAttribute("data-label", "Raw curve");
exportRoot.appendChild(exportHover);
exportRoot.appendChild(exportTitle);
exportRoot.appendChild(exportCurve);
api.sanitizeSvgExport(exportRoot);
assert.equal(exportHover.getAttribute("visibility"), "hidden");
assert.equal(exportTitle.classList.contains("layout-selected"), false);
assert.equal(exportTitle.classList.contains("layout-editable"), false);
assert.equal(exportTitle.getAttribute("data-layout-role"), null);
assert.equal(exportCurve.classList.contains("scientific-locked"), false);
assert.equal(exportCurve.getAttribute("data-label"), null);
elements.get("reset").listeners.click[0]();
assert.equal(api.getState().fontPt, 7);
assert.equal(api.getState().rawWidthPt, 1.0);
assert.equal(api.getState().majorTickTarget, 6);
assert.equal(api.getState().axisTitleGapEmX, 0.3);
assert.equal(api.getState().axisTitleGapEmY, 0.2);
assert.equal(elements.get("plot-title").textContent, "Synthetic resonance response");

console.log("editable_html_dom_test=passed");
