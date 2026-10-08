"""Build-time only: download a public GGUF at a resolved revision and record its hash."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default="Qwen/Qwen2.5-0.5B-Instruct-GGUF")
    p.add_argument("--file", default="qwen2.5-0.5b-instruct-q4_k_m.gguf")
    p.add_argument("--revision", default="main", help="Use a reviewed commit SHA for a frozen submission")
    p.add_argument("--output", type=Path, default=Path("models"))
    args = p.parse_args()
    from huggingface_hub import HfApi, hf_hub_download
    revision = HfApi().model_info(args.repo, revision=args.revision).sha
    path = Path(hf_hub_download(args.repo, args.file, revision=revision, local_dir=args.output))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    manifest = {"repo": args.repo, "file": args.file, "revision": revision,
                "sha256": digest.hexdigest(), "bytes": path.stat().st_size,
                "competition_approval": "UNCONFIRMED"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
