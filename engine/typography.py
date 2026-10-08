"""Measured font fitting; prefer official Skia, with an explicit Pillow fallback."""
from functools import lru_cache
from pathlib import Path
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "brand_kit" / "fonts"


@lru_cache(maxsize=1)
def official_manager():
    try:
        from renderer.converter.brand_fonts import load_brand_font_manager
        return load_brand_font_manager(str(FONTS))
    except ImportError:
        return None


def metric_backend():
    return "official-skia" if official_manager() is not None else "pillow-fallback"


@lru_cache(maxsize=128)
def font_path(family, bold=False, italic=False):
    stem = "".join(c for c in family.lower() if c.isalnum())
    files = sorted(p for p in FONTS.iterdir() if p.suffix.lower() in (".ttf", ".otf"))
    matches = [p for p in files if p.stem.split("-")[0].lower() == stem]
    suffix = ("Bold" if bold else "") + ("Italic" if italic else "") or "Regular"
    exact = [p for p in matches if p.stem.endswith("-" + suffix)]
    if exact:
        return exact[0]
    if matches:
        return matches[0]
    if not files:
        raise FileNotFoundError("No local brand fonts available")
    return files[0]


@lru_cache(maxsize=512)
def pillow_font(family, bold=False, italic=False, size=100):
    return ImageFont.truetype(str(font_path(family, bold, italic)), size)


@lru_cache(maxsize=8192)
def unit_widths(family, bold, italic, text):
    manager = official_manager()
    if manager is not None:
        from renderer.converter.wrap import char_widths
        style = "bolditalic" if bold and italic else "bold" if bold else "italic" if italic else "regular"
        return tuple(w / 100 for w in char_widths(manager, family, "bold" if bold else "regular", style, 100, text))
    font = pillow_font(family, bold, italic)
    return tuple(font.getlength(c) / 100 for c in text)


def widths_for(el, size):
    text = el.get("content", "")
    family = el.get("font_family", "Solstice Sans")
    bold, italic = el.get("font_weight") == "bold", el.get("font_style") == "italic"
    values = [v * size for v in unit_widths(family, bold, italic, text)]
    for run in el.get("style_runs") or []:
        alt = unit_widths(family, run.get("font_weight", "bold" if bold else "regular") == "bold",
                          run.get("font_style", "italic" if italic else "normal") == "italic", text)
        for i in range(max(0, run.get("start", 0)), min(len(text), run.get("end", len(text)))):
            values[i] = max(values[i], alt[i] * size)
    return [v + max(0, el.get("letter_spacing", 0)) for v in values]


def measure(el, size=None, width=None):
    size = el["font_size"] if size is None else size
    width = el["width"] if width is None else width
    chars = list(el.get("content", ""))
    values = widths_for(el, size)
    line_width, last_space = 0.0, None
    for i, char in enumerate(chars):
        if char == "\n":
            line_width, last_space = 0.0, None
            continue
        if line_width + values[i] > width and last_space is not None:
            chars[last_space] = "\n"
            line_width = sum(values[last_space + 1:i + 1])
            last_space = None
        else:
            line_width += values[i]
        if char == " ":
            last_space = i
    lines, current, maximum = 1, 0.0, 0.0
    for i, char in enumerate(chars):
        if char == "\n":
            maximum, current, lines = max(maximum, current), 0.0, lines + 1
        else:
            current += values[i]
    maximum = max(maximum, current)
    return {"width": maximum, "height": lines * size * max(1.0, el.get("line_height", 1.2)),
            "lines": lines, "wrapped": "".join(chars)}


def fits(el, size):
    m = measure(el, size)
    return (m["width"] <= el["width"] * .98 + 1e-7 and
            m["height"] <= el["height"] * .96 + 1e-7 and
            (not el.get("max_lines") or m["lines"] <= el["max_lines"]))


def fit_font(el, upper):
    lo, hi = 1.0, max(1.0, upper)
    for _ in range(18):
        mid = (lo + hi) / 2
        if fits(el, mid):
            lo = mid
        else:
            hi = mid
    return round(lo, 5)
