"""Offline, group-preserving candidate search with an optional local semantic model.

resize() keeps the competition contract. resize_with_diagnostics() also returns
candidate scores and model status for development, without polluting output JSON.
"""
from copy import deepcopy
import math
from typing import Any

from engine.geometry import area, background, bounds, contain, decorative, intersection, union
from engine.local_model import advise
from engine.typography import fit_font, fits, metric_backend
from engine.appearance import background_map, text_penalty
from engine.reflow import hide_missing, reflow
from evaluation.audit import audit


def _validate(source, target):
    for canvas in (source["canvas"], target):
        if any(not isinstance(canvas.get(k), int) or isinstance(canvas[k], bool) or canvas[k] < 1 for k in ("width", "height")):
            raise ValueError("Canvas dimensions must be positive integers")
    ids = [e["id"] for e in source["elements"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs cannot be preserved uniquely")
    for e in source["elements"]:
        for k in ("x", "y", "width", "height", "rotation", "font_size"):
            if k in e and (not isinstance(e[k], (int, float)) or not math.isfinite(e[k])):
                raise ValueError(f"Non-finite or invalid {k}")
        if e["width"] < 0 or e["height"] < 0:
            raise ValueError("Negative element dimensions")


def _units(source, hints):
    elements, canvas = source["elements"], source["canvas"]
    backgrounds = [i for i, e in enumerate(elements) if background(e, canvas)]
    decorations = [i for i, e in enumerate(elements) if i not in backgrounds and decorative(e, canvas)]
    foreground = [i for i in range(len(elements)) if i not in backgrounds + decorations]
    groups = {}
    for i in foreground:
        groups.setdefault(("group", elements[i]["group_id"]) if elements[i].get("group_id") else ("single", i), []).append(i)
    # Infer a simple unlabelled text-on-shape container, never image/text overlaps.
    singles = [key for key in groups if key[0] == "single"]
    for key in singles:
        if key not in groups:
            continue
        i = groups[key][0]
        shape = elements[i]
        if shape["type"] != "shape" or shape.get("rotation", 0):
            continue
        candidates = []
        for other in singles:
            if other not in groups or other == key:
                continue
            text = elements[groups[other][0]]
            if (text["type"] == "text" and text.get("z_index", 0) >= shape.get("z_index", 0)
                and intersection(bounds(shape), bounds(text)) >= area(bounds(text)) * .95
                and area(bounds(shape)) <= max(1, area(bounds(text))) * 6):
                candidates.append(other)
        if len(candidates) == 1:
            groups[key] += groups.pop(candidates[0])
    units = []
    max_font = max((e.get("font_size", 0) for e in elements), default=1) or 1
    for indices in groups.values():
        els = [elements[i] for i in indices]
        box = union(els)
        importance = max((e.get("font_size", 0) / max_font for e in els), default=.4)
        semantic = max(({"headline": 1.25, "cta": 1.1, "body": 1, "legal": .7, "label": .9}.get(hints.get(i), 1) for i in indices), default=1)
        demand = sum(max(1, len(e.get("content", ""))) * max(12, e.get("font_size", 12)) ** 2 * .55
                     if e["type"] == "text" else max(1, e["width"] * e["height"]) * .5 for e in els)
        units.append({"indices": indices, "box": box, "demand": max(1, demand) * semantic,
                      "importance": max(.35, importance) * semantic,
                      "image": all(e["type"] == "image" for e in els),
                      "text": len(els) == 1 and els[0]["type"] == "text"})
    units.sort(key=lambda u: (u["box"][1], u["box"][0], u["indices"][0]))
    return units, backgrounds, decorations


def _place(source, unit, rect, output, desired_scale):
    x, y, w, h = rect
    left, top, right, bottom = unit["box"]
    uw, uh = max(1e-6, right - left), max(1e-6, bottom - top)
    if unit["text"] and not source["elements"][unit["indices"][0]].get("rotation", 0):
        idx = unit["indices"][0]
        el = output[idx]
        el.update(x=x, y=y, width=max(.01, w), height=max(.01, h))
        original = source["elements"][idx]
        el["font_size"] = fit_font(el, max(10, original["font_size"] * desired_scale * 1.35))
        return
    scale = min(w / uw, h / uh)
    ox, oy = x + (w - uw * scale) / 2, y + (h - uh * scale) / 2
    for idx in unit["indices"]:
        original, el = source["elements"][idx], output[idx]
        el.update(x=ox + (original["x"] - left) * scale, y=oy + (original["y"] - top) * scale,
                  width=original["width"] * scale, height=original["height"] * scale)
        if el["type"] == "text":
            el["font_size"] = fit_font(el, max(1, original["font_size"] * scale))


def _partition(units, rect, exponent=.55, force_axis=None):
    if not units:
        return []
    if len(units) == 1:
        return [(units[0], rect)]
    x, y, w, h = rect
    axis = force_axis if force_axis is not None else (0 if w / max(h, .01) > 1.2 else 1)
    weights = [u["demand"] ** exponent for u in units]
    total = sum(weights)
    split = min(range(1, len(units)), key=lambda k: abs(sum(weights[:k]) / total - .5))
    fraction = sum(weights[:split]) / total
    gap = min(w, h) * .025
    if axis == 0:
        size = (w - gap) * fraction
        a, b = (x, y, size, h), (x + size + gap, y, w - size - gap, h)
    else:
        size = (h - gap) * fraction
        a, b = (x, y, w, size), (x, y + size + gap, w, h - size - gap)
    return _partition(units[:split], a, exponent) + _partition(units[split:], b, exponent)


def _grid(units, rect, columns, exponent):
    x, y, w, h = rect
    rows = [units[i:i + columns] for i in range(0, len(units), columns)]
    gap = min(w, h) * .018
    weights = [max(u["demand"] ** exponent for u in row) for row in rows]
    usable_h = max(h * .5, h - gap * (len(rows) - 1))
    result = []
    for row, weight in zip(rows, weights):
        rh = usable_h * weight / sum(weights)
        rw = [u["demand"] ** exponent for u in row]
        usable_w = max(w * .5, w - gap * (len(row) - 1))
        px = x
        for u, item_weight in zip(row, rw):
            cw = usable_w * item_weight / sum(rw)
            result.append((u, (px, y, cw, rh)))
            px += cw + gap
        y += rh + gap
    return result


def _base(source, target, backgrounds, decorations):
    out = deepcopy(source["elements"])
    sw, sh, tw, th = source["canvas"]["width"], source["canvas"]["height"], target["width"], target["height"]
    for i in backgrounds:
        e = out[i]
        if e["type"] == "shape" or e.get("fit") == "cover":
            e.update(x=0, y=0, width=tw, height=th)
        else:
            s = min(tw / max(e["width"], 1e-9), th / max(e["height"], 1e-9))
            e.update(x=(tw-e["width"]*s)/2, y=(th-e["height"]*s)/2,
                     width=e["width"]*s, height=e["height"]*s)
    for i in decorations:
        e = out[i]
        s = min(tw / sw, th / sh)
        e.update(x=e["x"] * tw / sw, y=e["y"] * th / sh, width=e["width"] * s, height=e["height"] * s)
        contain(e, tw, th)
    return out


def _score(source, target, out, units, desired_scale, backdrop):
    score = 0.0
    tw, th = target["width"], target["height"]
    boxes = []
    for u in units:
        els = [out[i] for i in u["indices"]]
        box = union(els)
        boxes.append(box)
        for i in u["indices"]:
            old, e = source["elements"][i], out[i]
            if e["type"] == "text":
                ideal = max(10, old["font_size"] * desired_scale)
                score += u["importance"] * math.log(max(.01, e["font_size"] / ideal)) * 3
                if not fits(e, e["font_size"]):
                    score -= 30
                score -= max(0, 10 - e["font_size"]) * .3
                shapes = [s for s in els if s["type"] == "shape" and s.get("z_index",0) <= e.get("z_index",0)]
                score -= text_penalty(e,backdrop,target,shapes)
            elif e["type"] == "image":
                original_area = max(1, old["width"] * old["height"] * desired_scale ** 2)
                score += .8 * math.log(max(.001, e["width"] * e["height"] / original_area))
        if box[0] < -.01 or box[1] < -.01 or box[2] > tw + .01 or box[3] > th + .01:
            score -= 100
        # Preserve coarse reading order/anchors, with less weight for extreme changes.
        b = u["box"]
        shift = abs((box[0]+box[2])/(2*tw)-(b[0]+b[2])/(2*source["canvas"]["width"]))
        shift += abs((box[1]+box[3])/(2*th)-(b[1]+b[3])/(2*source["canvas"]["height"]))
        score -= shift * .2
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            score -= 35 * intersection(a, b) / max(1, min(area(a), area(b)))
    return score


def resize_with_diagnostics(source: dict[str, Any], target_canvas: dict[str, Any]):
    """Run both layout engines and keep the better result.

    - reflow (engine/reflow.py): structure-aware layouts (preserve / stack /
      split / banner row) with renderer-exact text fitting; primary.
    - partition search (below): grid / partition / editorial candidates;
      kept as a competitor and as a safety net.
    The output-contract audit referees: reflow wins unless it breaks the
    contract or overflows more text than the partition search.
    """
    _validate(source, target_canvas)
    target = {k: target_canvas[k] for k in ("width", "height")}
    hints, model = advise(source["elements"])
    search_out, diagnostics = _partition_search(source, target, hints, model)
    for e in search_out["elements"]:
        if e["type"] == "text":  # the renderer draws int(font_size); floor so measured == drawn
            e["font_size"] = max(1, int(e["font_size"]))
    roles = {source["elements"][i]["id"]: r for i, r in hints.items()}
    try:
        reflow_out, reflow_info = reflow(source, target, roles)
    except Exception as exc:  # never let the primary engine take the run down
        reflow_out, reflow_info = None, {"error": f"{type(exc).__name__}: {exc}"}
    chosen, engine = search_out, "partition-search"
    if reflow_out is not None:
        mine, theirs = audit(source, reflow_out, target), audit(source, search_out, target)
        reflow_info["audit"] = {k: mine[k] for k in ("valid", "text_overflows", "small_texts", "collisions")}
        detail = reflow_info.get("detail", {})
        clean = detail.get("overlap", 1) < 0.05 and not detail.get("oob")

        def cost(a):
            return 3 * a["text_overflows"] + a["small_texts"] + 0.5 * a["collisions"]

        if mine["valid"] and (not theirs["valid"] or (
                mine["text_overflows"] <= theirs["text_overflows"] and (clean or cost(mine) <= cost(theirs)))):
            chosen, engine = reflow_out, "reflow"
    if engine != "reflow":
        tucked = deepcopy(chosen)
        hide_missing(tucked)
        if audit(source, tucked, target)["valid"]:
            chosen = tucked
    diagnostics.update(engine=engine, reflow=reflow_info)
    diagnostics["warnings"] = (["Some copy cannot remain comfortably readable at this target size."]
                               if any(e["type"] == "text" and e["font_size"] < 10 for e in chosen["elements"]) else [])
    return chosen, diagnostics


def _partition_search(source, target, hints, model):
    units, backgrounds, decorations = _units(source, hints)
    tw, th = target["width"], target["height"]
    desired_scale = min(2.0, math.sqrt(tw * th / (source["canvas"]["width"] * source["canvas"]["height"])))
    margin = min(tw, th) * .035
    rect = (margin, margin, tw - 2 * margin, th - 2 * margin)
    candidates = []
    base = _base(source, target, backgrounds, decorations)
    backdrop = background_map(base,backgrounds+decorations,target)

    def add(name, placements):
        out = deepcopy(base)
        for unit, cell in placements:
            _place(source, unit, cell, out, desired_scale)
        candidates.append((_score(source, target, out, units, desired_scale, backdrop), name, out))

    # Preserve relative anchors for mild changes; evaluate rather than always select.
    sw, sh = source["canvas"]["width"], source["canvas"]["height"]
    placements = []
    for u in units:
        l, t, r, b = u["box"]
        w, h = min(tw, (r-l)*tw/sw), min(th, (b-t)*th/sh)
        placements.append((u, (max(0, min(tw-w, l*tw/sw)), max(0, min(th-h, t*th/sh)), w, h)))
    add("source-anchors", placements)
    if not units:
        add("background-only", [])
    else:
        for exponent in (.3, .6, .9):
            for axis in (0, 1):
                add(f"partition-{axis}-{exponent}", _partition(units, rect, exponent, axis))
            for cols in sorted(set([1, 2, 3, min(len(units), 5), len(units)])):
                if cols <= len(units):
                    add(f"grid-{cols}-{exponent}", _grid(units, rect, cols, exponent))
        images = [u for u in units if u["image"]]
        others = [u for u in units if not u["image"]]
        if images and others:
            x, y, w, h = rect
            for fraction in (.22, .35, .48):
                gap = min(w, h) * .03
                if w > h:
                    a, b = (x, y, w*fraction-gap/2, h), (x+w*fraction+gap/2, y, w*(1-fraction)-gap/2, h)
                else:
                    a, b = (x, y, w, h*fraction-gap/2), (x, y+h*fraction+gap/2, w, h*(1-fraction)-gap/2)
                for exp in (.4, .75):
                    add(f"image-copy-{fraction}-{exp}", _partition(images, a, .5) + _partition(others, b, exp))
        # Editorial alternative: continuous copy column with grouped badges/buttons
        # in a separate band. This uses element types and geometry, never sample labels.
        copy_units = [u for u in units if u["text"]]
        groups = [u for u in units if not u["text"] and not u["image"]]
        if images and copy_units and groups:
            x, y, w, h = rect
            copy_units = sorted(copy_units, key=lambda u: -source["elements"][u["indices"][0]]["font_size"])
            for fraction in (.25, .38):
                for band in (.20, .30, .40):
                    gap = min(w,h)*.025
                    if w > h:
                        image_rect = (x,y,w*fraction-gap,h)
                        cx,cy,cw,ch = x+w*fraction,y,w*(1-fraction),h
                    else:
                        image_rect = (x,y,w,h*fraction-gap)
                        cx,cy,cw,ch = x,y+h*fraction,w,h*(1-fraction)
                    copy_rect = (cx,cy,cw,ch*(1-band)-gap)
                    group_rect = (cx,cy+ch*(1-band),cw,ch*band)
                    add(f"editorial-{fraction}-{band}", _partition(images,image_rect,.5) +
                        _grid(copy_units,copy_rect,1,.65) + _grid(groups,group_rect,len(groups),.4))
    candidates.sort(key=lambda c: c[0], reverse=True)
    # (partition search: best of its own candidates)
    best_score, name, elements = candidates[0]
    return {"canvas": target, "elements": elements}, {
        "selected": name, "score": best_score, "candidate_count": len(candidates), "model": model,
        "metrics_backend": metric_backend(), "units": len(units),
        "candidates": [{"name": n, "score": s} for s, n, _ in candidates],
        "warnings": ["Some copy cannot remain comfortably readable at this target size."]
                    if any(e["type"] == "text" and e["font_size"] < 10 for e in elements) else []}


def resize(source: dict[str, Any], target_canvas: dict[str, Any]) -> dict[str, Any]:
    return resize_with_diagnostics(source, target_canvas)[0]
