"""
Parameter sweeps: the same batch once for each value of one or more power settings.

    python -m sim sweep --set Sisyphus.STARTING_POINTS=2..6 -n 20000 --seed 7

Every value uses the same seed, so game N has the same lineup, seats and opening
dice at every value; only the setting differs. Each value is saved as a normal
run (every viewer page works on it), and the sweep itself goes to
results/<timestamp>_sweep_<label>/sweep.json. Each value is compared with the
current one game by game, which picks up much smaller changes than comparing
two independent runs.
"""
import itertools
import json
import math
import os
import random
import re
from array import array
from datetime import datetime

from sim import batch, settings, tracks
from sim.stats import Z_95

MAX_POINTS = 50
SWEEP_FILE = "sweep.json"
_NO_GAME = -(2 ** 31)  # marks games a racer wasn't in


def plan(assignments):
    """
    [(power class, setting, values, racer)] -> (points, baseline index).
    Each point is a tuple of (power class, setting, value) overrides. The current
    value of every setting is added if missing, so there's always a baseline.
    """
    axes, seen = [], set()
    for class_name, setting, values, _ in assignments:
        if (class_name, setting) in seen:
            raise settings.SettingError(f"{class_name}.{setting} is set twice.")
        seen.add((class_name, setting))
        current = settings.settings_of(settings.power_classes()[class_name])[setting]
        values = list(values)
        if current not in values:
            numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
            values = sorted(values + [current]) if numeric and values == sorted(values) else [current] + values
        axes.append([(class_name, setting, value, value == current) for value in values])

    points = list(itertools.product(*axes))
    if len(points) > MAX_POINTS:
        raise settings.SettingError(f"That's {len(points)} combinations; a sweep can run at most {MAX_POINTS}.")
    baseline = next(i for i, point in enumerate(points) if all(is_current for *_, is_current in point))
    return [tuple(o[:3] for o in point) for point in points], baseline


def subjects_of(assignments):
    """The racers a sweep is about: those named in --set, else the standard racers with each power."""
    names = []
    for class_name, _, _, racer in assignments:
        for name in [racer] if racer else settings.racers_with(class_name):
            if name not in names:
                names.append(name)
    return names


def point_label(point):
    return ", ".join(f"{setting}={value}" for _, setting, value in point)


def paired_difference(base, other):
    """Mean of other - base over games both played, with a 95% interval (None if too few)."""
    diffs = [o - b for b, o in zip(base, other) if b != _NO_GAME and o != _NO_GAME]
    n = len(diffs)
    if n < 2:
        return None
    mean = sum(diffs) / n
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    half = Z_95 * math.sqrt(variance / n)
    return {
        "games": n,
        "changed": sum(1 for d in diffs if d),
        "delta": mean,
        "ci": [mean - half, mean + half],
        "significant": bool(variance) and abs(mean) > half,
    }


def _compact(racer):
    keys = ("name", "games", "wins", "win_rate", "win_rate_ci", "pts_per_game", "pts_ci", "avg_place", "podium_rate")
    return {k: racer[k] for k in keys}


def _slug(text):
    return re.sub(r"[^A-Za-z0-9+_.=-]", "", re.sub(r"\s+", "-", text.strip()))[:80]


def run_sweep(*, assignments, games, seed=None, track="wild", players=7, places=2, focus=(), include=(),
              exclude=(), only=(), label=None, auto_focus=True, workers=None, results_dir=batch.RESULTS_DIR,
              command=None, on_point=None, on_progress=None, mp_context=None, isolate=False):
    """
    Run every point of a sweep and save it. Returns the sweep summary (as in sweep.json).
    on_point(index, total, point) is called as each point starts.
    """
    points, baseline = plan(assignments)
    subjects = subjects_of(assignments)
    focus = list(focus)
    added = [name for name in subjects if name not in focus] if auto_focus else []
    focus += added
    if seed is None:
        seed = random.SystemRandom().randrange(2 ** 32)

    # Validate everything before any games run.
    configs = [
        batch.build_config(games=games, seed=seed, track=track, players=players, places=places, focus=focus,
                           include=include, exclude=exclude, only=only, overrides=point)
        for point in points
    ]

    created = datetime.now()
    name = _slug(label or "+".join(f"{racer or c}.{setting}" for c, setting, _, racer in assignments))
    sweep_id = f"{created:%Y%m%d-%H%M%S}_sweep_{name or 'settings'}"
    sweep_dir, n = os.path.join(results_dir, sweep_id), 2
    while os.path.exists(sweep_dir):
        sweep_dir, n = os.path.join(results_dir, f"{sweep_id}-{n}"), n + 1
    sweep_id = os.path.basename(sweep_dir)
    os.makedirs(sweep_dir)

    first = configs[baseline][0]
    sweep = {
        "id": sweep_id,
        "label": label,
        "created": created.isoformat(timespec="seconds"),
        "command": command,
        "complete": False,
        "settings": [
            {
                "power": class_name,
                "setting": setting,
                "current": settings.settings_of(settings.power_classes()[class_name])[setting],
                "values": list(dict.fromkeys(point[i][2] for point in points)),
            }
            for i, (class_name, setting, _, _) in enumerate(assignments)
        ],
        "subjects": subjects,
        "auto_focus": added,
        "config": {
            "games": games,
            "seed": seed,
            "track": tracks.track_key(track),
            "track_name": first.track.name,
            "racers_per_game": players,
            "places_to_award": places,
            "focus": [e.name for e in first.focus],
        },
        "parity": 1 / players,
        "baseline": baseline,
        "points": [None] * len(points),
        "no_effect": None,
        "best": {},
    }

    outcomes = {}  # point index -> {racer: (wins, points)} per game
    order = [baseline] + [i for i in range(len(points)) if i != baseline]
    for step, index in enumerate(order):
        point = points[index]
        config, replaced = configs[index]
        if on_point:
            on_point(step, len(points), point)

        wins = {name: array("i", [_NO_GAME]) * games for name in subjects}
        chips = {name: array("i", [_NO_GAME]) * games for name in subjects}

        def collect(records):
            for record in records:
                if record["error"] is not None:
                    continue
                for racer in record["racers"]:
                    if racer["name"] in wins:
                        wins[racer["name"]][record["game"]] = int(racer["finished"] and racer["place"] == 1)
                        chips[racer["name"]][record["game"]] = racer["points"]

        out_dir = batch.default_out_dir(f"{label or 'sweep'} {point_label(point)}", track, config, results_dir)
        summary, _ = batch.execute(
            config,
            track_key=track,
            replaced=replaced,
            label=f"{label or 'Sweep'} · {point_label(point)}",
            out_dir=out_dir,
            workers=workers,
            command=batch.equivalent_command(
                games=games, track=tracks.track_key(track), players=players, places=places, seed=seed,
                focus=[e.name for e in config.focus], include=include, exclude=exclude, only=only,
                overrides=point,
            ),
            on_progress=on_progress,
            on_records=collect,
            mp_context=mp_context,
            isolate=isolate,
            extra_manifest={"sweep": {"id": sweep_id, "point": index}},
        )
        outcomes[index] = {name: (wins[name], chips[name]) for name in subjects}

        racers = summary["racers"]
        total_games = sum(r["games"] for r in racers)
        base = outcomes[baseline]
        sweep["points"][index] = {
            "index": index,
            "overrides": [{"power": c, "setting": k, "value": v} for c, k, v in point],
            "label": point_label(point),
            "current": index == baseline,
            "run_id": os.path.basename(out_dir),
            "errors": summary["totals"]["errors"],
            "field_pts": sum(r["pts_per_game"] * r["games"] for r in racers) / total_games if total_games else 0.0,
            "racers": [_compact(r) for r in racers],
            "paired": {
                name: {
                    "win": paired_difference(base[name][0], outcomes[index][name][0]),
                    "pts": paired_difference(base[name][1], outcomes[index][name][1]),
                }
                for name in subjects
            },
        }
        _save(sweep_dir, sweep)

    sweep["complete"] = True
    baseline_racers = sweep["points"][baseline]["racers"]
    sweep["no_effect"] = all(p["racers"] == baseline_racers for p in sweep["points"])
    for name in subjects:
        rows = [(p["index"], next((r for r in p["racers"] if r["name"] == name), None), p) for p in sweep["points"]]
        rows = [(i, r, p) for i, r, p in rows if r]
        if rows:
            # None when the setting doesn't move that number at all (any "best" would be arbitrary).
            win_rates = [r["win_rate"] for _, r, _ in rows]
            gaps = [r["pts_per_game"] - p["field_pts"] for _, r, p in rows]
            sweep["best"][name] = {
                "parity": None if max(win_rates) - min(win_rates) < 1e-12
                else min(rows, key=lambda row: abs(row[1]["win_rate"] - sweep["parity"]))[0],
                "points": None if max(gaps) - min(gaps) < 1e-12
                else min(rows, key=lambda row: abs(row[1]["pts_per_game"] - row[2]["field_pts"]))[0],
            }
    _save(sweep_dir, sweep)
    return sweep


def _save(sweep_dir, sweep):
    temp = os.path.join(sweep_dir, SWEEP_FILE + ".tmp")
    with open(temp, "w") as f:
        json.dump(sweep, f, indent=1)
    os.replace(temp, os.path.join(sweep_dir, SWEEP_FILE))
