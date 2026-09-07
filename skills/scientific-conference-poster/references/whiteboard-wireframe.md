# Editable HTML wireframe

Read this reference before creating, updating, interpreting, or freezing the poster wireframe.

## Default artifact

Create one editable HTML file for the wireframe. Do not generate a persistent PNG preview, wide screenshot, thumbnail, PDF, SVG, JSON export, Markdown plan, or separate layout contract unless the user explicitly requests that file type.

Visual QA may render the HTML and capture screenshots in an isolated temporary directory. Inspect them there, then leave them as temporary test artifacts; do not copy them into the poster directory or list them as deliverables. When the user explicitly asks for PNG, create only the requested viewport, crop, or scale instead of automatically producing normal and wide variants.

The HTML should preserve edits inside the same file when practical. If browser security prevents direct overwrite, provide an explicit “save edited HTML” action that serializes the current layout into a new HTML download. Do not make a sidecar JSON the default persistence mechanism.

## Board composition

Create three working regions:

1. **Content pool** — cards for the confirmed primary message, hero evidence, supporting evidence, context, identity, and deferred material.
2. **Poster canvas** — a frame with the real poster aspect ratio, orientation, safe margin, approximate panel rectangles, content labels, and reading-order cues.
3. **Review lane** — unresolved choices, author notes, conference constraints, and items proposed for removal or supplementary delivery.

Use concise provisional copy and schematic scientific content, but do not make the whole canvas low fidelity. The approved wireframe is high fidelity for page geometry, section bands, numbering, reading order, evidence grouping, visual hierarchy, typography tokens, spacing rhythm, and figure-slot proportions. Preserve real figure aspect ratios when they materially constrain layout. Make priority visible through relative area, placement, and hierarchy rather than decorative polish. Do not fill the board with final paragraphs or attempt final scientific rendering before the sources are ready.

Apply [poster-visual-system.md](poster-visual-system.md) at wireframe fidelity. Use one full-width row per affiliation and let the header height follow its content. Show a visibly larger local gap between each primary statement and its secondary explanation than between lines within the secondary text; keep the surrounding container compact. Use open figure groups, whitespace, and only the dividers needed to explain the reading structure. Use the fixed four-color semantics and size representative labels according to the intended final physical and relative hierarchy. Placeholder copy may be short, but it must not be artificially tiny: the wireframe should reveal when the approved content cannot fit at readable scale.

For every proposed scientific image, mark:

- its asset class: `quantitative-data`, `image-evidence`, or `schematic`;
- the poster claim it supports and the exact target panel;
- scientific elements that must remain, including axes, units, legends, colorbars, scale bars, arrows, and necessary annotations;
- neighboring panels, inherited labels, and fragments that must be excluded;
- the preferred standalone, editable, or vector source and whether it has been located;
- four intended crop boundaries only for non-quantitative image evidence that remains eligible for a documented crop exception;
- minimum clearance from nearby dividers.

Freeze a poster-slot contract from the current canvas before formal production. Record the slot's physical width and height, visual role (`primary`, `supporting`, `mechanism`, or `context`), geometry policy (`locked`), aspect policy (`preserve` or `semantic-reflow`), and final-size figure typography baseline `B` in millimetres. Width and height describe the usable scientific-figure region after its internal inset, not the enclosing card or column. For quantitative slots, store these as machine-readable values such as `data-slot-width-mm`, `data-slot-height-mm`, and `data-slot-base-mm`; do not derive `B` by shrinking text until the placeholder fits.

Assign a stable `data-layout-id` to every production-bound page region, including the page, header, claim, section, section title or ribbon, evidence unit, figure-slot wrapper, and footer. Mark the physical poster page with `data-role="poster-page"`, `data-page-width-mm`, and `data-page-height-mm`. Assign a stable `data-evidence-group` only to figures and explanations whose approved reading path or adjacency must remain together. Do not infer a group from the fact that two chart types were paired in a previous poster. These identifiers bind the approved composition to formal production; do not place them on expendable sketch controls or inside the scientific SVG payload.

Use a visible source-blocked note when no clean structural source has been found. Wireframe marks define the intended evidence unit and target layout; they do not authorize raster cropping or substitute for inspecting the final extraction.

The wireframe should let the user:

- drag a content card into or out of the canvas;
- resize or redraw panels;
- annotate a preferred crop, grouping, or reading path;
- mark content as mandatory, supporting, deferred, or removed;
- sketch new relationships without editing source code;
- save or export the edited state as HTML.

## Presentation to the user

Return the HTML file link and briefly explain the three working regions and editing controls. Do not generate or return a rendered PNG preview unless the user requests it. Do not describe the initial arrangement as approved.

## Re-read after user editing

When the user says the wireframe is ready:

1. open the latest saved HTML or inspect the current browser state supplied by the user;
2. compare the current layout with the initial proposal;
3. treat user moves, deletions, additions, resizing, and annotations as intentional unless they conflict or are ambiguous;
4. ask about ambiguous strokes, floating labels, overlapping cards, or contradictory notes;
5. summarize the final reading order and panel-content mapping;
6. verify the uniqueness and completeness of `data-layout-id`, `data-evidence-group`, and poster-slot mappings;
7. obtain explicit approval for formal production.

Do not rely on conversation memory of the original wireframe. The current HTML state is the authoritative composition state.

## Layout contract

After approval, preserve inside the HTML or in the conversation:

- the HTML file and layout version;
- confirmation time and approving user;
- poster dimensions and orientation;
- ordered panel list with assigned content and sources;
- agreed hero element, visual hierarchy, and deferred content;
- unresolved production details that do not alter structure.

The approved HTML itself is the production base. Formal production must copy or fork this current file and replace provisional content in place. It must not rebuild the page grid, section ribbons, evidence groups, or spacing system from memory or from a prose summary of the contract.

Do not create a separate Markdown contract, screenshot, or JSON file by default. If later requested changes alter content priority, panel structure, or reading order, return to the HTML wireframe and renew approval.

## Optional Feishu/Lark whiteboard

Use a Feishu/Lark whiteboard only when the user explicitly requests that collaboration surface. Follow the installed `lark-whiteboard` Skill for authentication, rendering, dry-run, update, and overwrite safety. Use `lark-doc` only to locate an existing embedded board or, with authorization, create a containing document and blank board at a specific destination.

When a Feishu/Lark board is requested, do not also create an HTML or PNG artifact unless requested. A static PNG or screenshot does not satisfy the editable-wireframe requirement by itself.
