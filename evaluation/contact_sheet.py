"""Render hidden-style designs at several formats into one PNG for visual review.

    python -m evaluation.contact_sheet out.png 1 13 25          # design seeds
    TARGETS=ig_post,leaderboard python -m evaluation.contact_sheet out.png 7

Each row is one design: its source, then the engine's output at each target,
rendered by the official cr-renderer with a mock judge kit (unknown asset names
aliased to real files).
"""
import os
import sys

from PIL import Image, ImageDraw

from engine.resize import resize_with_diagnostics
from evaluation.hidden_cases import FMT, design, mock_judge_kit

DEFAULT_TARGETS = "ig_post,ig_story,yt_thumb,linkedin_banner,leaderboard,med_rect,skyscraper"


def main() -> None:
    from renderer.converter.convert import render_design_to_png

    out_path, seeds = sys.argv[1], [int(s) for s in sys.argv[2:]]
    targets = os.environ.get("TARGETS", DEFAULT_TARGETS).split(",")
    kit = mock_judge_kit()
    rows = []
    for seed in seeds:
        arch, fmt, src = design(seed)
        tiles = []
        for t in [None] + targets:
            if t is None:
                d, label = src, f"#{seed} {arch} source {fmt}"
            else:
                d, diag = resize_with_diagnostics(src, dict(zip(("width", "height"), FMT[t])))
                label = f"{t} · {(diag.get('reflow') or {}).get('layout') or diag['engine']}"[:44]
            tmp = kit.parent / "tile.png"
            render_design_to_png(d, str(kit / "assets"), str(tmp))
            tiles.append((Image.open(tmp).convert("RGB"), label))
        rows.append(tiles)
    cell = 300
    sheet = Image.new("RGB", (cell * (len(targets) + 1), (cell + 18) * len(rows)), (230, 230, 230))
    draw = ImageDraw.Draw(sheet)
    for r, tiles in enumerate(rows):
        for c, (im, label) in enumerate(tiles):
            k = min((cell - 6) / im.width, (cell - 6) / im.height)
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))))
            x, y = c * cell, r * (cell + 18)
            sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
            draw.text((x + 3, y + cell + 3), label, fill=(0, 0, 0))
    sheet.save(out_path)
    print(out_path)


if __name__ == "__main__":
    main()
