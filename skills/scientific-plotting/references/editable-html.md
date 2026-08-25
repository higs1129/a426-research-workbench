# Editable HTML scientific figures

Read this reference only when an HTML figure is requested or a report needs an embedded editable figure.

## Outcome

Deliver a browser figure whose scientific data remain traceable and whose meaningful presentation state can be changed without editing source code. An SVG node tree visible in developer tools is not sufficient by itself; provide user-facing controls for the requested editing scope.

## Rendering and state

- Prefer standard SVG/DOM traces through a declarative chart library, Plotly standard 2D traces, D3/SVG, or native SVG.
- Avoid Canvas, WebGL, raster-only images, and Plotly WebGL traces when element-level editing is required. Use them only for data density that SVG cannot handle, and disclose the loss of editability.
- Keep three layers distinct:
  1. authoritative data and provenance;
  2. semantic figure state, such as labels, axes, colors, sizes, visibility, current view range, and interaction mode; keep transient hover state separate from serialized scientific state;
  3. the rendered SVG view.
- Editing presentation state must not silently alter source data, fitted values, uncertainty, or exact reported optima.
- Use `Calibri, "Microsoft YaHei", sans-serif` as the default SVG/CSS font stack so English uses Calibri and Chinese falls back to Microsoft YaHei. Keep all in-figure titles explicitly black.
- Use English-only figure, axis, and panel titles by default. Switch them to Chinese only when the current user explicitly requests Chinese; do not show bilingual duplicate titles.
- Do not render grid lines unless the current user explicitly requests them.

## Editing contract

Expose controls appropriate to the figure for:

- figure width, height, and aspect ratio;
- title, axis labels, legend labels, and annotations;
- font family, size, and weight; title color must reset to black;
- data, fit, guide, and axis stroke widths, colors, dash patterns, and opacity;
- marker shape, diameter, border, and opacity;
- axis range, linear/log scale, tick count, and numeric formatting;
- legend placement and trace visibility;
- panel spacing and shared-axis behavior for composites.

Use semantic controls and regenerate the view from state. Do not turn the deliverable into a freeform vector editor that lets users drag ticks or data marks away from their encoded values. Provide reset, current-state serialization, and SVG export; add PNG export when useful.

## Inspection interactions

- Support wheel zoom on desktop and visible zoom buttons as a pointer-independent fallback. Zoom around the pointer or current plot center while keeping axes and titles screen-readable.
- Make `Box zoom` the default pointer mode. A left-button drag draws a visible selection rectangle; releasing it zooms both x and y ranges to that rectangle. Treat very small drags as hover/tap inspection rather than accidental zoom.
- Provide an explicit, visibly selected `Pan` mode. In this mode, left-button drag moves both axis ranges. Change the cursor and concise nearby instruction with the active mode so the gesture is discoverable.
- Recompute data geometry, axes, ticks, markers, hover guides, and annotations from the updated view range rather than scaling a group that contains text.
- On desktop hover, snap to the nearest visible raw data point. Draw a solid focus marker with dashed horizontal and vertical guides through the point, and show its series identity and exact source values in an in-chart tooltip or adjacent readout.
- Hover inspection is transient: clear the focus marker, guides, and values on pointer leave. Do not create a persistent click selection or a `Clear selection` control unless the current user explicitly asks for pinning or multi-point comparison.
- Provide keyboard/focus and touch fallback for the exact readout without changing authoritative values. A focused plot may use arrow keys to move a virtual inspection cursor; a touch tap may show the nearest value until the next tap or reset because touch has no hover state.
- Keep visible `Box zoom`, `Pan`, and `Reset view` controls. Wheel zoom remains active in either pointer mode.
- Interpret “move” as moving the viewport. Never let pointer interaction move a measured point or rewrite authoritative data unless the current user explicitly requests a separate data-editing workflow.

## Two delivery modes

### Embedded report figure

- Embed the SVG figure and its data/state directly in the report HTML.
- Keep per-figure controls collapsed by default so they do not interrupt the reading path.
- Namespace element ids, CSS, and state when several figures share a page.
- Allow a report-level style setting to update multiple figures when the report owns a common visual profile.

### Standalone figure

- Generate a self-contained HTML file that opens offline without a build step or network dependency.
- Include the data or a documented local payload, the initial state, the SVG view, editing controls, reset, state download, and SVG export.
- If the HTML embeds authoritative or sensitive data, tell the user that sharing the file also shares those data.

Use the same renderer and state model for embedded and standalone modes; change only the surrounding page shell.

## Responsive behavior

- Preserve the 90 mm publication panel as an export baseline when appropriate, but render it at a comfortable responsive screen width rather than literal browser millimeters.
- Keep essential values and labels visible without hover. Replace hover-only actions with tap or focus on touch devices.
- On narrow screens, place editing controls below the figure or in a collapsible panel and keep the evidence visible above them.

## Validation

Before finishing:

1. Open the actual HTML offline at normal browser zoom.
2. Confirm the chart uses SVG/DOM for the editable marks and text.
3. Change at least one text property, one stroke width, one marker property, and one layout property; verify the rendered figure updates.
4. Hover a raw point and confirm the solid focus marker, dashed two-axis guides, and exact authoritative values appear; move outside the plot and confirm all transient inspection marks disappear.
5. Use left-drag box zoom and confirm both axis spans change. Switch visibly to Pan, left-drag in two dimensions, then Reset view and confirm the declared full data range returns.
6. Export SVG and serialized state, reopen them when practical, and confirm labels, sizes, current view, interaction mode, and data remain intact; transient hover and brush overlays should not become scientific annotations.
7. Check desktop and narrow/mobile widths for clipping, overlap, hidden evidence, inaccessible controls, and scroll/gesture conflicts.
8. Confirm the default titles are English only, the Calibri/Microsoft YaHei fallback remains available for an explicitly requested Chinese version, no grid lines are rendered, and every in-figure title is black.
