"""
Design analysis: turn a flat element list into layout "blocks".

The engine is never told what an element *means*, so we infer structure
from geometry, type and styling alone:

  background  - a full-bleed image/shape at the bottom of the stack
  decor       - translucent / oversized / off-canvas ungrouped shapes
  blocks      - the units that get laid out; each is one of
                  image  - a single picture (logo, product, ...)
                  text   - a single free-standing text box (reflowable)
                  group  - elements that travel together rigidly
                           (explicit group_id, or a shape that contains text,
                           e.g. a button / badge / ribbon)
                  shape  - an opaque free-standing shape (divider, accent bar)
                  row    - several similar blocks side by side (badge rows)

Each block also gets a priority (how bad it is to lose it), an alignment,
and optionally a corner anchor ("floater") for small items tucked into a
corner of the source, such as a sale ribbon or a corner badge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .measure import asset_visible_fraction, get_measurer

Rect = Tuple[float, float, float, float]


def el_rect(el: dict) -> Rect:
    """Union of the element's unrotated box and its rotated bounding box."""
    x, y = float(el.get("x", 0)), float(el.get("y", 0))
    w, h = float(el.get("width", 0)), float(el.get("height", 0))
    rot = float(el.get("rotation") or 0.0)
    if abs(rot) < 1e-6:
        return (x, y, x + w, y + h)
    cx, cy = x + w / 2, y + h / 2
    a = math.radians(rot)
    ca, sa = abs(math.cos(a)), abs(math.sin(a))
    hw = (w * ca + h * sa) / 2
    hh = (w * sa + h * ca) / 2
    return (min(x, cx - hw), min(y, cy - hh), max(x + w, cx + hw), max(y + h, cy + hh))


def union(rects: List[Rect]) -> Rect:
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def area(r: Rect) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def inter(a: Rect, b: Rect) -> float:
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def parse_alpha(color: Optional[str]) -> float:
    if not color or "(" not in color:
        return 1.0
    try:
        parts = color[color.index("(") + 1:color.rindex(")")].split(",")
        return float(parts[3]) if len(parts) >= 4 else 1.0
    except Exception:
        return 1.0


@dataclass
class Block:
    bid: str
    kind: str
    els: List[dict]
    rect: Rect
    priority: float = 0.5
    align: str = "center"
    children: List["Block"] = field(default_factory=list)
    is_logo: bool = False
    is_hero: bool = False
    is_cta: bool = False
    is_headline: bool = False
    floater: Optional[Tuple[str, str]] = None  # (left|right, top|bottom)

    @property
    def w(self) -> float:
        return self.rect[2] - self.rect[0]

    @property
    def h(self) -> float:
        return self.rect[3] - self.rect[1]

    @property
    def ids(self) -> List[str]:
        if self.kind == "row":
            return [i for c in self.children for i in c.ids]
        return [e["id"] for e in self.els]

    def texts(self) -> List[dict]:
        if self.kind == "row":
            return [t for c in self.children for t in c.texts()]
        return [e for e in self.els if e.get("type") == "text"]


@dataclass
class Analysis:
    W0: float
    H0: float
    background: List[dict]
    decor: List[dict]
    missing: List[dict]
    blocks: List[Block]
    fmax: float


def _is_full_bleed(el: dict, W0: float, H0: float) -> bool:
    if el.get("type") == "text":
        return False
    r = el_rect(el)
    return inter(r, (0, 0, W0, H0)) >= 0.85 * W0 * H0


def _contains(outer: Rect, inner: Rect, tol: float = 0.08) -> bool:
    iw, ih = inner[2] - inner[0], inner[3] - inner[1]
    return (inner[0] >= outer[0] - tol * iw and inner[2] <= outer[2] + tol * iw
            and inner[1] >= outer[1] - tol * ih - 2 and inner[3] <= outer[3] + tol * ih + 2)


def source_lines(el: dict) -> int:
    lay = get_measurer().layout(el, int(round(float(el.get("font_size", 16)))), float(el.get("width", 1)))
    return lay.lines


def analyze(source: dict, roles: Optional[Dict[str, str]] = None) -> Analysis:
    """`roles` optionally maps element id -> semantic role from the local model
    (headline / body / cta / legal / label); geometry still decides first."""
    roles = roles or {}
    W0 = float(source["canvas"]["width"])
    H0 = float(source["canvas"]["height"])
    A0 = W0 * H0
    els = [e for e in source["elements"] if isinstance(e, dict) and "id" in e]

    background, decor, missing = [], [], []
    rest = []
    for el in els:
        t = el.get("type")
        # An asset absent from the local brand kit is NOT treated as missing:
        # scoring renders with the full asset set, so it's laid out like any image.
        if _is_full_bleed(el, W0, H0):
            background.append(el)
        else:
            rest.append(el)

    # Explicit groups.
    groups: Dict[str, List[dict]] = {}
    singles: List[dict] = []
    for el in rest:
        gid = el.get("group_id")
        if gid:
            groups.setdefault(str(gid), []).append(el)
        else:
            singles.append(el)

    # Implicit groups: an opaque-ish shape that encloses free text (button, tag).
    texts = [e for e in singles if e.get("type") == "text"]
    used = set()
    for sh in [e for e in singles if e.get("type") == "shape"]:
        sr = el_rect(sh)
        if area(sr) > 0.3 * A0:
            continue
        inside = [t for t in texts if id(t) not in used and _contains(sr, el_rect(t))]
        if inside:
            gid = f"__implicit_{sh['id']}"
            groups[gid] = [sh] + inside
            used.add(id(sh))
            used.update(id(t) for t in inside)
    singles = [e for e in singles if id(e) not in used]

    # Implicit groups: images that overlap each other substantially (a collage, a
    # product over a photo) are an intentional composition, not a collision to
    # pull apart; they travel together like a designer's group.
    imgs = [e for e in singles if e.get("type") == "image" and float(e.get("opacity", 1.0)) > 0.4]
    parent = {id(e): id(e) for e in imgs}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, a in enumerate(imgs):
        ra = el_rect(a)
        for b in imgs[i + 1:]:
            rb = el_rect(b)
            if inter(ra, rb) >= 0.15 * min(area(ra), area(rb)) > 0:
                parent[find(id(a))] = find(id(b))
    clusters: Dict[int, List[dict]] = {}
    for e in imgs:
        clusters.setdefault(find(id(e)), []).append(e)
    cluster_ids = set()
    for members in clusters.values():
        if len(members) >= 2:
            gid = f"__cluster_{members[0]['id']}"
            groups[gid] = members
            cluster_ids.add(gid)
            used.update(id(m) for m in members)
    singles = [e for e in singles if id(e) not in used]

    blocks: List[Block] = []
    for gid, members in groups.items():
        if len(members) == 1:
            singles.append(members[0])
            continue
        blocks.append(Block(gid, "group", members, union([el_rect(m) for m in members])))

    for el in singles:
        t = el.get("type")
        r = el_rect(el)
        if t == "shape":
            alpha = parse_alpha(el.get("fill_color")) * float(el.get("opacity", 1.0))
            off = r[0] < -1 or r[1] < -1 or r[2] > W0 + 1 or r[3] > H0 + 1
            if alpha <= 0.55 or area(r) > 0.12 * A0 or off or el.get("shape_type") == "ellipse":
                decor.append(el)
                continue
            blocks.append(Block(el["id"], "shape", [el], r))
        elif t == "image":
            if float(el.get("opacity", 1.0)) <= 0.4:
                decor.append(el)
                continue
            blocks.append(Block(el["id"], "image", [el], r))
        else:
            blocks.append(Block(el["id"], "text", [el], r))

    fonts = [float(e.get("font_size", 16)) for b in blocks if b.kind == "text" for e in b.els]
    fmax = max(fonts) if fonts else max([float(t.get("font_size", 16)) for b in blocks for t in b.texts()] or [16.0])
    fmin = min(fonts) if fonts else fmax

    _assign_roles(blocks, W0, H0, fmax, fmin, roles)
    for b in blocks:
        if b.bid in cluster_ids:
            b.priority = 0.8
    blocks = _build_rows(blocks, W0, H0)
    _assign_floaters(blocks, W0, H0)
    blocks.sort(key=lambda b: (b.rect[1], b.rect[0]))
    return Analysis(W0, H0, background, decor, missing, blocks, fmax)


def _align_of(b: Block, W0: float) -> str:
    cx = (b.rect[0] + b.rect[2]) / 2
    if abs(cx - W0 / 2) <= 0.08 * W0:
        return "center"
    if b.kind == "text":
        ta = b.els[0].get("text_align", "left")
        if ta == "center" and abs(cx - W0 / 2) <= 0.2 * W0:
            return "center"
    return "left" if b.rect[0] < W0 - b.rect[2] else "right"


def _assign_roles(blocks: List[Block], W0: float, H0: float, fmax: float, fmin: float,
                  roles: Optional[Dict[str, str]] = None) -> None:
    roles = roles or {}
    A0 = W0 * H0
    images = [b for b in blocks if b.kind == "image"]
    for b in images:
        el = b.els[0]
        aid = str(el.get("asset_id", "")).lower()
        aspect = b.w / max(1.0, b.h)
        top_or_bottom = b.rect[1] < 0.25 * H0 or b.rect[3] > 0.8 * H0
        if "logo" in aid or (aspect >= 1.8 and area(b.rect) <= 0.06 * A0 and top_or_bottom):
            b.is_logo = True
            b.priority = 0.95
    others = [b for b in images if not b.is_logo]
    if others:
        hero = max(others, key=lambda b: area(b.rect))

        def beside(a: Block, b: Block) -> bool:
            ov = min(a.rect[3], b.rect[3]) - max(a.rect[1], b.rect[1])
            return ov >= 0.5 * min(a.h, b.h)

        # several equal images side by side (a product line-up) have no single
        # hero: they stay together as a row of equals
        peers = [b for b in others if b is not hero and area(b.rect) >= 0.66 * area(hero.rect) and beside(hero, b)]
        if area(hero.rect) >= 0.03 * A0 and not peers:
            hero.is_hero = True
            hero.priority = 0.75
        for b in others:
            if not b.is_hero:
                b.priority = 0.7 if (peers and (b is hero or b in peers)) else 0.5

    headline_done = False
    for b in sorted([b for b in blocks if b.kind == "text"], key=lambda b: (-float(b.els[0].get("font_size", 16)), b.rect[1])):
        el = b.els[0]
        f = float(el.get("font_size", 16))
        n = len(str(el.get("content", "")))
        if not headline_done:
            b.is_headline = True
            b.priority = 0.9
            headline_done = True
            continue
        p = 0.35 + 0.45 * (f / fmax)
        if n > 80 and f <= 0.6 * fmax:
            p -= 0.1
        if f <= fmin + 0.01 and f <= 0.45 * fmax:
            p = 0.12
        b.priority = p

    for b in blocks:
        if b.kind == "text" and not b.is_headline:
            role = roles.get(b.els[0]["id"])
            if role == "legal":
                b.priority = min(b.priority, 0.15)
            elif role == "label":
                b.priority *= 0.9

    buttons = []
    for b in blocks:
        if b.kind != "group":
            continue
        has_text = any(e.get("type") == "text" for e in b.els)
        has_fill = any(e.get("type") == "shape" and parse_alpha(e.get("fill_color")) * float(e.get("opacity", 1)) > 0.5 for e in b.els)
        if has_text and has_fill:
            buttons.append(b)
        b.priority = 0.4 if has_text else 0.3
    if buttons:
        rotated = lambda b: any(abs(float(e.get("rotation") or 0)) > 0.5 for e in b.els)
        cands = [b for b in buttons if not rotated(b)] or buttons
        said_cta = [b for b in cands if any(roles.get(t["id"]) == "cta" for t in b.texts())]
        cta = max(said_cta or cands, key=lambda b: (area(b.rect), b.rect[1]))
        cta.is_cta = True
        cta.priority = 0.85

    for b in blocks:
        if b.kind == "shape":
            b.priority = 0.25
        b.align = _align_of(b, W0)


def _signature(b: Block) -> Tuple:
    return (b.kind, tuple(sorted(e.get("type", "") for e in b.els)))


def _build_rows(blocks: List[Block], W0: float, H0: float) -> List[Block]:
    """Merge similar blocks that sit side by side into a row block."""
    pool = sorted(blocks, key=lambda b: (b.rect[1], b.rect[0]))
    out: List[Block] = []
    taken = set()
    for i, b in enumerate(pool):
        if id(b) in taken or b.is_cta or b.is_logo or b.is_hero or b.kind == "text":
            continue
        mates = [b]
        for c in pool[i + 1:]:
            if id(c) in taken or c.is_cta or c.is_logo or c.is_hero or _signature(c) != _signature(b):
                continue
            ov = min(b.rect[3], c.rect[3]) - max(b.rect[1], c.rect[1])
            hmin = min(b.h, c.h)
            if hmin > 0 and ov >= 0.5 * hmin and max(b.h, c.h) / hmin <= 1.6:
                if not any(abs(float(e.get("rotation") or 0)) > 0.5 for e in c.els):
                    mates.append(c)
        if len(mates) >= 2:
            mates.sort(key=lambda m: m.rect[0])
            for m in mates:
                taken.add(id(m))
            row = Block("row:" + "+".join(m.bid for m in mates), "row", [], union([m.rect for m in mates]),
                        priority=max(m.priority for m in mates) + 0.02, children=mates)
            row.align = _align_of(row, W0)
            out.append(row)
    out.extend(b for b in pool if id(b) not in taken)
    return out


def _assign_floaters(blocks: List[Block], W0: float, H0: float) -> None:
    A0 = W0 * H0
    for b in blocks:
        if b.kind == "row" or b.is_hero or b.is_cta or b.is_headline:
            continue
        r = b.rect
        if area(r) > 0.06 * A0 or (r[2] - r[0]) > 0.5 * W0:
            continue
        rotated = any(abs(float(e.get("rotation") or 0)) > 0.5 for e in b.els)
        left = r[0] <= 0.1 * W0
        right = r[2] >= 0.9 * W0
        top = r[1] <= 0.12 * H0
        bottom = r[3] >= 0.88 * H0
        if (left or right) and (top or bottom):
            if b.is_logo and not rotated and abs((r[0] + r[2]) / 2 - W0 / 2) < 0.1 * W0:
                continue
            b.floater = ("left" if left else "right", "top" if top else "bottom")
            if not b.is_logo:
                b.priority *= 0.8
