"""Rotation-aware geometry. IDs carry no semantic meaning."""
import math


def bounds(el):
    r = math.radians(el.get("rotation", 0))
    w, h = el["width"], el["height"]
    rw, rh = abs(math.cos(r)) * w + abs(math.sin(r)) * h, abs(math.sin(r)) * w + abs(math.cos(r)) * h
    cx, cy = el["x"] + w / 2, el["y"] + h / 2
    return cx - rw / 2, cy - rh / 2, cx + rw / 2, cy + rh / 2


def union(elements):
    boxes = [bounds(e) for e in elements]
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def background(el, canvas):
    if el["type"] == "text" or el.get("rotation", 0):
        return False
    return (el["width"] >= canvas["width"] * .9 and el["height"] >= canvas["height"] * .9
            and el["x"] <= canvas["width"] * .1 and el["y"] <= canvas["height"] * .1)


def decorative(el, canvas):
    return (not el.get("group_id") and el["type"] == "shape" and
            (el.get("opacity", 1) <= .3 or el.get("shape_type") == "line"))


def contain(el, width, height):
    left, top, right, bottom = bounds(el)
    factor = min(1.0, width / max(right - left, 1e-9), height / max(bottom - top, 1e-9))
    if factor < 1:
        el["width"] *= factor
        el["height"] *= factor
        if el["type"] == "text":
            el["font_size"] = max(1, el["font_size"] * factor)
    left, top, right, bottom = bounds(el)
    el["x"] += max(0, -left) - max(0, right - width)
    el["y"] += max(0, -top) - max(0, bottom - height)
