# Local model

The default model is `google/flan-t5-small`, pinned to revision
`0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab` (77M parameters, Apache-2.0).
`manifest.json` records the expected file sizes and SHA-256 hashes.

Model weights are not committed to Git. For a local run, prepare a complete
snapshot while online:

```sh
python -m scripts.prepare_flan
```

The Docker build prepares the model at build time. At runtime the tokenizer and
weights load locally; the engine does not download them. `--model required`
fails if inference is unavailable, `--model auto` reports unavailability, and
`--model off` disables inference for an explicit geometric ablation.

The model ranks fixed text-role labels only. It does not generate geometry,
rewrite copy, or modify assets. Existing paired synthetic experiments show no
measured reduction in small-text counts from enabling FLAN; the model is a
bounded hint, not a demonstrated quality improvement. See
[`docs/RESULTS.md`](../docs/RESULTS.md).

The repository also contains an optional GGUF adapter, but it is not part of the
default Docker image and is not included in the verified model results.
The brief says model constraints were being finalized; later info-session notes
reported that downloadable open weights were acceptable and small, swappable
models were encouraged. Check for any newer organizer guidance.
