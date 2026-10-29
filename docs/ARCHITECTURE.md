# Approach and research

## Decision

Use a local language model for bounded semantic advice, and measured candidate search
for geometry. Input already contains elements; training an image segmentation model
or regenerating the artwork would solve the wrong input problem and could violate rules.

1. Validate finite dimensions and unique IDs. Deep-copy the source.
2. Identify large backgrounds and faint decorative shapes geometrically. Preserve explicit
   groups; infer only a narrow text-inside-shape container relation.
3. Classify text into headline/body/CTA/legal/label using a local FLAN-T5 model.
   Rank fixed label sequences by mean token loss. Copy is data, not executable instructions.
   Advice changes bounded importance/demand weights, never the element schema/content.
4. Generate source-anchor, weighted-grid, recursive partition, image/copy and editorial
   layouts at several allocation weights. Groups retain their internal geometry;
   single text boxes can reflow; images keep proportions.
5. Fit text by measured local glyph widths and binary search, retaining explicit newlines,
   max_lines and immutable content. Skia metrics are preferred when installed. The
   pinned official renderer is now exercised on the supplied samples; proxy quality
   checks still do not reproduce the organizer's AI evaluation.
6. Rank font readability, foreground collisions, image size, coarse source anchors,
   and approximate contrast/background variation sampled from the actual assets.
7. Independently audit the winning JSON. Render and report quality limitations separately.

The API is resize(source, target_canvas) -> design. A diagnostic API returns model
status, candidate scores, warnings, and metric backend outside the scored JSON.
No learned weights are fine-tuned here. Model-off mode is a measured ablation, not an
undisclosed fallback. Required mode fails if inference cannot run.

## Primary sources consulted

- [LayoutFormer++](https://arxiv.org/abs/2208.08037): motivates respecting explicit
  layout constraints during generation. We use bounded candidate geometry rather than
  implement its trained autoregressive architecture.
- [Constrained Graphic Layout Generation via Latent Optimization](https://arxiv.org/abs/2108.00871):
  motivates combining aesthetic objectives with alignment/overlap constraints. Our search
  runs in direct geometry space and does not reproduce the paper's latent optimizer.
- [Google FLAN-T5-small](https://huggingface.co/google/flan-t5-small): public instruction
  model with CPU usage and Apache-2.0 license. Chosen as the verified initial model because
  complete weights and compatible CPU dependencies were already available locally.
- [Qwen official GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF): researched
  as an alternative small quantized model. Its adapter exists, but inference was not verified
  because new weights and llama-cpp-python could not be downloaded in this environment.
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python): local GGUF loading and
  schema-constrained chat output for the optional adapter.
- [Adobe image import API](https://developer.adobe.com/express/add-ons/docs/guides/learn/how-to/use-images)
  and [manifest schema](https://developer.adobe.com/express/add-ons/docs/references/manifest/):
  used for the preview/import panel. A native scenegraph round-trip is beyond this baseline.

These are design influences and API references, not evidence our heuristic matches a
paper's results. No claim of beating learned methods or Adobe's official scorer is made.

## Known tradeoffs

- FLAN is a small text model, not a vision model; it cannot recognize a logo in pixels.
  Geometric prominence and the preserved original assets carry image hierarchy.
- Group preservation is conservative. Complex groups can become too small instead of
  intelligently reflowing their children. Arbitrary nested groups are not represented
  by the current schema's single group_id.
- Background samples estimate contrast and busyness; they are not full perceptual QA.
- Intentional overlap outside explicit/simple inferred groups is ambiguous. Conservative
  collision avoidance may lose a source composition's character.
- Typography measures glyph advances; official sample rendering now works, but
  systematic pixel-level contrast, clipping and text-visibility checks remain needed.
- No method can guarantee readable long paragraphs at every extreme canvas while
  preserving all content. The baseline flags small copy instead of dropping it.
- Candidate evaluation is approximately quadratic in foreground unit count, and text
  measurement grows with content length. The interactive service caps requests; the
  scored batch API does not impose that UI cap.

## Next experiments

Collect independent human-designed sources, add pixel-level text/contrast checks with
the official renderer, improve group reflow and copy adjacency, then compare a stronger
approved local model against this measured baseline. Do not tune on the existing holdout
and continue calling it unseen; reserve new source designs for the next iteration.
