# Results and verification

These are local engineering checks for the `combined-engine-merged` code at
`bbd0fb6`, not results from Adobe's hidden evaluator. The current branch contains
documentation cleanup in addition to that engine revision.

## Supplied samples: required model and official renderer

Command:

```sh
python -m engine.main --model required --renderer official --input input --output output
```

On 2026-10-29, all three sample tasks completed with the pinned local
`google/flan-t5-small` model and official `cr-renderer`. All three outputs passed
the local hard-contract audit, with zero measured text overflows and zero
flagged collisions. The advanced 728×90 sample still had **seven text elements
below 10 px**. Its JSON validity therefore does not imply comfortable
readability; inspect the PNG as well as the JSON.

The opt-in test `tests/test_model_live.py::test_real_model_runs_without_network`
also passed with the local weights and outbound socket connections blocked.

## Test suite

The default `pytest -q` run collected 106 tests: **105 passed and one
opt-in real-model test was skipped**. Setting `CHAMELEON_TEST_LIVE_MODEL=1`
enables the skipped test. A full-suite run with that setting is the recommended
final verification.

## Generated hidden-style stress suite

Command:

```sh
CHAMELEON_MODEL_MODE=required python -m evaluation.stress --suite hidden --designs 240 --procs 4
```

This run crossed 240 locally generated designs from 12 archetypes with 21
platform-format targets (**5,040 cases**). It reported:

| Measure | Result |
|---|---:|
| Crashes / invalid outputs / measured text-overflow cases | 0 / 0 / 0 |
| Reflow selections / partition-search fallbacks | 4,980 / 60 |
| Cases with text below 10 px | 846 |
| Cases with audit-flagged possible collisions | 329 |
| Cases with a new text-over-image overlap (viewer heuristic) | 7 |
| Cases where the original largest text was no longer largest | 56 |
| Near-invisible image cases (viewer heuristic) | 5 |
| Per-case time, mean / p99 / maximum | 0.585 s / 6.921 s / 27.573 s |

These are generated local cases, not the organizer's hidden designs. The
collision and viewer checks are heuristics; some reported overlaps may be
intentional or inherited from a source design. The small-text count is
nevertheless a meaningful warning that structural validity alone is
insufficient.

The separate mutation suite is `python -m evaluation.stress --suite mutations
--designs 200`. It covers sample mutations and synthetic designs across 35
sizes (**10,570 cases**):

| Measure | Result |
|---|---:|
| Crashes / invalid outputs | 0 / 0 |
| Cases with measured text overflow | 2 |
| Cases with text below 10 px / audit-flagged possible collisions | 2,307 / 303 |
| New text-over-image overlaps (viewer heuristic) | 35 |
| Near-invisible images (viewer heuristic) | 57 |
| Original largest text no longer largest (viewer heuristic) | 260 |
| Reflow selections / partition-search fallbacks | 10,103 / 467 |
| Per-case time, mean / p99 / maximum | 0.413 s / 3.636 s / 15.998 s |

Both overflows occurred in the deliberately extreme `level3_advanced+long-copy`
mutation, at 50×50 and 72×90. This is a useful stress failure, not a clean
pass: both targets force substantial copy into tiny canvases, and the engine's
partition-search fallback still shipped overflowing text. The 50×50 case also
produced near-invisible text and an image. Treat the counts as local quality
proxies, not confirmed human-judged defects. Determinism was not enabled for
this run.

## Model ablation and measured limits

Earlier paired experiments on the repository's synthetic generators found no
measured reduction in small-text elements from enabling FLAN: 47 versus 48 in
one 72-case holdout comparison and 20 versus 20 in a paired 48-case comparison.
The model changed candidate choices, but those experiments do not establish an
aesthetic improvement. FLAN is retained as a small, replaceable semantic hint,
not claimed as the reason the layout succeeds.

The stress designs share generated archetypes and do not establish
generalization to human-authored or hidden cases. The official scorer's prompt
and score formula are not supplied, so none of these numbers predicts a
competition score or finalist selection.

## Packaging and integration status

An earlier macOS/Colima run recorded an offline Docker execution with the model
used on all tasks and 51/51 supplied-sample/platform-format outputs valid. That
run predates the latest engine change at `bbd0fb6`. Docker is unavailable in
the current Windows environment, so rebuild and run the exact submission
revision with `--network none` before delivery.

The local preview panel has a prior Chrome walkthrough recorded in the project
history. Adobe Express-hosted integration remains unverified. The challenge
brief places the full Express add-on, pitch, and video in the finale deliverables;
the stage-one deliverable is the engine and its run instructions.

For reviewer commands and the limits of the local proof of concept, see the
[review guide](REVIEW_GUIDE.md) and
[technical rationale](TECHNICAL_RATIONALE.md).
