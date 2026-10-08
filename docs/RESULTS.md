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
| Level 1 | 12.97 s (cold model load) | Pass | 0 |
| Level 2 | 0.95 s | Pass | 0 |
| Level 3 | 2.23 s | Pass | 8 |

All had zero measured text overflows and zero flagged foreground collisions.
These PNGs use the explicitly labeled Pillow development renderer. They are not
official cr-renderer outputs, and the counts are not Adobe's scoring rubric.

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

The earlier development run (72 cases, before the final contrast/editorial additions)
was 72/72 structurally valid with zero overflow/collisions and 51 small text elements.
It is logged as an intermediate result, not a final model comparison.

## Verification performed

- Final run: 93 tests passed, 1 skipped in 28.03 seconds, including actual CPU model
  inference with socket connections forbidden. The skip explicitly identifies the
  unavailable official renderer. Two dependency SWIG deprecation warnings were reported.
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

1. Official cr-renderer pixel output: dependency installation was blocked by network rules.
2. Docker build and --network none execution: Docker is not installed on this machine.
3. Browser interactions and live Adobe Express import: no browser was connected.
4. Approved-model list and final hardware limits: absent from the supplied brief.
5. Extreme banners: the sample Level 3 text is visibly too small despite valid geometry.
6. Native Express editable-node import/export: not implemented; current import is one PNG.
7. Third-party renderer dependency lock: freeze a tested revision after installation succeeds.

## Reproducible evidence

- output/model-samples/index.html and report.json: actual local-model sample gallery.
- output/holdout-model/report.json: model-required held-out run.
- output/holdout-off/report.json: matching ablation.
- output/baseline-dev/report.json: earlier development run.
- output/demo/chameleon-engine-demo.avi: labeled engine walkthrough.

Generated outputs and large weights are not committed; commands in README reproduce
them. The model manifest and this measured summary are tracked with the implementation.
