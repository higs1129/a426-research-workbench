# Editable HTML scientific figures

Read this reference only when an HTML figure is requested or a report needs an embedded editable figure.

Poster use is not a separate plotting profile. A poster receives the standard semantic SVG and adapts it through the figure model; do not attach zoom, pan, hover, or the editable-figure runtime merely because an SVG is inline.

## Outcome

Deliver a browser figure whose scientific data remain traceable and whose meaningful presentation state can be changed without editing source code. An SVG node tree visible in developer tools is not sufficient by itself; provide user-facing controls for the requested editing scope.

## Rendering and state

- For ordinary single-linear-axes line, scatter, spectrum, and similar standard data plots, prefer the Matplotlib SVG fast path in [matplotlib-fast-path.md](matplotlib-fast-path.md). Matplotlib should construct the vector figure; do not reimplement its coordinate transforms, axes, ticks, and initial SVG geometry in task code.
- Select one supported SVG/DOM adapter for the figure before production; its component supplies every delivery view.
- Avoid Canvas, WebGL, raster-only images, and Plotly WebGL traces when element-level editing is required. Use them only for data density that SVG cannot handle, and disclose the loss of editability.
- Keep three layers distinct:
  1. authoritative data and provenance;
  2. semantic figure state, such as the fixed delivery-profile identity, labels, axes, colors, sizes, visibility, major-tick target, current view range, inspection mode, presentation-element offsets, and per-element presentation overrides; keep transient hover and selection state separate from serialized scientific state;
  3. the rendered SVG view.
- Read delivery defaults from `../assets/style-profiles.json`, which is shared with the Matplotlib path. Select exactly one profile before rendering and embed only that profile object into standalone output so it remains offline and reproducible; do not retype a second set of JavaScript-only defaults.
- Treat physical export width and height as immutable structural state in a formal figure. A 90 mm figure and a 185 mm figure are two generated deliverables, not two runtime views of the same deliverable. Changing profile requires regeneration.
- Editing presentation state must not silently alter source data, fitted values, uncertainty, or exact reported optima.
- Use `Calibri, "Microsoft YaHei", sans-serif` as the default SVG/CSS font stack so English uses Calibri and Chinese falls back to Microsoft YaHei. Keep all in-figure titles explicitly black.
- Use English-only figure, axis, and panel titles by default. Switch them to Chinese only when the current user explicitly requests Chinese; do not show bilingual duplicate titles.
- Do not render grid lines unless the current user explicitly requests them.

### Archival inline-data contract

When an editable HTML figure is intended to become a reusable scientific source, keep it self-contained and include the authoritative physical data, axes and units, scale/domain definitions, series semantics, stable `data-series-id` mappings into the rendered SVG, renderer version, and provenance. The HTML is a qualified source only when those elements can regenerate or verify the visual result without reading screen coordinates or loading a network/machine-local file. Read [source-and-svg-contract.md](source-and-svg-contract.md).

This is the preferred archive for newly generated figures when practical, not a requirement to rewrite every historical SVG or AI file. Sharing a qualified HTML also shares its embedded data.

## Production fast path

- For a standard single-axes figure, read [matplotlib-fast-path.md](matplotlib-fast-path.md) and use `../scripts/render_matplotlib_editable.py`. Keep only `load_data()` and `build_figure(data, profile)` in the task-local Python generator. The renderer applies the selected profile, preserves SVG text with `svg.fonttype = "none"`, embeds the SVG and authoritative data, and loads the maintained interaction bridge.
- Use `../assets/editable-figure-runtime.js` as shared interaction infrastructure. The standard bridge at `../assets/matplotlib-svg-bridge.js` supplies zoom, pan, hover, tick redraw, basic label/font/line editing, direct selection and movement of supported presentation elements, bounded layout undo, and clean SVG export without a project-specific HTML application.
- Read [renderer-contract.md](renderer-contract.md) and create a custom adapter only when the figure has multi-axes, nonlinear or broken scales, specialized linked annotations, diagram-like visual structure, or other effects outside the standard bridge contract.
- Reuse its wheel and button zoom, box zoom, pan, inspection dispatch, persistence/history helpers, measured horizontal-title placement, and clean-export sanitization unless the requested figure exposes a real missing capability. Layout-edit roles and scientific rendering remain adapter-owned because they vary by figure.
- Keep task-specific code with the task output and limit the standard route to locating data, constructing Matplotlib artists, declaring units and labels, and returning the figure, axes, and supported series. Do not copy a second independently evolving renderer into the task folder.
- Bundle the task shell, adapter, JSON data, one fixed profile, and shared runtime with `../scripts/bundle_editable_figure.py`; the final HTML must not depend on the Skill path or a network connection.
- During ordinary figure generation, produce only the requested deliverable and run cheap deterministic checks on it. Do not regenerate Skill fixtures, test both physical-width profiles, create debug screenshots, open a browser for generic visual inspection, or run browser/DOM regression suites unless the user explicitly requests testing, deterministic checks identify an unresolved risk, or reusable renderer code is being changed.
- When the selected renderer lacks a required capability, describe the missing behavior and its effect on the confirmed figure. Confirm an adapter change or extension before continuing; keep one rendering implementation for that figure.

The callbacks defined by the renderer contract are JavaScript extension points inside the generated figure. They are unrelated to Codex lifecycle Hooks and must not be implemented through global Codex configuration.

## Editing contract

Expose controls appropriate to the figure for:

- responsive screen-preview width and, when scientifically safe, plot height or aspect ratio; do not let these controls change the fixed physical export width class;
- title, axis labels, legend labels, and annotations;
- font family, size, and weight; title color must reset to black;
- data, fit, guide, and axis stroke widths, colors, dash patterns, and opacity;
- marker shape, diameter, border, and opacity; for scatter and point-line series, initialize marker diameter to half the axis tick-label font size unless the user or authoritative source explicitly sets another value, and expose marker diameter as independent semantic presentation state;
- axis range, linear/log scale, tick count, and numeric formatting;
- typography and stroke tokens initialized from the fixed delivery profile. At export size, the 185 mm profile uses 12 pt ticks, ordinary plot text, axis labels, and legend text, plus a 10 pt figure title;
- compact hover-title and hover-value sizes independent of the plot font; the 185 mm defaults are 9 pt and 8 pt so inspection does not cover a large fraction of the trace;
- legend placement and trace visibility;
- panel spacing and shared-axis behavior for composites.

Use semantic controls and regenerate the view from state. Direct manipulation is allowed only as a semantic shortcut for presentation elements:

Do not expose a delivery-profile selector in a formal standalone or embedded figure. The shared configuration may contain several profiles for generator use, but the output must carry only the selected profile and fixed `exportWidthMm`/`exportHeightMm`. A runtime selector is acceptable only in an explicitly requested comparison/demo page that is clearly labeled as non-final.

- figure title, axis titles, legend, panel labels, non-data-anchored explanatory notes, and each axis's numeric tick-label group may be selected and repositioned;
- x-axis numeric labels move as one group, and y-axis numeric labels move as one group; the shared offsets are presentation state, while individual values, tick marks, and tick positions remain unchanged;
- a data-linked annotation may move its label box while its authoritative anchor remains fixed;
- curves, measured points, fitted/theory coordinates, uncertainty geometry, axis scales, tick values, tick marks, tick positions, and data-linked anchors remain locked;
- selecting a locked element should give a concise explanation instead of silently doing nothing.

Keep direct-edit offsets and overrides in semantic state rather than treating the mutated SVG markup as the source of truth. Provide bounded undo, restore defaults, current-state serialization, browser-local persistence when appropriate, and SVG export; add PNG export when useful. Strip selection outlines, hover guides, brushes, hit targets, and editor-only metadata from clean exports.

## Direct layout editing

- Default to data inspection. Enter direct editing through an explicit, visibly selected `Edit layout` control; do not overload the same left drag with box zoom, pan, and element movement.
- In layout-edit mode, clicking an eligible element highlights it and opens a context-specific inspector containing only relevant fields. Give composite presentation elements a transparent whole-bounds hit target so the empty space inside a legend or grouped tick labels is selectable. Allow direct drag in SVG coordinates and provide numeric offsets for precise adjustment.
- Keep the editor collapsible. Selecting an eligible element may reopen it automatically. On narrow screens, use a side drawer or place the inspector below the figure without covering the evidence.
- Save meaningful edits and the current view into the portable HTML state. Embedded state is authoritative on reopen; browser-local caches are optional convenience and never silently replace the report's saved baseline. Use a figure-specific, versioned identity.
- Keep a bounded undo history, an obvious default restoration action, and concise status feedback for selection, drag completion, saving, undo, reset, and export.
- Support keyboard selection with Enter or Space for focusable presentation elements. Provide visible focus and selected states that do not appear in exported figures.

For linear axes, target about 5-6 visible major ticks and choose a nice step from `1, 2, 2.5, 5, 10 × 10^n`. Do not generate ticks by equally interpolating arbitrary endpoints, and do not require the first or last axis limit to be a tick. Recompute nice ticks after zooming or panning.

Keep the clear tick-mark-to-number gap at about `0.28 em` of the tick-label font on both axes. For a horizontal legend immediately above the axes, keep the clear legend-to-top-spine gap at about `0.25 em` of the legend font unless collision handling requires a different placement. Store both as delivery-profile tokens so Matplotlib initialization and the interactive SVG redraw use the same values.

Store horizontal and vertical axis-title spacing separately. Default the horizontal title to `0.3 em` and the rotated vertical title to `0.2 em` of the axis-title font. After inserting the tick labels and applying final font styles, measure their rendered SVG boxes with `getBBox()`. Place the horizontal title so its top edge is exactly the requested distance below the lowest tick-label edge; do not add that distance to a separate hard-coded baseline allowance or bottom margin. Measure again after a font-size, font-family, tick-format, zoom, or label-text change. Use an estimate only when `getBBox()` is unavailable, and replace it after the SVG enters the document.

## Inspection interactions

- Support wheel zoom on desktop and visible zoom buttons as a pointer-independent fallback. Zoom around the pointer or current plot center while keeping axes and titles screen-readable.
- Make `Box zoom` the default pointer mode. A left-button drag draws a visible selection rectangle; releasing it zooms both x and y ranges to that rectangle. Treat very small drags as hover/tap inspection rather than accidental zoom.
- Provide an explicit, visibly selected `Pan` mode. In this mode, left-button drag moves both axis ranges. Change the cursor and concise nearby instruction with the active mode so the gesture is discoverable.
- Recompute data geometry, axes, ticks, markers, hover guides, and annotations from the updated view range rather than scaling a group that contains text.
- On desktop hover, snap to the nearest visible raw data point. Draw a solid focus marker with dashed horizontal and vertical guides through the point, and show its series identity and exact source values in an in-chart tooltip or adjacent readout.
- Size the in-chart tooltip from its content, use the separate compact hover tokens, cap its width when practical, and place it on the side of the point with more room. Never inherit the wide figure's main 12 pt plot font by accident.
- Hover inspection is transient: clear the focus marker, guides, and values on pointer leave. Do not create a persistent click selection or a `Clear selection` control unless the current user explicitly asks for pinning or multi-point comparison.
- Provide keyboard/focus and touch fallback for the exact readout without changing authoritative values. A focused plot may use arrow keys to move a virtual inspection cursor; a touch tap may show the nearest value until the next tap or reset because touch has no hover state.
- Keep visible `Box zoom`, `Pan`, and `Reset view` controls. Wheel zoom remains active in either pointer mode.
- Interpret “move” as moving the viewport. Never let pointer interaction move a measured point or rewrite authoritative data unless the current user explicitly requests a separate data-editing workflow.
- When switching to layout-edit mode, suspend plot hit targets and disable or visually deactivate box zoom, pan, and view-reset controls. Restoring inspection mode must re-enable them without changing data or the current viewport.

## Two delivery modes

### Embedded report figure

- Use [report-component.md](report-component.md) and the maintained report bundler. Each self-contained figure lives in one inline `srcdoc` iframe, isolating its CSS, ids and state; expanding it keeps that same instance.
- Keep presentation editing controls collapsed by default. A common report style is proposed before figure generation and applied through figure configuration; report CSS controls only surrounding layout.

### Standalone figure

- Generate a self-contained HTML file that opens offline without a build step or network dependency.
- Include the data or a documented local payload, the initial state, the SVG view, editing controls, reset, state download, and SVG export.
- If the HTML embeds authoritative or sensitive data, tell the user that sharing the file also shares those data.

Use the same component for embedded, expanded and standalone modes; export from its declared current state and save figure state alongside report prose.

## Responsive behavior

- Preserve the 90 mm publication panel as an export baseline when appropriate, but render it at a comfortable responsive screen width rather than literal browser millimeters.
- Keep essential values and labels visible without hover. Replace hover-only actions with tap or focus on touch devices.
- On narrow screens, place editing controls below the figure or in a collapsible panel and keep the evidence visible above them.

## Validation policy

For ordinary production, stop after the requested HTML has been generated and cheap deterministic checks confirm its profile, labels, editable SVG structure, required controls, and known spacing tokens. Do not open the figure in a browser merely to “look once”; an unstructured visual pass is slow and is not a reliable substitute for assertions tied to the user's requirements.

Run the detailed checklist below only when the user asks for validation, deterministic checks identify a layout uncertainty, the figure uses a genuinely custom/complex visual structure, or the reusable renderer itself has been changed. When browser validation is justified, make it targeted: assert the specific geometry or interaction that changed, and avoid repeated screenshot-driven aesthetic iteration.

When applicable:

1. Open the actual HTML offline at normal browser zoom.
2. Confirm the chart uses SVG/DOM for the editable marks and text.
3. Change at least one text property, one stroke width, one marker property, and one layout property; verify the rendered figure updates.
4. Confirm the width choice follows feature structure: a one-peak or one-trend example remains single-column, while a broad scan with several distinct peaks selects the 180-185 mm profile. Confirm the generated formal HTML contains no 90/185 mm selector and cannot mutate its physical export width at runtime.
5. For each linear axis, confirm roughly 5-6 visible major ticks with readable nice values at the initial view and after zoom; confirm arbitrary limits are not mechanically interpolated into labels.
6. Confirm from rendered bounding boxes that the horizontal axis-title gap is about `0.3 em` and the rotated vertical gap about `0.2 em`, without clipping or a visually detached title. Confirm the implementation did not stack the nominal gap on top of fixed baseline or margin allowances.
7. Hover a raw point and confirm the solid focus marker, dashed two-axis guides, and exact authoritative values appear; for 185 mm verify the tooltip uses 9 pt/8 pt text and remains compact; move outside the plot and confirm all transient inspection marks disappear.
8. Use left-drag box zoom and confirm both axis spans change. Switch visibly to Pan, left-drag in two dimensions, then Reset view and confirm the declared full data range returns.
9. Export SVG and serialized state, reopen them when practical, and confirm labels, sizes, current view, interaction mode, and data remain intact; transient hover and brush overlays should not become scientific annotations.
10. Check desktop and narrow/mobile widths for clipping, overlap, hidden evidence, inaccessible controls, and scroll/gesture conflicts.
11. Confirm the default titles are English only, the Calibri/Microsoft YaHei fallback remains available for an explicitly requested Chinese version, no grid lines are rendered, and every in-figure title is black.
12. Compare the single embedded profile with `assets/style-profiles.json` and confirm Matplotlib and HTML/SVG previews resolve the same physical size, typography, line, marker, tick, and gap tokens.
13. Enter layout-edit mode, select and drag a title or the whole legend bounds, edit one property, undo it, save the HTML and reopen that file to confirm portable state is restored. Select each axis's tick-label group, change its offset and confirm labels move together while values and tick marks stay fixed. Confirm the inspector shows only relevant fields and can be collapsed.
14. Attempt to drag a curve, measured point, axis spine, and tick mark. Confirm each remains fixed and the interface explains the semantic lock. Return to inspection mode and verify hover, box zoom, pan, and Reset view still work.
15. Export after selecting and dragging a presentation element. Confirm the semantic edit is present while selection glow, hover guides, brush rectangle, interaction surface, and editor-only metadata are absent.
