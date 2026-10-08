from copy import deepcopy
import json
import math
from pathlib import Path
import socket

import pytest

from engine.resize import resize, resize_with_diagnostics
from engine.typography import measure
from engine.local_model import decode_roles, infer
from evaluation.audit import audit
from evaluation.cases import TARGETS, synthetic, mutate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline_ablation(monkeypatch):
    monkeypatch.setenv("CHAMELEON_MODEL_MODE", "off")
    def no_network(*args, **kwargs):
        raise AssertionError("Runtime network access forbidden")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("size", TARGETS)
def test_synthetic_contract(seed, size):
    source = synthetic(seed)
    original = deepcopy(source)
    target = dict(zip(("width","height"),size))
    output = resize(source,target)
    assert source == original
    assert audit(source,output,target)["hard_errors"] == []


@pytest.mark.parametrize("path", sorted((ROOT/"input").glob("*.json")))
def test_samples_and_id_independence(path):
    task = json.loads(path.read_text())
    source, target = task["source"],task["target_canvas"]
    out = resize(source,target)
    assert audit(source,out,target)["hard_errors"] == []
    assert resize(source,target) == out
    renamed = resize(mutate(source,"renamed"),target)
    for a,b in zip(out["elements"],renamed["elements"]):
        assert [a[k] for k in ("x","y","width","height")] == [b[k] for k in ("x","y","width","height")]


@pytest.mark.parametrize("variant", ["long-copy","rotation"])
def test_adversarial_mutations(variant):
    for seed in range(4):
        source = mutate(synthetic(seed),variant)
        target = {"width":728,"height":90}
        out = resize(source,target)
        assert audit(source,out,target)["hard_errors"] == []


def test_long_unbreakable_word_and_max_lines():
    source = synthetic(0)
    text = next(e for e in source["elements"] if e["type"] == "text")
    text.update(content="SUPERCALIFRAGILISTIC"*5,max_lines=1,letter_spacing=1.5)
    target = {"width":1080,"height":1080}
    out = resize(source,target)
    result = next(e for e in out["elements"] if e["id"] == text["id"])
    assert measure(result)["lines"] == 1
    assert audit(source,out,target)["hard_errors"] == []


def test_explicit_newlines():
    source = synthetic(0)
    text = next(e for e in source["elements"] if e["type"] == "text")
    text["content"] = "One\nTwo\nThree"
    assert measure(text)["lines"] >= 3


def test_zero_size_elements_and_background_only():
    source = synthetic(0)
    source["elements"] = source["elements"][:1]
    assert len(resize(source,{"width":1280,"height":720})["elements"]) == 1
    source["elements"].append({"id":"zero","type":"image","asset_id":"missing.png","x":0,"y":0,"width":0,"height":0})
    out = resize(source,{"width":320,"height":100})
    assert audit(source,out,{"width":320,"height":100})["hard_errors"] == []


def test_duplicate_and_nonfinite_rejected():
    source = synthetic(0)
    source["elements"][1]["id"] = source["elements"][0]["id"]
    with pytest.raises(ValueError):
        resize(source,{"width":100,"height":100})
    source = synthetic(0)
    source["elements"][1]["x"] = math.nan
    with pytest.raises(ValueError):
        resize(source,{"width":100,"height":100})


def test_required_model_does_not_silently_fallback(monkeypatch,tmp_path):
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","required")
    monkeypatch.setenv("CHAMELEON_MODEL_PATH",str(tmp_path/"absent.gguf"))
    with pytest.raises(RuntimeError,match="Required local model failed"):
        resize(synthetic(0),{"width":1000,"height":1000})


def test_auto_model_reports_absence(monkeypatch,tmp_path):
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","auto")
    monkeypatch.setenv("CHAMELEON_MODEL_PATH",str(tmp_path/"absent.gguf"))
    _, diagnostics = resize_with_diagnostics(synthetic(0),{"width":1000,"height":1000})
    assert diagnostics["model"]["status"] == "unavailable"


def test_model_output_validation():
    assert decode_roles({"roles":["headline","cta"]},2) == ["headline","cta"]
    for bad in [[],{}, {"roles":["delete image"]},{"roles":[]}]:
        with pytest.raises(ValueError):
            decode_roles(bad,1)


def test_advisor_integration_with_stub_not_real_inference(monkeypatch):
    import engine.local_model as module
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","required")
    monkeypatch.setattr(module,"infer",lambda path,data: ["headline" for _ in json.loads(data)])
    source = synthetic(0)
    out,diag = resize_with_diagnostics(source,{"width":1000,"height":1000})
    assert diag["model"]["status"] == "used"
    assert audit(source,out,{"width":1000,"height":1000})["valid"]


def test_validator_catches_dishonest_output():
    source = synthetic(0)
    target = {"width":1000,"height":1000}
    out = resize(source,target)
    out["elements"][1]["content"] = "Rewritten"
    out["elements"].append(deepcopy(out["elements"][0]))
    assert not audit(source,out,target)["valid"]


def test_group_geometry_moves_as_one_unit():
    task = json.loads((ROOT/"input/chameleon_sample_level3_advanced.json").read_text())
    output = resize(task["source"],task["target_canvas"])
    before = {e["id"]:e for e in task["source"]["elements"]}
    groups = {}
    for e in output["elements"]:
        if e.get("group_id"):
            groups.setdefault(e["group_id"],[]).append(e)
    for items in groups.values():
        anchor = items[0]
        old_anchor = before[anchor["id"]]
        factor = anchor["width"]/old_anchor["width"]
        for item in items[1:]:
            old = before[item["id"]]
            assert item["width"] == pytest.approx(old["width"]*factor)
            assert item["height"] == pytest.approx(old["height"]*factor)
            assert item["x"]-anchor["x"] == pytest.approx((old["x"]-old_anchor["x"])*factor)
            assert item["y"]-anchor["y"] == pytest.approx((old["y"]-old_anchor["y"])*factor)


def test_contrast_proxy_penalizes_white_on_white():
    from PIL import Image
    from engine.appearance import text_penalty
    el = next(e for e in synthetic(0)["elements"] if e["type"] == "text")
    target = {"width":1000,"height":1000}
    assert text_penalty(el,Image.new("RGB",(96,96),"white"),target,[]) > text_penalty(el,Image.new("RGB",(96,96),"black"),target,[])
