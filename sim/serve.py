"""
Local web server for the results viewer: python -m sim serve

Serves saved runs from results/ as JSON under /api, and the built React app
from web/dist. Binds to 127.0.0.1 by default; nothing here writes to disk.

    GET /api/runs                    run list (manifest + totals for each run)
    GET /api/runs/<id>               full summary.json for one run
    GET /api/runs/<id>/files/<name>  download racers.csv, head_to_head.csv, ...
"""
import json
import os
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
WEB_DIST = os.path.join(ROOT, "web", "dist")

DOWNLOADABLE = {
    "summary.json": "application/json",
    "racers.csv": "text/csv",
    "head_to_head.csv": "text/csv",
    "errors.jsonl": "application/x-ndjson",
}


class RunStore:
    def __init__(self, results_dir):
        self.results_dir = results_dir
        self._cache = {}  # path -> (mtime, parsed summary)

    def run_dir(self, run_id):
        """The folder for a run id, or None. Ids are plain folder names under results/."""
        if not run_id or run_id in (".", "..") or "/" in run_id or "\\" in run_id:
            return None
        path = os.path.join(self.results_dir, run_id)
        if not os.path.isfile(os.path.join(path, "summary.json")):
            return None
        return path

    def summary(self, run_id):
        path = self.run_dir(run_id)
        if path is None:
            return None
        summary_path = os.path.join(path, "summary.json")
        mtime = os.path.getmtime(summary_path)
        cached = self._cache.get(summary_path)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(summary_path) as f:
            data = json.load(f)
        self._cache[summary_path] = (mtime, data)
        return data

    def list_runs(self):
        if not os.path.isdir(self.results_dir):
            return []
        runs = []
        for run_id in os.listdir(self.results_dir):
            try:
                summary = self.summary(run_id)
            except (OSError, ValueError):
                continue
            if summary is None:
                continue
            runs.append({
                "id": run_id,
                "manifest": summary.get("manifest", {}),
                "totals": summary.get("totals", {}),
                "racer_count": len(summary.get("racers", [])),
            })
        runs.sort(key=lambda r: r["manifest"].get("created", ""), reverse=True)
        return runs


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, store, **kwargs):
        self.store = store
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/runs":
            return self.send_json(self.store.list_runs())
        if path.startswith("/api/runs/"):
            return self.handle_run(unquote(path[len("/api/runs/"):]))
        if path.startswith("/api/"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not os.path.isfile(os.path.join(self.directory, "index.html")):
            return self.send_text(HTTPStatus.NOT_FOUND, "The viewer isn't built yet. Run: cd web && npm install && npm run build\n")
        return super().do_GET()

    def handle_run(self, rest):
        run_id, _, tail = rest.partition("/files/")
        if tail:
            if tail not in DOWNLOADABLE:
                return self.send_error(HTTPStatus.NOT_FOUND)
            run_dir = self.store.run_dir(run_id)
            file_path = run_dir and os.path.join(run_dir, tail)
            if not file_path or not os.path.isfile(file_path):
                return self.send_error(HTTPStatus.NOT_FOUND)
            with open(file_path, "rb") as f:
                body = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", DOWNLOADABLE[tail])
            self.send_header("Content-Disposition", f'attachment; filename="{run_id}_{tail}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        summary = self.store.summary(run_id)
        if summary is None:
            return self.send_error(HTTPStatus.NOT_FOUND)
        return self.send_json(summary)

    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status, text):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def make_server(host="127.0.0.1", port=8000, results_dir=RESULTS_DIR, web_dir=WEB_DIST):
    handler = partial(Handler, store=RunStore(results_dir), directory=web_dir)
    return ThreadingHTTPServer((host, port), handler)


def serve(host="127.0.0.1", port=8000, results_dir=RESULTS_DIR):
    server = make_server(host, port, results_dir)
    print(f"Results viewer at http://{host}:{server.server_port}  (results from {os.path.relpath(results_dir)})", flush=True)
    if not os.path.isfile(os.path.join(WEB_DIST, "index.html")):
        print("The UI isn't built yet, so only /api is available. Build it with: cd web && npm install && npm run build", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
