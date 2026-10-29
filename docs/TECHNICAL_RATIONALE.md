# Technical rationale and proof of concept

This note explains why the engine is a plausible resizing method and what its
checks do—and do not—prove. It is not a proof of visual quality or of a high
score from Adobe's hidden evaluator.

## The resizing problem as constrained search

Represent a design as elements \(E = \{e_1,\ldots,e_n\}\) on a source canvas.
Each element has immutable design data (such as its ID, text, font family, color,
asset, and layer order) and mutable geometry. The target canvas imposes hard
constraints: preserve the design data, fit the element boxes inside the canvas,
and keep images in proportion. Within those constraints, the engine wants a
layout with readable hierarchy, useful alignment, and few unintended collisions.

Those visual goals conflict on extreme aspect ratios. The engine therefore
generates a finite set of alternatives—preserving the source anchors, stacking,
splitting image and copy, arranging a row, and partitioning content into regions.
It measures text, scores candidates with explicit geometric and readability
proxies, and compares two independently generated layouts. The exact candidate
families and referee are implemented in [`engine/reflow.py`](../engine/reflow.py)
and [`engine/resize.py`](../engine/resize.py).

## Properties the implementation can check

For an input accepted by `resize`, the engine rejects non-positive canvas sizes,
duplicate IDs, non-finite geometry, and negative element dimensions. Candidates
are built from copies of the input. The output audit then checks the schema,
target canvas, element IDs and count, immutable element properties, finite
geometry, rotated bounds, and image proportions. See
[`engine/resize.py`](../engine/resize.py) and
[`evaluation/audit.py`](../evaluation/audit.py).

Two limited claims follow from those mechanics:

1. **Audit-passing outputs preserve the checked contract.** If the local audit
   reports `valid`, its checked structural constraints hold for that source and
   target. This statement is only as complete as the local audit; it is not a
   proof that the organizer's validator is identical.
2. **The image-sizing primitive preserves aspect ratio.** For a non-cover image
   scaled by a positive factor \(s\), the implementation uses
   \(w' = s w\) and \(h' = s h\). Therefore
   \[
   \frac{w'}{h'} = \frac{s w}{s h} = \frac{w}{h}.
   \]
   The independent audit accepts up to 5% ratio drift; that is an audit
   tolerance, not a claim of exact equality for every output. Cover-fit images
   are excluded because cropping is their declared behavior.

The referee has a further conditional guarantee, assuming candidate generation
and both audit calls complete. If either generated result passes the local
hard-contract audit, the referee returns a passing result:
when the partition candidate fails, a valid reflow candidate is selected; when
the partition candidate passes, it remains the default unless a valid reflow
candidate meets the documented comparison rule. If neither candidate passes,
the engine does not claim success—the batch entry point reports the audit
failure.

## What candidate search does not prove

The search is bounded and deterministic; it is not an exhaustive search over
all possible layouts. “Best” means best among the candidates generated under
this implementation's scoring rules, not a global optimum. Its overlap,
legibility, contrast, and hierarchy measures are local proxies, not the
organizer's Judge LLM or human rubric. A zero-overflow result can still contain
illegibly small text.

The model is deliberately limited to text-role hints. It does not write copy,
change fonts, create images, or output coordinates. It is not a vision model and
cannot identify a logo from pixels. The deterministic layout engine remains
responsible for placement, and `--model off` provides an explicit ablation.
Model details and related layout-generation research are documented in
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

## Proof-of-concept evidence and known counterexample

On the three supplied samples, the latest branch ran the required local model
and official renderer successfully: all three JSON outputs passed the local
hard-contract audit, with no measured text overflows or flagged collisions.
The advanced 728×90 sample still had **seven text elements below 10 px**. That is
an explicit counterexample to any claim that passing the structural audit proves
readability. Results and reproduction commands are in
[`docs/RESULTS.md`](RESULTS.md) and [`docs/REVIEW_GUIDE.md`](REVIEW_GUIDE.md).

This evidence supports the narrower proof of concept: a small local model can
provide bounded semantic hints while a deterministic, constraint-checked search
produces valid layouts for the supplied cases. It does not establish a likely
finalist outcome. The challenge brief says stage one uses hidden designs across
all three difficulty levels and does not publish the evaluator's score formula.
