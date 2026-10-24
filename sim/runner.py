"""
Deterministic, parallel batch runner.

Every game is derived only from (seed, game index): the lineup, seat order and
dice are the same no matter how many worker processes run the batch, so any
single game from a big run can be replayed with its full log.
"""
import multiprocessing
import os
import random
from dataclasses import dataclass

from Basics import Game, racer_score

from sim.stats import Tally


@dataclass(frozen=True)
class BatchConfig:
    track: object
    pool: tuple            # RacerEntry candidates for the open seats
    focus: tuple = ()      # RacerEntry seated in every game
    games: int = 1000
    racers_per_game: int = 7
    places_to_award: int = 2
    seed: int = 0

    def __post_init__(self):
        if self.games < 1:
            raise ValueError("Games must be at least 1.")
        if self.racers_per_game < 2:
            raise ValueError("A game needs at least 2 racers.")
        if not 1 <= self.places_to_award <= self.racers_per_game:
            raise ValueError(f"Scoring places must be between 1 and {self.racers_per_game}.")
        open_seats = self.racers_per_game - len(self.focus)
        if open_seats < 0:
            raise ValueError(f"{len(self.focus)} focus racers don't fit in a {self.racers_per_game}-racer game.")
        if open_seats > len(self.pool):
            raise ValueError(f"Need {open_seats} racers from the pool but only {len(self.pool)} are available.")


def lineup_for(config, index):
    """Seat order and seeds for one game. Depends only on (seed, index, pool, focus)."""
    rng = random.Random(f"{config.seed}:{index}")
    lineup = rng.sample(config.pool, config.racers_per_game - len(config.focus)) + list(config.focus)
    # shuffle() draws depend only on length, so focus racers land in the same seat
    # across runs that differ only in which focus racer (or variant) is used.
    rng.shuffle(lineup)
    return lineup, rng.getrandbits(64), rng.getrandbits(64)


def setup_game(config, index):
    lineup, game_seed, aux_seed = lineup_for(config, index)

    # Duelist, Flip Flop and Genius draw from the module-level `random` rather than
    # game.rng, so seed it per game too (with its own seed, so it never mirrors the dice).
    random.seed(aux_seed)

    return Game(
        racers=[entry.make() for entry in lineup],
        track=config.track,
        rng=random.Random(game_seed),
        places_to_award=config.places_to_award,
    )


def play_game(config, index):
    game = setup_game(config, index)
    record = {"game": index, "turns": 0, "stalled": False, "error": None, "racers": []}

    try:
        results = game.run_race()
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["racers"] = [{"name": r.name, "seat": seat} for seat, r in enumerate(game.racers, 1)]
        return record

    place = {id(r): p for p, r in enumerate(results, 1)}
    record["turns"] = game.turn_number - 1
    record["stalled"] = not game.race_over()
    record["racers"] = [
        {
            "name": r.name,
            "seat": seat,
            "place": place[id(r)],
            "points": r.points,
            "progress": racer_score(game, r),
            "finished": r.finished,
            "eliminated": r.eliminated,
        }
        for seat, r in enumerate(game.racers, 1)
    ]
    return record


def play_chunk(task):
    config, start, stop, keep_records = task
    tally = Tally(config.places_to_award)
    records = []

    for index in range(start, stop):
        record = play_game(config, index)
        tally.add(record)
        if keep_records:
            records.append(record)

    return stop - start, tally, records


def run_batch(config, workers=None, chunk_size=500, keep_records=False, mp_context=None):
    """
    Yield (games_done, tally, records) per chunk, in game order.

    Merge the tallies for the batch totals. `records` holds per-game dicts only
    when keep_records is set. `mp_context` picks the process start method
    (e.g. "spawn"); the platform default is used when it's None.
    """
    tasks = [
        (config, start, min(start + chunk_size, config.games), keep_records)
        for start in range(0, config.games, chunk_size)
    ]
    workers = max(1, min(workers or os.cpu_count() or 1, len(tasks)))

    if workers == 1:
        yield from map(play_chunk, tasks)
        return

    context = multiprocessing.get_context(mp_context)
    with context.Pool(workers) as pool:
        yield from pool.imap(play_chunk, tasks)
