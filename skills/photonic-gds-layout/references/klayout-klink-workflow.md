# KLayout and klink workflow

Read this reference before changing a live KLayout layout.

## Connection sequence

1. Run the environment preflight and `python -m klink.doctor`.
2. Confirm the KLayout window/session that owns the target layout.
3. Inspect `klink.status`, layout summary, top cells, layers, and current selection.
4. If the user clicked `SEND`, resolve the latest durable selection/ruler id before acting.
5. Start a KLayout transaction/undo unit for each user intention.
6. Use typed batch RPCs for generated shapes or instances.
7. Re-query structured geometry after the mutation.

The KLayout GUI is the live workspace; the external Python environment hosts klink, optional gdsfactory, and project logic. Their Python ABIs need not match because communication crosses localhost RPC, but the klink Python client and KLayout plugin must remain version-matched.

## Tool preference

Prefer structured queries and typed mutation tools. Use screenshots only when the user requests a visual artifact. Use raw `exec.python` only when a required `pya` operation has no typed RPC and the target layout/cell is explicit.

For many points, polygons, or instances, use one batch operation rather than thousands of RPC calls. Keep reusable geometry in hierarchical cells.

## Selections and rulers

- “Current selection” means live KLayout state.
- “The one I just sent” means the latest durable SEND record.
- Daily-canvas strokes are conceptual evidence; KLayout selections/rulers are coordinate evidence.
- A region plan should be prepared and validated before apply. Regeneration must refuse silently overwriting hand-edited managed output.

## Working versus clean layout

Working layouts may retain Port, Anchor, Region, annotation, and verification layers. Clean export must name the top cell and explicit layer allowlist, strip helper markers, re-read the result, and leave the live working layout unchanged.
