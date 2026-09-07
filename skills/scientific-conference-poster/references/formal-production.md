# Formal poster production

Read this reference only after the current editable HTML wireframe has been reopened and explicitly approved.

## One-file output

Create one formal editable HTML file by copying or versioning the approved wireframe. Do not automatically produce PNG previews, PDF, PPTX, SVG sidecars, layout JSON, or Markdown notes.

## In-place replacement contract

- Preserve the approved production-bound DOM/CSS scaffold and `data-layout-id` membership.
- Replace provisional text and figure placeholders inside their existing wrappers.
- Preserve section bands, numbering, reading order, evidence groups, typography tokens, spacing rhythm, and major geometry.
- A generator may locate ids and replace contents; it may not create a new page grid or reinterpret the wireframe.
- If markers are missing or editor-only borders are ambiguous, correct and refreeze the wireframe before production.
- If real content cannot remain readable in the slot, return to the wireframe instead of shrinking type or silently resizing sections.

## Scientific figure replacement

Obtain a standard semantic SVG from `scientific-plotting` for every quantitative module. Inline it and adapt it with the poster slot adapter. Preserve figure-model metadata and exact/approximate source markers. Do not use screenshots or raster crops for quantitative data.

The poster adapter may change plot-box aspect, margins, type/stroke/tick tokens, legend and annotation placement, and module gaps. It must recalculate internal geometry from semantic groups/model coordinates and must not apply non-uniform scaling to the whole SVG.

For each quantitative slot, pass its frozen physical width, height, and poster base token `B` to the adapter. The output `viewBox` numbers must equal the slot dimensions in millimetres so one SVG user unit equals one millimetre. Treat slot capacity and readable type as independent constraints: resize/reflow the data region when the slot changes, and revise the wireframe when the approved `B` cannot fit. Do not use `non-scaling-stroke`.

Use proportional placement for photographs, micrographs, and visual assets without a coordinate model. Each figure gets clear space on all four sides and must not touch headings, dividers, captions, or adjacent modules.

## Poster visual rules

- Use the accepted abstract title exactly.
- Mark the presenter in the author list with red, bold, underlined text.
- Put one affiliation on each line; keep approximately one author-font-size gap before affiliations, about `0.5em` between affiliation lines, and a compact gap below the affiliation block.
- Keep native text black and at least normal weight; use size, weight, and spacing for hierarchy.
- Keep the active palette to black, red, blue, and green unless an approved venue/brand exception applies.
- Make the local gap between primary and secondary information larger than spacing inside the secondary group.
- Use a flat page without an outer frame or repeated nested boxes. Use square corners for necessary enclosure.
- Keep editor controls hidden in print mode.

## Cheap integrity check

Run [check_poster_integrity.py](../scripts/check_poster_integrity.py) against the formal HTML and, when available, the approved wireframe. It checks parsing, finite values, required/unique ids, local references, `data-layout-id` membership, and standard inline semantic SVG presence.

It does not compare browser-computed positions or styles, inspect scientific meaning, conduct visual QA, or establish print readiness. Do not generate multi-round screenshots or repeat layout changes merely to satisfy an automated aesthetic score.

Report `file integrity satisfied; awaiting user review`. The user owns final scientific, visual, and print acceptance.

## Handoff disclosure

List:

- approved wireframe and formal HTML;
- exact and approximate scientific modules;
- blocked sources or returns to wireframe;
- any custom workaround made because a Skill condition was unavailable;
- cheap checks performed;
- user-review items.
