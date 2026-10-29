"""
Candidate layouts + scoring.

For a target canvas we build several genuinely different arrangements of the
same blocks, then score each one and keep the best:

  preserve  - keep the original arrangement: uniform scale, positions
              re-anchored proportionally (great for nearby aspect ratios)
  stack     - single column, reading order top-to-bottom (tall / square)
  split     - hero image in one column, everything else stacked beside it
              (landscape)
  row       - banner strip: [logo] [hero] [text stack] [CTA] (very wide)

Every arrangement is fitted with real text measurement (same fonts + wrap
as the renderer), so text sizes are chosen to genuinely fit, never to spill.
If something cannot fit legibly even at the minimum readable size, the
lowest-priority block is demoted (its text may go smaller than the readable
minimum) and the arrangement is retried. Nothing is ever hidden or removed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .analyze import Analysis, Block, Rect, area, el_rect, inter, source_lines, union
from .measure import asset_visible_fraction, get_measurer

INF = float("inf")


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------

@dataclass
class Ctx:
    an: Analysis
    W: float
    H: float

    def __post_init__(self) -> None:
        an = self.an
        self.sx = self.W / an.W0
        self.sy = self.H / an.H0
        self.s_fit = min(self.sx, self.sy)
        self.s_ideal = math.sqrt(self.sx * self.sy)
        self.s_cap = max(self.s_fit, self.s_ideal * 1.3)
        short = min(self.W, self.H)
        self.minf = float(min(16, max(10, round(0.011 * max(self.W, self.H)))))
        # demoted (low-priority) text may go this small rather than vanish
        self.minf_floor = max(5.0, 0.6 * self.minf)
        self.demoted: set = set()
        # lay images out by visible pixels (True) or by their full box (False)
        self.visible_fp = True
        self.mx = max(6.0, min(80.0, 0.05 * short, 0.04 * self.W)) if self.W / self.H < 3 else max(6.0, min(60.0, 0.12 * self.H, 0.02 * self.W))
        self.my = max(5.0, min(80.0, 0.05 * short)) if self.W / self.H < 3 else max(5.0, 0.09 * self.H)
        if self.H / self.W >= 3:
            self.mx = max(6.0, 0.06 * self.W)
        self.gmin = max(3.0, 0.014 * short)
        self.measurer = get_measurer()
        self.sized_cache: Dict[tuple, "Sized"] = {}

    def minf_for(self, el: dict) -> float:
        floor = self.minf_floor if el.get("id") in self.demoted else self.minf
        return min(floor, float(el.get("font_size", 16)))


# --------------------------------------------------------------------------
# Sizing a block at a scale
# --------------------------------------------------------------------------

@dataclass
class Sized:
    block: Block
    w: float
    h: float
    geo: Dict[str, dict]           # id -> {x,y,width,height,(font_size,letter_spacing)} relative
    vis: List[Rect]                # visual footprint rects, relative
    eff: float                     # effective scale vs the source
    ok: bool = True                # legible & nothing overflowing
    fonts: List[Tuple[float, float]] = field(default_factory=list)  # (font, src font)

    def pads(self) -> Tuple[float, float, float, float]:
        """How far the real element boxes stick out past the footprint
        (left, top, right, bottom) - e.g. transparent image padding."""
        if not self.geo:
            return (0.0, 0.0, 0.0, 0.0)
        x0 = min(g["x"] for g in self.geo.values())
        y0 = min(g["y"] for g in self.geo.values())
        x1 = max(g["x"] + g["width"] for g in self.geo.values())
        y1 = max(g["y"] + g["height"] for g in self.geo.values())
        return (max(0.0, -x0), max(0.0, -y0), max(0.0, x1 - self.w), max(0.0, y1 - self.h))


def _normalize(geo: Dict[str, dict], els: Dict[str, dict], vis: List[Rect]) -> Tuple[float, float, List[Rect]]:
    rects = []
    for i, g in geo.items():
        rects.append(el_rect({**g, "rotation": els[i].get("rotation", 0)}))
    r = union(rects)
    for g in geo.values():
        g["x"] -= r[0]
        g["y"] -= r[1]
    vis = [(a - r[0], b - r[1], c - r[0], d - r[1]) for a, b, c, d in vis]
    return r[2] - r[0], r[3] - r[1], vis


def _image_vis(el: dict, x: float, y: float, w: float, h: float) -> Rect:
    fit = el.get("fit", "contain")
    if fit != "contain":
        return (x, y, x + w, y + h)
    from .measure import asset_size
    size = asset_size(el.get("asset_id"))
    if not size:
        return (x, y, x + w, y + h)
    iw, ih = size
    sc = min(w / iw, h / ih)
    cw, ch = iw * sc, ih * sc
    ox, oy = x + (w - cw) / 2, y + (h - ch) / 2
    fx0, fy0, fx1, fy1 = asset_visible_fraction(el.get("asset_id"))
    return (ox + fx0 * cw, oy + fy0 * ch, ox + fx1 * cw, oy + fy1 * ch)


def size_text(b: Block, s: float, max_w: float, ctx: Ctx, widen: Optional[float]) -> Sized:
    el = b.els[0]
    f0 = float(el.get("font_size", 16))
    w0 = float(el.get("width", 100))
    minf = ctx.minf_for(el)
    target = int(max(math.ceil(minf - 1e-9), round(f0 * s)))
    target = max(1, target)
    wl = max_w if widen is None else min(max_w, max(w0 * s * widen, target * 8, 0.6 * max_w))
    wl = max(1.0, wl)
    ml = el.get("max_lines")
    M = ctx.measurer
    lay = M.fit(el, wl, INF, target, 1, int(ml) if ml else None)
    if lay is None:
        lay = M.layout(el, 1, wl)
    f = lay.font_size
    tight = min(wl, lay.max_line_width + 2)
    if tight < wl:
        chk = M.layout(el, f, tight)
        if chk.lines != lay.lines or chk.overflow:
            tight = wl
    ok = (f >= minf - 1e-6) and not lay.overflow
    geo = {el["id"]: {"x": 0.0, "y": 0.0, "width": tight, "height": lay.height, "font_size": f}}
    return Sized(b, tight, lay.height, geo, [(0, 0, tight, lay.height)], f / f0, ok, [(f, f0)])


def size_image(b: Block, s: float, max_w: float, max_h: float, k: float = 1.0,
               ctx: Optional[Ctx] = None) -> Sized:
    """Images are laid out by their *visible* footprint (transparent padding
    inside a `contain` box is ignored), while the element box itself keeps the
    source aspect ratio and is limited to the canvas size."""
    el = b.els[0]
    w0, h0 = float(el.get("width", 1)), float(el.get("height", 1))
    v = _image_vis(el, 0, 0, w0, h0)
    fw, fh = max(1e-6, (v[2] - v[0]) / w0), max(1e-6, (v[3] - v[1]) / h0)
    sc = s * k
    if b.is_logo and ctx is not None:
        # a logo must stay recognisable: visible height ≥ ~3.5× min font
        sc = max(sc, 3.5 * ctx.minf / (h0 * fh))
    elif ctx is not None:
        # never let an image shrink into an invisible speck to make text fit
        sc = max(sc, 2.5 * ctx.minf / max(h0 * fh, w0 * fw))
    if ctx is not None and not ctx.visible_fp:
        fw, fh = 1.0, 1.0
    sc = min(sc, max_w / (w0 * fw), max_h / (h0 * fh))
    if ctx is not None:
        sc = min(sc, ctx.W / w0, ctx.H / h0)
    w, h = w0 * sc, h0 * sc
    if abs(float(el.get("rotation") or 0)) > 0.5:
        geo = {el["id"]: {"x": 0.0, "y": 0.0, "width": w, "height": h}}
        ww, hh, vis = _normalize(geo, {el["id"]: el}, [(0, 0, w, h)])
        return Sized(b, ww, hh, geo, vis, sc)
    vx0, vy0 = v[0] * sc, v[1] * sc
    vw, vh = (v[2] - v[0]) * sc, (v[3] - v[1]) * sc
    if ctx is not None and not ctx.visible_fp:
        geo = {el["id"]: {"x": 0.0, "y": 0.0, "width": w, "height": h}}
        return Sized(b, w, h, geo, [(vx0, vy0, vx0 + vw, vy0 + vh)], sc)
    geo = {el["id"]: {"x": -vx0, "y": -vy0, "width": w, "height": h}}
    return Sized(b, vw, vh, geo, [(0, 0, vw, vh)], sc)


def size_group(b: Block, s: float, max_w: float, max_h: float, ctx: Ctx) -> Sized:
    g = s
    for t in b.texts():
        f0 = float(t.get("font_size", 16))
        g = max(g, ctx.minf_for(t) / f0)
    if b.w > 0:
        g = min(g, max_w / b.w)
    if b.h > 0:
        g = min(g, max_h / b.h)
    g = max(g, 1e-3)
    M = ctx.measurer
    geo: Dict[str, dict] = {}
    els = {}
    ok = True
    fonts = []
    vis = []
    for e in b.els:
        els[e["id"]] = e
        x = (float(e.get("x", 0)) - b.rect[0]) * g
        y = (float(e.get("y", 0)) - b.rect[1]) * g
        w = float(e.get("width", 0)) * g
        h = float(e.get("height", 0)) * g
        d = {"x": x, "y": y, "width": w, "height": h}
        if e.get("type") == "text":
            # Rigid group: the label keeps its scaled box exactly; only the
            # font is chosen, as large as fits (and at least legible if it can).
            f0 = float(e.get("font_size", 16))
            minf = ctx.minf_for(e)
            upper = max(1, int(round(f0 * g)), int(math.ceil(minf - 1e-9)))
            src = source_lines(e)
            lay = (M.fit(e, w, h, upper, 1, src) or M.fit(e, w, h, upper, 1)
                   or M.fit(e, w, INF, upper, 1, src) or M.layout(e, 1, w))
            d["font_size"] = lay.font_size
            ok = ok and lay.font_size >= minf - 1e-6 and not lay.overflow
            fonts.append((lay.font_size, f0))
        geo[e["id"]] = d
        vis.append(el_rect({**d, "rotation": e.get("rotation", 0)}))
    ww, hh, vis = _normalize(geo, els, vis)
    return Sized(b, ww, hh, geo, vis, g, ok, fonts)


def size_shape(b: Block, s: float, max_w: float, max_h: float) -> Sized:
    el = b.els[0]
    w0, h0 = float(el.get("width", 1)), float(el.get("height", 1))
    sc = min(s, max_w / max(w0, 1e-6), max_h / max(h0, 1e-6))
    geo = {el["id"]: {"x": 0.0, "y": 0.0, "width": w0 * sc, "height": h0 * sc}}
    ww, hh, vis = _normalize(geo, {el["id"]: el}, [])
    return Sized(b, ww, hh, geo, [(0, 0, ww, hh)], sc)


def size_row(b: Block, s: float, max_w: float, max_h: float, ctx: Ctx, widen) -> Sized:
    kids = [size_block(c, s, max_w, max_h, ctx, widen) for c in b.children]
    src_gaps = [b.children[i + 1].rect[0] - b.children[i].rect[2] for i in range(len(b.children) - 1)]
    sg = sorted(src_gaps)[len(src_gaps) // 2] if src_gaps else 20
    gap = max(ctx.gmin, max(0.0, sg) * min(kid.eff for kid in kids))
    lines: List[List[Sized]] = [[]]
    lw = 0.0
    for k in kids:
        need = k.w if not lines[-1] else lw + gap + k.w
        if lines[-1] and need > max_w:
            lines.append([k])
            lw = k.w
        else:
            lines[-1].append(k)
            lw = need
    widths = [sum(k.w for k in ln) + gap * (len(ln) - 1) for ln in lines]
    W = max(widths)
    geo, vis, fonts = {}, [], []
    y = 0.0
    ok = True
    for ln, lw in zip(lines, widths):
        x = (W - lw) / 2
        lh = max(k.h for k in ln)
        for k in ln:
            oy = y + (lh - k.h) / 2
            for i, g in k.geo.items():
                geo[i] = {**g, "x": g["x"] + x, "y": g["y"] + oy}
            vis.extend((a + x, bb + oy, c + x, d + oy) for a, bb, c, d in k.vis)
            fonts.extend(k.fonts)
            ok = ok and k.ok
            x += k.w + gap
        y += lh + gap
    return Sized(b, W, y - gap, geo, vis, min(k.eff for k in kids), ok, fonts)


def size_block(b: Block, s: float, max_w: float, max_h: float, ctx: Ctx,
               widen: Optional[float] = None, img_k: float = 1.0) -> Sized:
    # The layout search sizes the same block with the same inputs many times;
    # Sized results are never mutated, so they can be shared.
    key = (id(b), s, max_w, max_h, widen, img_k, ctx.visible_fp, ctx.minf_floor, frozenset(ctx.demoted))
    z = ctx.sized_cache.get(key)
    if z is None:
        z = ctx.sized_cache[key] = _size_block(b, s, max_w, max_h, ctx, widen, img_k)
    return z


def _size_block(b: Block, s: float, max_w: float, max_h: float, ctx: Ctx,
                widen: Optional[float], img_k: float) -> Sized:
    if b.kind == "text":
        return size_text(b, s, max_w, ctx, widen)
    if b.kind == "image":
        return size_image(b, s, max_w, max_h, img_k, ctx)
    if b.kind == "group":
        return size_group(b, s, max_w, max_h, ctx)
    if b.kind == "row":
        return size_row(b, s, max_w, max_h, ctx, widen)
    return size_shape(b, s, max_w, max_h)


# --------------------------------------------------------------------------
# Layout result
# --------------------------------------------------------------------------

@dataclass
class Placed:
    sized: Sized
    x: float
    y: float

    def rects(self) -> List[Rect]:
        return [(a + self.x, b + self.y, c + self.x, d + self.y) for a, b, c, d in self.sized.vis]

    def box(self) -> Rect:
        return (self.x, self.y, self.x + self.sized.w, self.y + self.sized.h)

    def extent(self) -> Rect:
        """Union of the real element boxes (incl. transparent image padding
        and rotation), in canvas coordinates."""
        els = {e["id"]: e for e in (self.sized.block.els if self.sized.block.kind != "row"
                                    else [e for c in self.sized.block.children for e in c.els])}
        rs = [el_rect({**g, "x": g["x"] + self.x, "y": g["y"] + self.y,
                       "rotation": els.get(i, {}).get("rotation", 0)}) for i, g in self.sized.geo.items()]
        return union(rs) if rs else self.box()


def settle(lay: "Layout", ctx: "Ctx") -> None:
    """Shift each placed block so its real element boxes stay on canvas
    (mirrors the final clamp, so scoring sees any overlap it would cause)."""
    for p in lay.placed:
        x0, y0, x1, y1 = p.extent()
        if x1 - x0 <= ctx.W:
            p.x += -x0 if x0 < 0 else (ctx.W - x1 if x1 > ctx.W else 0.0)
        if y1 - y0 <= ctx.H:
            p.y += -y0 if y0 < 0 else (ctx.H - y1 if y1 > ctx.H else 0.0)


@dataclass
class Layout:
    name: str
    placed: List[Placed]
    dropped: List[Block] = field(default_factory=list)
    score: float = -INF
    detail: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Vertical stack primitive
# --------------------------------------------------------------------------

def _stack_measure(items: List[Block], s: float, rw: float, rh: float, ctx: Ctx, widen, img_k):
    sized = [size_block(b, s, rw, rh, ctx, widen, img_k) for b in items]
    gaps = []
    for i in range(1, len(items)):
        sg = items[i].rect[1] - items[i - 1].rect[3]
        base = sg * s if sg > 0 else ctx.gmin * 2
        gaps.append(min(max(base, ctx.gmin), max(ctx.gmin, 0.12 * rh)))
    total = sum(z.h for z in sized) + sum(gaps)
    ok = all(z.ok for z in sized) and all(z.w <= rw + 0.5 for z in sized)
    return ok, total, sized, gaps


def stack_fit(items: List[Block], rw: float, rh: float, ctx: Ctx, s_hi: float,
              widen: Optional[float] = None, img_k: float = 1.0):
    """Largest scale (≤ s_hi) at which `items` stack inside rw×rh."""
    if not items:
        return 0.0, [], []
    ok, total, sized, gaps = _stack_measure(items, s_hi, rw, rh, ctx, widen, img_k)
    if ok and total <= rh:
        return s_hi, sized, gaps
    # Feasibility isn't monotonic in scale: a rigid group with long copy can be
    # legible only when large. Scan down for the largest feasible scale, then
    # refine between it and the infeasible step above.
    hi, best = s_hi, None
    for s in [s_hi * 0.8 ** i for i in range(1, 25)] + [1e-3]:
        ok, total, sized, gaps = _stack_measure(items, s, rw, rh, ctx, widen, img_k)
        if ok and total <= rh:
            best = (s, sized, gaps)
            break
        hi = s
    if best is None:
        return None
    lo = best[0]
    for _ in range(18):
        mid = (lo + hi) / 2
        ok, total, sized, gaps = _stack_measure(items, mid, rw, rh, ctx, widen, img_k)
        if ok and total <= rh:
            best = (mid, sized, gaps)
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.004 * s_hi:
            break
    return best


def stack_place(sized: List[Sized], gaps: List[float], rx: float, ry: float, rw: float, rh: float,
                spread: float = 0.6, valign: str = "center", align_override: Optional[str] = None) -> List[Placed]:
    total = sum(z.h for z in sized) + sum(gaps)
    extra = max(0.0, rh - total)
    gaps = list(gaps)
    if gaps and extra > 0:
        budget = min(extra * spread, sum(gaps) * 1.5 + len(gaps) * 6)
        weights = [g + 4 for g in gaps]
        tw = sum(weights)
        gaps = [g + budget * w / tw for g, w in zip(gaps, weights)]
        extra -= budget
    y = ry + (extra / 2 if valign == "center" else (0 if valign == "top" else extra))
    out = []
    for i, z in enumerate(sized):
        al = align_override or z.block.align
        if al == "left":
            x = rx
        elif al == "right":
            x = rx + rw - z.w
        else:
            x = rx + (rw - z.w) / 2
        out.append(Placed(z, x, y))
        y += z.h + (gaps[i] if i < len(gaps) else 0)
    return out


# --------------------------------------------------------------------------
# Floaters (corner-anchored items)
# --------------------------------------------------------------------------

def _vclamp(z: Sized, y: float, ctx: Ctx) -> float:
    pl, pt, pr, pb = z.pads()
    return min(max(y, pt), ctx.H - pb - z.h)


def place_floaters(fl: List[Block], ctx: Ctx, s: float) -> List[Placed]:
    out = []
    used: Dict[Tuple[str, str], float] = {}
    for b in fl:
        z = size_block(b, s, 0.4 * ctx.W, 0.4 * ctx.H, ctx)
        hs, vs = b.floater
        x = ctx.mx if hs == "left" else ctx.W - ctx.mx - z.w
        off = used.get((hs, vs), 0.0)
        y = ctx.my + off if vs == "top" else ctx.H - ctx.my - z.h - off
        used[(hs, vs)] = off + z.h + ctx.gmin
        out.append(Placed(z, x, y))
    return out


def _floater_scale(ctx: Ctx) -> float:
    return max(ctx.s_fit, min(ctx.s_ideal, ctx.s_fit * 1.6))


# --------------------------------------------------------------------------
# Candidate builders. Each takes (ctx, blocks) and returns a Layout or None
# if the given set of blocks can't be fitted.
# --------------------------------------------------------------------------

def build_preserve(ctx: Ctx, blocks: List[Block], k: float) -> Optional[Layout]:
    an = ctx.an
    s = ctx.s_fit * k
    placed = []
    for b in blocks:
        z = size_block(b, s, max(b.w * s * 1.02, 1), ctx.H, ctx, widen=1.0)
        if b.kind == "text":
            # keep the source wrap width so line breaks match the original
            pass
        cx = (b.rect[0] + b.rect[2]) / 2 / an.W0 * ctx.W
        cy = (b.rect[1] + b.rect[3]) / 2 / an.H0 * ctx.H
        if b.align == "left":
            x = b.rect[0] / an.W0 * ctx.W
            x = min(x, cx - z.w / 2) if z.w < b.w * s else x
        elif b.align == "right":
            x = b.rect[2] / an.W0 * ctx.W - z.w
        else:
            x = cx - z.w / 2
        y = cy - z.h / 2
        x = min(max(x, ctx.mx * 0.5), ctx.W - ctx.mx * 0.5 - z.w)
        y = min(max(y, ctx.my * 0.5), ctx.H - ctx.my * 0.5 - z.h)
        placed.append(Placed(z, x, y))
    return Layout(f"preserve{k:.2f}", placed)


def build_stack(ctx: Ctx, blocks: List[Block], inline: bool, img_k: float) -> Optional[Layout]:
    flo = [b for b in blocks if b.floater and not inline]
    items = [b for b in blocks if b not in flo]
    fs = _floater_scale(ctx)
    fp = place_floaters(flo, ctx, fs)
    top_res = max([p.y + p.sized.h for p in fp if p.sized.block.floater[1] == "top"], default=0.0)
    bot_res = max([ctx.H - p.y for p in fp if p.sized.block.floater[1] == "bottom"], default=0.0)
    rx, rw = ctx.mx, ctx.W - 2 * ctx.mx
    ry = max(ctx.my, top_res + ctx.gmin) if top_res else ctx.my
    rb = min(ctx.H - ctx.my, ctx.H - bot_res - ctx.gmin) if bot_res else ctx.H - ctx.my
    rh = rb - ry
    if rh <= 10:
        return None
    res = stack_fit(items, rw, rh, ctx, ctx.s_cap, widen=1.25, img_k=img_k)
    if res is None:
        return None
    s, sized, gaps = res
    if sized:
        ry2 = max(ry, sized[0].pads()[1])
        rb2 = min(ry + rh, ctx.H - sized[-1].pads()[3])
        if rb2 - ry2 >= sum(z.h for z in sized) + sum(gaps):
            ry, rh = ry2, rb2 - ry2
    placed = stack_place(sized, gaps, rx, ry, rw, rh)
    return Layout(f"stack{'-inline' if inline else ''}-k{img_k}", placed + fp)


def build_split(ctx: Ctx, blocks: List[Block], side: str, frac: float, inline: bool) -> Optional[Layout]:
    hero = next((b for b in blocks if b.is_hero), None)
    if hero is None:
        return None
    flo = [b for b in blocks if b.floater and not inline and b is not hero]
    items = [b for b in blocks if b is not hero and b not in flo]
    rx, ry = ctx.mx, ctx.my
    rw, rh = ctx.W - 2 * ctx.mx, ctx.H - 2 * ctx.my
    gap = max(ctx.gmin * 2, 0.04 * rw)
    hw = rw * frac
    hz = size_image(hero, ctx.s_cap * 1.5, hw, rh, ctx=ctx)
    pl, pt, pr, pb = hz.pads()
    hx = max(rx, pl) if side == "left" else min(rx + rw, ctx.W - pr) - hz.w
    tx = hx + hz.w + gap if side == "left" else rx
    tw = (rx + rw - tx) if side == "left" else (hx - gap - rx)
    if tw < 0.25 * rw:
        return None
    fs = _floater_scale(ctx)
    fp = place_floaters(flo, ctx, fs)
    res = stack_fit(items, tw, rh, ctx, ctx.s_cap, widen=None)
    if res is None:
        return None
    s, sized, gaps = res
    placed = stack_place(sized, gaps, tx, ry, tw, rh)
    content_h = max(p.y + p.sized.h for p in placed) - min(p.y for p in placed) if placed else rh
    hp = Placed(hz, hx, _vclamp(hz, ry + (rh - hz.h) / 2, ctx))
    # pull the two columns together if the text column is much narrower than allotted
    if placed:
        used_w = max(p.x + p.sized.w for p in placed) - min(p.x for p in placed)
        slack = tw - used_w
        if slack > 0:
            shift = slack / 2
            for p in placed:
                p.x += -shift if side == "left" else shift
            hp.x += shift if side == "left" else -shift
    return Layout(f"split-{side}-{frac}{'-inline' if inline else ''}", [hp] + placed + fp)


def _split_columns(items: List[Block], tw: float, rh: float, k: int, gap: float, ctx: Ctx):
    """Split reading-ordered items into k contiguous text columns, choosing the
    split that lets everything be largest; all columns share one scale."""
    from itertools import combinations
    n = len(items)
    k = min(k, n)
    avail = tw - gap * (k - 1)
    if avail / k <= 10:
        return None

    def demand(b: Block) -> float:
        d = sum(len(str(t.get("content", ""))) * float(t.get("font_size", 16)) ** 2 for t in b.texts())
        return d + (0.0 if b.kind == "text" else 0.4 * b.w * b.h)

    best = None
    for cuts in combinations(range(1, n), k - 1):
        bounds = (0,) + cuts + (n,)
        chunks = [items[bounds[i]:bounds[i + 1]] for i in range(k)]
        # columns sized by how much they hold (text needs width to stay short)
        wts = [max(1.0, sum(demand(b) for b in ch)) ** 0.7 for ch in chunks]
        widths = [avail * w / sum(wts) for w in wts]
        scales = []
        for ch, cw in zip(chunks, widths):
            res = stack_fit(ch, cw, rh, ctx, ctx.s_cap, widen=None)
            if res is None:
                break
            scales.append(res[0])
        else:
            s = min(scales)
            if best is None or s > best[0]:
                best = (s, chunks, widths)
    if best is None:
        return None
    s, chunks, widths = best
    cols = []
    for ch, cw in zip(chunks, widths):
        ok, total, sized, gaps = _stack_measure(ch, s, cw, rh, ctx, None, 1.0)
        if not ok or total > rh + 0.5:
            res = stack_fit(ch, cw, rh, ctx, s, widen=None)
            if res is None:
                return None
            _, sized, gaps = res
        cols.append((sized, gaps, max(z.w for z in sized)))
    return cols


def build_row(ctx: Ctx, blocks: List[Block], hero_side: str, logo_in_stack: bool, inline: bool,
              text_cols: int = 1) -> Optional[Layout]:
    rx, ry = ctx.mx, ctx.my
    rw, rh = ctx.W - 2 * ctx.mx, ctx.H - 2 * ctx.my
    gap = max(ctx.gmin * 2, 0.025 * ctx.W)
    flo = [b for b in blocks if b.floater and not inline and not b.is_logo]
    logos = [b for b in blocks if b.is_logo and not logo_in_stack]
    imgs = [b for b in blocks if b.kind == "image" and not b.is_logo and b not in flo]
    cta = next((b for b in blocks if b.is_cta and b not in flo), None)
    stack_items = [b for b in blocks if b not in flo and b not in logos and b not in imgs and b is not cta]

    cols_left: List[Sized] = []
    cols_right: List[Sized] = []
    for b in logos:
        z = size_image(b, INF, 0.2 * rw, 0.8 * rh, ctx=ctx)
        cols_left.append(z)
    for b in imgs:
        z = size_image(b, INF, 0.3 * rw if b.is_hero else 0.18 * rw, rh, ctx=ctx)
        (cols_left if hero_side == "left" else cols_right).append(z)
    cta_z = None
    if cta is not None:
        cta_z = size_group(cta, ctx.s_cap, 0.3 * rw, 0.62 * rh, ctx) if cta.kind == "group" else size_block(cta, ctx.s_cap, 0.3 * rw, 0.62 * rh, ctx)
        cols_right.append(cta_z)
    fixed = cols_left + cols_right
    lead = cols_left[0].pads()[0] if cols_left else 0.0
    trail = cols_right[-1].pads()[2] if cols_right else 0.0
    if lead > rx or trail > rx:
        rx2 = max(rx, lead)
        rw = ctx.W - rx2 - max(ctx.mx, trail)
        rx = rx2
    n_cols = len(fixed) + (1 if stack_items else 0)
    tw = rw - sum(z.w for z in fixed) - gap * max(0, n_cols - 1)
    if stack_items and tw < 0.22 * rw:
        return None
    text_columns = []
    if stack_items:
        if text_cols > 1 and len(stack_items) < 2:
            return None
        text_columns = _split_columns(stack_items, tw, rh, text_cols, gap, ctx)
        if text_columns is None:
            return None
    widths = [z.w for z in cols_left] + [c[2] for c in text_columns] + [z.w for z in cols_right]
    used = sum(widths) + gap * max(0, len(widths) - 1)
    extra = max(0.0, rw - used)
    g = gap + (min(extra * 0.7, gap * 2.5 * max(1, len(widths) - 1)) / max(1, len(widths) - 1) if len(widths) > 1 else 0)
    used = sum(widths) + g * max(0, len(widths) - 1)
    x = rx + (rw - used) / 2
    placed: List[Placed] = []
    for z in cols_left:
        placed.append(Placed(z, x, _vclamp(z, ry + (rh - z.h) / 2, ctx)))
        x += z.w + g
    for sized, gaps, cw in text_columns:
        placed.extend(stack_place(sized, gaps, x, ry, cw, rh, spread=0.0, align_override="center"))
        x += cw + g
    for z in cols_right:
        placed.append(Placed(z, x, _vclamp(z, ry + (rh - z.h) / 2, ctx)))
        x += z.w + g
    if placed:
        ext = union([p.extent() for p in placed])
        span = ext[2] - ext[0]
        if span <= ctx.W:
            dx = min(max((ctx.W - span) / 2 - ext[0], -ext[0]), ctx.W - ext[2])
            fx0 = min(p.x for p in placed)
            fx1 = max(p.x + p.sized.w for p in placed)
            # center the visible content, as long as no element box leaves the canvas
            dx = min(max((ctx.W - (fx1 - fx0)) / 2 - fx0, -ext[0]), ctx.W - ext[2])
            for p in placed:
                p.x += dx
    fp = place_floaters(flo, ctx, _floater_scale(ctx))
    return Layout(f"row{text_cols}-{hero_side}{'-logostack' if logo_in_stack else ''}{'-inline' if inline else ''}", placed + fp)


# --------------------------------------------------------------------------
# Drop loop + scoring
# --------------------------------------------------------------------------

def with_demotions(ctx: Ctx, blocks: List[Block], builder: Callable[[List[Block]], Optional[Layout]]) -> Optional[Layout]:
    """Build; if it can't fit legibly, demote the least important block (its
    text may go below the readable minimum) and retry. Nothing is ever hidden
    or removed: every element stays visible with its original properties."""
    order = sorted([b for b in blocks if not (b.is_logo or b.is_headline)], key=lambda b: b.priority)
    demoted: List[Block] = []
    ctx.demoted = set()
    floor = ctx.minf_floor
    try:
        for _ in range(len(order) + 1):
            lay = builder(blocks)
            if lay is not None:
                lay.dropped = list(demoted)
                return lay
            if not order:
                break
            d = order.pop(0)
            demoted.append(d)
            ctx.demoted |= {t["id"] for t in d.texts()}
        # last resort for extreme canvases: demoted copy becomes fine print
        ctx.minf_floor = 3.0
        lay = builder(blocks)
        if lay is None:
            # nothing fits even then: the headline may shrink too, rather than
            # falling back to an unorganized layout
            ctx.demoted |= {t["id"] for b in blocks for t in b.texts()}
            lay = builder(blocks)
        if lay is not None:
            lay.dropped = list(demoted)
            lay.name += "-fineprint"
        return lay
    finally:
        ctx.demoted = set()
        ctx.minf_floor = floor


def score_layout(ctx: Ctx, lay: Layout, all_blocks: List[Block]) -> float:
    total_p = sum(b.priority for b in all_blocks) or 1.0
    q = 0.0
    illegible = 0.0
    for p in lay.placed:
        b = p.sized.block
        ratio = p.sized.eff / ctx.s_ideal
        if p.sized.fonts:
            # target: proportional size, but at least comfortably readable
            # (more so for important text), never above what the cap allows
            ratio = min(f / min(f0 * ctx.s_cap, max(f0 * ctx.s_ideal, ctx.minf * (1 + 0.6 * b.priority)))
                        for f, f0 in p.sized.fonts)
        q += b.priority * min(1.0, ratio) ** 0.8
        if not p.sized.ok:
            illegible += b.priority
    q /= total_p
    drop = sum(b.priority for b in lay.dropped) / total_p

    overlap = 0.0
    rects = [(p.sized.block, p.rects()) for p in lay.placed]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            for ra in rects[i][1]:
                for rb in rects[j][1]:
                    a = inter(ra, rb)
                    if a > 0:
                        overlap += a / max(1.0, min(area(ra), area(rb)))
    oob = 0.0
    for p in lay.placed:
        x0, y0, x1, y1 = p.box()
        if x0 < -0.5 or y0 < -0.5 or x1 > ctx.W + 0.5 or y1 > ctx.H + 0.5:
            oob += 1

    # element boxes (incl. transparent image padding) that overlap: invisible
    # in the render, but a structural checker could still flag them
    box_overlap = 0.0
    ext = [p.extent() for p in lay.placed]
    for i in range(len(ext)):
        for j in range(i + 1, len(ext)):
            a = inter(ext[i], ext[j])
            if a > 0:
                box_overlap += a / max(1.0, min(area(ext[i]), area(ext[j])))

    boxes = [p.box() for p in lay.placed]
    cov = 0.0
    if boxes:
        u = union(boxes)
        cov = (u[2] - u[0]) * (u[3] - u[1]) / (ctx.W * ctx.H)

    bonus = 0.0
    if lay.name.startswith("preserve"):
        bonus += 0.04
    sc = (q - 0.7 * drop - 2.5 * overlap - 1.0 * box_overlap - 1.2 * illegible / total_p - 3.0 * oob
          + 0.12 * min(1.0, cov / 0.55) + bonus)
    lay.detail = {"q": round(q, 3), "demoted": round(drop, 3), "overlap": round(overlap, 3),
                  "box_overlap": round(box_overlap, 3),
                  "illegible": round(illegible / total_p, 3), "cov": round(cov, 3), "oob": oob}
    lay.score = sc
    return sc


def candidates(ctx: Ctx) -> List[Layout]:
    blocks = ctx.an.blocks
    A = ctx.W / ctx.H
    A0 = ctx.an.W0 / ctx.an.H0
    out: List[Layout] = []

    def add_one(builder):
        try:
            lay = with_demotions(ctx, blocks, builder)
        except Exception:
            lay = None
        if lay is not None:
            if not ctx.visible_fp:
                lay.name += "-box"
            settle(lay, ctx)
            score_layout(ctx, lay, blocks)
            out.append(lay)

    def add(builder):
        for vis in (True, False):
            ctx.visible_fp = vis
            add_one(builder)
        ctx.visible_fp = True

    for k in (1.0, 1.12, 1.25):
        add(lambda bl, k=k: build_preserve(ctx, bl, k))
    if A < 2.6:
        for inline in (False, True):
            for img_k in (1.0, 0.75, 0.55):
                add(lambda bl, i=inline, k=img_k: build_stack(ctx, bl, i, k))
    if A >= 1.15:
        for side in ("left", "right"):
            for frac in (0.36, 0.45, 0.55):
                for inline in (False, True):
                    add(lambda bl, s=side, f=frac, i=inline: build_split(ctx, bl, s, f, i))
    if A >= 2.2:
        for side in ("left", "right"):
            for ls in (False, True):
                for inline in (True, False):
                    for tc in (1, 2, 3):
                        add(lambda bl, s=side, l=ls, i=inline, t=tc: build_row(ctx, bl, s, l, i, t))
    return out
