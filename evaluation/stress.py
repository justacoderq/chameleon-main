"""Stress test: run the engine over thousands of design × canvas cases.

    python -m evaluation.stress --suite mutations            # samples + mutations + synthetic, 35 sizes
    python -m evaluation.stress --suite hidden --designs 240 # hidden-style designs, 21 platform formats

Every output gets the contract audit (evaluation/audit.py) plus checks for what
a viewer notices: images shrunk to near-invisible, the headline no longer the
largest text, new text-over-image overlaps, zero-size elements, non-integer
font sizes, and (optionally) determinism. Writes <out>/stress.json and prints a
summary. These are local proxies, not the organizers' AI evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from engine.resize import resize_with_diagnostics
from evaluation.audit import audit, box, validator
from evaluation.cases import mutate, synthetic
from evaluation.hidden_cases import FMT, design

ROOT = Path(__file__).resolve().parents[1]

MUTATION_TARGETS = [
    (1080, 1080), (1080, 1350), (1080, 1920), (1920, 1080), (1280, 720), (1200, 628), (1200, 1200),
    (1500, 500), (1584, 396), (1600, 400), (1080, 566), (1000, 1500), (2048, 1152), (820, 312),
    (728, 90), (970, 250), (970, 90), (468, 60), (320, 50), (320, 100), (300, 250), (336, 280),
    (160, 600), (120, 600), (300, 600), (250, 250), (200, 200),
    (2000, 90), (90, 2000), (72, 90), (1280, 240), (240, 1280), (50, 50), (4000, 4000), (3000, 500),
]


def _inter(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def viewer_checks(src: dict, out: dict) -> list:
    issues = []
    S = {e["id"]: e for e in src["elements"]}
    O = {e["id"]: e for e in out["elements"]}
    W0, H0 = src["canvas"]["width"], src["canvas"]["height"]
    W, H = out["canvas"]["width"], out["canvas"]["height"]
    for i, e in O.items():
        s = S[i]
        if e["type"] == "image" and min(s["width"], s["height"]) > 40 and \
                min(e["width"], e["height"]) < 0.02 * min(W, H) + 6:
            issues.append("image shrunk to near-invisible")
        if (e["width"] <= 0.5 or e["height"] <= 0.5) and s["width"] > 0.5 and s["height"] > 0.5:
            issues.append("element collapsed to zero size")
        if e["type"] == "text" and e["font_size"] != int(e["font_size"]):
            issues.append("non-integer font size")
    texts = [i for i in S if S[i]["type"] == "text" and S[i].get("opacity", 1) > 0 and S[i]["content"].strip()]
    if len(texts) >= 2:
        top = max(texts, key=lambda i: S[i]["font_size"])
        others = [O[i]["font_size"] for i in texts if i != top and S[i]["font_size"] < 0.7 * S[top]["font_size"]]
        if others and O[top]["font_size"] < max(others):
            issues.append("headline no longer the largest text")
    full = lambda e: e["width"] >= 0.9 * W0 and e["height"] >= 0.9 * H0
    imgs = [i for i in O if O[i]["type"] == "image" and not full(S[i])]
    for t in texts:
        for m in imgs:
            if S[t].get("group_id") and S[t].get("group_id") == S[m].get("group_id"):
                continue
            if _inter(box(O[t]), box(O[m])) > 0.15 * O[t]["width"] * O[t]["height"] and \
                    _inter(box(S[t]), box(S[m])) <= 0.15 * S[t]["width"] * S[t]["height"]:
                issues.append("new text-over-image overlap")
    return sorted(set(issues))


def _cases(suite: str, n: int):
    if suite == "hidden":
        return [("hidden", s, t) for s in range(n) for t in FMT]
    names = []
    for p in sorted((ROOT / "input").glob("*.json")):
        for v in ("", "renamed", "long-copy", "rotation"):
            names.append(("sample", p.stem, v))
    for seed in range(100, 100 + n):
        for v in ([""] + (["renamed", "long-copy", "rotation"] if seed < 130 else [])):
            names.append(("synthetic", seed, v))
    return [(kind, (key, v), t) for kind, key, v in names for t in MUTATION_TARGETS]


def _source(kind, key):
    if kind == "hidden":
        arch, fmt, src = design(key)
        return f"{arch}#{key}({fmt})", src
    ref, variant = key
    if kind == "sample":
        src = json.loads((ROOT / "input" / f"{ref}.json").read_text())["source"]
        name = ref.replace("chameleon_sample_", "")
    else:
        src, name = synthetic(ref), f"syn{ref}"
    return (name + (f"+{variant}" if variant else "")), (mutate(src, variant) if variant else src)


def run_case(job):
    kind, key, t = job
    tw, th = FMT[t] if kind == "hidden" else t
    tgt = {"width": tw, "height": th}
    rec = {"target": f"{tw}x{th}"}
    try:
        rec["name"], src = _source(kind, key)
        rec["family"] = rec["name"].split("#")[0].split("+")[0]
        errs = [e.message for e in validator().iter_errors(src)]
        if errs:
            rec["bad_source"] = errs[:2]
            return rec
        t0 = time.perf_counter()
        out, diag = resize_with_diagnostics(src, tgt)
        rec["sec"] = time.perf_counter() - t0
        a = audit(src, out, tgt)
        rec.update(valid=a["valid"], hard=a.get("hard_errors", [])[:3], overflow=a.get("text_overflows", 0),
                   small=a.get("small_texts", 0), coll=a.get("collisions", 0), engine=diag["engine"],
                   layout=(diag.get("reflow") or {}).get("layout"), issues=viewer_checks(src, out),
                   reflow_error=(diag.get("reflow") or {}).get("error"))
        if os.environ.get("STRESS_DETERMINISM"):
            again, _ = resize_with_diagnostics(src, tgt)
            rec["deterministic"] = json.dumps(out, sort_keys=True) == json.dumps(again, sort_keys=True)
    except Exception as exc:
        rec["crash"] = f"{type(exc).__name__}: {exc}"
        rec["tb"] = traceback.format_exc()[-1200:]
    return rec


def summarize(R: list) -> dict:
    ok = [r for r in R if "valid" in r]
    secs = sorted(r["sec"] for r in ok) or [0.0]
    by = defaultdict(Counter)
    for r in ok:
        for flag, hit in (("invalid", not r["valid"]), ("overflow", r["overflow"] > 0), ("collision", r["coll"] > 0)):
            if hit:
                by[flag][r["family"]] += 1
        for x in r["issues"]:
            by[x][r["family"]] += 1
    return {
        "cases": len(R), "bad_sources": sum("bad_source" in r for r in R), "crashes": sum("crash" in r for r in R),
        "invalid": sum(not r["valid"] for r in ok), "text_overflow_cases": sum(r["overflow"] > 0 for r in ok),
        "small_text_cases": sum(r["small"] > 0 for r in ok), "collision_cases": sum(r["coll"] > 0 for r in ok),
        "reflow_errors": sum(bool(r["reflow_error"]) for r in ok),
        "nondeterministic": sum(r.get("deterministic") is False for r in ok),
        "engine": dict(Counter(r["engine"] for r in ok)),
        "seconds": {"mean": round(sum(secs) / len(secs), 3), "p99": round(secs[int(0.99 * (len(secs) - 1))], 3),
                    "max": round(secs[-1], 3)},
        "viewer_issues": dict(Counter(x for r in ok for x in r["issues"])),
        "by_family": {k: dict(v) for k, v in by.items()},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", choices=["mutations", "hidden"], default="hidden")
    p.add_argument("--designs", type=int, default=None, help="hidden designs (default 240) or synthetic seeds (default 200)")
    p.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--output", type=Path, default=ROOT / "output" / "stress")
    args = p.parse_args()
    n = args.designs or (240 if args.suite == "hidden" else 200)
    jobs = _cases(args.suite, n)
    print(f"{args.suite}: {len(jobs)} cases on {args.procs} processes", flush=True)
    with Pool(args.procs) as pool:
        R = []
        for i, r in enumerate(pool.imap_unordered(run_case, jobs, chunksize=4), 1):
            R.append(r)
            if i % 500 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    summary = summarize(R)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "stress.json").write_text(json.dumps({"summary": summary, "cases": R}, indent=1))
    print(json.dumps(summary, indent=2))
    for r in [r for r in R if "crash" in r][:5]:
        print("CRASH", r.get("name"), r["target"], r["crash"])
    for r in [r for r in R if r.get("valid") is False][:10]:
        print("INVALID", r["name"], r["target"], r["engine"], r["hard"])
    return 0 if summary["crashes"] == 0 and summary["invalid"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
