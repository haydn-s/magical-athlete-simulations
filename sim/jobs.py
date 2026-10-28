"""
Background batch runs started from the web viewer (POST /api/jobs).

Jobs run one at a time on a worker thread (each batch already uses every CPU
core) and save their results to results/ exactly like `python -m sim run`.
The job list is kept in results/.jobs.json, so it survives server restarts;
jobs that were running when the server stopped come back as "interrupted".
"""
import json
import os
import queue
import secrets
import shutil
import threading
import time
from collections import OrderedDict

from sim import batch, settings as power_settings, tracks

MAX_GAMES = 2_000_000
MAX_NAMES = 200
MAX_LABEL = 60
KEEP_FINISHED = 50
HISTORY_FILE = ".jobs.json"
HISTORY_LIMIT = 200
SAVE_PROGRESS_EVERY = 5  # seconds

DEFAULTS = {"games": 10_000, "track": "wild", "players": 7, "places": 2}
ACTIVE_STATES = ("queued", "running")
INTERRUPTED = "The server stopped before this run finished, so nothing was saved."


class JobError(ValueError):
    """A request the server should reject with 400 Bad Request."""


def _int(data, key, default, lo, hi):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise JobError(f"{key} must be a whole number.")
    if not lo <= value <= hi:
        raise JobError(f"{key} must be between {lo:,} and {hi:,}.")
    return value


def _names(data, key):
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(n, str) and 0 < len(n) <= 64 for n in value):
        raise JobError(f"{key} must be a list of racer names.")
    if len(value) > MAX_NAMES:
        raise JobError(f"{key} can list at most {MAX_NAMES} racers.")
    return value


def _optional_str(data, key, limit):
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise JobError(f"{key} must be text of at most {limit} characters.")
    return value.strip() or None


def parse_request(data):
    """Validate a job request. Returns (settings, config, replaced) or raises JobError."""
    if not isinstance(data, dict):
        raise JobError("Expected a JSON object.")
    known = {"games", "track", "players", "places", "seed", "focus", "include", "exclude", "only",
             "label", "save_games", "workers", "from_run", "overrides"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise JobError(f"Unknown setting: {', '.join(unknown)}.")

    seed = data.get("seed")
    if seed is not None:
        seed = _int(data, "seed", None, 0, 2 ** 63 - 1)
    track = data.get("track", DEFAULTS["track"])
    if not isinstance(track, str):
        raise JobError("track must be a track key.")
    save_games = data.get("save_games", False)
    if not isinstance(save_games, bool):
        raise JobError("save_games must be true or false.")
    workers = data.get("workers")
    if workers is not None:
        workers = _int(data, "workers", None, 1, os.cpu_count() or 1)

    raw_overrides = data.get("overrides", [])
    if not isinstance(raw_overrides, list) or len(raw_overrides) > 20:
        raise JobError("overrides must be a list of {power, setting, value}.")
    overrides = []
    for item in raw_overrides:
        if not isinstance(item, dict) or set(item) != {"power", "setting", "value"}:
            raise JobError("Each override needs exactly power, setting and value.")
        try:
            overrides.append(power_settings.check_override(item["power"], item["setting"], item["value"]))
        except ValueError as exc:
            raise JobError(str(exc)) from None

    settings = {
        "games": _int(data, "games", DEFAULTS["games"], 1, MAX_GAMES),
        "track": track,
        "players": _int(data, "players", DEFAULTS["players"], 2, 20),
        "places": _int(data, "places", DEFAULTS["places"], 1, 20),
        "seed": seed,
        "focus": _names(data, "focus"),
        "include": _names(data, "include"),
        "exclude": _names(data, "exclude"),
        "only": _names(data, "only"),
        "overrides": overrides,
    }
    try:
        config, replaced = batch.build_config(**settings)
    except (KeyError, ValueError) as exc:
        raise JobError(exc.args[0] if exc.args else str(exc)) from None

    settings["seed"] = config.seed  # a random seed is fixed now, so the job can show it
    settings["track"] = tracks.track_key(track)
    settings["label"] = _optional_str(data, "label", MAX_LABEL)
    settings["save_games"] = save_games
    settings["workers"] = workers
    settings["from_run"] = _optional_str(data, "from_run", 200)
    settings["overrides"] = [{"power": c, "setting": k, "value": v} for c, k, v in config.overrides]
    return settings, config, replaced


class Job:
    def __init__(self, settings, config, replaced):
        self.id = secrets.token_hex(6)
        self.settings = settings
        self.config = config
        self.replaced = replaced
        self.command = batch.equivalent_command(
            **{k: settings[k] for k in ("games", "track", "players", "places", "seed", "focus",
                                        "include", "exclude", "only", "label", "save_games")},
            overrides=config.overrides,
        )
        self.state = "queued"
        self.done = 0
        self.created = time.time()
        self.started = None
        self.finished = None
        self.run_id = None
        self.folder = None  # results/ folder being written while running
        self.error = None
        self.cancel_requested = threading.Event()

    def to_json(self):
        now = self.finished or time.time()
        elapsed = now - self.started if self.started else 0.0
        rate = self.done / elapsed if elapsed > 0 else 0.0
        remaining = (self.config.games - self.done) / rate if self.state == "running" and rate > 0 else None
        return {
            "id": self.id,
            "state": self.state,
            "label": self.settings["label"],
            "settings": self.settings,
            "command": self.command,
            "replaced": self.replaced,
            "done": self.done,
            "total": self.config.games,
            "created": self.created,
            "started": self.started,
            "finished": self.finished,
            "elapsed_sec": round(elapsed, 2),
            "rate": round(rate, 1),
            "remaining_sec": None if remaining is None else round(remaining, 1),
            "run_id": self.run_id,
            "folder": self.folder,
            "error": self.error,
        }


class JobManager:
    def __init__(self, results_dir=batch.RESULTS_DIR, mp_context="spawn", keep_history=True):
        self.results_dir = results_dir
        self.mp_context = mp_context
        self._jobs = OrderedDict()  # this session's jobs
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._thread = None
        self._history_path = os.path.join(results_dir, HISTORY_FILE) if keep_history else None
        self._history = self._load_history()  # snapshots from earlier sessions, newest first

    def submit(self, data):
        job = Job(*parse_request(data))
        with self._lock:
            self._jobs[job.id] = job
            self._trim()
            self._save()
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, name="sim-jobs", daemon=True)
                self._thread.start()
        self._queue.put(job)
        return job

    def get(self, job_id):
        """A job from this session (None for older ones; see snapshot())."""
        with self._lock:
            return self._jobs.get(job_id)

    def list(self):
        """This session's jobs, newest first."""
        with self._lock:
            return list(reversed(self._jobs.values()))

    def snapshots(self):
        """Every job as JSON-ready data, this session's first, then earlier ones."""
        with self._lock:
            live = [job.to_json() for job in reversed(self._jobs.values())]
            ids = {entry["id"] for entry in live}
            return live + [entry for entry in self._history if entry["id"] not in ids]

    def snapshot(self, job_id):
        return next((entry for entry in self.snapshots() if entry["id"] == job_id), None)

    def cancel(self, job_id):
        """Stop a queued or running job. Returns its snapshot, or None if there's no such job."""
        job = self.get(job_id)
        if job is not None and job.state in ACTIVE_STATES:
            job.cancel_requested.set()
            if job.state == "queued":
                job.state = "cancelled"
                job.finished = time.time()
                with self._lock:
                    self._save()
        return self.snapshot(job_id)

    def clear_finished(self):
        """Forget every job that isn't queued or running. Returns how many were removed."""
        with self._lock:
            finished = [job_id for job_id, job in self._jobs.items() if job.state not in ACTIVE_STATES]
            for job_id in finished:
                del self._jobs[job_id]
            removed = len(finished) + len(self._history)
            self._history = []
            self._save()
        return removed

    def wait(self, job_id, timeout=None):
        """Block until a job finishes (for tests and scripts). Returns the job."""
        deadline = None if timeout is None else time.time() + timeout
        job = self.get(job_id)
        while job is not None and job.state in ACTIVE_STATES:
            if deadline is not None and time.time() > deadline:
                raise TimeoutError(f"Job {job_id} still {job.state}.")
            time.sleep(0.02)
        return job

    def shutdown(self):
        for job in self.list():
            self.cancel(job.id)
        self._queue.put(None)

    def _load_history(self):
        if not self._history_path:
            return []
        try:
            with open(self._history_path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        entries = [e for e in data if isinstance(e, dict) and isinstance(e.get("id"), str)] if isinstance(data, list) else []
        for entry in entries:
            if entry.get("state") in ACTIVE_STATES:
                entry.update(state="interrupted", error=INTERRUPTED, remaining_sec=None)
                self._remove_partial_run(entry.get("folder"))
        return entries

    def _remove_partial_run(self, folder):
        """Delete the half-written folder of a run the server stopped mid-way (never a finished run)."""
        if not isinstance(folder, str) or not folder or folder.startswith(".") or os.sep in folder or "/" in folder:
            return
        path = os.path.join(self.results_dir, folder)
        if os.path.isdir(path) and not os.path.exists(os.path.join(path, "summary.json")):
            shutil.rmtree(path, ignore_errors=True)

    def _save(self):
        """Write the job list to results/.jobs.json. Call with the lock held; failures are ignored."""
        if not self._history_path:
            return
        live = [job.to_json() for job in reversed(self._jobs.values())]
        ids = {entry["id"] for entry in live}
        entries = (live + [entry for entry in self._history if entry["id"] not in ids])[:HISTORY_LIMIT]
        temp = self._history_path + ".tmp"
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            with open(temp, "w") as f:
                json.dump(entries, f)
            os.replace(temp, self._history_path)
        except OSError:
            pass  # history is a convenience; never let it stop a run

    def _trim(self):
        finished = [j for j in self._jobs.values() if j.state not in ACTIVE_STATES]
        for job in finished[: max(0, len(finished) - KEEP_FINISHED)]:
            del self._jobs[job.id]

    def _work(self):
        while True:
            job = self._queue.get()
            if job is None:
                return
            if job.cancel_requested.is_set():
                continue
            self._run(job)

    def _run(self, job):
        settings = job.settings
        out_dir = batch.default_out_dir(settings["label"], settings["track"], job.config, self.results_dir)
        job.state = "running"
        job.started = time.time()
        job.folder = os.path.basename(out_dir)
        with self._lock:
            self._save()
        last_save = time.time()

        def progress(done, total):
            nonlocal last_save
            job.done = done
            if time.time() - last_save >= SAVE_PROGRESS_EVERY:
                last_save = time.time()
                with self._lock:
                    self._save()

        try:
            batch.execute(
                job.config,
                track_key=settings["track"],
                replaced=job.replaced,
                label=settings["label"],
                out_dir=out_dir,
                workers=settings["workers"],
                save_games=settings["save_games"],
                command=job.command,
                on_progress=progress,
                should_stop=job.cancel_requested.is_set,
                mp_context=self.mp_context,
                isolate=True,  # never run games in the server process (see sim/settings.py)
            )
        except batch.Cancelled:
            job.state = "cancelled"
            job.folder = None  # execute() already removed it
        except Exception as exc:
            job.state = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            job.folder = None
        else:
            job.run_id = job.folder
            job.state = "done"
        finally:
            job.finished = time.time()
            with self._lock:
                self._save()
