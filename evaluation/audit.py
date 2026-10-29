"""Independent output-contract checks, plus explicitly non-official quality proxies."""
from collections import Counter
import json
import math
from pathlib import Path
from functools import lru_cache
from jsonschema import Draft202012Validator
from engine.typography import measure


@lru_cache(maxsize=1)
def validator():
    path = Path(__file__).resolve().parents[1] / "chameleon_design_schema_v0.9.json"
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def box(e):
    angle = math.radians(e.get("rotation", 0))
    c, s = abs(math.cos(angle)), abs(math.sin(angle))
    w, h = e["width"]*c + e["height"]*s, e["width"]*s + e["height"]*c
    x, y = e["x"]+e["width"]/2, e["y"]+e["height"]/2
    return x-w/2, y-h/2, x+w/2, y+h/2


def overlap(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def audit(source, output, target):
    hard, quality = [], []
    for err in validator().iter_errors(output):
        hard.append("schema: " + err.message)
    if hard:
        return {"hard_errors": hard, "quality_warnings": quality, "valid": False}
    if output["canvas"] != target:
        hard.append("Wrong target canvas")
    if Counter(e["id"] for e in source["elements"]) != Counter(e["id"] for e in output["elements"]):
        hard.append("Element IDs/count changed")
    original = {e["id"]: e for e in source["elements"]}
    w, h = target["width"], target["height"]
    foreground, fonts = [], []
    allowed = {"x", "y", "width", "height", "font_size"}
    for e in output["elements"]:
        old = original.get(e["id"])
        if old is None:
            continue
        if {k:v for k,v in old.items() if k not in allowed} != {k:v for k,v in e.items() if k not in allowed}:
            hard.append(e["id"] + ": immutable properties changed")
        if not all(math.isfinite(e[k]) for k in ("x", "y", "width", "height")):
            hard.append(e["id"] + ": non-finite geometry")
            continue
        b = box(e)
        if b[0] < -.01 or b[1] < -.01 or b[2] > w+.01 or b[3] > h+.01:
            hard.append(e["id"] + ": rotated bounds outside canvas")
        if e["type"] == "image" and old.get("fit") != "cover" and old["height"] and e["height"]:
            before, after = old["width"]/old["height"], e["width"]/e["height"]
            if before and abs(after/before-1) > .05:
                hard.append(e["id"] + ": distorted image")
        if e["type"] == "text":
            fonts.append(e["font_size"])
            m = measure(e)
            if m["height"] > e["height"]+.1 or m["width"] > e["width"]+.1 or (e.get("max_lines") and m["lines"] > e["max_lines"]):
                quality.append(e["id"] + ": text overflow")
            if e["font_size"] < 10:
                quality.append(e["id"] + ": font below 10px")
        is_bg = old["type"] != "text" and old["width"] >= source["canvas"]["width"]*.9 and old["height"] >= source["canvas"]["height"]*.9
        is_deco = old["type"] == "shape" and not old.get("group_id") and (old.get("opacity", 1) <= .3 or old.get("shape_type") == "line")
        if not is_bg and not is_deco:
            foreground.append(e)
    for i, a in enumerate(foreground):
        for b in foreground[i+1:]:
            if a.get("group_id") and a.get("group_id") == b.get("group_id"):
                continue
            if {a["type"], b["type"]} == {"shape", "text"}:
                # A contained text label may intentionally sit on an ungrouped shape.
                text, shape = (a,b) if a["type"] == "text" else (b,a)
                if overlap(box(original[text["id"]]),box(original[shape["id"]])) >= original[text["id"]]["width"]*original[text["id"]]["height"]*.95:
                    continue
            if {a["type"], b["type"]} <= {"image", "shape"}:
                # Layering the source already had (a collage, a product on a card) is
                # intentional, as long as the overlap hasn't grown much.
                def frac(p, q):
                    bp, bq = box(p), box(q)
                    small = min((bp[2]-bp[0])*(bp[3]-bp[1]), (bq[2]-bq[0])*(bq[3]-bq[1]))
                    return overlap(bp, bq) / small if small > 0 else 0.0
                before = frac(original[a["id"]], original[b["id"]])
                if before > 0.02 and frac(a, b) <= before + 0.1:
                    continue
            if overlap(box(a), box(b)) > 1:
                quality.append(a["id"] + "/" + b["id"] + ": possible collision")
    return {"hard_errors": hard, "quality_warnings": quality, "valid": not hard,
            "min_font": min(fonts, default=None), "text_overflows": sum("overflow" in q for q in quality),
            "small_texts": sum("below 10px" in q for q in quality),
            "collisions": sum("collision" in q for q in quality)}
