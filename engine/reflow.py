"""
Structure-aware reflow: the layout half of the combined engine.

  1. analyze()     - infer structure (background, decor, groups, rows, corner
                     floaters, logo/hero/CTA/headline, priorities) from
                     geometry and styling, nudged by the local model's roles.
  2. candidates()  - several genuinely different re-layouts (preserve / stack
                     / split / row), fitted with renderer-exact text metrics;
                     low-priority text is demoted (smaller), never hidden.
  3. emit          - write geometry back onto copies of the source elements.

Contract: only x / y / width / height / font_size change. Colours, opacity,
fonts, content, fit, letter spacing, z-order and groups are untouched.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Tuple

from .analyze import analyze, el_rect, inter
from .layout import Ctx, candidates


def reflow(source: dict, target: dict, roles: Optional[Dict[str, str]] = None) -> Tuple[dict, dict]:
    W, H = int(target["width"]), int(target["height"])
    an = analyze(source, roles)
    ctx = Ctx(an, float(W), float(H))
    cands = candidates(ctx)
    if not cands:
        raise RuntimeError("no reflow candidate fits")
    best = max(cands, key=lambda l: l.score)

    geo: Dict[str, dict] = {}
    for p in best.placed:
        for i, g in p.sized.geo.items():
            geo[i] = {**g, "x": g["x"] + p.x, "y": g["y"] + p.y}

    content = [(r, 3.0 if p.sized.block.texts() else 1.0) for p in best.placed for r in p.rects()]
    bg_ids = {e["id"] for e in an.background}
    decor_ids = {e["id"] for e in an.decor}
    missing_ids = {e["id"] for e in an.missing}

    out_els = []
    for el in source["elements"]:
        e = copy.deepcopy(el)
        eid = e.get("id")
        if eid in geo:
            e.update(geo[eid])
        elif eid in bg_ids:
            _place_background(e, W, H)
        elif eid not in missing_ids:
            _place_decor(e, ctx, content)
        out_els.append(e)
    out = {"canvas": {"width": W, "height": H}, "elements": out_els}
    for e in out_els:
        if e.get("id") in missing_ids:
            _place_missing(e, out_els, ctx, content)
    _finalize(out, W, H)

    info = {"layout": best.name, "score": round(best.score, 4), "detail": best.detail,
            "demoted": [b.bid for b in best.dropped], "missing_assets": sorted(missing_ids),
            "candidates": len(cands)}
    return out, info


# --------------------------------------------------------------------------

def _place_background(e: dict, W: int, H: int) -> None:
    w0, h0 = float(e.get("width", 1)), float(e.get("height", 1))
    if e.get("type") == "image" and e.get("fit") != "cover" and w0 > 0 and h0 > 0:
        # can't stretch a non-cover image: scale it in proportion, centred
        s = min(W / w0, H / h0)
        e.update(x=(W - w0 * s) / 2, y=(H - h0 * s) / 2, width=w0 * s, height=h0 * s)
    else:
        e.update(x=0, y=0, width=W, height=H)


def _place_decor(e: dict, ctx: Ctx, content) -> None:
    """Re-anchor proportionally, keep aspect, keep inside, avoid content."""
    an = ctx.an
    w0, h0 = float(e.get("width", 0)), float(e.get("height", 0))
    cx = (float(e.get("x", 0)) + w0 / 2) / an.W0 * ctx.W
    cy = (float(e.get("y", 0)) + h0 / 2) / an.H0 * ctx.H
    s = ctx.s_fit
    if e.get("type") == "shape" and e.get("shape_type") in ("rectangle", "line") and not e.get("rotation"):
        # bars / lines may stretch along the axis that grew
        w = w0 * ctx.sx if w0 >= 0.6 * an.W0 else w0 * s
        h = h0 * ctx.sy if h0 >= 0.6 * an.H0 else h0 * s
    else:
        w, h = w0 * s, h0 * s
    w, h = _fit_box(e, w, h, ctx.W, ctx.H)
    x, y = min(max(cx - w / 2, 0.0), ctx.W - w), min(max(cy - h / 2, 0.0), ctx.H - h)
    if content:
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
                options.append((cost(px, py, pw, ph) + 0.15 * move + 0.25 * (1 - k) + (0 if i == 0 else 0.03),
                                px, py, pw, ph))
        _, x, y, w, h = min(options)
    e.update(x=x, y=y, width=w, height=h)


def _fit_box(e: dict, w: float, h: float, W: float, H: float) -> Tuple[float, float]:
    k = min(1.0, W / w if w > 0 else 1.0, H / h if h > 0 else 1.0)
    return w * k, h * k


def _place_missing(e: dict, out_els: List[dict], ctx: Ctx, content) -> None:
    """An image whose asset file is missing renders as a grey placeholder.
    We can't drop or hide it (ids and properties must be preserved), so keep
    it in proportion but small, and tuck it behind an opaque element that
    paints over it when one is big enough; otherwise into the quietest corner."""
    w0, h0 = float(e.get("width", 0)), float(e.get("height", 0))
    if w0 <= 0 or h0 <= 0:
        e.update(x=0.0, y=0.0, width=0.0, height=0.0)
        return
    z = e.get("z_index", 0)
    covers = []
    for o in out_els:
        if o is e or o.get("z_index", 0) <= z or o.get("rotation"):
            continue
        if o.get("type") == "shape" and float(o.get("opacity", 1)) >= 0.99 and "rgba" in str(o.get("fill_color")) \
                and str(o.get("fill_color")).replace(" ", "").endswith(",1)"):
            covers.append(o)
    best = None
    for o in covers:
        ow, oh = float(o["width"]), float(o["height"])
        inset = 0.2 * min(ow, oh)  # stay clear of rounded corners
        k = min((ow - 2 * inset) / w0, (oh - 2 * inset) / h0)
        if k <= 0:
            continue
        if best is None or k > best[0]:
            best = (k, o)
    if best is not None:
        k, o = best
        w, h = w0 * k, h0 * k
        e.update(x=float(o["x"]) + (float(o["width"]) - w) / 2, y=float(o["y"]) + (float(o["height"]) - h) / 2,
                 width=w, height=h)
        return
    k = max(4.0, 0.05 * min(ctx.W, ctx.H)) / h0
    e.update(width=w0 * k, height=h0 * k, x=float(e.get("x", 0)), y=float(e.get("y", 0)))
    _place_decor_fixed(e, ctx, content)


def _place_decor_fixed(e: dict, ctx: Ctx, content) -> None:
    w, h = float(e["width"]), float(e["height"])
    best = None
    for fx in (0.0, 1.0, 0.5):
        for fy in (1.0, 0.0, 0.5):
            px, py = (ctx.W - w) * fx, (ctx.H - h) * fy
            r = (px, py, px + w, py + h)
            c = sum(inter(r, cr) for cr, _ in content)
            if best is None or c < best[0]:
                best = (c, px, py)
    e["x"], e["y"] = best[1], best[2]


def _finalize(out: dict, W: int, H: int) -> None:
    """Every element fully inside the canvas (rotated footprint included),
    images keep aspect, text boxes cover their measured text."""
    from .typography import measure  # the audit's own measurement

    for e in out["elements"]:
        w, h = max(0.0, float(e.get("width", 0))), max(0.0, float(e.get("height", 0)))
        r = el_rect({**e, "width": w, "height": h})
        rw, rh = r[2] - r[0], r[3] - r[1]
        k = min(1.0, W / rw if rw > 0 else 1.0, H / rh if rh > 0 else 1.0)
        if k < 1.0:
            cx, cy = float(e.get("x", 0)) + w / 2, float(e.get("y", 0)) + h / 2
            if e.get("type") == "text":
                w, h = min(w, W), min(h, H)
            else:
                w, h = w * k, h * k
            e["x"], e["y"] = cx - w / 2, cy - h / 2
        e["width"], e["height"] = w, h
        if e.get("type") == "text":
            e["font_size"] = max(1, int(round(float(e.get("font_size", 1)))))
            _reconcile_text(e, W, H, measure)
        _clamp(e, W, H)


def _reconcile_text(e: dict, W: int, H: int, measure) -> None:
    """Grow the box (or, failing that, shrink the font) until the audit's
    measurement of the text fits inside it."""
    rigid = bool(e.get("group_id"))  # grouped labels keep their box; only the font gives
    for _ in range(60):
        m = measure(e)
        over_w = m["width"] > e["width"] + 0.05
        over_h = m["height"] > e["height"] + 0.05
        if not over_w and not over_h:
            return
        if rigid:
            if e["font_size"] <= 1:
                return
            e["font_size"] = max(1, e["font_size"] - 1)
            continue
        if over_w and m["width"] + 0.5 <= W:
            grow = m["width"] + 0.5 - e["width"]
            align = e.get("text_align", "left")
            e["x"] -= grow / 2 if align == "center" else (grow if align == "right" else 0.0)
            e["width"] += grow
            continue
        if over_h and m["height"] + 0.5 <= H and not over_w:
            e["height"] = m["height"] + 0.5
            continue
        if e["font_size"] <= 1:
            return
        e["font_size"] -= 1


def _clamp(e: dict, W: int, H: int) -> None:
    r = el_rect(e)
    dx = -r[0] if r[0] < 0 else (W - r[2] if r[2] > W else 0.0)
    dy = -r[1] if r[1] < 0 else (H - r[3] if r[3] > H else 0.0)
    e["x"] = float(e.get("x", 0)) + dx
    e["y"] = float(e.get("y", 0)) + dy
    for key in ("x", "y", "width", "height"):
        e[key] = float(e[key])
    # float error can leave an edge a hair outside; pull it back in
    r = el_rect(e)
    if r[0] < 0:
        e["x"] -= r[0] - 1e-6
    if r[1] < 0:
        e["y"] -= r[1] - 1e-6
    r = el_rect(e)
    if r[2] > W:
        e["x"] -= r[2] - W + 1e-6
    if r[3] > H:
        e["y"] -= r[3] - H + 1e-6
