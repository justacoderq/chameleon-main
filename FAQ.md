# Chameleon repository FAQ

This page describes this implementation. The challenge brief in
[`Final Chameleon Challenge.pdf`](Final%20Chameleon%20Challenge.pdf) is the
authority for competition rules and deliverables.

## What does the engine take and return?

`engine.resize.resize(source, target_canvas)` accepts a design and target canvas
and returns the resized design JSON. The batch entry point reads each JSON task
from `input/`, validates outputs, and writes JSON, PNG, and diagnostics into
`output/`.

## How do I run it?

For reviewer-ready Docker and test commands, use the
[review guide](docs/REVIEW_GUIDE.md). For local Python setup, see the
[README](README.md). Docker builds the pinned renderer and model; runtime
inference is configured to run offline.

## Which renderer is used?

The default batch renderer is the pinned official `cr-renderer`. Pillow is
available only when explicitly selected for development previews; it is not
official-renderer or scoring evidence.

## What does FLAN-T5 do?

The pinned `google/flan-t5-small` model ranks a fixed set of text-role labels.
It does not generate layout coordinates, edit copy, alter assets, or call a
remote service. `--model off` runs the deterministic geometric path without
model inference. See [`models/README.md`](models/README.md).

## What is not proven?

The local contract audit and generated stress cases are not the organizers'
hidden evaluation. On the supplied 728×90 advanced sample, seven text elements
remain below 10 px even though the JSON passes the structural audit. See
[`docs/RESULTS.md`](docs/RESULTS.md) and
[`docs/TECHNICAL_RATIONALE.md`](docs/TECHNICAL_RATIONALE.md).
