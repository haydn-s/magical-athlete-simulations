"""
Tracks the simulator can race on.

Every tracks/<key>.json file is a track, raced with `--track <key>` (or picked in
the viewer). A track file looks like this:

    {
      "name": "Wild Wilds",
      "length": 30,
      "spaces": {
        "1": {"points": 1},
        "5": {"trip": true},
        "7": {"move": 3},
        "16": {"move": -4}
      }
    }

Spaces run from 1 to length - 1 (0 is Start, length is the finish line). An effect
is a point chip ("points"), a trip ("trip"), or an arrow ("move", negative to go
back); a space can combine them. Files are read fresh whenever tracks are listed
or looked up, so edits show up without restarting anything. A file anywhere on
disk can also be raced with `--track path/to/track.json`.
"""
import json
import os
import re

from Basics import Track, TrackSpace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS_DIR = os.path.join(ROOT, "tracks")

MIN_LENGTH = 10
MAX_LENGTH = 200
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SPACE_KEYS = {"trip", "move", "points"}


class TrackError(ValueError):
    """A track that can't be raced, with a message saying why."""


def track_from_spec(spec, source="track"):
    """Build a Track from a parsed track file, or raise TrackError explaining the problem."""
    if not isinstance(spec, dict):
        raise TrackError(f"{source}: expected a JSON object with name, length and spaces.")
    unknown = sorted(set(spec) - {"name", "length", "spaces", "description"})
    if unknown:
        raise TrackError(f"{source}: unknown field {', '.join(map(repr, unknown))}.")

    name = spec.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise TrackError(f"{source}: name must be text of 1 to 60 characters.")
    length = spec.get("length")
    if isinstance(length, bool) or not isinstance(length, int) or not MIN_LENGTH <= length <= MAX_LENGTH:
        raise TrackError(f"{source}: length must be a whole number from {MIN_LENGTH} to {MAX_LENGTH}.")

    raw_spaces = spec.get("spaces", {})
    if isinstance(raw_spaces, list):  # the API's form: [{"position": 7, "move": 3, ...}, ...]
        try:
            raw_spaces = {str(s["position"]): {k: v for k, v in s.items() if k != "position"} for s in raw_spaces}
        except (TypeError, KeyError):
            raise TrackError(f"{source}: each space in the list needs a position.") from None
    if not isinstance(raw_spaces, dict):
        raise TrackError(f"{source}: spaces must map space numbers to effects.")

    spaces = {}
    for key, effects in raw_spaces.items():
        where = f"{source}: space {key}"
        if not str(key).isdigit() or not 1 <= int(key) < length:
            raise TrackError(f"{where}: space numbers run from 1 to {length - 1}.")
        position = int(key)
        if position in spaces:
            raise TrackError(f"{where} is listed twice.")
        if not isinstance(effects, dict):
            raise TrackError(f'{where}: expected effects like {{"trip": true}} or {{"move": 3}}.')
        unknown = sorted(set(effects) - SPACE_KEYS)
        if unknown:
            raise TrackError(f"{where}: unknown effect {', '.join(map(repr, unknown))} (use trip, move, points).")

        trip = effects.get("trip", False)
        move = effects.get("move", 0)
        points = effects.get("points", 0)
        if not isinstance(trip, bool):
            raise TrackError(f"{where}: trip must be true or false.")
        for label, value in (("move", move), ("points", points)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TrackError(f"{where}: {label} must be a whole number.")
        if not 0 <= position + move <= length:
            raise TrackError(f"{where}: an arrow of {move:+d} would leave the track.")
        if not (trip or move or points):
            raise TrackError(f"{where} has no effect; remove it or add trip, move or points.")
        spaces[position] = TrackSpace(trip=trip, move=move, points=points)

    return Track(name=name.strip(), length=length, spaces=dict(sorted(spaces.items())))


def track_to_json(track):
    return {
        "name": track.name,
        "length": track.length,
        "spaces": [
            {"position": position, "trip": space.trip, "move": space.move, "points": space.points}
            for position, space in sorted(track.spaces.items())
        ],
    }


def load_file(path):
    name = os.path.basename(path)
    try:
        with open(path) as f:
            spec = json.load(f)
    except OSError as exc:
        raise TrackError(f"{name}: can't read it ({exc.strerror}).") from None
    except ValueError as exc:
        raise TrackError(f"{name}: not valid JSON ({exc}).") from None
    return track_from_spec(spec, source=name)


_cache = {}  # path -> (mtime, Track or TrackError)


def scan(tracks_dir=TRACKS_DIR):
    """Every track file in tracks_dir as ({key: Track}, {key: error message}), sorted by key."""
    found, errors = {}, {}
    names = sorted(os.listdir(tracks_dir)) if os.path.isdir(tracks_dir) else []
    for name in names:
        if not name.endswith(".json"):
            continue
        key = name[: -len(".json")]
        if not KEY_PATTERN.match(key):
            errors[key] = f"{name}: rename it using lowercase letters, digits, - and _ only."
            continue
        path = os.path.join(tracks_dir, name)
        mtime = os.path.getmtime(path)
        cached = _cache.get(path)
        if not cached or cached[0] != mtime:
            try:
                cached = (mtime, load_file(path))
            except TrackError as exc:
                cached = (mtime, exc)
            _cache[path] = cached
        if isinstance(cached[1], TrackError):
            errors[key] = str(cached[1])
        else:
            found[key] = cached[1]
    return found, errors


def available():
    """{key: Track} for every valid file in tracks/."""
    return scan()[0]


def is_path(value):
    return value.endswith(".json") or "/" in value or os.sep in value


def lookup(key):
    """A track by key (tracks/<key>.json), or by path to any track file."""
    if is_path(key):
        return load_file(key)
    found, errors = scan()
    key = key.lower()
    if key in found:
        return found[key]
    if key in errors:
        raise TrackError(errors[key])
    raise KeyError(f"Unknown track {key!r}. Known tracks: {', '.join(found) or 'none'}")


def track_key(value):
    """The key a --track value is recorded under: the file name, for paths."""
    if is_path(value):
        return os.path.splitext(os.path.basename(value))[0].lower()
    return value.lower()


MILD_MILE = lookup("mild")
WILD_WILDS = lookup("wild")
