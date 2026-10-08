"""Release check: never substitutes the development renderer for this test."""
import importlib.util
from pathlib import Path
import json
import pytest


@pytest.mark.skipif(importlib.util.find_spec("cr_renderer") is None,reason="Official cr-renderer not installed; release verification pending")
def test_official_sample_pipeline(tmp_path,monkeypatch):
    from PIL import Image
    from engine.resize import resize
    from engine.preview import render
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","off")
    root = Path(__file__).resolve().parents[1]
    for path in (root/"input").glob("*.json"):
        task = json.loads(path.read_text())
        output = resize(task["source"],task["target_canvas"])
        target = tmp_path/(path.stem+".png")
        render(output,target,"official")
        with Image.open(target) as image:
            assert image.width > 0 and image.height > 0
            assert image.getbbox() is not None
