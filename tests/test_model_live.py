"""Opt in: actual safetensors inference with outgoing connections blocked."""
import os
import socket
import pytest


@pytest.mark.skipif(os.environ.get("CHAMELEON_TEST_LIVE_MODEL") != "1",reason="Set CHAMELEON_TEST_LIVE_MODEL=1 for actual local inference")
def test_real_model_runs_without_network(monkeypatch):
    from engine.resize import resize_with_diagnostics
    from evaluation.audit import audit
    from evaluation.cases import synthetic
    def forbidden(*args,**kwargs):
        raise AssertionError("Model attempted network access")
    monkeypatch.setattr(socket.socket,"connect",forbidden)
    monkeypatch.setattr(socket,"create_connection",forbidden)
    monkeypatch.setenv("CHAMELEON_MODEL_MODE","required")
    source,target = synthetic(3),{"width":1280,"height":720}
    out,diagnostics = resize_with_diagnostics(source,target)
    assert diagnostics["model"]["status"] == "used"
    assert audit(source,out,target)["valid"]
