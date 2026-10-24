"""
Running a batch end to end and saving its results.

Shared by `python -m sim run` (sim/cli.py) and the web viewer's run launcher
(sim/jobs.py), so a run started from either one produces the same files.
"""
import csv
import hashlib
import json
import os
import platform
import random
import re
import shlex
import shutil
import subprocess
import time
from datetime import datetime

from sim import roster, tracks
from sim.runner import BatchConfig, run_batch
from sim.stats import Tally, summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")


class Cancelled(Exception):
    """Raised by execute() when should_stop() asks the batch to stop."""


def build_config(*, games, track="wild", players=7, places=2, seed=None,
                 focus=(), include=(), exclude=(), only=()):
    """
    Resolve settings and racer names into (BatchConfig, replaced).
    Raises KeyError or ValueError with a readable message for bad input.
    """
    pool, focus, replaced = roster.build_pool(only=only, include=include, exclude=exclude, focus=focus)
    if seed is None:
        seed = random.SystemRandom().randrange(2 ** 32)
    config = BatchConfig(
        track=tracks.lookup(track),
        pool=tuple(pool),
        focus=tuple(focus),
        games=games,
        racers_per_game=players,
        places_to_award=places,
        seed=seed,
    )
    return config, replaced


def equivalent_command(*, games, track="wild", players=7, places=2, seed=None, focus=(), include=(),
                       exclude=(), only=(), label=None, save_games=False):
    """The `python -m sim run` command line that reproduces these settings."""
    parts = ["python", "-m", "sim", "run", "-n", str(games)]
    if seed is not None:
        parts += ["--seed", str(seed)]
    if track != "wild":
        parts += ["--track", track]
    if players != 7:
        parts += ["--players", str(players)]
    if places != 2:
        parts += ["--places", str(places)]
    for flag, names in (("--focus", focus), ("--only", only), ("--include", include), ("--exclude", exclude)):
        if names:
            parts += [flag, ",".join(names)]
    if label:
        parts += ["--label", label]
    if save_games:
        parts.append("--save-games")
    return " ".join(shlex.quote(p) for p in parts)


def config_to_json(config, track_key, replaced):
    return {
        "games": config.games,
        "seed": config.seed,
        "track": track_key,
        "track_name": config.track.name,
        "racers_per_game": config.racers_per_game,
        "places_to_award": config.places_to_award,
        "focus": [e.name for e in config.focus],
        "pool": [e.name for e in config.pool],
        "replaced": replaced,
        "variants": {e.name: e.variant_of for e in config.pool + config.focus if e.variant_of},
    }


def config_from_json(data, games=None):
    return BatchConfig(
        track=tracks.lookup(data["track"]),
        pool=tuple(roster.lookup(n) for n in data["pool"]),
        focus=tuple(roster.lookup(n) for n in data["focus"]),
        games=games if games is not None else data["games"],
        racers_per_game=data["racers_per_game"],
        places_to_award=data["places_to_award"],
        seed=data["seed"],
    )


def git_state():
    try:
        def git(*cmd):
            return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "*.py"))}
    except (OSError, subprocess.CalledProcessError):
        return None


def code_fingerprint():
    """Hash of the engine and harness source, so a replay can tell if the code changed since a run."""
    digest = hashlib.sha256()
    paths = ["Basics.py", "Events.py", "Powers.py", "Racers.py", "sim/runner.py", "sim/roster.py", "sim/tracks.py"]
    for path in (os.path.join(ROOT, p) for p in paths):
        digest.update(os.path.relpath(path, ROOT).encode())
        with open(path, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:16]


def default_out_dir(label, track_key, config, results_dir=RESULTS_DIR):
    """results/<timestamp>_<label>, made unique if a run already used that name this second."""
    parts = [label] if label else [track_key.lower(), f"{config.games}g"]
    if config.focus and not label:
        parts.append("focus-" + "+".join(e.name for e in config.focus))
    slug = re.sub(r"[^A-Za-z0-9+_.-]", "", re.sub(r"\s+", "-", "_".join(parts).strip()))
    base = os.path.join(results_dir, f"{datetime.now():%Y%m%d-%H%M%S}_{slug}")
    path, n = base, 2
    while os.path.exists(path):
        path, n = f"{base}-{n}", n + 1
    return path


def execute(config, *, track_key, replaced=(), label=None, out_dir=None, workers=None, chunk_size=500,
            save_games=False, sort="pts", command=None, on_progress=None, should_stop=None, mp_context=None):
    """
    Run a batch, save its results to out_dir (if given) and return (summary, tally).

    on_progress(done, total) is called after every chunk. If should_stop() returns
    True the batch stops, nothing is kept, and Cancelled is raised. A folder this
    call created is removed again if the batch doesn't finish.
    """
    workers = workers or os.cpu_count() or 1
    created_dir = bool(out_dir) and not os.path.exists(out_dir)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    games_file = open(os.path.join(out_dir, "games.jsonl"), "w") if out_dir and save_games else None

    tally = Tally(config.places_to_award)
    batches = run_batch(config, workers=workers, chunk_size=chunk_size, keep_records=games_file is not None,
                        mp_context=mp_context)
    started = time.time()
    done = 0

    try:
        for n, part, records in batches:
            tally.merge(part)
            if games_file:
                for record in records:
                    games_file.write(json.dumps(record, separators=(",", ":")) + "\n")
            done += n
            if on_progress:
                on_progress(done, config.games)
            if should_stop and should_stop():
                raise Cancelled()
    except BaseException:
        batches.close()
        if games_file:
            games_file.close()
        if created_dir:
            shutil.rmtree(out_dir, ignore_errors=True)
        raise
    if games_file:
        games_file.close()

    summary = summarize(tally, sort=sort)
    summary["manifest"] = {
        "label": label,
        "created": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "duration_sec": round(time.time() - started, 2),
        "workers": workers,
        "python": platform.python_version(),
        "git": git_state(),
        "code_fingerprint": code_fingerprint(),
        "config": config_to_json(config, track_key.lower(), list(replaced)),
    }

    if out_dir:
        write_results(out_dir, summary, tally)
    return summary, tally


def write_results(out_dir, summary, tally):
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    columns = ["name", "games", "wins", "win_rate", "win_rate_lo", "win_rate_hi", "podium_rate",
               "pts_per_game", "pts_lo", "pts_hi", "avg_place", "avg_progress", "finish_rate",
               "elim_rate", "avg_game_turns"]
    with open(os.path.join(out_dir, "racers.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for r in summary["racers"]:
            row = dict(r, win_rate_lo=r["win_rate_ci"][0], win_rate_hi=r["win_rate_ci"][1],
                       pts_lo=r["pts_ci"][0], pts_hi=r["pts_ci"][1])
            writer.writerow([row[c] for c in columns])

    h2h = summary["head_to_head"]
    with open(os.path.join(out_dir, "head_to_head.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["row placed ahead of column"] + h2h["names"])
        for name, row in zip(h2h["names"], h2h["ahead_rate"]):
            writer.writerow([name] + ["" if v is None else f"{v:.4f}" for v in row])

    if tally.errors:
        with open(os.path.join(out_dir, "errors.jsonl"), "w") as f:
            for error in sorted(tally.errors, key=lambda e: e["game"]):
                f.write(json.dumps(error) + "\n")


def load_summary(path):
    if os.path.isdir(path):
        path = os.path.join(path, "summary.json")
    with open(path) as f:
        return json.load(f)
