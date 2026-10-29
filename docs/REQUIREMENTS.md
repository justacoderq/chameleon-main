# Submission readiness and evidence

The [challenge brief](../Final%20Chameleon%20Challenge.pdf) describes stage one
as an offline containerized engine evaluated on hidden designs across all three
difficulty levels. The output JSON and the official-rendered PNG both matter.
This table maps those requirements to this repository without treating local
proxies as the organizer's score.

| Requirement | Implementation / evidence | Status and limitation |
|---|---|---|
| Accept a source design and target canvas; return resized JSON | `engine.resize.resize`; `engine.main` batch entry point | Implemented and exercised on all three supplied samples |
| Preserve elements, IDs, and immutable design properties | Deep-copy candidate construction; `evaluation/audit.py`; contract tests | Checked by the local audit; not a substitute for the organizer's validator |
| Keep geometry on-canvas and images in proportion | rotated-bounds and image-ratio checks; image/group sizing helpers | Tested locally; cover-fit images retain their declared crop behavior |
| Produce judge-visible images with the official renderer | pinned `cr-renderer`; `engine.preview.render`; official-renderer test | Latest local run rendered all three samples successfully |
| Readable, intentional layouts across target sizes | structure-aware candidates, scoring, independent partition search, audit referee | Not guaranteed. The 728×90 sample still has seven text elements below 10 px |
| Offline execution with a local model | pinned `google/flan-t5-small`; required/auto/off modes; socket-blocked model test | Actual local inference passed. Info-session notes favor small, swappable public models; follow newer organizer guidance |
| Standard container and no runtime network | `Dockerfile`; build-time model preparation; offline runtime environment | A prior macOS run is recorded in `docs/RESULTS.md`; rebuild the exact submission commit before delivery |
| Generalize beyond supplied samples | `evaluation.hidden_cases`, `evaluation.stress`, mutation and synthetic suites | Local generated cases only; not the organizer's hidden set or independent human designs |
| Explain how to inspect and run the submission | `README.md`, `docs/REVIEW_GUIDE.md`, `docs/TECHNICAL_RATIONALE.md` | Reviewer commands and limitations are documented |

The brief places the full Adobe Express add-on, pitch, and demo video in the
finale deliverables. The repository includes an optional preview panel, but it
inserts a flattened PNG and does not import editable native Express elements.
That scope should not be confused with the stage-one engine.

## Readiness judgment

The code and reviewer materials are organized for inspection, and the supplied
samples pass the current local structural checks. This is **not evidence of an
official score or a prediction of finalist selection**. Before submitting,
rebuild and run Docker from this exact commit with networking disabled, inspect
the rendered outputs—especially the advanced banner—and confirm the latest
organizer model guidance. See [`docs/RESULTS.md`](RESULTS.md) for precise
verification details.
