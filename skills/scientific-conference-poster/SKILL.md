---
name: scientific-conference-poster
description: Creates and revises evidence-traceable scientific conference posters through staged requirements, source reading, content prioritization, style confirmation, an editable HTML wireframe, and wireframe-derived HTML production with semantic scientific SVG. Use for research poster preparation from abstracts, meeting folders, figures, and author materials. Do not use for slide decks, manuscripts, standalone scientific figures, or general promotional posters.
metadata:
  version: "2.1"
  skill-author: "Personal Research Workflow"
---

# Scientific Conference Poster

## Purpose and boundaries

Turn author-provided conference material into one editable HTML poster through explicit content, style, and layout gates. This Skill owns poster-level decisions, the editable wireframe, page layout, and adaptation of standard semantic scientific SVG into approved figure slots. Use `scientific-plotting` to create or reconstruct scientific figures; do not ask it to redesign the poster slot.

## Default artifact policy

Unless the user explicitly asks for another format, create exactly one HTML file for each requested wireframe or formal version. Keep decisions and contracts in the conversation or inside that HTML. Do not generate or preserve PNG previews, PDF, PPTX, SVG sidecars, layout JSON, or Markdown plans by default.

## Staged workflow

Use:

`requirements → source reading → content priorities → style brief → editable HTML wireframe → layout approval → formal replacement → user review`

Do not skip an unresolved gate. Reuse information already supplied.

### 1. Establish requirements

If the user has supplied no usable context, ask together for:

1. conference name and official notice/site;
2. accepted or intended abstract;
3. printed/electronic form, size, orientation, language, template, output format, deadline, and any short oral introduction;
4. authoritative conference material folder or document.

### 2. Read materials

Read the source project's applicable rules first. Inventory conference requirements, accepted abstract, authors/affiliations, figures/data, logos, citations, permissions, and prior visual material. Report conflicts rather than silently choosing a convenient version. The accepted abstract is authoritative for the poster title, including wording, symbols, punctuation, and capitalization.

Read [references/content-and-evidence.md](references/content-and-evidence.md). Classify scientific assets as `quantitative-data`, `image-evidence`, or `schematic`. Use [scripts/inspect_figure_sources.py](scripts/inspect_figure_sources.py) when candidate sources need a mechanical inventory.

### 3. Confirm message and priorities

After reading, ask only what is needed to learn the one remembered statement, hero evidence, mandatory/supporting/omittable content, audience, and whether the poster must stand alone. Propose a source-linked priority hierarchy and obtain confirmation before style design.

### 4. Confirm style

Read [references/poster-visual-system.md](references/poster-visual-system.md) and [references/story-and-style.md](references/story-and-style.md). Keep the established defaults: physically readable type, black normal-or-bold text, one affiliation per line, visible primary-to-secondary spacing, black/red/blue/green active hues, presenter highlighted within the author list, square corners where enclosure is needed, and a flat low-border composition. Ask only about unresolved character, density, composition, palette roles, branding, and language.

### 5. Create the editable HTML wireframe

Read [references/whiteboard-wireframe.md](references/whiteboard-wireframe.md). The wireframe is production-binding for page geometry, section bands, numbering, reading order, evidence grouping, hierarchy, typography tokens, spacing rhythm, and figure-slot proportions. Scientific placeholders may remain schematic.

Every production-bound wrapper needs a stable `data-layout-id`. Every scientific slot needs a unique `data-figure-id`, asset class, claim, source target, physical width/height, role, must-keep semantics, and whether it accepts a standard semantic SVG or a proportional non-data image. For a quantitative slot, also freeze the poster base type token `B` in millimetres; slot capacity and `B` are independent constraints. Use `data-evidence-group` only when an approved reading relationship must stay together.

Use a Feishu/Lark whiteboard only when explicitly requested.

### 6. Freeze the approved wireframe

Reopen the current edited HTML, not the original proposal. Resolve ambiguous marks, verify unique `data-layout-id` and figure-slot mappings, summarize the reading order, and obtain explicit approval for formal production. If production markers are missing, add them to the wireframe and freeze it again before proceeding.

### 7. Produce the formal HTML in place

Read [references/formal-production.md](references/formal-production.md) and [references/figure-extraction-and-placement.md](references/figure-extraction-and-placement.md).

Copy/version the approved wireframe HTML and replace placeholders inside the same DOM/CSS scaffold. Preserve production-bound wrappers, section styling, typography tokens, spacing, order, and evidence groups. A generator may locate `data-layout-id` elements and replace their contents; it must not create a new page scaffold or acquire page-structure design authority.

For quantitative scientific figures:

1. obtain a standard semantic SVG from `scientific-plotting`;
2. inline it in the approved figure slot;
3. use [scripts/adapt_semantic_svg_for_slot.py](scripts/adapt_semantic_svg_for_slot.py) to recalculate plot box, data paths, ticks, titles, legend, annotations, margins, and style tokens for the real slot;
4. make the adapted SVG viewport millimetre-isomorphic: a `245 mm × 116 mm` slot uses `width="245mm" height="116mm" viewBox="0 0 245 116"`, so one user unit equals one millimetre;
5. preserve exact/approximate source confidence and the embedded figure model;
6. never use a screenshot, raster crop, white mask, whole-SVG non-uniform stretch, or `non-scaling-stroke`.

For photographs, micrographs, and proportional schematics without a coordinate model, use the best standalone or structurally extracted source and preserve aspect ratio. A controlled crop is available only for non-quantitative image evidence when no clean standalone/vector source exists.

If a standard figure cannot remain readable inside the approved slot, return to the wireframe rather than silently changing the page structure.

## Integrity check and review boundary

Use [scripts/check_poster_integrity.py](scripts/check_poster_integrity.py) for cheap checks only:

- HTML/SVG parses;
- finite numeric values;
- unique required ids;
- local references exist;
- approved and formal files contain the same production-bound `data-layout-id` membership;
- quantitative regions contain standard semantic inline SVG with figure-model metadata and source-confidence markers.

Do not automatically generate multi-round browser screenshots, compare computed geometry/styles, run a scientific visual audit, maintain source-integrity/placement/print-ready state machines, or declare `PASS` or print readiness. The user decides scientific correctness, visual quality, and printing acceptance.

Handoff language is: `file integrity satisfied; awaiting user review`. Disclose any Skill condition that could not be met and every custom workaround or approximation used.

## Completion record

Report:

- approved central message and wireframe version;
- formal HTML path;
- source route for each scientific figure;
- exact or approximate SVG reconstructions;
- any blocked source, layout return, or custom workaround;
- integrity checks performed;
- that final scientific, visual, and print approval remains with the user.

## Failure modes

- Starting layout before reading the conference material and intended message.
- Rewriting the accepted abstract title.
- Rebuilding formal HTML from a blank scaffold instead of replacing the approved wireframe in place.
- Continuing when stable `data-layout-id` or slot contracts are missing.
- Letting a generator redefine rows, section bands, borders, or evidence grouping.
- Cropping or masking quantitative data figures.
- Inlining legacy or raster-wrapper SVG instead of a standard semantic SVG.
- Losing or upgrading an approximate reconstruction marker.
- Applying whole-figure non-uniform scaling.
- Prescribing subplot pairings from chart type.
- Shrinking text instead of revising content or returning to the wireframe.
- Adding repeated borders, gray/light native text, extra active hues, or a presenter box.
- Reporting mechanical integrity as scientific or print approval.
- Failing to disclose deviations or custom workarounds at handoff.

## Resources

- [references/content-and-evidence.md](references/content-and-evidence.md): intake and priority decisions.
- [references/story-and-style.md](references/story-and-style.md): visual direction.
- [references/poster-visual-system.md](references/poster-visual-system.md): typography, color, spacing, header, and flat-layout defaults.
- [references/whiteboard-wireframe.md](references/whiteboard-wireframe.md): editable production-binding wireframe.
- [references/figure-extraction-and-placement.md](references/figure-extraction-and-placement.md): scientific-source routing and semantic SVG placement.
- [references/formal-production.md](references/formal-production.md): in-place production and user-review boundary.
- [scripts/inspect_figure_sources.py](scripts/inspect_figure_sources.py): read-only source inventory.
- [scripts/extract_grouped_panels.py](scripts/extract_grouped_panels.py): manifest-driven batch extraction of named SVG groups.
- [scripts/adapt_semantic_svg_for_slot.py](scripts/adapt_semantic_svg_for_slot.py): deterministic slot adaptation of standard semantic SVG.
- [scripts/check_poster_integrity.py](scripts/check_poster_integrity.py): cheap poster file-integrity check without a scientific or print verdict.
