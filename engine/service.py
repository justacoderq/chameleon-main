"""Local panel service; no cloud inference. HTTPS is supported for Express development."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import ssl
import tempfile

from engine.resize import resize_with_diagnostics
from engine.preview import render
from evaluation.audit import audit, validator

ROOT = Path(__file__).resolve().parents[1]


def process_task(task, renderer="official"):
    source, target = task["source"], task["target_canvas"]
    validator().validate(source)
    if len(source["elements"]) > 200:
        raise ValueError("Interactive preview supports at most 200 elements; batch engine has no such cap")
    for canvas in (source["canvas"],target):
        if any(not isinstance(canvas.get(k),int) or not 1 <= canvas[k] <= 4096 for k in ("width","height")):
            raise ValueError("Interactive canvas dimensions must be between 1 and 4096")
    assets = (ROOT/"brand_kit/assets").resolve()
    for e in source["elements"]:
        if e["type"] == "image":
            candidate = (assets/e["asset_id"]).resolve()
            if not candidate.is_relative_to(assets):
                raise ValueError("Asset references must stay inside brand_kit/assets")
    output, diagnostics = resize_with_diagnostics(source,target)
    result = audit(source,output,target)
    if not result["valid"]:
        raise ValueError("Output contract failed: " + "; ".join(result["hard_errors"]))
    with tempfile.TemporaryDirectory(prefix="chameleon-preview-") as tmp:
        out_path, src_path = Path(tmp)/"result.png", Path(tmp)/"source.png"
        warnings = render(output,out_path,renderer) + render(source,src_path,renderer)
        encoded = {"png":base64.b64encode(out_path.read_bytes()).decode("ascii"),
                   "source_png":base64.b64encode(src_path.read_bytes()).decode("ascii")}
    return {"design":output,"diagnostics":diagnostics,"audit":result,"renderer":renderer,"warnings":warnings,**encoded}


class Handler(BaseHTTPRequestHandler):
    renderer = "official"

    def reply(self, status, body, content_type="application/json"):
        if isinstance(body,dict):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = self.path.split("?",1)[0]
        if route == "/health":
            return self.reply(200,{"status":"ready","renderer":self.renderer,"model_mode":os.environ.get("CHAMELEON_MODEL_MODE","auto")})
        if route == "/samples":
            return self.reply(200,{p.stem:json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT/"input").glob("*.json"))})
        files = {"/":("index.html","text/html"),"/index.html":("index.html","text/html"),
                 "/app.js":("app.js","text/javascript"),"/styles.css":("styles.css","text/css"),
                 "/manifest.json":("manifest.json","application/json")}
        if route not in files:
            return self.reply(404,{"error":"Not found"})
        name,content_type = files[route]
        self.reply(200,(ROOT/"addon"/name).read_bytes(),content_type)

    def do_POST(self):
        if self.path != "/resize":
            return self.reply(404,{"error":"Not found"})
        # Same-origin panel only; no wildcard CORS grants to other websites.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{self.headers.get('Host')}", f"https://{self.headers.get('Host')}"):
            return self.reply(403,{"error":"Cross-origin request rejected"})
        try:
            length = int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 2_000_000:
                return self.reply(413,{"error":"Request must be 1 byte to 2 MB"})
            task = json.loads(self.rfile.read(length))
            result = process_task(task,self.renderer)
            self.reply(200,result)
        except Exception as exc:
            self.reply(400,{"error":str(exc)})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",type=int,default=5241)
    p.add_argument("--renderer",choices=["official","pillow"],default="official")
    p.add_argument("--model",choices=["off","auto","required"],default="auto")
    p.add_argument("--cert",type=Path)
    p.add_argument("--key",type=Path)
    args = p.parse_args()
    if bool(args.cert) != bool(args.key):
        p.error("--cert and --key must be provided together")
    os.environ["CHAMELEON_MODEL_MODE"] = args.model
    Handler.renderer = args.renderer
    server = HTTPServer(("127.0.0.1",args.port),Handler)
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert,args.key)
        server.socket = context.wrap_socket(server.socket,server_side=True)
    print(f"Chameleon panel: {'https' if args.cert else 'http'}://localhost:{args.port}",flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
