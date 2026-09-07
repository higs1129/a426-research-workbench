# One scientific figure component in a report

Read for embedding an interactive scientific figure, saving reports containing figures, or developing their shared tools.

## Ownership and state

`scientific-plotting` owns data mapping, axes/ticks/formatting, legend, typography, measured spacing, interaction, figure state and SVG export. `research-progress-summary` owns prose, sources, page placement and report saving.

Choose and confirm the scientific content and adapter once. Keep the data and full presentation state with that figure. Container enlargement preserves its domains, ticks, legend and relative geometry. A new physical export size is a separate confirmed layout decision.

The Matplotlib path exposes `window.ScientificFigure`:

- `ready`: fonts and measured initial layout have settled;
- `getState()`: a portable copy of current style/layout and view range;
- `serializeHtml()`: self-contained HTML carrying that state;
- `exportCurrentSvg()`: clean semantic SVG matching the current displayed state;
- `setView(view)`: explicit viewport operation.

Default inspection is transient hover/focus/touch readout. Persistent point pinning or comparison is an explicitly requested capability. Hover guides and editor selection outlines are transient and disappear from exports.

## Production entry

Generate each supported single-linear-axes figure with `scripts/render_matplotlib_editable.py`. Provide confirmed legend presence/placement and tick strategy in `build_figure`; exact tick lists use `FixedLocator`, while a periodic locator includes the intended origin. For example, `[1,4,7,10,13,16]` is a different confirmed layout from multiples of three starting at zero.

When an exact semantic model already exists, use the same entry with `--model figure-model.json --profile-id 90mm-single --output figure.html` instead of `--plot-script`. This adapter accepts linear polyline/scatter/point-line series, explicit ticks, colors, line/marker sizes, `legend: {visible, loc}`, and optional `presentation.marginsMm`; model height and profile must match the selected physical configuration. Unsupported fields stop with a capability message so presentation choices remain explicit. Both input forms produce the same maintained component, including its initial axes and legend.

The report shell reserves one slot per figure and one runtime slot:

```html
<!-- SCIENTIFIC_FIGURE:measurement -->
<!-- SCIENTIFIC_REPORT_RUNTIME -->
```

A JSON manifest gives `id`, `label`, and `html` (relative to that manifest):

```json
[{"id":"measurement","label":"Measurement response","html":"assets/measurement.html"}]
```

Run with explicit task paths:

```text
python scripts/bundle_report_figures.py --shell report-shell.html --figures figures.json --output report.html
```

This embeds the same figure document once in an isolated iframe. Its expand control enlarges that instance without navigation, data reload or new axes. Page CSS affects the container; figure typography and geometry remain adapter-owned. The final report opens offline without the source HTML files or a server.

For report saving, use `await ScientificReport.serializeHtml()` inside the report's save workflow, or attach the download handler to a `data-sf-save-report` button. This captures both report text and every component's current state. Save standalone figures with their `Save current figure HTML` control. Browser caches are not required for reopening or sharing these files.

SVG export uses current state. Its metadata records current domains, labels and presentation state. The unit conversion from Matplotlib points to a millimetre root preserves the existing geometry; it introduces no new axes or layout. Use the semantic integrity checker on an exported SVG when changing this tool.

## Capability and verification boundary

The bundler accepts components implementing this API, currently the maintained Matplotlib bridge. A custom adapter must implement and verify the same interface before report integration. On a capability error, report the precise gap and confirm any adapter/design change. Stop the affected output instead of substituting a raster or a second drawing path.

During shared-tool development, run `python tests/test_report_component.py`. It uses synthetic single-scatter and double-point-line cases, real browser font bounds, normalized geometry at two container sizes, semantic export integrity and portable report save/reopen. Generated artifacts and browser profiles stay under `tests/` and are temporary.

Ordinary reports reuse these components. Check new data, embedded appearance and changed behavior once; the development regression is not part of each report's production workflow.
