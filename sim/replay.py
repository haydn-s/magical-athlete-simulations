"""
Turn-by-turn recordings of single games, for the viewer's replay page.

A game is re-run from (seed, game number) exactly as it ran in its batch. Every
line the engine writes to game.log becomes a frame holding the board at that
moment, so the animation and the log always line up. The engine is untouched:
the recorder only swaps game.log for a list that takes a snapshot on append,
and listens for StartTurnEvent to know whose turn it is.
"""
from Events import StartTurnEvent
from Powers import CrossingGuardPower

from sim import settings
from sim.runner import lineup_for, setup_game
from sim.tracks import track_to_json

# Stop scanning for matching games after this many, so a filter that matches
# nothing (a racer who isn't in the run) still answers quickly.
MAX_SCAN = 20_000


def racer_status(racer):
    if racer.finished:
        return "finished"
    if racer.eliminated:
        return "eliminated"
    if racer.is_tripped:
        return "tripped"
    return ""


class _RecordingLog(list):
    def __init__(self, recorder):
        super().__init__()
        self._recorder = recorder

    def append(self, text):
        super().append(text)
        self._recorder.snapshot(text)


class Recorder:
    def __init__(self, game):
        self.game = game
        self.actor = None
        self.frames = []
        game.event_bus.on(StartTurnEvent, self._start_turn, priority=-1000)
        game.log = _RecordingLog(self)

    def _start_turn(self, game, event):
        self.actor = next(i for i, r in enumerate(game.racers) if r is event.racer)

    def state(self):
        game = self.game
        seat_of = {id(r): i for i, r in enumerate(game.racers)}
        return {
            "positions": [r.position for r in game.racers],
            "status": [racer_status(r) for r in game.racers],
            "points": [r.points for r in game.racers],
            "finish_order": [seat_of[id(r)] for r in game.finish_order],
            "bombs": sorted(game.bombs),
        }

    def snapshot(self, text):
        self.frames.append({"text": text, "turn": self.game.turn_number, "actor": self.actor, **self.state()})


def record_game(config, index):
    """Re-run one game of a batch and return every frame of it as JSON-ready data."""
    with settings.applied(config.overrides, exclusive=True):
        game = setup_game(config, index)
        recorder = Recorder(game)
        initial = recorder.state()

        error = None
        try:
            results = game.run_race()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            results = game.get_results()

    seat_of = {id(r): i for i, r in enumerate(game.racers)}
    crosswalk = next(
        (p.crosswalk_position for r in game.racers for p in r.powers if isinstance(p, CrossingGuardPower)),
        None,
    )
    return {
        "game": index,
        "seed": config.seed,
        "track": track_to_json(config.track),
        "places_to_award": config.places_to_award,
        "racers": [{"name": r.name, "seat": seat} for seat, r in enumerate(game.racers, 1)],
        "crosswalk": crosswalk,
        "initial": initial,
        "frames": recorder.frames,
        "results": [
            {"seat": seat_of[id(r)], "place": place, "points": r.points, "status": racer_status(r)}
            for place, r in enumerate(results, 1)
        ],
        "turns": game.turn_number - 1,
        "stalled": error is None and not game.race_over(),
        "error": error,
    }


def find_games(config, racer=None, start=0, limit=20):
    """
    Game numbers (with their lineups) from `start` on, optionally only games
    `racer` was in. Lineups come from the seed alone, so nothing is simulated.
    Returns (games, next_start), where next_start is None at the end of the batch.
    """
    games = []
    index = max(0, start)
    stop = min(config.games, index + MAX_SCAN)
    while index < stop and len(games) < limit:
        lineup, _, _ = lineup_for(config, index)
        names = [entry.name for entry in lineup]
        if racer is None or racer in names:
            games.append({"game": index, "lineup": names})
        index += 1
    return games, (index if index < config.games else None)
