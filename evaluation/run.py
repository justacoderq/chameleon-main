"""Run sample/synthetic holdout evaluations and export a reviewable HTML gallery."""
import argparse
from copy import deepcopy
import html
import json
import os
from pathlib import Path
import time

from engine.resize import resize_with_diagnostics
from engine.preview import render
from evaluation.audit import audit
from evaluation.cases import TARGETS, synthetic

ROOT = Path(__file__).resolve().parents[1]


def stretch(source, target):
    out = deepcopy(source)
    sx, sy = target["width"]/source["canvas"]["width"], target["height"]/source["canvas"]["height"]
    out["canvas"] = dict(target)
    for e in out["elements"]:
        e["x"] *= sx
        e["y"] *= sy
        e["width"] *= sx
        e["height"] *= sy
        if e["type"] == "text":
            e["font_size"] = max(1, e["font_size"]*min(sx,sy))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", choices=["samples","dev","holdout"], default="samples")
    p.add_argument("--count", type=int, default=12, help="Synthetic source count; each uses six targets")
    p.add_argument("--renderer", choices=["official","pillow","none"], default="official")
    p.add_argument("--model", choices=["off","auto","required"], default="auto")
    p.add_argument("--output", type=Path, default=ROOT / "output/evaluation")
    args = p.parse_args()
    os.environ["CHAMELEON_MODEL_MODE"] = args.model
    args.output.mkdir(parents=True, exist_ok=True)
    if args.split == "samples":
        cases = [(path.stem,json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT/"input").glob("*.json"))]
    else:
        start = 1000 if args.split == "holdout" else 100
        cases = [(f"{args.split}-{seed}-{w}x{h}", {"source":synthetic(seed),"target_canvas":{"width":w,"height":h}})
                 for seed in range(start,start+args.count) for w,h in TARGETS]
    records, cards = [], []
    for name, task in cases:
        t0 = time.perf_counter()
        output, diag = resize_with_diagnostics(task["source"], task["target_canvas"])
        seconds = time.perf_counter()-t0
        result = audit(task["source"], output, task["target_canvas"])
        baseline = stretch(task["source"],task["target_canvas"])
        before = audit(task["source"], baseline, task["target_canvas"])
        record = {"name":name,"seconds":seconds,"audit":result,"baseline":before,"diagnostics":diag}
        records.append(record)
        (args.output/f"{name}.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
        if args.renderer != "none":
            warnings = []
            for suffix, design in [("source",task["source"]),("stretch",baseline),("result",output)]:
                warnings += render(design,args.output/f"{name}-{suffix}.png",args.renderer)
            record["render_warnings"] = warnings
            images = "".join(f'<figure><figcaption>{s}</figcaption><img src="{name}-{s}.png"></figure>' for s in ["source","stretch","result"])
            cards.append(f'<article><h2>{html.escape(name)}</h2><div class="row">{images}</div><pre>{html.escape(json.dumps(result,indent=2))}</pre></article>')
        print(f"{name}: valid={result['valid']}, overflow={result.get('text_overflows')}, small={result.get('small_texts')}, {seconds:.3f}s")
    summary = {"split":args.split,"case_count":len(records),"renderer":args.renderer,"model_mode":args.model,
               "valid_cases":sum(r["audit"]["valid"] for r in records),
               "baseline_valid_cases":sum(r["baseline"]["valid"] for r in records),
               "text_overflows":sum(r["audit"].get("text_overflows",0) for r in records),
               "small_texts":sum(r["audit"].get("small_texts",0) for r in records),
               "collisions":sum(r["audit"].get("collisions",0) for r in records),
               "mean_seconds":sum(r["seconds"] for r in records)/max(1,len(records)),
               "real_model_used_cases":sum(r["diagnostics"]["model"]["status"]=="used" for r in records),
               "notice":"Local proxies only; not official scores. Synthetic holdout shares a generator with dev."}
    report = {"summary":summary,"cases":records}
    (args.output/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    page = '<!doctype html><meta charset="utf-8"><title>Chameleon evaluation</title><style>body{font:16px system-ui;margin:32px;background:#f4f3ef;color:#20202a}.row{display:flex;gap:16px}figure{margin:0;flex:1;min-width:0}img{width:100%;max-height:480px;object-fit:contain;background:#ddd}article{background:white;padding:24px;margin:24px 0}pre{white-space:pre-wrap}figcaption{font-weight:600;margin:12px 0}</style><h1>Chameleon evaluation</h1><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'+"".join(cards)
    (args.output/"index.html").write_text(page,encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return 0 if summary["valid_cases"] == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
