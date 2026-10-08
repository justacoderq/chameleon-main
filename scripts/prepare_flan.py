"""Copy/download public safetensors and tokenizer files into the submission bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

REVISION = "0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab"
FILES = ["config.json","generation_config.json","model.safetensors","special_tokens_map.json",
         "spiece.model","tokenizer.json","tokenizer_config.json","README.md"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,help="Existing complete local snapshot; no network needed")
    p.add_argument("--output",type=Path,default=Path("models/flan-t5-small"))
    args = p.parse_args()
    source = args.source
    if source is None:
        from huggingface_hub import snapshot_download
        source = Path(snapshot_download("google/flan-t5-small",revision=REVISION,allow_patterns=FILES))
    missing = [name for name in FILES if not (source/name).is_file()]
    if missing:
        raise FileNotFoundError(f"Incomplete model snapshot: {missing}")
    args.output.mkdir(parents=True,exist_ok=True)
    manifest = {"repo":"google/flan-t5-small","revision":REVISION,"license":"Apache-2.0",
                "competition_approval":"UNCONFIRMED","files":{}}
    for name in FILES:
        target = args.output/name
        shutil.copyfile(source/name,target)
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):
                digest.update(block)
        manifest["files"][name] = {"sha256":digest.hexdigest(),"bytes":target.stat().st_size}
    (args.output.parent/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
