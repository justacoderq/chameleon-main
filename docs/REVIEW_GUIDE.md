# Reviewer quick guide

This is the fastest path to inspect the submission branch and reproduce its
sample outputs. The intended submission version is **`combined-engine-merged`**.
The stage-one engine is the focus; the challenge brief describes the Express
add-on as a finale deliverable.

## Run the engine

From the repository root, build the standard Linux image:

```sh
docker build --platform linux/amd64 -t chameleon .
```

Run the samples with runtime networking disabled:

```sh
docker run --rm --network none \
  -v "$(pwd)/input:/app/input:ro" \
  -v "$(pwd)/output:/app/output" \
  chameleon
```

The image uses the required local FLAN-T5 model and the pinned official
`cr-renderer`. It writes one `*_output.json`, `*_output.png`, and
`*_diagnostics.json` per input. The Docker build downloads and packages the
model and renderer; inference does not need network access.

For a local Python run, see the setup commands in [`README.md`](../README.md).
To test the engine suite:

```sh
pytest -q
```

The actual-weight integration test is opt-in. Run it with
`CHAMELEON_TEST_LIVE_MODEL=1` in the environment. The stress suites are separate
from pytest:

```sh
python -m evaluation.stress --suite hidden --designs 240
python -m evaluation.stress --suite mutations --designs 200
```

These audits and stress suites are local engineering checks, not the organizer's
AI score.

## What to inspect

1. **The three sample tasks:** `input/` contains warm-up, core, and advanced
   examples. The advanced example resizes a 17-element design to 728×90.
2. **Both scored artifacts:** inspect the output JSON for preserved IDs and
   properties, then inspect the PNG rendered through `cr-renderer`. They are
   generated together by `engine.main`.
3. **The decision path:** `engine/analyze.py` infers structural roles;
   `engine/reflow.py` builds responsive layouts; `engine/resize.py` provides a
   partition-search alternative and referee; `evaluation/audit.py` checks the
   output contract and reports separate quality warnings.
4. **The model boundary:** `engine/local_model.py` uses pinned
   `google/flan-t5-small` weights for text-role hints only. It does not generate
   geometry, rewrite content, or regenerate imagery. The model can be disabled
   explicitly with `--model off`.

The brief's visual criteria include no unwanted collisions, readable text with
adequate contrast, preserved brand identity, intentional hierarchy/alignment,
and reliability across unseen designs. The local audit is a proxy for these
criteria, not a substitute for judging the rendered PNG.

## Results and limitations

The current recorded sample run uses the required local model and official
renderer. All three samples pass the local hard-contract audit; the advanced
728×90 sample has no measured overflow or flagged collision, but has **seven
text elements below 10 px**. Tiny text is the principal visible quality risk.
See [`RESULTS.md`](RESULTS.md) for measured evidence and known validation limits.

The supplied PDF says model constraints and exact reference hardware were being
finalized. Later info-session notes reported that downloadable open weights were
acceptable and small, swappable models were encouraged; the team should follow
any newer organizer guidance. The 77M-parameter model is documented
transparently. Local metrics are not an official score or an assurance of
finalist selection.
