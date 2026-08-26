# Formal poster production and release review

Read this reference only after the current editable HTML wireframe has been re-read, summarized as a layout contract, and explicitly approved for formal production.

## Default output

Create one formal editable HTML file. Keep CSS, poster text, generated SVG or DOM figures, editing state, and necessary metadata inside that HTML when practical. Reuse authoritative input assets without creating duplicate derived files unless embedding is required for the one-file HTML deliverable.

Do not automatically generate PNG previews, normal/wide screenshot pairs, PDF exports, PPTX files, layout JSON, Markdown production notes, or other sidecars. Perform browser rendering and screenshot checks in an isolated temporary directory without copying the QA artifacts into the task directory.

If the user explicitly requests a non-HTML deliverable, generate only the requested format and variants. If conference or printer rules appear to require PDF or another format but the user has not requested it, report the requirement and ask before generating it.

## Build from the approved contract

- Read and apply [poster-visual-system.md](poster-visual-system.md) as the default production contract unless the approved style brief records an explicit override.
- Use the confirmed accepted abstract title exactly, allowing only layout line breaks and whitespace normalization.
- Represent the presenter within the author list using the visual-system red, bold, underlined treatment; preserve author order, affiliation mapping, and authorship markers from the source.
- Read [figure-extraction-and-placement.md](figure-extraction-and-placement.md) before cropping, masking, or extracting any scientific image from a composite source.
- Preserve the approved panel order, relative prominence, and central message.
- Use authoritative local material and keep source locations traceable.
- Invoke `scientific-plotting` for every new or revised scientific chart.
- Distinguish raw data, processed data, fits, models, annotations, and proposed applications.
- Preserve meaningful image crops and aspect ratios; confirm all four source boundaries before placement and keep axes, scale bars, legends, plot boxes, and required annotations complete.
- Keep author, affiliation, citation, funding, logo, contact, and permission details exact.
- Keep unresolved items visibly in the production record, not as plausible invented poster text.

## HTML profile

- Declare the physical page size and orientation with print CSS.
- Express final poster typography in physical units such as `mm` or an equivalent calibrated system, and verify the effective printed sizes against the visual-system minima. Do not rely on browser zoom to make undersized text appear acceptable.
- Use at least `font-weight: 400` for native poster text and `700–800` for key information. Keep native prose, captions, and affiliations black; express hierarchy through size, weight, spacing, and placement. Audit computed sizes against both the physical minima and author-anchored ratios; use the larger required value.
- Keep title, authors, affiliations, contact, presenter details, and required marks as one visually contiguous header block. Give each affiliation one full-width row. Set author-to-affiliation spacing near one author-size `em`, affiliation-row spacing near `0.5em`, and the bottom gap below the affiliation block near `0.5–0.75em` of the affiliation size.
- Size the header and subsequent page rows from content using normal flow or content-sized grid rows. Reflow all later sections after affiliation changes; fixed heights, distributed flex space, and retained absolute positions must not leave an empty header band.
- Use the semantic spacing rhythm from the visual system. The local gap between primary information and its secondary explanation is visibly larger than spacing within the secondary group, while the surrounding container remains compact. Treat a blank band larger than two body line heights as intentional only when it marks a major section transition.
- Use an open page without an outer frame. Group sections and figures through alignment, whitespace, headings, and the minimum local dividers needed for the reading path. Keep ordinary enclosing-border depth to one level; any used enclosure has square corners and no shadow.
- Give each figure at least half a body-text size of clearance on all four sides from poster dividers and neighboring elements.
- Use local assets and provide a clean print mode without editor controls.
- Prefer SVG for regenerated data plots and vector diagrams when practical.
- Verify that referenced local assets exist and that no accidental remote dependency is required for printing.
- If visual editing controls are included, keep their state separate from scientific data and ensure exported or saved layout can be reopened.
- Mark key elements with stable semantic roles such as `data-role="poster-title"`, `data-role="author-list"`, `data-role="presenter"`, `data-role="affiliations"`, and `data-role="figure-region"` so source and layout checks can target the intended elements.
- Inspect the actual page through a local-only browser workflow at normal zoom and in print preview.
- Keep test screenshots and print-preview captures outside the task directory unless the user explicitly requests them as deliverables.

## Explicit non-HTML requests

- For PNG, confirm the requested viewport, crop, scale, and whether HTML should also be delivered. Generate one image unless multiple views are explicitly requested.
- For PDF, preserve the approved physical page size and inspect the exported PDF independently.
- For editable PPTX, keep text, shapes, figures, and logos as separate native objects where practical; do not call a flattened poster image editable.
- For LaTeX, use it only when explicitly requested or when an established user-provided source must be maintained.

## Release review

Verify at least:

1. current conference dimensions, orientation, naming, format, and file-size rules;
2. exact accepted-abstract title, author order, presenter styling, affiliations, contact, citations, acknowledgements, and required marks;
3. every scientific number, unit, caption, conclusion, and limitation against its source;
4. visual hierarchy at distance, browse, and close-reading scales;
5. native text is black or a confirmed semantic accent, uses weight `400` or stronger, and passes both the physical-size minimum and the author-anchored relative-size ladder;
6. each affiliation occupies one full-width row; its row spacing and bottom gap match the compact header rhythm; the next section begins from the reflowed header boundary without a residual blank band;
7. each primary-to-secondary information pair has a visibly larger local gap than lines within the secondary group, without expanding the entire surrounding container;
8. every extracted scientific image passes the four-boundary gate plus both the source-integrity and poster-placement reviews, including complete axes, scale bars, legends, plot boxes, clean edges, and four-sided clearance;
9. final raster effective resolution and vector rendering quality;
10. fonts, symbols, equations, the four-active-hue limit, color contrast, redundant non-color encodings, grayscale behavior inside scientific figures when relevant, and printer color handling;
11. QR targets and visible fallback text when QR codes are used;
12. one-page physical dimensions, trim, safe margin, and bleed according to the printer rather than assumption;
13. a reduced-scale print or equivalent physical-size review before release, without preserving an extra image file unless requested.

Also audit the structural CSS and rendered artwork for fixed or stretched header rows, multicolumn affiliation placement, an outer page frame, repeated enclosing borders, rounded semantic enclosures, gradients, card shadows, extra semantic hues, gray native text, light font weights, weak primary-to-secondary separation, and broken header continuity. A physically or relatively small text style, fifth hue, unconfirmed crop boundary, incomplete crop, unsafe figure inset, residual blank band, or repeated frame hierarchy is a release defect unless an approved exception records why it is necessary.

Any structural revision returns to the editable HTML wireframe contract. Any scientific change returns to source and content-priority review. Re-run affected production checks after each change.

## Status language

Use precise handoff states:

- **working draft:** content, layout, or sources remain unresolved;
- **layout approved:** the board contract is confirmed, but formal rendering or scientific checks remain;
- **author-approved:** the author has reviewed the current content and composition;
- **print-ready candidate:** technical preflight passed, subject to the confirmed printer or venue process.

Do not call a file print-ready merely because it exported successfully.
