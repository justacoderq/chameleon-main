"""Read-only preflight; exit nonzero when required submission dependencies are missing."""
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    modules = {name:importlib.util.find_spec(name) is not None for name in
               ("PIL","jsonschema","cr_renderer","torch","transformers","safetensors")}
    report = {"python":sys.version,"platform":platform.platform(),"dependencies":modules,
              "docker":shutil.which("docker"),"local_model":(root/"models/flan-t5-small/model.safetensors").is_file(),
              "model_manifest":(root/"models/manifest.json").is_file()}
    print(json.dumps(report,indent=2))
    return 0 if all(modules.values()) and report["local_model"] and report["docker"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
