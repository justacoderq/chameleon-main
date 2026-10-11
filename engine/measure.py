"""
Text measurement that mirrors the official renderer.

The renderer wraps text greedily at real glyph widths (skia + the brand
fonts) but never enforces a text box's height, so text that doesn't fit
silently spills out of its box. To pick font sizes that genuinely fit, the
engine measures text with the exact same font lookup + wrap routine the
renderer uses. If skia / cr-renderer are unavailable we fall back to PIL
with the brand font files, and finally to a crude per-character estimate,
so the engine never crashes on a missing dependency.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LINE_HEIGHT = 1.2


def _find_dir(*candidates: Path) -> Optional[Path]:
    for c in candidates:
        if c.is_dir():
            return c
    return None


FONTS_DIR = _find_dir(Path("brand_kit/fonts"), _REPO_ROOT / "brand_kit" / "fonts")
ASSETS_DIR = _find_dir(Path("brand_kit/assets"), _REPO_ROOT / "brand_kit" / "assets")


def _weight_style(bold: bool, italic: bool) -> Tuple[str, str]:
    if bold and italic:
        return "bold", "bolditalic"
    if bold:
        return "bold", "bold"
    if italic:
        return "regular", "italic"
    return "regular", "regular"


def _greedy_wrap(text: str, widths: List[float], max_width: float) -> str:
    """Same algorithm as renderer/converter/wrap.py::wrap_text (used when that
    module can't be imported)."""
    if not text or max_width <= 0:
        return text
    chars = list(text)
    line_width = 0.0
    last_space_idx = None
    for i, c in enumerate(chars):
        if c == "\n":
            line_width = 0.0
            last_space_idx = None
            continue
        w = widths[i] if i < len(widths) else 0.0
        if line_width + w > max_width and last_space_idx is not None:
            chars[last_space_idx] = "\n"
            line_width = sum(widths[j] for j in range(last_space_idx + 1, i + 1) if chars[j] != "\n")
            last_space_idx = None
        else:
            line_width += w
        if c == " ":
            last_space_idx = i
    return "".join(chars)


class _Backend:
    def char_widths(self, family: str, bold: bool, italic: bool, size: int, text: str) -> List[float]:
        raise NotImplementedError

    def metrics(self, family: str, bold: bool, italic: bool) -> Tuple[float, float]:
        """(ascent, descent) per 1px of font size, both positive."""
        raise NotImplementedError


class _SkiaBackend(_Backend):
    def __init__(self) -> None:
        import skia  # type: ignore
        from renderer.converter.brand_fonts import load_brand_font_manager  # type: ignore

        if FONTS_DIR is None:
            raise FileNotFoundError("brand_kit/fonts not found")
        self._skia = skia
        self._fm = load_brand_font_manager(str(FONTS_DIR))
        self._typefaces = {}

    def _typeface(self, family, bold, italic):
        key = (family, bold, italic)
        tf = self._typefaces.get(key)
        if tf is None:
            weight, style = _weight_style(bold, italic)
            tf = self._skia.Typeface.MakeFromData(self._fm.lookup(family, weight, style))
            self._typefaces[key] = tf
        return tf

    def char_widths(self, family, bold, italic, size, text):
        if not text:
            return []
        font = self._skia.Font(self._typeface(family, bold, italic), size)
        return list(font.getWidths(font.textToGlyphs(text)))

    def metrics(self, family, bold, italic):
        m = self._skia.Font(self._typeface(family, bold, italic), 100).getMetrics()
        return abs(m.fAscent) / 100.0, abs(m.fDescent) / 100.0


class _PilBackend(_Backend):
    def __init__(self) -> None:
        from PIL import ImageFont  # noqa: F401

        if FONTS_DIR is None:
            raise FileNotFoundError("brand_kit/fonts not found")
        self._files = {}
        for p in FONTS_DIR.glob("*.[ot]tf"):
            fam, _, suffix = p.stem.partition("-")
            suffix = suffix.lower()
            self._files[(fam.lower(), "bold" in suffix, "italic" in suffix)] = p
        self._cache = {}

    def _path(self, family, bold, italic):
        fam = family.replace(" ", "").lower()
        for key in ((fam, bold, italic), (fam, bold, False), (fam, False, False)):
            if key in self._files:
                return self._files[key]
        return next(iter(self._files.values()))

    def _font(self, family, bold, italic, size):
        from PIL import ImageFont

        key = (family, bold, italic, size)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(str(self._path(family, bold, italic)), size)
        return self._cache[key]

    def char_widths(self, family, bold, italic, size, text):
        f = self._font(family, bold, italic, max(1, size))
        return [f.getlength(c) for c in text]

    def metrics(self, family, bold, italic):
        asc, desc = self._font(family, bold, italic, 100).getmetrics()
        return asc / 100.0, desc / 100.0


class _EstimateBackend(_Backend):
    def char_widths(self, family, bold, italic, size, text):
        k = 0.58 if bold else 0.54
        return [size * (0.28 if c == " " else k) for c in text]

    def metrics(self, family, bold, italic):
        return 1.05, 0.35


def _make_backend() -> _Backend:
    for cls in (_SkiaBackend, _PilBackend):
        try:
            return cls()
        except Exception:
            continue
    return _EstimateBackend()


class TextLayout:
    __slots__ = ("font_size", "lines", "max_line_width", "height", "overflow", "wrap_width")

    def __init__(self, font_size, lines, max_line_width, height, overflow, wrap_width):
        self.font_size = font_size
        self.lines = lines
        self.max_line_width = max_line_width
        self.height = height
        self.overflow = overflow
        self.wrap_width = wrap_width


class TextMeasurer:
    def __init__(self) -> None:
        self.backend = _make_backend()
        try:
            from renderer.converter.wrap import wrap_text  # type: ignore

            self._wrap = wrap_text
        except Exception:
            self._wrap = _greedy_wrap

    @staticmethod
    def style_of(el: dict) -> Tuple[str, bool, bool]:
        family = el.get("font_family", "Solstice Sans")
        bold = (el.get("font_weight") or "regular").lower() in {"bold", "semibold", "extrabold", "black"}
        italic = el.get("font_style") == "italic"
        return family, bold, italic

    def layout(self, el: dict, font_size: int, width: float, letter_spacing: float = 0.0) -> TextLayout:
        family, bold, italic = self.style_of(el)
        line_height = float(el.get("line_height") or _DEFAULT_LINE_HEIGHT)
        return self._layout(str(el.get("content", "")), family, bold, italic, int(font_size),
                            round(float(width), 2), line_height, round(float(letter_spacing), 3))

    @lru_cache(maxsize=200_000)
    def _layout(self, text, family, bold, italic, size, width, line_height, letter_spacing) -> TextLayout:
        widths = self.backend.char_widths(family, bold, italic, size, text)
        wrapped = self._wrap(text, widths, width)
        lines = wrapped.split("\n")
        max_w = 0.0
        idx = 0
        for line in lines:
            n = len(line)
            lw = sum(widths[idx:idx + n]) + letter_spacing * max(0, n - 1)
            max_w = max(max_w, lw)
            idx += n + 1
        asc, desc = self.backend.metrics(family, bold, italic)
        n_lines = len(lines)
        height = (n_lines - 1) * size * line_height + (asc + desc) * size
        overflow = max_w > width + 0.5
        return TextLayout(size, n_lines, max_w, height, overflow, width)

    def fit(self, el: dict, width: float, max_height: float, f_max: int, f_min: int = 1,
            ls_ratio: float = 0.0, max_lines: Optional[int] = None) -> Optional[TextLayout]:
        """Largest integer font size in [f_min, f_max] whose wrap fits `width`
        without overflowing words and whose height fits `max_height`."""
        f_max = max(1, int(f_max))
        f_min = max(1, min(int(f_min), f_max))

        def ok(f: int) -> Optional[TextLayout]:
            lay = self.layout(el, f, width, ls_ratio * f)
            if lay.overflow or lay.height > max_height + 0.5:
                return None
            if max_lines is not None and lay.lines > max_lines:
                return None
            return lay

        best = ok(f_max)
        if best is not None:
            return best
        lo, hi = f_min, f_max - 1
        found = None
        while lo <= hi:
            mid = (lo + hi) // 2
            lay = ok(mid)
            if lay is not None:
                found = lay
                lo = mid + 1
            else:
                hi = mid - 1
        if found is not None:
            # Wrap height is not perfectly monotonic in font size; nudge upward.
            f = found.font_size + 1
            while f < f_max:
                lay = ok(f)
                if lay is None:
                    break
                found = lay
                f += 1
        return found


_MEASURER: Optional[TextMeasurer] = None


def get_measurer() -> TextMeasurer:
    global _MEASURER
    if _MEASURER is None:
        _MEASURER = TextMeasurer()
    return _MEASURER


@lru_cache(maxsize=256)
def asset_exists(asset_id: Optional[str]) -> bool:
    """True if the asset is present. If the assets folder itself can't be
    located we can't tell, so assume it exists (never hide on a guess)."""
    if ASSETS_DIR is None:
        return True
    if not asset_id:
        return False
    return (ASSETS_DIR / asset_id).is_file()


@lru_cache(maxsize=256)
def asset_visible_fraction(asset_id: Optional[str]) -> Tuple[float, float, float, float]:
    """Visible (non-transparent) bbox of an asset as fractions (x0, y0, x1, y1)."""
    try:
        from PIL import Image

        if ASSETS_DIR is None or not asset_id:
            return (0.0, 0.0, 1.0, 1.0)
        im = Image.open(ASSETS_DIR / asset_id)
        w, h = im.size
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        bbox = im.split()[3].point(lambda a: 255 if a > 8 else 0).getbbox()
        if not bbox:
            return (0.0, 0.0, 1.0, 1.0)
        return (bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h)
    except Exception:
        return (0.0, 0.0, 1.0, 1.0)


@lru_cache(maxsize=256)
def asset_size(asset_id: Optional[str]) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image

        if ASSETS_DIR is None or not asset_id:
            return None
        with Image.open(ASSETS_DIR / asset_id) as im:
            return im.size
    except Exception:
        return None
