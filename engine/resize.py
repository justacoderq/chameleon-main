"""
CHAMELEON resize engine.

Pipeline:
  1. analyze()      - infer structure (background, decor, groups, rows,
                      corner floaters, logo/hero/CTA/headline, priorities)
                      from geometry and styling alone.
  2. candidates()   - build several genuinely different re-layouts
                      (preserve / stack / split / row), each fitted with
                      real text measurement, dropping the least important
                      block only if something can't fit legibly.
  3. score + pick   - readability, size, overlaps, drops, use of space.
  4. emit           - write geometry back onto copies of the source
                      elements; background goes full-bleed, decor is
                      re-anchored, everything is clamped inside the canvas.

If anything in that pipeline throws, we fall back to a safe proportional
re-anchor so the engine always returns a valid design.
"""

from __future__ import annotations

import copy
import math
import os
import sys
from typing import Any, Dict, List

from .analyze import analyze, el_rect, inter
from .layout import Ctx, candidates, size_block

DEBUG = bool(os.environ.get("CHAMELEON_DEBUG"))


def resize(source: dict[str, Any], target_canvas: dict[str, Any]) -> dict[str, Any]:
    W, H = int(target_canvas["width"]), int(target_canvas["height"])
    try:
        out = _resize(source, W, H)
    except Exception as exc:  # never crash on an adversarial input
        if DEBUG:
            import traceback
            traceback.print_exc()
        print(f"    [engine] layout failed ({exc!r}); using safe fallback", file=sys.stderr)
        out = _fallback(source, W, H)
    _finalize(out, source, W, H)
    return out


# --------------------------------------------------------------------------

def _resize(source: dict, W: int, H: int) -> dict:
    an = analyze(source)
    ctx = Ctx(an, float(W), float(H))
    cands = candidates(ctx)
    if not cands:
        return _fallback(source, W, H)
    best = max(cands, key=lambda l: l.score)
    if DEBUG:
        for l in sorted(cands, key=lambda l: -l.score)[:8]:
            print(f"      {l.score:+.3f} {l.name:32s} {l.detail} drop={[b.bid for b in l.dropped]}", file=sys.stderr)

    geo: Dict[str, dict] = {}
    for p in best.placed:
        for i, g in p.sized.geo.items():
            geo[i] = {**g, "x": g["x"] + p.x, "y": g["y"] + p.y}

    hidden: List[dict] = list(an.missing)
    for b in best.dropped:
        hidden.extend(b.els if b.kind != "row" else [e for c in b.children for e in c.els])

    content = [(r, 3.0 if p.sized.block.texts() else 1.0) for p in best.placed for r in p.rects()]
    ctx.content_rects = content

    out_els = []
    for el in source["elements"]:
        e = copy.deepcopy(el)
        eid = e.get("id")
        if eid in geo:
            e.update({k: v for k, v in geo[eid].items()})
        elif any(eid == b.get("id") for b in an.background):
            e.update({"x": 0, "y": 0, "width": W, "height": H})
            if e.get("type") == "image":
                e["fit"] = "cover"
        elif any(eid == d.get("id") for d in an.decor):
            _place_decor(e, ctx)
        elif any(eid == h.get("id") for h in hidden):
            _place_hidden(e, ctx)
        else:
            _place_decor(e, ctx)
        out_els.append(e)
    return {"canvas": {"width": W, "height": H}, "elements": out_els}


def _place_decor(e: dict, ctx: Ctx) -> None:
    """Re-anchor proportionally to the canvas, keep aspect, keep inside."""
    an = ctx.an
    w0, h0 = float(e.get("width", 0)), float(e.get("height", 0))
    cx = (float(e.get("x", 0)) + w0 / 2) / an.W0 * ctx.W
    cy = (float(e.get("y", 0)) + h0 / 2) / an.H0 * ctx.H
    s = ctx.s_fit
    if e.get("type") == "shape" and e.get("shape_type") in ("rectangle", "line") and not e.get("rotation"):
        # bars / lines may stretch along the axis that grew
        w, h = w0 * ctx.sx if w0 >= 0.6 * an.W0 else w0 * s, h0 * ctx.sy if h0 >= 0.6 * an.H0 else h0 * s
    else:
        w, h = w0 * s, h0 * s
    w, h = min(w, ctx.W), min(h, ctx.H)
    x, y = min(max(cx - w / 2, 0.0), ctx.W - w), min(max(cy - h / 2, 0.0), ctx.H - h)
    content = getattr(ctx, "content_rects", None)
    if content and e.get("opacity", 1) != 0:
        # decor is intentional layering, but it shouldn't sit on the content:
        # try the proportional spot, then corners/edges, then smaller.
        def cost(px, py, pw, ph):
            r = (px, py, px + pw, py + ph)
            return sum(wt * inter(r, c) for c, wt in content) / max(1.0, pw * ph)
        options = []
        for k in (1.0, 0.7, 0.5):
            pw, ph = w * k, h * k
            spots = [(min(max(cx - pw / 2, 0.0), ctx.W - pw), min(max(cy - ph / 2, 0.0), ctx.H - ph))]
            for fx in (0.0, 0.5, 1.0):
                for fy in (0.0, 0.5, 1.0):
                    spots.append(((ctx.W - pw) * fx, (ctx.H - ph) * fy))
            for i, (px, py) in enumerate(spots):
                move = math.hypot(px - x, py - y) / math.hypot(ctx.W, ctx.H)
                options.append((cost(px, py, pw, ph) + 0.15 * move + 0.25 * (1 - k) + (0 if i == 0 else 0.03), px, py, pw, ph))
        _, x, y, w, h = min(options)
    e["width"], e["height"] = w, h
    e["x"], e["y"] = x, y
    if "corner_radius" in e:
        e["corner_radius"] = float(e["corner_radius"]) * min(s, w / max(w0, 1e-6))


def _place_hidden(e: dict, ctx: Ctx) -> None:
    """Element we can't show (missing asset / dropped for space): keep it in
    the JSON (same id set), proportional and inside the canvas, but invisible."""
    _place_decor(e, ctx)
    e["opacity"] = 0.0
    if e.get("type") == "text":
        e["font_size"] = max(1, int(round(float(e.get("font_size", 12)) * ctx.s_fit)))
        # The renderer ignores `opacity` on text (paint colour overrides it),
        # so also zero the colour alpha to make the hide actually render.
        e["color"] = _transparent(e.get("color"))
        for run in e.get("style_runs") or []:
            if "color" in run:
                run["color"] = _transparent(run["color"])


def _transparent(color) -> str:
    try:
        inner = str(color)[str(color).index("(") + 1:str(color).rindex(")")].split(",")
        r, g, b = (int(float(v)) for v in inner[:3])
        return f"rgba({r},{g},{b},0)"
    except Exception:
        return "rgba(0,0,0,0)"


def _fallback(source: dict, W: int, H: int) -> dict:
    W0, H0 = float(source["canvas"]["width"]), float(source["canvas"]["height"])
    s = min(W / W0, H / H0)
    out = []
    for el in source["elements"]:
        e = copy.deepcopy(el)
        w0, h0 = float(e.get("width", 0)), float(e.get("height", 0))
        if e.get("type") != "text" and w0 * h0 >= 0.85 * W0 * H0:
            e.update({"x": 0, "y": 0, "width": W, "height": H})
            if e.get("type") == "image":
                e["fit"] = "cover"
        else:
            cx = (float(e.get("x", 0)) + w0 / 2) / W0 * W
            cy = (float(e.get("y", 0)) + h0 / 2) / H0 * H
            e["width"], e["height"] = w0 * s, h0 * s
            e["x"], e["y"] = cx - w0 * s / 2, cy - h0 * s / 2
            if e.get("type") == "text":
                e["font_size"] = max(1, int(round(float(e.get("font_size", 16)) * s)))
        out.append(e)
    return {"canvas": {"width": W, "height": H}, "elements": out}


def _finalize(out: dict, source: dict, W: int, H: int) -> None:
    """Guarantee hard constraints: every element fully inside the canvas
    (rotated footprint included), images keep aspect, sane numbers."""
    src = {e.get("id"): e for e in source["elements"]}
    for e in out["elements"]:
        s_el = src.get(e.get("id"), e)
        w, h = max(0.0, float(e.get("width", 0))), max(0.0, float(e.get("height", 0)))
        keep_aspect = e.get("type") == "image" and not (w >= W - 1 and h >= H - 1)
        # shrink if larger than canvas
        r = el_rect({**e, "width": w, "height": h})
        rw, rh = r[2] - r[0], r[3] - r[1]
        k = min(1.0, W / rw if rw > 0 else 1.0, H / rh if rh > 0 else 1.0)
        if k < 1.0:
            cx, cy = float(e.get("x", 0)) + w / 2, float(e.get("y", 0)) + h / 2
            if keep_aspect or e.get("type") != "text":
                w, h = w * k, h * k
            else:
                w, h = min(w, W), min(h, H)
            e["x"], e["y"] = cx - w / 2, cy - h / 2
        e["width"], e["height"] = w, h
        # shift inside
        r = el_rect(e)
        dx = -r[0] if r[0] < 0 else (W - r[2] if r[2] > W else 0.0)
        dy = -r[1] if r[1] < 0 else (H - r[3] if r[3] > H else 0.0)
        e["x"] = float(e.get("x", 0)) + dx
        e["y"] = float(e.get("y", 0)) + dy
        for key in ("x", "y", "width", "height"):
            e[key] = round(float(e[key]), 2)
        # rounding can nudge an edge past the canvas by a hair
        e["x"] = min(max(e["x"], 0.0), max(0.0, W - e["width"])) if not e.get("rotation") else e["x"]
        e["y"] = min(max(e["y"], 0.0), max(0.0, H - e["height"])) if not e.get("rotation") else e["y"]
        if e.get("type") == "text":
            e["font_size"] = max(1, int(round(float(e.get("font_size", 1)))))
            if "letter_spacing" in e:
                e["letter_spacing"] = round(float(e["letter_spacing"]), 3)
            if not s_el.get("letter_spacing") and not e.get("letter_spacing"):
                e.pop("letter_spacing", None) if "letter_spacing" not in s_el else None
        if "opacity" in e:
            e["opacity"] = min(1.0, max(0.0, float(e["opacity"])))
