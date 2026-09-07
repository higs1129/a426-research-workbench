# Default poster visual system

Read this reference before style confirmation, the editable HTML wireframe, and formal production. It defines the personal default for large-format scientific posters. Conference mandates and explicit user decisions may override individual details, but every departure must be recorded in the style brief or layout contract.

## 1. Design objective

Prioritize physical readability, a clear scientific hierarchy, and a restrained engineered appearance. The system is intentionally stricter than a generic web-card layout: content is edited to fit the poster rather than made to fit by shrinking type, lowering contrast, or multiplying decorative components.

## 2. Physical typography profile

For A0 and similarly sized printed posters, including approximately 90 × 110 cm formats, use these final physical sizes as the starting contract:

| Role | Default range |
| --- | ---: |
| Poster title | 24–28 mm |
| Authors | 11–13 mm |
| Affiliations and contact details | 8.5–10 mm |
| Section headings | 14–17 mm |
| Central claim or take-home statement | 14–17 mm |
| Body text and figure captions | 9.5–12 mm |
| Plot axes, tick labels, and legends | 8–10 mm |
| Smallest auxiliary text | never below 8 mm |

These are effective final sizes, not CSS values viewed at an arbitrary browser zoom. Scale the profile proportionally only when the confirmed physical page size differs materially from A0-class output, and preserve the same viewing-distance logic.

Use `font-weight: 400` as the minimum for native poster text. Use `700` or `800` for titles, section headings, key facts, presenter emphasis, and other high-priority statements. Affiliations use `400` or `700`; affiliation numbers may be bold. Select a typeface whose installed `400` face remains visibly normal rather than hairline at print scale.

Use the author list as the internal type anchor in addition to the physical minima:

- affiliation and contact text is at least `0.75×` the author size;
- body text and figure captions are at least `0.8×` the author size;
- plot axes, tick labels, and legends are at least `0.8×` the body size;
- the smallest auxiliary text is at least `0.65×` the author size and never below the physical minimum;
- a bridge statement, conclusion strip, or other key explanatory sentence is at least the body size and preferably `1.1–1.2×` the body size with bold weight.

When the absolute range and relative ratio disagree, use the larger result. A key bridge or conclusion is not auxiliary information merely because it occupies a narrow strip.

Use black for native poster prose, captions, affiliations, and secondary explanations. Establish hierarchy with font size, normal-versus-bold weight, spacing, and placement rather than gray text or reduced opacity. Imported scientific images may retain grayscale data when it is part of the evidence; poster-added labels still follow this text rule.

Never reduce text below the minimum merely to retain content. Resolve overflow in this order:

1. remove or defer lower-priority content;
2. shorten prose and captions;
3. merge repeated context or panels;
4. reduce the number of sections or callouts;
5. reallocate canvas area and simplify the composition.

Keep title, authors, affiliations, contact, presenter details, logos, and required identification marks in a visually contiguous, content-driven header block. Give each affiliation one full-width row rather than distributing affiliations across columns. Set the vertical gap from the author list to the affiliation block to approximately `1em` of the author-list font size. Set the gap between affiliation rows to approximately `0.5em` of the affiliation size; implement this as row spacing, not as `line-height: 0.5`. Set the affiliation-block bottom gap to about `0.5–0.75em` of the affiliation size and never more than `1em` without an explicit reason.

Use `height: auto`, content-sized grid rows, and normal document flow for the header and following sections. After author or affiliation edits, recompute the header height and let every later section move with it. Fixed header heights, vertically distributed flex space, or retained absolute positions must not create an empty band below the affiliations.

Validate at three real viewing distances:

- about 3 m: title and central claim are immediately readable;
- about 1–2 m: section headings, primary relationships, and key numbers are readable;
- close range: body text, captions, axes, ticks, and legends are readable without zoom.

## 3. Semantic spacing rhythm

Use spacing to express relationships rather than filling a fixed-height container. Measure header spacing against the author or affiliation size and body spacing against the body line height.

- Between a primary statement and its supporting explanation, use about `0.75–1.0×` the secondary text line height. This gap must be visibly larger than the spacing between lines or items inside the secondary information.
- Between a key number and its short descriptor, use about `0.5–0.75em` of the descriptor size.
- Between lines or repeated rows within one secondary-information group, use about `0.25–0.5em`.
- Between tightly related components inside a section, use about `0.75–1.0×` the body line height.
- Between major sections, use about `1.25–1.5×` the body line height when a divider does not already provide enough separation.

The enlarged primary-to-secondary gap is local to that semantic pair. Keep the outer padding of its container compact and content-driven. A continuous blank band larger than two body line heights requires an explicit role such as a major section transition; otherwise reflow the surrounding content.

## 4. Four-color active palette

Use no more than these four active hues by default:

- black `#111111` — text, axes, neutral rules, and structure;
- red `#D6001C` — primary emphasis, key conclusions, critical values, and decisive structural accents;
- blue `#126AB3` — one physical category, dataset branch, mechanism, or comparison family;
- green `#138A48` — the other physical category, dataset branch, mechanism, or comparison family.

White is the substrate and open-canvas background and does not count as an active hue. Native poster text uses black or an explicitly assigned semantic accent. Light fills, when genuinely necessary, must be tints of the same semantic hue rather than new hues. Grayscale values already present inside source figures remain evidence colors rather than poster typography.

Do not introduce amber, purple, cyan, brown, navy as a separate theme color, or any fifth semantic hue. Keep headings black rather than creating a parallel navy hierarchy. Assign blue and green to the scientific categories after inspecting the evidence; their exact meaning is not globally fixed.

Color must never be the only encoding. Reinforce categories with labels, line styles, markers, panel letters, or spatial grouping. Required institutional or sponsor logo colors may appear inside the original logo artwork, but do not adopt them as additional poster-wide semantic colors unless the user explicitly approves an exception.

## 5. Flat structural language

Use an open white canvas. Separate major regions with whitespace, alignment, section titles, and a single local red or black divider. A page edge, section, figure group, and key-number group should not each contribute another enclosing rectangle around the same content.

Use full rectangular borders only when one boundary is necessary to communicate a genuinely enclosed comparison, claim, or independent content region. Keep ordinary border nesting to no more than one enclosing level. When an enclosure is used, keep square corners and a flat surface:

```css
.poster-page,
.poster-section,
.figure-group {
  border: 0;
  box-shadow: none;
}

.semantic-enclosure {
  border: 0.35mm solid #111111;
  border-radius: 0;
  box-shadow: none;
}
```

Within one section, group multiple figures through common alignment, figure letters, concise labels, captions, and controlled spacing. Use one divider between scientifically distinct branches when needed. The native axes or boundary of a scientific plot already provides visual containment and normally needs no poster-added frame.

Round forms remain valid when they encode a real physical object or data mark, such as a wafer, cavity, resonance, node, circular device, scatter point, or icon. Gradients, glass effects, frosted cards, and interior shadows are outside the default structural language.

## 6. Default component pairings

### Header

- White background with a strong red top rule and red lower divider.
- Use the exact confirmed abstract title in black.
- Keep authors, affiliations, contact, and required meeting metadata visually contiguous.
- Present the presenter within the author list using red, bold, underlined text.
- Apply the full-width affiliation rows, compact bottom gap, and content-driven header reflow defined in the typography profile above.
- Place required logos or poster identification at the right when practical.
- Preserve corresponding-author and equal-contribution markers from the source in black; reserve the red, bold, underlined author treatment for the presenter.

### Section heading

- Red section number followed by a bold black title.
- Use whitespace and, when useful, one red top rule or a short local divider to establish the section boundary.

### Central claim

- Place bold black claim text on the open white canvas with a strong red left rule.
- Separate the primary claim from its supporting sentence with the semantic primary-to-secondary gap while keeping the outer claim padding compact.
- When enclosure is needed for contrast, use one square-cornered boundary around the complete claim region.

### Scientific figure panel

- Place figures as open groups on white, using shared alignment and whitespace rather than one frame per image.
- Keep figure titles and explanatory text black; use a semantic accent for a panel letter, category label, data trace, or key annotation.
- Preserve a clear inset between every figure and nearby poster divider: at least half of the body-text size, approximately 4–6 mm for A0-class output.
- Use a single divider only when it clarifies two scientifically distinct branches inside the same section.
- Keep source-figure backgrounds neutral so the data remain dominant.

### Key number

- Show one main number per callout in black or its semantic accent.
- Separate the number from its descriptor by `0.5–0.75em` of the descriptor size so their roles remain distinct.
- Prefer an open aligned group with a short label; use one square enclosure only when the numbers form a bounded comparison.

### Footer

- Use the open white page with a red top divider.
- Place references and acknowledgements on the left and contact or QR information on the right when the content supports that split.
- Preserve readable minimum type and the same flat alignment grid as the main page.

## 7. What remains task-specific

Do not hard-code:

- the number of columns, sections, or panels;
- section order or whether a central claim band is needed;
- the hero object, dominant figure, or exact reading path;
- the blue-versus-green category assignment;
- whether one scientifically meaningful region benefits from a full enclosure;
- logo count, venue marks, or language division;
- deliberate exceptions required by an official template or explicitly approved by the user.

The content hierarchy and evidence determine these choices. The fixed visual system constrains how those choices are expressed, not what scientific story the poster must tell.
