"""Explicit development rendering. Never silently substitutes for the official renderer."""
from pathlib import Path
from PIL import Image, ImageDraw
from engine.typography import measure, pillow_font
from renderer.converter.assets import load_asset_image
from renderer.converter.shapes import render_shape, shape_fill_alpha
from renderer.converter.colorutil import parse_rgba

ROOT = Path(__file__).resolve().parents[1]


def rgba(value):
    r, g, b, a = parse_rgba(value)
    return r, g, b, round(a * 255)


def render(design, path, backend="official"):
    if backend == "official":
        from renderer.converter.convert import render_design_to_png
        return render_design_to_png(design, ROOT / "brand_kit/assets", path)
    if backend != "pillow":
        raise ValueError("Renderer must be official or pillow")
    w, h = design["canvas"]["width"], design["canvas"]["height"]
    image = Image.new("RGBA", (w, h), "white")
    warnings = ["Pillow development preview; NOT official scoring-renderer output."]
    for el in sorted(design["elements"], key=lambda e: e.get("z_index", 0)):
        ew, eh = max(1, round(el["width"])), max(1, round(el["height"]))
        opacity = el.get("opacity", 1)
        if el["type"] == "image":
            asset = ROOT / "brand_kit/assets" / el["asset_id"]
            if not asset.is_file():
                warnings.append("Missing asset: " + el["asset_id"])
            tile = load_asset_image(str(ROOT / "brand_kit/assets"), el["asset_id"], ew, eh, el.get("fit", "contain"))
        elif el["type"] == "shape":
            tile = render_shape(el)
            opacity *= shape_fill_alpha(el)
        else:
            tile = Image.new("RGBA", (ew, eh))
            draw = ImageDraw.Draw(tile)
            wrapped = measure(el)["wrapped"]
            font = pillow_font(el["font_family"], el.get("font_weight") == "bold", el.get("font_style") == "italic", max(1, round(el["font_size"])))
            y, offset = 0.0, 0
            for line in wrapped.split("\n"):
                line_w = font.getlength(line) + max(0, len(line)-1) * el.get("letter_spacing", 0)
                x = (ew-line_w)/2 if el.get("text_align") == "center" else ew-line_w if el.get("text_align") == "right" else 0
                for j, char in enumerate(line):
                    style = dict(el)
                    for run in el.get("style_runs") or []:
                        if run["start"] <= offset+j < run["end"]:
                            style.update(run)
                    runfont = pillow_font(el["font_family"], style.get("font_weight") == "bold", style.get("font_style") == "italic", max(1, round(el["font_size"])))
                    draw.text((x, y), char, font=runfont, fill=rgba(style["color"]), anchor="lt")
                    x += runfont.getlength(char) + el.get("letter_spacing", 0)
                offset += len(line)+1
                y += el["font_size"] * el.get("line_height", 1.2)
        if opacity != 1:
            tile.putalpha(tile.getchannel("A").point(lambda a: round(a * opacity)))
        rotation = el.get("rotation", 0)
        if rotation:
            tile = tile.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
        x = round(el["x"] + el["width"]/2 - tile.width/2)
        y = round(el["y"] + el["height"]/2 - tile.height/2)
        image.alpha_composite(tile, (x, y))
    image.convert("RGB").save(path)
    return warnings
