"""
Aggregation of game records into per-racer statistics.

Tallies hold only integer counts so partial tallies from worker processes can be
merged in any order and still give identical results.
"""
import math
from collections import Counter
from dataclasses import dataclass, field

Z_95 = 1.96


@dataclass
class RacerTally:
    games: int = 0
    wins: int = 0
    podiums: int = 0
    finished: int = 0
    eliminated: int = 0
    points: int = 0
    points_sq: int = 0
    place_sum: int = 0
    progress_sum: int = 0
    turns_sum: int = 0
    places: Counter = field(default_factory=Counter)

    def merge(self, other):
        for name in ("games", "wins", "podiums", "finished", "eliminated", "points",
                     "points_sq", "place_sum", "progress_sum", "turns_sum"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.places.update(other.places)


class Tally:
    def __init__(self, places_to_award):
        self.places_to_award = places_to_award
        self.games = 0
        self.stalled = 0
        self.turns = 0
        self.errors = []  # {"game", "error", "lineup"} for games that raised
        self.racers: dict[str, RacerTally] = {}
        self.seat_games = Counter()
        self.seat_wins = Counter()
        self.ahead = Counter()     # (a, b) -> races where a placed ahead of b
        self.together = Counter()  # (a, b) -> races a and b were both in

    def add(self, record):
        if record["error"] is not None:
            self.errors.append({
                "game": record["game"],
                "error": record["error"],
                "lineup": [r["name"] for r in record["racers"]],
            })
            return

        self.games += 1
        self.turns += record["turns"]
        if record["stalled"]:
            self.stalled += 1

        racers = record["racers"]
        for r in racers:
            t = self.racers.get(r["name"])
            if t is None:
                t = self.racers[r["name"]] = RacerTally()

            won = r["finished"] and r["place"] == 1
            t.games += 1
            t.wins += won
            t.podiums += r["finished"] and r["place"] <= self.places_to_award
            t.finished += r["finished"]
            t.eliminated += r["eliminated"]
            t.points += r["points"]
            t.points_sq += r["points"] * r["points"]
            t.place_sum += r["place"]
            t.progress_sum += r["progress"]
            t.turns_sum += record["turns"]
            t.places[r["place"]] += 1

            self.seat_games[r["seat"]] += 1
            self.seat_wins[r["seat"]] += won

        for a in racers:
            for b in racers:
                if a is b:
                    continue
                self.together[a["name"], b["name"]] += 1
                if a["place"] < b["place"]:
                    self.ahead[a["name"], b["name"]] += 1

    def merge(self, other):
        self.games += other.games
        self.stalled += other.stalled
        self.turns += other.turns
        self.errors.extend(other.errors)
        for name, t in other.racers.items():
            self.racers.setdefault(name, RacerTally()).merge(t)
        self.seat_games.update(other.seat_games)
        self.seat_wins.update(other.seat_wins)
        self.ahead.update(other.ahead)
        self.together.update(other.together)


def wilson_interval(k, n, z=Z_95):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mean_interval(total, total_sq, n, z=Z_95):
    if n == 0:
        return (0.0, 0.0, 0.0)
    mean = total / n
    if n == 1:
        return (mean, mean, mean)
    variance = max(0.0, (total_sq - n * mean * mean) / (n - 1))
    half = z * math.sqrt(variance / n)
    return (mean, mean - half, mean + half)


SORT_KEYS = {
    "pts": lambda r: r["pts_per_game"],
    "win": lambda r: r["win_rate"],
    "place": lambda r: -r["avg_place"],
    "name": None,
}


def summarize(tally, sort="pts"):
    """Turn a Tally into a JSON-ready dict (the format written to summary.json)."""
    max_place = max((p for t in tally.racers.values() for p in t.places), default=0)

    racers = []
    for name, t in tally.racers.items():
        n = t.games
        pts, pts_lo, pts_hi = mean_interval(t.points, t.points_sq, n)
        win_lo, win_hi = wilson_interval(t.wins, n)
        racers.append({
            "name": name,
            "games": n,
            "wins": t.wins,
            "win_rate": t.wins / n,
            "win_rate_ci": [win_lo, win_hi],
            "podium_rate": t.podiums / n,
            "pts_per_game": pts,
            "pts_ci": [pts_lo, pts_hi],
            "avg_place": t.place_sum / n,
            "place_counts": [t.places.get(p, 0) for p in range(1, max_place + 1)],
            "avg_progress": t.progress_sum / n,
            "finish_rate": t.finished / n,
            "elim_rate": t.eliminated / n,
            "avg_game_turns": t.turns_sum / n,
        })

    key = SORT_KEYS[sort]
    if key is None:
        racers.sort(key=lambda r: r["name"].lower())
    else:
        racers.sort(key=key, reverse=True)

    names = [r["name"] for r in racers]
    ahead_rate = [
        [
            tally.ahead[a, b] / tally.together[a, b] if tally.together[a, b] else None
            for b in names
        ]
        for a in names
    ]

    seats = [
        {
            "seat": seat,
            "games": tally.seat_games[seat],
            "wins": tally.seat_wins[seat],
            "win_rate": tally.seat_wins[seat] / tally.seat_games[seat],
        }
        for seat in sorted(tally.seat_games)
    ]

    return {
        "totals": {
            "games": tally.games,
            "errors": len(tally.errors),
            "stalled": tally.stalled,
            "avg_turns": tally.turns / tally.games if tally.games else 0.0,
        },
        "racers": racers,
        "seats": seats,
        "head_to_head": {
            "names": names,
            "ahead_rate": ahead_rate,
            "together": [[tally.together[a, b] for b in names] for a in names],
        },
    }


def two_proportion_z(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0:
        return 0.0
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0
    return (k2 / n2 - k1 / n1) / se
