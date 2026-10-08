# Chameleon baseline — Prachi

Branch: baseline-solution-prachi. An offline design reflow engine, local Hugging Face
model, test harness, comparison gallery, and Express preview panel.

The CPU model is **google/flan-t5-small** at a pinned revision. It ranks text roles;
deterministic search fits groups, images, and measured text into the target canvas.
Original text, font families, IDs, assets, colors, layers, and groups are preserved.
There is no image generation or runtime model download.

## Current verification

The real model runs on the inspected Ryzen 5 5625U Windows laptop with approximately
14 GiB usable RAM. The baseline has passed offline model integration and contract
tests. See docs/RESULTS.md for measured results and limitations.

**Not submission-verified yet:** the official cr-renderer dependency could not be
installed through this session's blocked network; Docker is not installed, and no
browser was connected for live Express testing. Current PNGs use an explicitly
labeled Pillow development renderer. Extreme banners still contain unreadably small
text. Model approval must be checked against the organizer's final list.

## Run on this workspace now (PowerShell)

From the inner chameleon-main directory:

    .\.venv\Scripts\python.exe -m engine.main --model required --renderer pillow --output output/local-run
    .\.venv\Scripts\python.exe -m engine.service --model required --renderer pillow

Open http://localhost:5241 for the local panel. It accepts the supplied sample tasks
or a source design JSON, then previews/downloads the resized design. Assets referenced
by imported JSON must already be in brand_kit/assets; a flat image is not a structured
design input. Missing assets are preserved as references and shown as placeholders.

The local public FLAN weights have been copied into models/flan-t5-small. They are
not committed to Git; models/manifest.json records their revision and SHA256 hashes.

## Set up a clean machine

Python 3.11 is recommended for dependency wheel compatibility. A GPU is unnecessary.

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-model.txt
    .\.venv\Scripts\python.exe -m scripts.prepare_flan
    .\.venv\Scripts\python.exe -m engine.main --model required

Setup needs internet; inference does not. On Linux/macOS use .venv/bin/python.
The default renderer is official and fails explicitly if unavailable. Never present
the Pillow gallery as official renderer/scorer evidence.

## Test and inspect

    .\.venv\Scripts\python.exe -m pytest -q
    $env:CHAMELEON_TEST_LIVE_MODEL = "1"
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m evaluation.run --split samples --model required --renderer pillow --output output/model-samples
    .\.venv\Scripts\python.exe -m evaluation.run --split holdout --count 12 --model required --renderer none --output output/holdout-model
    .\.venv\Scripts\python.exe -m scripts.doctor

Open output/model-samples/index.html for original/stretch/result comparisons.
Reports separate hard contract failures, overflow, small text, potential collisions,
model status, and latency. They are local quality proxies, **not Adobe scores**.
Run with --model off for an ablation. The synthetic holdout uses separate seeds but
the same generator; add genuinely new designs before trusting generalization.

## Offline container validation (requires Docker)

    docker build --platform linux/amd64 -t chameleon-prachi .
    docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/input,target=/app/input,readonly" --mount "type=bind,source=$((Get-Location).Path)/output,target=/app/output" chameleon-prachi

Build downloads pinned public model weights and required packages. Runtime requires
the model and official renderer; missing dependencies produce errors. Confirm the
final organizer architecture/hardware requirements before freezing a submission.
The upstream cr-renderer Git dependency is not commit-pinned yet; capture a verified
revision and dependency lock after the first successful official build.

## Files

- engine/resize.py: public resize contract, grouping, candidate generation and scoring.
- engine/local_model.py: local FLAN label likelihoods; optional GGUF adapter.
- engine/typography.py, geometry.py, appearance.py: fitting, bounds, contrast proxy.
- engine/main.py: batch JSON/PNG outputs and honest failure diagnostics.
- evaluation/: independent contract checks, synthetic cases and review galleries.
- tests/: invariants, mutations, service checks, actual offline-model integration.
- addon/ and engine/service.py: local/Express preview panel and engine endpoint.
- docs/ARCHITECTURE.md: approach, research sources and tradeoffs.
- docs/REQUIREMENTS.md: brief-to-deliverable mapping and unresolved rules.
- docs/EXPRESS.md: HTTPS and Adobe host testing steps; current insertion limits.
- docs/PITCH.md: short pitch and demo narration.
- WORK_LOG.md: chronological actions, failures, decisions and checks.

Generate the silent 18-second engine walkthrough with python -m scripts.make_demo.
It writes output/demo/chameleon-engine-demo.avi from actual model sample previews.
This is not a live Express recording; record that separately after host verification.
