import base64
import json
from pathlib import Path
import pytest
from engine.service import process_task
from evaluation.cases import synthetic


@pytest.fixture(autouse=True)
def model_off(monkeypatch):
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","off")


def test_service_returns_original_assets_preview_and_json():
    result = process_task({"source":synthetic(1),"target_canvas":{"width":640,"height":360}},"pillow")
    assert result["audit"]["valid"]
    assert base64.b64decode(result["png"]).startswith(b"\x89PNG")
    assert result["renderer"] == "pillow"
    assert any("NOT official" in warning for warning in result["warnings"])


def test_service_rejects_path_escape():
    source = synthetic(1)
    next(e for e in source["elements"] if e["type"] == "image")["asset_id"] = "../../private.png"
    with pytest.raises(ValueError,match="inside brand_kit"):
        process_task({"source":source,"target_canvas":{"width":640,"height":360}},"pillow")


def test_service_rejects_unbounded_preview():
    with pytest.raises(ValueError,match="4096"):
        process_task({"source":synthetic(1),"target_canvas":{"width":100000,"height":100000}},"pillow")


def test_addon_manifest_and_dom_contract():
    root = Path(__file__).resolve().parents[1]/"addon"
    manifest = json.loads((root/"manifest.json").read_text())
    assert manifest["manifestVersion"] == 2
    assert (root/manifest["entryPoints"][0]["main"]).is_file()
    import re
    ids = set(re.findall(r'id="([^"]+)"',(root/"index.html").read_text()))
    references = set(re.findall(r'\$\("([^"]+)"\)',(root/"app.js").read_text()))
    assert references <= ids
