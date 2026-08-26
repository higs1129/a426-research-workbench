# Scientific figure extraction and placement

Read this reference whenever a poster uses a crop, mask, screenshot, or subpanel extracted from a composite scientific figure. The goal is a complete, clean, source-traceable visual that preserves the scientific evidence and sits safely inside the poster layout.

## 1. Source priority

Use the highest-quality authoritative source available:

1. original EPS, SVG, or vector PDF;
2. original high-resolution PNG or TIFF;
3. an editable plot or figure source that can be regenerated through `scientific-plotting`;
4. extraction from a full composite figure;
5. a page or screen screenshot only when no better source is available.

Inventory the desired subpanel independently from the composite figure. Record the source file, target panel, caption meaning, required axes, scale bar, legend, colorbar, annotations, and intended poster role before cropping.

## 2. Extraction plan

For each extracted image, decide:

- the exact scientific object or panel that must remain;
- which neighboring panels, inherited panel letters, captions, or decorations belong outside the result;
- which labels, axes, scale bars, legends, and annotations are necessary for interpretation;
- whether the result will be cropped only, cropped and masked, or regenerated from an original source;
- whether the available resolution is adequate at final physical size.

When the target panel is ambiguous, confirm it from the caption, surrounding text, and user-approved content hierarchy. Visual convenience is not evidence that a particular subpanel is the intended one.

## 3. Four-boundary confirmation before cropping

Determine the target panel's top, right, bottom, and left semantic boundaries on the full source before creating the poster crop. The boundary includes every required axis title, tick label, scale bar, legend, colorbar, annotation, or object edge, while excluding neighboring panels and their labels.

Use this boundary gate:

1. display the full source with a visible candidate crop rectangle;
2. identify and record the four boundaries in source coordinates or normalized coordinates;
3. render the candidate crop alone at `200–300%` inspection scale;
4. inspect the top, right, bottom, and left edges separately for foreign fragments and missing target content;
5. revise the coordinates until all four edges pass;
6. place the crop into the poster only after the boundary gate passes.

The crop rectangle overlay and enlarged candidate are internal QA views, not additional deliverables. Keep the accepted coordinates in the HTML metadata. If the same edge remains ambiguous after comparison with the full source, stop approximate cropping and request an original source or a user-marked target boundary.

## 4. Optional white-mask cleanup

After the four-boundary crop passes, use non-destructive white rectangular masks only for small neighboring labels or irregular fragments that cannot be removed by a rectangular crop without losing target content.

For an HTML-first poster, implement masks inside the HTML when practical:

- an inline SVG can place the source image, apply the confirmed crop viewBox or clip path, and add white `<rect>` elements above neighboring material;
- an HTML wrapper can use `overflow: hidden` for the confirmed crop and positioned white elements for cleanup;
- embed or reference the authoritative source according to the one-file delivery decision rather than creating a derived PNG by default.

A mask may cover a neighboring panel, neighboring caption fragment, or inherited panel letter when the poster supplies its own unambiguous panel label. It must preserve every part of the selected data, axes, scale bar, legend, unit, uncertainty mark, and necessary annotation. Re-run the four-edge inspection after masking. If a clean result requires covering scientific content, request a better source.

## 5. Completeness profiles

### Micrographs and device images

Preserve:

- the complete intended object and meaningful surrounding context;
- the full scale bar and unit;
- orientation marks and labels needed to understand the device;
- the natural image boundary or a clean crop edge.

Remove neighboring-panel fragments and duplicated inherited panel letters through a verified crop or mask. Inspect the result for slivers along every edge.

### Plots and maps

Preserve:

- the full plotting box or intended open-axis geometry;
- x- and y-axis titles, units, ticks, and tick labels;
- legends, colorbars, normalization notes, and uncertainty encodings required for interpretation;
- annotations, arrows, regime labels, and panel headings used by the poster's claim.

Treat a crop that shows only a strip of a plot, loses an axis title, clips the native plot frame, or assembles discontinuous fragments as incomplete. Extract the whole intended subpanel or regenerate it from the original source.

### Schematics and composite explanatory figures

Preserve the arrows, labels, legends, object boundaries, and spatial relationships needed for the stated mechanism. If the poster needs only one branch of a composite schematic, verify that its labels remain interpretable outside the original context.

## 6. Placement clearance

Place every raster image, SVG, or masked extraction inside a figure region with visible clearance on all four sides. Use at least half of the poster body-text size as the minimum inset; for A0-class output this is typically about 4–6 mm. Increase the inset when axis titles, scale bars, or annotations approach the source edge.

The image content and its native plot boundary must remain separate from poster dividers, section rules, neighboring text, and the edge of any semantic enclosure. Group multiple figures through alignment, labels, captions, and whitespace rather than adding a frame around each image.

## 7. Source-quality gate

Pause extraction and request an original EPS, SVG, PDF, high-resolution raster, or editable plot source when:

- the target-panel boundary cannot be identified reliably;
- adjacent panels overlap the selected scientific content;
- required axes, scale bars, legends, or annotations are already clipped in the available source;
- white masks would cover real scientific content;
- the result is visibly soft, pixelated, or unreadable at final physical size;
- the source screenshot contains resampling, compression, or color artifacts that affect interpretation.

Apply this gate before poster placement. State which panel or boundary is needed and why the available source cannot produce a clean result. Continue with the existing source only after the user accepts the limitation or provides a replacement.

## 8. Traceability inside HTML

Keep crop decisions traceable without creating a sidecar file. Use HTML comments, embedded metadata, or stable data attributes such as:

```html
<figure
  data-source="relative/source/figure.pdf"
  data-source-panel="b"
  data-crop="left,top,right,bottom"
  data-boundary-status="confirmed"
  data-mask="left-label;right-neighbor"
  data-role="figure-region">
</figure>
```

Use project-relative or portable source identifiers when practical. Metadata describes the transformation; it does not replace reopening and visually comparing the result with the source.

## 9. Mandatory two-pass review

### Source-integrity pass

Compare the extraction with the authoritative source and verify:

- the full-source crop overlay and recorded coordinates describe the intended four boundaries;
- the intended panel and scientific object were selected;
- no target data or required annotation was removed or covered;
- no neighboring-panel fragment or duplicate label remains;
- each of the top, right, bottom, and left edges passes at enlarged inspection scale;
- scale, aspect ratio, color mapping, and orientation were preserved;
- the crop remains interpretable with its poster caption.

### Poster-placement pass

Render the HTML at intended physical size and verify:

- all four sides have the required inset;
- axes, tick labels, legends, scale bars, and plot boxes are complete;
- image content does not intersect a poster divider or neighboring element;
- effective resolution and text sharpness are adequate;
- open grouping and local dividers communicate the intended relationship without repeated frames.

A crop passes only when both reviews pass. Source quality and placement quality are separate checks.
