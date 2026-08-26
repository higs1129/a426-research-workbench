---
name: scientific-conference-poster
description: Creates, revises, and validates evidence-traceable scientific conference posters through staged requirements, source reading, content prioritization, style confirmation, an editable HTML wireframe, and HTML-first formal production. Use for research poster preparation from abstracts, meeting folders, figures, and author materials. Do not use for slide decks, manuscripts, standalone scientific figures, existing-poster explanation without edits, or general promotional posters.
metadata:
  version: "1.4"
  skill-author: "Personal Research Workflow"
---

# Scientific Conference Poster

## Purpose and boundaries

Turn author-provided conference materials into a poster whose central message, evidence, visual hierarchy, and final production choices have been explicitly confirmed. Treat poster preparation as a staged collaboration rather than a one-shot layout task.

This skill governs the poster-level workflow. Use `scientific-plotting` for new or revised data figures. Use a format-specific document, presentation, PDF, browser, or image workflow only after the poster wireframe is approved and the requested deliverable is known.

## Default artifact policy

Unless the user explicitly requests another file type, create exactly one editable HTML file for each requested wireframe or formal poster version. Keep content inventories, style decisions, and layout contracts in the conversation or embed them as HTML metadata instead of creating separate Markdown, JSON, image, or preview files.

Do not persist PNG screenshots, thumbnails, normal/wide preview pairs, PDF exports, PPTX files, SVG sidecars, or layout JSON in the poster task directory unless the user explicitly asks for that format. Browser rendering and screenshot-based visual QA may use an isolated temporary directory, but those files are test artifacts: do not deliver, preserve, or copy them into the task directory.

When the user explicitly requests PNG, generate only the requested view or views. Do not infer that both a standard and a wide preview are wanted. Keep HTML as the editable source unless the user explicitly requests PNG-only delivery. Apply the same explicit-request rule to PDF, PPTX, and other non-HTML deliverables.

## Stage model

Progress through:

`requirements → source reading → content priorities → style brief → editable HTML wireframe → approved layout → formal production → release review`

Do not skip an unresolved gate merely to produce a quick visual. Do not repeat questions whose answers are already present in the conversation or authoritative material. If the user supplies several stages at once, summarize the inferred decisions and continue from the first unresolved gate.

### 1. Establish the poster task

When the user only says they want to prepare or make a poster and provides no usable context, ask together for:

1. the conference name and, when available, its official notice or website;
2. the accepted or intended abstract, or confirmation that it is inside the material folder;
3. the presentation form: printed or electronic, size, orientation, language, official template, required submission format, deadline, and whether a short oral introduction accompanies it;
4. the local folder, cloud folder, document, or other authoritative material location for this conference.

Do not start layout or offer a generic poster template at this stage. If current conference rules are missing from the supplied material and they affect the design, verify them from the official conference source before layout.

### 2. Read the supplied materials

Before reading a supplied project or folder, read its applicable `AGENTS.md` or equivalent local rules. Respect read-only project and storage boundaries. Do not infer scientific facts from filenames, timestamps, logs, or absent files.

Read the relevant material before asking the user what to show. Build a concise source inventory covering conference requirements, abstract or manuscript, authors and affiliations, figures and data, logos and images, citations, permissions, and previous visual material. Report missing, conflicting, or ambiguous items without silently selecting a convenient version.

Read [references/content-and-evidence.md](references/content-and-evidence.md) for intake, source inventory, and content-priority decisions.

Treat the confirmed accepted abstract as the authoritative source for the poster title. Preserve its wording, symbols, punctuation, and capitalization; line breaks may change for layout. Resolve competing abstract versions before design. When figures must be extracted from a composite source, inventory the original vector or high-resolution assets before relying on a page screenshot.

### 3. Elicit the intended message

After source reading, ask only the questions needed to learn:

- the one statement the viewer should remember;
- the result, object, system, or application that should be the visual center;
- content that must appear, content that may be supporting, and content that may be omitted or moved to supplementary material;
- the intended audience and whether the poster must stand alone or will be explained in person.

Do not decide the author's central scientific claim from available figures alone.

### 4. Propose and confirm content priorities

Convert the user's answer into a source-linked priority proposal:

- primary message and hero evidence;
- direct supporting evidence;
- necessary context or method;
- identity, citation, contact, and acknowledgement material;
- candidates to merge, shorten, defer, or omit.

For each item, state its role, source, proposed visual prominence, and any unresolved scientific or editorial issue. Use relative priorities rather than universal word counts, section counts, column counts, or visual percentages. Obtain confirmation of the content priorities before style design.

### 5. Confirm a style brief

After content priorities are stable, derive what is already constrained by the conference, institution, and supplied references. Ask only about unresolved choices such as visual character, density, hero-led versus modular composition, color and branding, language treatment, and whether to continue an existing visual system.

Apply the personal poster defaults in [references/poster-visual-system.md](references/poster-visual-system.md): enlarged physically readable typography, black native text with normal-or-bold hierarchy, one full-width row per affiliation, visible primary-to-secondary spacing, no more than four active hues, inline presenter identification, and a flat composition with minimal enclosing borders. When semantic enclosure is genuinely needed, use square corners. Do not ask the user to reselect these defaults unless conference rules conflict or the user explicitly asks to override them. Offer two or three concrete directions only for the unresolved composition and character choices. Read [references/story-and-style.md](references/story-and-style.md) for style elicitation and layout reasoning.

### 6. Create an editable HTML wireframe

Create the wireframe only after both content priorities and style direction are confirmed. Produce one editable HTML file that supports the agreed editing scope, such as moving and resizing panels, editing text, adding notes, saving state, and exporting or embedding the updated state without generating sidecar files by default. Read [references/whiteboard-wireframe.md](references/whiteboard-wireframe.md).

The HTML wireframe is a working surface, not a polished poster. Represent the real poster aspect ratio, safe margins, reading order, content hierarchy, approximate panel proportions, and unresolved notes. Express the intended large-poster type hierarchy, one-row affiliations, content-driven header height, primary-to-secondary spacing, four-color semantics, open figure groups, and minimal dividers from the start; do not use tiny placeholder text or repeated enclosing frames that conceal density problems. Mark intended figure boundaries, required axes or scale bars, and source-quality concerns. Keep the initial content cards and the poster canvas visible together so the user can rearrange the design.

Use a Feishu/Lark whiteboard only when the user explicitly requests it. In that case, follow the `lark-whiteboard` workflow and its authorization and overwrite rules; do not create a parallel HTML wireframe unless the user also requests one.

### 7. Re-read and freeze the approved wireframe

After the user says they have finished editing or approves the sketch:

1. reopen the current user-edited HTML or its current in-browser/saved state rather than relying on the originally generated layout;
2. identify moved, resized, added, deleted, and annotated content;
3. ask only about marks whose intended meaning remains ambiguous;
4. summarize the current content placement and reading order as the layout contract;
5. embed the approved layout state and confirmation metadata in the HTML when persistence is needed; do not create a separate preview, Markdown contract, or JSON file unless requested;
6. obtain explicit approval to begin formal production.

Structural changes after approval return to the editable HTML wireframe stage. Small typographic or production corrections may remain in formal production when they do not alter content priority or reading order.

### 8. Produce and validate the formal poster

Use the approved layout contract and authoritative sources to create the formal HTML poster. Read [references/poster-visual-system.md](references/poster-visual-system.md) and [references/formal-production.md](references/formal-production.md) before production. When any scientific image is cropped, masked, or extracted from a composite source, also read [references/figure-extraction-and-placement.md](references/figure-extraction-and-placement.md). Create PDF, editable PPTX, PNG, or any other additional deliverable only when the user explicitly requests it.

Formal production must preserve the confirmed scientific meaning and clearly distinguish measured data, processing, fits, interpretation, and proposed applications. Enforce exact abstract-title wording, inline presenter styling, the enlarged typography and relative-size ladder, content-driven affiliation layout, semantic spacing hierarchy, the four-hue limit, boundary-confirmed figure crops, safe figure insets, and the flat low-border composition. Render and inspect the actual deliverable at its intended physical or display size. Do not treat source compilation or export success as visual or scientific approval.

## Completion record

At handoff, report:

- the approved central message and layout version;
- produced source and delivery files;
- source, figure, visual, and print checks performed;
- unresolved author, conference, printer, permission, or scientific items;
- whether the deliverable is a draft, author-approved version, or print-ready candidate.

## Failure modes

- Starting from a generic visual template before learning the conference, evidence, and intended message.
- Asking the user to repeat information already present in the supplied folder.
- Treating all available results as equally important or shrinking typography to retain them all.
- Rewriting or shortening the accepted abstract title for visual convenience.
- Losing the presenter emphasis, author order, affiliation mapping, or authorship marks from the confirmed source.
- Shrinking below the physical typography minima instead of cutting, merging, or reprioritizing content.
- Introducing a fifth semantic hue, multicolored card backgrounds, or color as the only category encoding.
- Using gray or light-weight native poster text to simulate hierarchy instead of size, spacing, and normal-or-bold weight.
- Assigning key bridge statements or supporting explanations to auxiliary-text size, or violating the relative type ladder.
- Giving primary and secondary information the same tight gap, or creating hierarchy by stretching the entire surrounding container instead of their local relationship.
- Nesting page, section, figure, and metric borders until the scientific content appears inside repeated frames.
- Cropping before confirming all four source boundaries; cropping away axes, scale bars, legends, or plot frames; leaking neighboring panels; or letting figure content touch a poster divider.
- Distributing affiliations across columns, fixing the header height, or leaving a large empty band below the affiliation block instead of reflowing the page.
- Asking for aesthetic preferences before the content hierarchy is understood.
- Presenting a static screenshot as the editable wireframe, or generating persistent preview screenshots without an explicit request.
- Beginning formal production from the agent's original HTML state after the user has edited it.
- Leaving browser QA screenshots, wide/normal preview pairs, layout JSON, or planning Markdown in the task directory by default.
- Treating an approved composition as approval of unverified claims, figures, citations, image permissions, or printer settings.
- Copying task-specific research assets or machine-specific paths into this reusable skill.

## Resources

- [references/content-and-evidence.md](references/content-and-evidence.md): read during intake, source review, and content-priority evaluation.
- [references/poster-visual-system.md](references/poster-visual-system.md): read before style confirmation, the editable HTML wireframe, and formal production; contains the default typography, color, container, and component rules.
- [references/figure-extraction-and-placement.md](references/figure-extraction-and-placement.md): read whenever a scientific image is cropped, masked, extracted from a composite panel, or judged for source quality and placement clearance.
- [references/story-and-style.md](references/story-and-style.md): read after the intended message is known and before proposing visual directions.
- [references/whiteboard-wireframe.md](references/whiteboard-wireframe.md): read before creating, updating, or freezing the editable HTML wireframe, or when the user explicitly requests a Feishu/Lark whiteboard.
- [references/formal-production.md](references/formal-production.md): read only after the wireframe is approved and formal production is authorized.
