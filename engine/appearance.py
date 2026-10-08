"""Cheap background contrast/busyness proxy using only existing assets."""
from pathlib import Path
from statistics import pstdev
from PIL import Image, ImageColor
from renderer.converter.assets import load_asset_image
from renderer.converter.colorutil import parse_rgba
from renderer.converter.shapes import render_shape, shape_fill_alpha

ASSETS = Path(__file__).resolve().parents[1] / "brand_kit/assets"


def color(value):
    if value and not value.startswith("rgb"):
        try:
            rgb = ImageColor.getrgb(value)
            return (*rgb[:3], rgb[3]/255 if len(rgb)>3 else 1)
        except ValueError:
            pass
    return parse_rgba(value)


def luminance(rgb):
    def channel(v):
        v = v/255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    return sum(a*channel(v) for a,v in zip((.2126,.7152,.0722),rgb))


def background_map(elements, indices, target):
    w,h = target["width"],target["height"]
    image = Image.new("RGBA",(96,96),"white")
    for i in sorted(indices,key=lambda i:elements[i].get("z_index",0)):
        e = dict(elements[i])
        e.update(width=max(1,e["width"]*96/w),height=max(1,e["height"]*96/h))
        if e["type"] == "image":
            # Unknown assets cannot provide reliable contrast evidence.
            if not (ASSETS/e["asset_id"]).is_file():
                continue
            tile = load_asset_image(str(ASSETS),e["asset_id"],e["width"],e["height"],e.get("fit","contain"))
            opacity = e.get("opacity",1)
        else:
            tile,opacity = render_shape(e),e.get("opacity",1)*shape_fill_alpha(e)
        tile.putalpha(tile.getchannel("A").point(lambda a:round(a*opacity)))
        image.alpha_composite(tile,(round(e["x"]*96/w),round(e["y"]*96/h)))
    return image.convert("RGB")


def text_penalty(el, background, target, group_shapes):
    fg = color(el["color"])
    samples = []
    for rx in (.2,.5,.8):
        for ry in (.2,.5,.8):
            x = max(0,min(95,int((el["x"]+el["width"]*rx)*96/target["width"])))
            y = max(0,min(95,int((el["y"]+el["height"]*ry)*96/target["height"])))
            pixel = background.getpixel((x,y))
            if group_shapes:
                fill = color(group_shapes[-1]["fill_color"])
                pixel = tuple(fill[c]*fill[3]+pixel[c]*(1-fill[3]) for c in range(3))
            samples.append(pixel)
    contrast = []
    for pixel in samples:
        composite = tuple(fg[c]*fg[3]+pixel[c]*(1-fg[3]) for c in range(3))
        a,b = luminance(composite),luminance(pixel)
        contrast.append((max(a,b)+.05)/(min(a,b)+.05))
    threshold = 3 if el["font_size"] >= 18 else 4.5
    low = sum(max(0,threshold-c)/threshold for c in contrast)/len(contrast)
    busy = pstdev([luminance(p) for p in samples])
    return low*2.5 + busy*.7
