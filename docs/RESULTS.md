# Baseline results and limits

## Environment

Windows 11, AMD Ryzen 5 5625U, 12 logical CPU threads, 13.86 GiB usable RAM.
About 4.08 GiB RAM was available at initial inspection. Python 3.13.7, CPU PyTorch
2.11.0 and Transformers 4.57.6. No GPU is needed for the tested FLAN-T5-small model.
Its public cached weights were copied into the workspace and hashed in models/manifest.json.

## Actual model execution

The three supplied samples ran with model mode required, not an inference stub:

| Sample | Engine time including any model loading | Structural result | Text below 10px |
| --- | ---: | --- | ---: |
| Level 1 | 13.45 s (cold model load) | Pass | 0 |
| Level 2 | 0.62 s | Pass | 0 |
| Level 3 | 1.83 s | Pass | 8 |

All had zero measured text overflows and zero flagged foreground collisions.
These results were re-rendered with the pinned official cr-renderer. The counts are
still local audit proxies, not Adobe's AI scores.

## Official renderer and visual review

The official `cr-renderer` 0.1.0 dependency was installed from commit
`a17e1fb9a732959dd6c21ae168d5ee09d74bd64f` and pinned in requirements.txt.
The renderer integration test passed, and the actual-model sample gallery is at
output/final-official/index.html. The paired model-off gallery is at
output/final-official-off/index.html.

- Level 1: the source logo, headline, bottle artwork, colors and CTA survive; the
  composition is clearer than simple stretching.
- Level 2: the logo/product and headline, supporting copy and CTA are retained and
  separated into readable regions.
- Level 3: the extreme 728x90 banner is contract-valid but visibly too dense. All
  eight text elements are below 10px, including the headline and supporting copy;
  the intentionally missing image is displayed as a placeholder. This is the main
  quality failure to address before claiming competition-ready readability.

This confirms official rendering works. It does **not** confirm the organizer's
automated AI evaluation or an official score.

## What the provided judging materials say

The challenge brief and [RULES.md](../RULES.md) describe two independently evaluated
artifacts: the output JSON and the official-rendered PNG. The brief's stated visual
criteria are:

- no unwanted collisions; text should not sit on a busy image
- readable text with sufficient contrast and no clipping
- brand colors, fonts and logo preserved in proportion
- intentional alignment, spacing, hierarchy and image proportions
- consistent results across many designs and target shapes

The JSON is also checked for structure, preserved element IDs, required fields,
on-canvas geometry and image proportions. The supplied materials do not disclose
the AI evaluator prompt, numeric weights or a score formula. The local audit counts
below are diagnostics only, not a reconstruction of that scorer.

## Held-out synthetic comparison

Twelve new source seeds (1000-1011), each crossed with six target formats: 72 cases.
This set was first evaluated after the initial algorithm was built; no tuning was
performed using these outcomes. It shares generator families with development data,
so it is weaker evidence than independent human-designed sources.

| Measure | Stretch baseline | Model off | Actual local model |
| --- | ---: | ---: | ---: |
| Contract-valid cases | 3/72 | 72/72 | 72/72 |
| Measured text overflows | See raw report | 0 | 0 |
| Flagged foreground collisions | See raw report | 0 | 0 |
| Text elements below 10px | See raw report | 48 | 47 |
| Mean engine time | Not timed | 0.117 s | 0.500 s |

The model changed the selected candidate family on 23/72 cases. This is a modest
proxy improvement, not a proven aesthetic advantage. Timing includes a cold model
load amortized across a batch and cached role inference across target sizes; concurrent
test activity also affected this run. Do not present it as isolated per-request latency.

## Paired model and scoring experiments

I ran the same 48 cases (synthetic seeds 2000-2007 crossed with six target formats)
with model mode `required` and `off`. This is a paired experiment using the existing
synthetic generator, not 48 independently authored designs.

| Measure | FLAN required | Model off |
| --- | ---: | ---: |
| Contract-valid | 48/48 | 48/48 |
| Text overflow | 0 | 0 |
| Flagged collisions | 0 | 0 |
| Text below 10px | 20 | 20 |
| Stretch baseline valid | 4/48 | 4/48 |
| Mean engine time | 0.729 s | 0.244 s |

FLAN changed the selected candidate on 17/48 paired cases, but did not change the
measured quality counts. On the advanced sample, a local role-classification spot
check also assigned the headline and CTA to `label`, so semantic guidance is not
reliably correct yet. Keep model mode optional; these results alone do not justify
claiming that FLAN improves quality.

A separate scoring sweep increased the below-10px penalty from 0.3 to 1.5 and 5.0
on the same 48 synthetic cases. All three settings selected the same measured
quality outcome (48/48 valid, 0 overflow/collisions, 20 small texts); the advanced
sample render was likewise unchanged. The sweep report and rendered samples are in
output/experiment-small-text/.

Three generic prompt variants were tested on 16 hand-labeled challenge/generic text
examples. The current prompt classified 5/16 correctly; adding definitions scored
3/16 and few-shot examples 6/16. This tiny exploratory check is not a robust model
benchmark, so no prompt change was made. Raw predictions are in
output/experiment-role-prompts/report.json.

The earlier development run (72 cases, before the final contrast/editorial additions)
was 72/72 structurally valid with zero overflow/collisions and 51 small text elements.
It is logged as an intermediate result, not a final model comparison.

## Verification performed

- Full test suite: 102 passed, 1 skipped in 33.65 seconds. One local pytest cache
  permission warning did not affect the test result.
- Actual CPU model inference passed with socket connections forbidden.
- The official-renderer integration test passed after pinning the verified dependency.
- Local service health, sample listing, and official-renderer resize endpoints returned
  HTTP 200; the advanced result returned valid JSON and a PNG.
- Tests cover input immutability, schema/ID preservation, sample-ID independence,
  image proportions, rotated bounds, newlines, long words, groups, missing assets,
  invalid coordinates, malformed model responses and explicit required-model failure.
- Additional checks verify rigid relative geometry within groups and that the contrast
  proxy penalizes white text on a white background more than white text on black.
- Service tests validate PNG/JSON responses, preview size limits and asset path bounds.
- HTTP smoke test: health, sample loading, model-required resize and panel GET succeeded.
- Node syntax check for addon/app.js passed; DOM IDs and manifest references passed.
- Generated video: 18 seconds, 36 verified JPEG frames in an MJPEG AVI container.
  File structure/frame decoding checked; playback in a video player was not verified.
- Git diff whitespace checks passed (only normal Windows LF/CRLF notices).

## Not verified / remaining risks

1. The organizer's AI scorer and numeric/weighted rubric are not supplied, so no official
   score or “best method” claim can be made from these proxies.
2. Docker build and `--network none` execution: Docker is not installed on this machine.
3. Full Adobe Express host integration was not validated; the available headless browser
   lacked its Chromium executable. Local HTTP endpoints were verified separately.
4. Approved-model list and final reference-hardware limits remain unspecified in the brief.
5. Extreme banners: level 3 remains visibly too small despite valid geometry.
6. Native Express editable-node import/export is not implemented; current import is one PNG.

## Reproducible evidence

- output/final-official/index.html and report.json: actual local-model sample gallery
  rendered through the pinned official renderer.
- output/final-official-off/index.html: paired model-off official-renderer gallery.
- output/paired-benchmark-model/report.json and
  output/paired-benchmark-off/report.json: same 48 synthetic cases in both modes.
- output/experiment-small-text/report.json: small-font score-weight sweep.
- output/experiment-role-prompts/report.json: exploratory prompt comparison.
- output/model-samples/index.html and report.json: earlier Pillow development gallery.
- output/holdout-model/report.json: model-required held-out run.
- output/holdout-off/report.json: matching ablation.
- output/baseline-dev/report.json: earlier development run.
- output/demo/chameleon-engine-demo.avi: labeled engine walkthrough.

Generated outputs and large weights are not committed; commands in README reproduce
them. The model manifest and this measured summary are tracked with the implementation.
