"""Seeded synthetic designs from distinct families; not a substitute for real unseen designs."""
from copy import deepcopy
import random

TARGETS = [(1080,1080), (1080,1350), (1080,1920), (1280,720), (1600,400), (728,90)]
# Development formats only. The organizer's exact catalogue is not published here.


def synthetic(seed):
    rng = random.Random(seed)
    sw, sh = rng.choice([(900,1200), (1200,800), (1000,1000)])
    elements = [{"id":"e0", "type":"shape", "shape_type":"rectangle", "fill_color":"rgba(25,28,42,1)",
                 "x":0, "y":0, "width":sw, "height":sh, "z_index":0}]
    family = seed % 4
    count = rng.randint(3, 9)
    for i in range(count):
        row, col = (i//2, i%2) if family == 1 else (i,0)
        width = sw * (.4 if family == 1 else .78)
        height = sh / (count+2) * .7
        x, y = sw*.08 + col*sw*.46, sh*.07 + row*sh/(count+1)
        element = {"id":f"e{i+1}", "x":x, "y":y, "width":width, "height":height, "z_index":2}
        if i == 1 or (family == 2 and i%3 == 1):
            element.update(type="image", asset_id="solstice_bottle.png", fit="contain", width=height, height=height)
        else:
            content = rng.choice(["Meet the next season", "Thoughtfully crafted. Made to share.", "Explore the collection", "Friday 7 PM", "Terms and availability apply."])
            if family == 3 and i == 2:
                content = "Details for the launch event and community gathering. " * 5
            element.update(type="text", content=content, font_family="Solstice Sans", font_size=36 if i==0 else rng.randint(14,24),
                           font_weight="bold" if i==0 else "regular", color="rgba(255,255,255,1)", text_align=rng.choice(["left","center"]))
        elements.append(element)
    if family in (0,3):
        label = elements[-1]
        if label["type"] == "text":
            label["group_id"] = "group-a"
            shape = {"id":"button", "type":"shape", "shape_type":"rectangle", "fill_color":"rgba(166,54,30,1)",
                     "x":label["x"]-8,"y":label["y"]-8,"width":label["width"]+16,"height":label["height"]+16,
                     "z_index":1,"group_id":"group-a","corner_radius":10}
            elements.append(shape)
    return {"canvas":{"width":sw,"height":sh},"elements":elements}


def mutate(source, variant):
    out = deepcopy(source)
    if variant == "renamed":
        groups = {}
        for i, e in enumerate(out["elements"]):
            e["id"] = f"opaque-{i*137+19}"
            for key in list(e):
                if key.startswith("_"):
                    del e[key]
            if e.get("group_id"):
                groups.setdefault(e["group_id"], f"g-{len(groups)}")
                e["group_id"] = groups[e["group_id"]]
    elif variant == "long-copy":
        for e in out["elements"]:
            if e["type"] == "text":
                e["content"] += " Available for a limited time, while supplies last."
    elif variant == "rotation":
        for e in out["elements"]:
            if e["type"] == "text" and not e.get("group_id"):
                e["rotation"] = 17
                break
    return out
