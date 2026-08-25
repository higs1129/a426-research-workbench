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
    this.textContent = "";
    this.value = "";
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

  getBoundingClientRect() {
    return {left: 0, top: 0, width: 340, height: 220};
  }

  click() {}

  cloneNode(deep = false) {
    const clone = new ElementStub(this.tagName, this.id);
    clone.attributes = {...this.attributes};
    clone.style = {...this.style};
    clone.textContent = this.textContent;
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
};

const context = {
  Blob,
  console,
  document: documentStub,
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
assert.equal(api.getState().fontPt, 7);
assert.equal(api.getState().fontFamily, 'Calibri, "Microsoft YaHei", sans-serif');
assert.equal(api.getState().title, "Synthetic resonance response");
assert.ok(!api.getState().title.includes("合成"), "Default title should not be bilingual");
assert.equal(api.getState().interactionMode, "zoom");
assert.equal(elements.get("box-zoom-mode").getAttribute("aria-pressed"), "true");
assert.equal(elements.get("pan-mode").getAttribute("aria-pressed"), "false");
assert.ok(!html.includes('id="clear-selection"'), "Transient hover must not need Clear selection");
assert.ok(!html.includes('id="selected-point"'), "Persistent point selection should not be present");
assert.ok(!html.includes('id="grid"'), "Figure must not render a grid group");
assert.ok(html.includes("#chart text { fill: #000; }"), "All SVG text should default to black");
assert.ok(html.includes('id="hover-guide-x" stroke="#217565" stroke-width="1.4" stroke-dasharray="5 4"'));
assert.equal(elements.get("raw-line").getAttribute("stroke-width"), String(4 / 3));
assert.equal(elements.get("markers").children.length, 11);
for (const eventName of ["wheel", "pointerdown", "pointermove", "pointerup", "pointerleave", "keydown"]) {
  assert.ok(elements.get("interaction-surface").listeners[eventName]?.length, `Missing ${eventName} interaction`);
}
for (const buttonId of ["box-zoom-mode", "pan-mode", "zoom-in", "zoom-out", "reset-view"]) {
  assert.ok(elements.get(buttonId).listeners.click?.length, `Missing ${buttonId} action`);
}
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
});
assert.equal(api.getState().title, "Edited response");
assert.equal(elements.get("plot-title").textContent, "Edited response");
assert.ok(Math.abs(parseFloat(elements.get("chart").style.fontSize) - 10 * 4 / 3) < 1e-9);
assert.ok(Math.abs(Number(elements.get("raw-line").getAttribute("stroke-width")) - 2.2 * 4 / 3) < 1e-9);
assert.equal(elements.get("markers").children.length, 11);
assert.equal(elements.get("figure-wrap").style.width, "min(100%, 820px)");

const surface = elements.get("interaction-surface");
surface.listeners.pointermove[0]({clientX: 186.5, clientY: 104.5, pointerType: "mouse"});
assert.notEqual(api.getHoverIndex(), null);
assert.equal(elements.get("hover-crosshair").getAttribute("visibility"), "visible");
assert.equal(elements.get("hover-tooltip").getAttribute("visibility"), "visible");
assert.match(elements.get("hover-readout").textContent, /Frequency: \d+\.\d{3} kHz; response: \d+\.\d{6}/);
assert.match(elements.get("hover-tooltip-value").textContent, /x \d+\.\d{3}; y \d+\.\d{6}/);
assert.notEqual(elements.get("hover-guide-x").getAttribute("x1"), null);
assert.notEqual(elements.get("hover-guide-y").getAttribute("y1"), null);
surface.listeners.pointerleave[0]();
assert.equal(api.getHoverIndex(), null);
assert.equal(elements.get("hover-crosshair").getAttribute("visibility"), "hidden");
assert.equal(elements.get("hover-readout").textContent, "Hover over the curve to inspect a raw value.");

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

elements.get("export-svg").listeners.click[0]();
assert.equal(elements.get("status").textContent, "90 mm SVG exported.");
elements.get("reset").listeners.click[0]();
assert.equal(api.getState().fontPt, 7);
assert.equal(api.getState().rawWidthPt, 1.0);
assert.equal(elements.get("plot-title").textContent, "Synthetic resonance response");

console.log("editable_html_dom_test=passed");
