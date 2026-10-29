# Challenge requirements summary

This is a repository-side summary, not a replacement for the official
[`Final Chameleon Challenge.pdf`](Final%20Chameleon%20Challenge.pdf). The
challenge brief is the source of truth.

## Stage-one engine

The brief describes stage one as an offline engine run in a standard container
against hidden designs and target sizes across all three difficulty levels. The
engine returns a resized design; both its JSON structure and its official
rendered PNG are evaluated.

## Stated visual and structural criteria

The brief asks for outputs that:

- Avoid unwanted collisions while preserving intentional layering.
- Keep all text readable, sufficiently contrasted, and inside the canvas.
- Preserve brand colors, fonts, logos, and image proportions.
- Maintain intentional alignment, spacing, and visual hierarchy.
- Work across many designs and target sizes, rather than relying on
  design-specific tuning.
- Preserve the source elements and IDs and do not regenerate image content.

The brief permits font-size changes to fit text; stage-one guidance treats
content and font family as fixed. Image regeneration is prohibited.

## Model and environment

Stage one runs offline and permits local models subject to a shared model-size
limit and approved-model list. The supplied brief says those details and the
exact reference-machine limits are being finalized. Later info-session notes
reported that downloadable open weights were acceptable and small, swappable
models were encouraged. This repository documents its pinned local model and
dependencies; follow any newer organizer guidance.

## What this implementation claims

The engine, tests, Dockerfile, and run instructions are present. The local
quality metrics are proxies, not official scores. Current measured limitations
and verification status are listed in [`docs/RESULTS.md`](docs/RESULTS.md).
The finalist-stage Express experience is supplementary; it is not a substitute
for the stage-one engine deliverable.
