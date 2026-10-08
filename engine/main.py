"""Competition batch entry point. Official rendering is required unless explicitly overridden."""
import argparse
import json
import logging
import os
from pathlib import Path
import time

from engine.resize import resize_with_diagnostics
from engine.preview import render
from evaluation.audit import audit


def self_check(source, output):
    """Retained for compatibility, now with schema and rotated-geometry checks."""
    return audit(source, output, output.get("canvas", {}))["hard_errors"]


def render_to_png(design, assets_dir, png_path):
    # Preserve the starter helper signature; brand assets are repo-relative.
    return render(design, png_path, "official")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=Path("input"))
    p.add_argument("--output", type=Path, default=Path("output"))
    p.add_argument("--renderer", choices=["official","pillow"], default="official")
    p.add_argument("--model", choices=["off","auto","required"], default=os.environ.get("CHAMELEON_MODEL_MODE","auto"))
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING)
    os.environ["CHAMELEON_MODEL_MODE"] = args.model
    args.output.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.input.glob("*.json"))
    if not paths:
        print(f"No task files in {args.input}")
        return 1
    failed = False
    for path in paths:
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            start = time.perf_counter()
            output, diagnostics = resize_with_diagnostics(task["source"],task["target_canvas"])
            result = audit(task["source"],output,task["target_canvas"])
            if not result["valid"]:
                raise ValueError("Output contract failed: " + "; ".join(result["hard_errors"]))
            stem = args.output / (path.stem + "_output")
            warnings = render(output, stem.with_suffix(".png"), args.renderer)
            stem.with_suffix(".json").write_text(json.dumps(output,indent=2),encoding="utf-8")
            diagnostics.update(audit=result,renderer=args.renderer,render_warnings=warnings,seconds=time.perf_counter()-start)
            (args.output/(path.stem+"_diagnostics.json")).write_text(json.dumps(diagnostics,indent=2),encoding="utf-8")
            print(f"{path.name}: valid; model={diagnostics['model']['status']}; renderer={args.renderer}; quality warnings={len(result['quality_warnings'])}")
        except Exception as exc:
            failed = True
            print(f"FAILED {path.name}: {type(exc).__name__}: {exc}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
