"""Build the README animations from real engine output.

Every frame is a design rendered by the official cr-renderer; nothing is mocked.

    python -m scripts.make_readme_media          # writes docs/media/*.gif
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.analyze import analyze
from engine.layout import Ctx, candidates
from engine.preview import render
from engine.reflow import emit
from engine.resize import resize_with_diagnostics
from evaluation.audit import audit
from evaluation.run import stretch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media"
FRAME = (960, 540)
STAGE = (900, 410)          # area the rendered design is fitted into
BG = (24, 24, 29)
FG = (236, 236, 240)
DIM = (150, 150, 160)
ACCENT = (232, 106, 51)

TMP = Path(tempfile.mkdtemp(prefix="chameleon-media-"))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    fonts = sorted((ROOT / "brand_kit" / "fonts").glob("*.[ot]tf"))
    want = [f for f in fonts if ("Bold" in f.name) == bold and "Italic" not in f.name and "Sans" in f.name]
    try:
        return ImageFont.truetype(str((want or fonts)[0]), size)
    except Exception:
        return ImageFont.load_default()


def load(name: str) -> dict:
    return json.loads((ROOT / "input" / f"chameleon_sample_{name}.json").read_text())["source"]


def rendered(design: dict, tag: str) -> Image.Image:
    path = TMP / f"{tag}.png"
    render(design, path, "official")
    return Image.open(path).convert("RGB")


def frame(img: Image.Image, title: str, sub: str = "", badge: str = "", border=None) -> Image.Image:
    canvas = Image.new("RGB", FRAME, BG)
    k = min(STAGE[0] / img.width, STAGE[1] / img.height)   # small banners are scaled up to be legible
    im = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
    x = (FRAME[0] - im.width) // 2
    y = 22 + (STAGE[1] - im.height) // 2
    if border:
        ImageDraw.Draw(canvas).rectangle((x - 4, y - 4, x + im.width + 3, y + im.height + 3), outline=border, width=4)
    canvas.paste(im, (x, y))
    d = ImageDraw.Draw(canvas)
    d.text((30, FRAME[1] - 92), title, font=font(28, True), fill=FG)
    if sub:
        d.text((30, FRAME[1] - 52), sub, font=font(19), fill=DIM)
    if badge:
        f = font(20, True)
        w = d.textlength(badge, font=f)
        d.rounded_rectangle((FRAME[0] - w - 58, FRAME[1] - 90, FRAME[0] - 30, FRAME[1] - 56), 14, fill=ACCENT)
        d.text((FRAME[0] - w - 44, FRAME[1] - 86), badge, font=f, fill=(255, 255, 255))
    return canvas


def save_gif(frames, durations, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pal = [f.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(OUT / name, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    print(OUT / name, f"{(OUT / name).stat().st_size / 1e6:.1f} MB")


FORMATS = [
    ("Source design", None),
    ("Instagram post", (1080, 1080)),
    ("Instagram story", (1080, 1920)),
    ("YouTube thumbnail", (1280, 720)),
    ("LinkedIn banner", (1584, 396)),
    ("Pinterest pin", (1000, 1500)),
    ("Leaderboard ad", (728, 90)),
    ("Medium rectangle ad", (300, 250)),
    ("Wide skyscraper ad", (160, 600)),
    ("Billboard ad", (970, 250)),
    ("Mobile banner ad", (468, 60)),
]


def tour(name: str, gif: str) -> None:
    src = load(name)
    frames, durs = [], []
    for label, size in FORMATS:
        if size is None:
            design, sub = src, f"{src['canvas']['width']}×{src['canvas']['height']} · {len(src['elements'])} elements"
        else:
            design, diag = resize_with_diagnostics(src, {"width": size[0], "height": size[1]})
            layout = (diag.get("reflow") or {}).get("layout", diag["engine"]) if diag["engine"] == "reflow" else "partition search"
            sub = f"{size[0]}×{size[1]} · layout: {layout.split('-')[0]}"
        frames.append(frame(rendered(design, f"{name}-{label}"), label, sub))
        durs.append(1600)
    save_gif(frames, durs, gif)


def search(name: str, size, gif: str, keep: int = 7) -> None:
    src = load(name)
    an = analyze(src)
    ctx = Ctx(an, float(size[0]), float(size[1]))
    cands = candidates(ctx)
    best = max(cands, key=lambda c: c.score)
    # one candidate per layout family/variant, worst to best, so the search reads left to right
    seen, picked = set(), []
    for c in sorted(cands, key=lambda c: c.score):
        fam = c.name.replace("-box", "")
        if fam not in seen:
            seen.add(fam)
            picked.append(c)
    picked = picked[-keep:]
    if best not in picked:
        picked[-1] = best
    frames, durs = [], []
    for i, c in enumerate(picked, 1):
        d = c.detail
        sub = (f"score {c.score:+.2f} · legibility {d['q']:.2f} · overlap {d['overlap']:.2f}"
               f" · demoted {d['demoted']:.2f}")
        win = c is best
        img = rendered(emit(src, an, ctx, c), f"cand-{i}")
        frames.append(frame(img, f"Candidate {i}/{len(picked)}: {c.name}", sub,
                            badge="chosen" if win else "", border=ACCENT if win else None))
        durs.append(3200 if win else 1500)
    save_gif(frames, durs, gif)


def _facts(src: dict, design: dict, tgt: dict) -> str:
    """The contract audit's own findings for this output, stated plainly."""
    a = audit(src, design, tgt)
    if not a["valid"]:
        return f"fails the output contract ({len(a['hard_errors'])} hard errors)"
    return (f"valid · {a.get('text_overflows', 0)} text overflows · {a.get('collisions', 0)} collisions"
            f" · {a.get('small_texts', 0)} texts under 10px")


def versus(cases, gif: str) -> None:
    frames, durs = [], []
    for name, size in cases:
        src = load(name)
        tgt = {"width": size[0], "height": size[1]}
        ours, _ = resize_with_diagnostics(src, tgt)
        naive = stretch(src, tgt)
        tag = f"{size[0]}×{size[1]}"
        frames.append(frame(rendered(naive, f"st-{name}"), f"Naive scaling · {tag}", _facts(src, naive, tgt)))
        frames.append(frame(rendered(ours, f"ours-{name}"), f"Chameleon · {tag}", _facts(src, ours, tgt),
                            badge="ours", border=ACCENT))
        durs += [1800, 2600]
    save_gif(frames, durs, gif)


if __name__ == "__main__":
    tour("level3_advanced", "tour-level3.gif")
    tour("level2_core", "tour-level2.gif")
    search("level2_core", (1600, 400), "search-level2.gif")
    versus([("level3_advanced", (728, 90)), ("level2_core", (1600, 400)), ("level1_warmup", (1080, 1350))],
           "stretch-vs-chameleon.gif")
