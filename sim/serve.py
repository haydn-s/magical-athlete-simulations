"""
Local web server for the results viewer: python -m sim serve

Serves saved runs from results/ as JSON under /api, the built React app from
web/dist, and starts new runs in the background. Binds to 127.0.0.1 by default.

    GET  /api/runs                    run list (manifest + totals for each run)
    GET  /api/runs/<id>               full summary.json for one run
    GET  /api/runs/<id>/files/<name>  download racers.csv, head_to_head.csv, ...
    GET  /api/runs/<id>/games         game numbers and lineups (?racer=&start=&limit=)
    GET  /api/runs/<id>/games/<n>     turn-by-turn replay of game n
    GET  /api/roster                  racers, tracks and limits for the run form
    GET  /api/jobs                    runs started from the viewer, newest first (kept across restarts)
    GET  /api/jobs/<id>               one job's state and progress
    POST /api/jobs                    start a run (JSON body, see sim/jobs.py)
    POST /api/jobs/<id>/cancel        stop a queued or running job
    POST /api/jobs/clear              forget finished jobs (their results stay)

Starting runs costs real CPU and writes to results/, so POST requests must be
JSON sent from the viewer's own origin, and on a loopback address requests
must name a loopback host (which blocks DNS-rebinding pages).
"""
import ipaddress
import json
import os
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from sim import batch, roster, tracks
from sim.jobs import DEFAULTS, MAX_GAMES, JobError, JobManager
from sim.replay import find_games, record_game

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
WEB_DIST = os.path.join(ROOT, "web", "dist")

LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
MAX_BODY = 64 * 1024

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


def _hostname(value):
    """Host part of a Host header or Origin URL, lowercased, without port or brackets."""
    if not value:
        return None
    if "://" not in value:
        value = "//" + value
    try:
        return (urlparse(value).hostname or "").lower() or None
    except ValueError:
        return None


def _is_loopback(host):
    if host in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def roster_info():
    found, errors = tracks.scan()
    return {
        "racers": [
            {"name": e.name, "identifier": e.identifier, "default": e.in_default_pool, "variant_of": e.variant_of}
            for e in roster.ROSTER.values()
        ],
        "tracks": [{"key": key, **tracks.track_to_json(t)} for key, t in found.items()],
        "track_errors": [{"key": key, "error": message} for key, message in errors.items()],
        "defaults": DEFAULTS,
        "limits": {"max_games": MAX_GAMES, "cpu_count": os.cpu_count() or 1},
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, store, jobs, loopback_only, **kwargs):
        self.store = store
        self.jobs = jobs
        self.loopback_only = loopback_only
        super().__init__(*args, **kwargs)

    def host_allowed(self):
        if not self.loopback_only:
            return True
        host = _hostname(self.headers.get("Host"))
        return host is not None and _is_loopback(host)

    def do_GET(self):
        if not self.host_allowed():
            return self.send_error(HTTPStatus.FORBIDDEN, "Unexpected Host header")
        url = urlparse(self.path)
        path = url.path
        if path == "/api/runs":
            return self.send_json(self.store.list_runs())
        if path.startswith("/api/runs/"):
            return self.handle_run(unquote(path[len("/api/runs/"):]), parse_qs(url.query))
        if path == "/api/roster":
            return self.send_json(roster_info())
        if path == "/api/jobs":
            return self.send_json(self.jobs.snapshots())
        if path.startswith("/api/jobs/"):
            job = self.jobs.snapshot(unquote(path[len("/api/jobs/"):]))
            if job is None:
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self.send_json(job)
        if path.startswith("/api/"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not os.path.isfile(os.path.join(self.directory, "index.html")):
            return self.send_text(HTTPStatus.NOT_FOUND, "The viewer isn't built yet. Run: cd web && npm install && npm run build\n")
        return super().do_GET()

    def do_POST(self):
        if not self.host_allowed():
            return self.send_error(HTTPStatus.FORBIDDEN, "Unexpected Host header")
        origin = self.headers.get("Origin")
        if origin is not None and not self.same_site(origin):
            return self.send_error(HTTPStatus.FORBIDDEN, "Cross-origin requests aren't allowed")
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send JSON")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_error(HTTPStatus.BAD_REQUEST, "Bad Content-Length")
        if length > MAX_BODY:
            # Read what was sent (up to a limit) so the client sees the 413, not a reset connection.
            self.rfile.read(min(length, 16 * MAX_BODY))
            self.close_connection = True
            return self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json({"error": "The request body isn't valid JSON."}, HTTPStatus.BAD_REQUEST)

        path = urlparse(self.path).path
        if path == "/api/jobs":
            try:
                job = self.jobs.submit(data)
            except JobError as exc:
                return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return self.send_json(job.to_json(), HTTPStatus.ACCEPTED)
        if path == "/api/jobs/clear":
            return self.send_json({"cleared": self.jobs.clear_finished()})
        if path.startswith("/api/jobs/") and path.endswith("/cancel"):
            job = self.jobs.cancel(unquote(path[len("/api/jobs/"):-len("/cancel")]))
            if job is None:
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self.send_json(job)
        return self.send_error(HTTPStatus.NOT_FOUND)

    def same_site(self, origin):
        origin_host = _hostname(origin)
        if origin_host is None:
            return False
        return _is_loopback(origin_host) or origin_host == _hostname(self.headers.get("Host"))

    def handle_run(self, rest, query):
        # <id> | <id>/files/<name> | <id>/games | <id>/games/<n>; ids are plain folder names.
        run_id, *tail = rest.split("/")
        summary = self.store.summary(run_id)
        if summary is None:
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not tail:
            return self.send_json(summary)
        if len(tail) == 2 and tail[0] == "files":
            return self.send_file(run_id, tail[1])
        if tail[0] == "games" and len(tail) <= 2:
            return self.handle_games(summary, tail[1] if len(tail) == 2 else None, query)
        return self.send_error(HTTPStatus.NOT_FOUND)

    def send_file(self, run_id, name):
        if name not in DOWNLOADABLE:
            return self.send_error(HTTPStatus.NOT_FOUND)
        file_path = os.path.join(self.store.run_dir(run_id), name)
        if not os.path.isfile(file_path):
            return self.send_error(HTTPStatus.NOT_FOUND)
        with open(file_path, "rb") as f:
            body = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", DOWNLOADABLE[name])
        self.send_header("Content-Disposition", f'attachment; filename="{run_id}_{name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_games(self, summary, game, query):
        manifest = summary.get("manifest", {})
        try:
            config = batch.config_from_json(manifest["config"])
        except KeyError as exc:
            # Usually a racer or track that has since been renamed or removed.
            message = exc.args[0] if exc.args else str(exc)
            return self.send_json({"error": f"This run can't be replayed with the current code: {message}"},
                                  HTTPStatus.CONFLICT)

        if game is None:
            racer = (query.get("racer") or [None])[0]
            try:
                start = int((query.get("start") or ["0"])[0])
                limit = min(100, max(1, int((query.get("limit") or ["20"])[0])))
            except ValueError:
                return self.send_json({"error": "start and limit must be whole numbers."}, HTTPStatus.BAD_REQUEST)
            games, next_start = find_games(config, racer=racer, start=start, limit=limit)
            return self.send_json({"games": games, "next": next_start, "total": config.games})

        if not game.isdigit() or int(game) >= config.games:
            return self.send_json({"error": f"Game numbers run from 0 to {config.games - 1:,}."},
                                  HTTPStatus.NOT_FOUND)
        replay = record_game(config, int(game))
        replay["code_changed"] = manifest.get("code_fingerprint") != batch.code_fingerprint()
        return self.send_json(replay)

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode()
        self.send_response(status)
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


def make_server(host="127.0.0.1", port=8000, results_dir=RESULTS_DIR, web_dir=WEB_DIST, jobs=None):
    jobs = jobs or JobManager(results_dir)
    handler = partial(
        Handler,
        store=RunStore(results_dir),
        jobs=jobs,
        loopback_only=_is_loopback(host.strip("[]").lower()),
        directory=web_dir,
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.jobs = jobs
    return server


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
        server.jobs.shutdown()
        server.server_close()
