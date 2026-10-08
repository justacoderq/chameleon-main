# Local model

Verified baseline: google/flan-t5-small (77M parameters, Apache-2.0), revision
0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab. Model eligibility is UNCONFIRMED until the
organizer publishes its approved list and size cap.

Run python -m scripts.prepare_flan while online, or pass --source with a complete
local snapshot directory. This copies only safetensors/tokenizer/config/card files
into models/flan-t5-small and records revision, SHA256 hashes and sizes in manifest.json.
The weights are ignored by Git. A local copy is already prepared in this workspace.

Set CHAMELEON_MODEL_MODE=required to fail when inference is unavailable. Both the model
and tokenizer load with local_files_only=True. No runtime downloads occur. The Docker
build downloads weights at build time and requires the local model at runtime.

The model ranks five text-role labels. It cannot invent geometry, rewrite text, add
elements or alter assets. On the first held-out synthetic comparison, its benefit was
small: 47 text elements below 10px versus 48 with the model disabled.

Optional unverified alternative: install requirements-gguf.txt, run
python -m scripts.prepare_model, and set CHAMELEON_MODEL_PATH to the downloaded .gguf.
The adapter supports Qwen2.5-0.5B-Instruct GGUF through llama-cpp-python. Its weights and
runtime could not be downloaded here, so do not claim it has been tested.
