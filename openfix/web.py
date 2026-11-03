"""Loopback-only local application; model credentials never persist in runs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
from socketserver import TCPServer
import threading
from urllib.parse import parse_qs, urlparse

from .evidence import EvidenceStore
from .model import configuration, request_model
from .runner import bundled_demo, docker_available

ROOT = Path(__file__).resolve().parents[1]


class LoopbackThreadingHTTPServer(ThreadingHTTPServer):
    """HTTP server that avoids a reverse-DNS lookup during local startup."""

    def server_bind(self):
        # HTTPServer.server_bind() calls socket.getfqdn(), which can block on
        # machines whose reverse-DNS resolver is unavailable. TCPServer's bind
        # is sufficient because OpenFix always binds to an explicit loopback IP.
        TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def handler_class(root=None, port=8765):
    store = EvidenceStore(root or ROOT / "artifacts")
    token = secrets.token_urlsafe(32)
    work_lock = threading.Lock()
    trusted_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    for raw_origin in os.environ.get("OPENFIX_TRUSTED_ORIGINS", "").split(","):
        raw_origin = raw_origin.strip().rstrip("/")
        if not raw_origin:
            continue
        parsed_origin = urlparse(raw_origin)
        if (parsed_origin.scheme != "https" or not parsed_origin.netloc
                or parsed_origin.path or parsed_origin.params
                or parsed_origin.query or parsed_origin.fragment
                or parsed_origin.username or parsed_origin.password):
            raise ValueError("OPENFIX_TRUSTED_ORIGINS accepts comma-separated HTTPS origins only")
        trusted_origins.add(raw_origin)
    trusted_hosts = {urlparse(origin).netloc for origin in trusted_origins}

    class Handler(BaseHTTPRequestHandler):
        server_version = "OpenFix/0.3"

        def log_message(self, fmt, *args):
            # Request bodies and API keys are deliberately absent from access logs.
            pass

        def send(self, status, data, content_type="application/json"):
            raw = json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if content_type=="application/json" else data
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def local_request(self):
            host = self.headers.get("Host","")
            if host not in trusted_hosts:
                self.send(403,{"error":"This application accepts configured trusted hosts only"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in trusted_origins:
                self.send(403,{"error":"Cross-origin requests are blocked"})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            parsed = urlparse(self.path)
            route = parsed.path
            try:
                if route == "/api/status":
                    return self.send(200,{"token":token,"model":configuration(),"docker_available":docker_available(),"version":"0.3.0"})
                if route == "/api/runs":
                    return self.send(200,{"runs":store.list()})
                if route.startswith("/api/runs/"):
                    run_id = route.rsplit("/",1)[-1]
                    return self.send(200,{"run":store.read(run_id),"integrity":store.audit(run_id)})
                if route == "/api/artifact":
                    query = parse_qs(parsed.query)
                    run_id, name = query.get("id",[""])[0], query.get("name",[""])[0]
                    record = store.read(run_id)
                    if name not in [a["name"] for a in record["artifacts"]] or Path(name).name != name:
                        raise ValueError("Unknown artifact")
                    path = store.root / run_id / name
                    if path.is_symlink():
                        raise ValueError("Symlink artifacts are not accepted")
                    return self.send(200,path.read_bytes(),"text/plain; charset=utf-8")
                static = {"/":"index.html","/app.js":"app.js","/style.css":"style.css"}
                if route in static:
                    kind = {"/":"text/html; charset=utf-8","/app.js":"application/javascript","/style.css":"text/css"}[route]
                    return self.send(200,(ROOT/"web"/static[route]).read_bytes(),kind)
                return self.send(404,{"error":"Not found"})
            except (ValueError, OSError, KeyError) as exc:
                self.send(400,{"error":str(exc)})

        def do_POST(self):
            if not self.local_request():
                return
            if not secrets.compare_digest(self.headers.get("X-OpenFix-Token",""),token):
                return self.send(403,{"error":"Reload the application before submitting a request"})
            try:
                size = int(self.headers.get("Content-Length","0"))
                if size<=0 or size>200000:
                    raise ValueError("Request body must be between 1 and 200,000 bytes")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data,dict):
                    raise ValueError("Expected a JSON object")
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send(400,{"error":str(exc)})
            if not work_lock.acquire(blocking=False):
                return self.send(409,{"error":"Another investigation step is running"})
            try:
                if self.path == "/api/demo":
                    run = bundled_demo(store)
                elif self.path == "/api/workflow":
                    from .workflow import investigate
                    run = investigate(store,api_key=data.get("api_key") or None,
                                      image=os.environ.get("OPENFIX_DOCKER_IMAGE","openfix-runner:local"),
                                      model=data.get("model") or None)
                elif self.path == "/api/finalize":
                    from .workflow import finalize_candidate
                    run = finalize_candidate(store,data.get("repair_id",""),api_key=data.get("api_key") or None,
                                             image=os.environ.get("OPENFIX_DOCKER_IMAGE","openfix-runner:local"),
                                             model=data.get("model") or None)
                elif self.path == "/api/intake":
                    from .__main__ import intake
                    from .github import ingest
                    url = data.get("issue_url","")
                    if url.rstrip("/")=="https://github.com/facebookresearch/sam3/issues/585" and not data.get("refresh"):
                        source = json.loads((ROOT/"examples/sam3-585.json").read_text())
                        record = intake(source)
                        record["intake_source"] = "bundled snapshot; revision is pinned, current issue/PR state has not been rechecked"
                        source_files = {"sam3/eval/cgf1_eval.py":(ROOT/"vendor/sam3/cgf1_eval.py").read_text()}
                    else:
                        paths = data.get("source_paths",[])
                        if not isinstance(paths,list) or len(paths)>3:
                            raise ValueError("Supply at most three source paths")
                        source = ingest(url, paths)
                        record = intake(source)
                        record.update({k:source[k] for k in ("title","issue_state","retrieved_at","related_pull_requests")})
                        source_files = source["source_files"]
                    record.update({"kind":"intake","source_files":source_files})
                    run = store.create(record)
                elif self.path == "/api/model":
                    parent = store.read(data.get("run_id",""))
                    record = parent["record"]
                    context_id = record.get("investigation_id")
                    investigation = store.read(context_id)["record"] if context_id else record
                    source_files = investigation.get("source_files",{})
                    if source_files:
                        source = json.dumps(source_files,ensure_ascii=False)
                    elif record.get("kind")=="sam3_demo" or investigation.get("issue_url")=="https://github.com/facebookresearch/sam3/issues/585":
                        source = (ROOT/"vendor/sam3/cgf1_eval.py").read_text()
                    else:
                        raise ValueError("Add source file paths during intake before requesting a diagnosis")
                    task = data.get("action","diagnose")
                    if task=="repair" and investigation.get("issue_url")!="https://github.com/facebookresearch/sam3/issues/585":
                        raise ValueError("Repair proposal support is currently limited to the SAM 3 demonstration")
                    execution = record if record.get("kind")=="sam3_demo" else None
                    if record.get("kind","").startswith("model_"):
                        execution = {"previous_proposal":record,"parent_evidence_id":record.get("parent_evidence_id")}
                    result = request_model(investigation,source,action=task,api_key=data.get("api_key") or None,
                                           execution=execution,model=data.get("model") or None)
                    result.update({"parent_evidence_id":parent["id"], "investigation_id":context_id or parent["id"],
                                   "issue_url":investigation.get("issue_url"),"revision":investigation.get("revision")})
                    artifacts = {}
                    if result.get("proposal") and isinstance(result["proposal"].get("unified_diff"),str):
                        artifacts["model-proposal.patch"] = result["proposal"]["unified_diff"]
                        result["verification_status"] = "not_executed; Docker verification required"
                    run = store.create(result,artifacts)
                elif self.path == "/api/verify":
                    from .verification import verify_proposal
                    run = verify_proposal(store,data.get("run_id",""),os.environ.get("OPENFIX_DOCKER_IMAGE","openfix-runner:local"))
                else:
                    return self.send(404,{"error":"Not found"})
                self.send(200,{"run":run,"integrity":store.audit(run["id"])})
            except (OSError, ValueError, KeyError, RuntimeError, TypeError) as exc:
                self.send(400,{"error":str(exc)})
            finally:
                work_lock.release()

    return Handler


def serve(root=None, port=8765):
    Handler = handler_class(root, port)
    server = LoopbackThreadingHTTPServer(("127.0.0.1",port), Handler)
    print(f"OpenFix Lab: http://127.0.0.1:{port}", flush=True)
    print("Only reviewed bundled fixtures run on the host. Repository execution requires Docker.",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
