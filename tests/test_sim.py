"""
Tests for the batch harness (not the racer mechanics).

    python -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import Powers
from Events import StartTurnEvent
from sim import roster, tracks
from sim.roster import PowerRacer, RacerEntry
from sim.runner import BatchConfig, play_game, run_batch, setup_game
from sim.stats import Tally, summarize


def make_config(games=300, seed=7, **overrides):
    pool, focus, _ = roster.build_pool(**overrides)
    return BatchConfig(track=tracks.WILD_WILDS, pool=tuple(pool), focus=tuple(focus), games=games, seed=seed)


def batch_summary(config, workers=1, chunk_size=100):
    tally = Tally(config.places_to_award)
    for _, part, _ in run_batch(config, workers=workers, chunk_size=chunk_size):
        tally.merge(part)
    return summarize(tally)


class BoomPower(Powers.Power):
    def register(self, bus):
        bus.on(StartTurnEvent, self.boom)

    def boom(self, game, event):
        raise RuntimeError("boom")


class DeterminismTest(unittest.TestCase):
    def test_same_seed_same_results(self):
        config = make_config()
        self.assertEqual(batch_summary(config), batch_summary(config))

    def test_different_seed_different_results(self):
        self.assertNotEqual(batch_summary(make_config(seed=1)), batch_summary(make_config(seed=2)))

    def test_worker_count_and_chunking_do_not_matter(self):
        config = make_config()
        self.assertEqual(
            batch_summary(config, workers=1, chunk_size=300),
            batch_summary(config, workers=3, chunk_size=37),
        )

    def test_hash_seed_does_not_matter(self):
        cmd = [sys.executable, "-c",
               "import json; from tests.test_sim import make_config, batch_summary; "
               "print(json.dumps(batch_summary(make_config(games=150))))"]
        outputs = [
            subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True,
                           env=dict(os.environ, PYTHONHASHSEED=hash_seed)).stdout
            for hash_seed in ("1", "2")
        ]
        self.assertEqual(json.loads(outputs[0]), json.loads(outputs[1]))

    def test_powers_only_use_the_games_own_rng(self):
        # Any call to the module-level random during a race fails the test; game.rng
        # and the lineup's Random instances are separate objects and still work.
        import random
        from unittest import mock

        def forbidden(*args, **kwargs):
            raise AssertionError("a power used the module-level random instead of game.rng")

        config = make_config(games=400, focus=["Duelist", "FlipFlop", "Genius"])
        names = ["random", "randint", "randrange", "choice", "choices", "shuffle", "sample", "uniform"]
        with mock.patch.multiple(random, **{name: forbidden for name in names}):
            summary = batch_summary(config)
        self.assertEqual(summary["totals"]["errors"], 0)

    def test_replay_matches_batch_record(self):
        config = make_config(games=50)
        for index in (0, 17, 49):
            record = play_game(config, index)
            game = setup_game(config, index)
            results = game.run_race()
            self.assertEqual([r["name"] for r in record["racers"]], [r.name for r in game.racers])
            by_place = sorted(record["racers"], key=lambda r: r["place"])
            self.assertEqual([r["name"] for r in by_place], [r.name for r in results])


class LineupTest(unittest.TestCase):
    def test_focus_racer_in_every_game(self):
        config = make_config(games=100, focus=["Oddball"])
        for index in range(config.games):
            names = [r.name for r in setup_game(config, index).racers]
            self.assertEqual(names.count("Oddball"), 1)
            self.assertEqual(len(names), 7)

    def test_variant_replaces_base_and_keeps_opponents(self):
        base = make_config(games=50, focus=["Scoocher"])
        variant = make_config(games=50, focus=["ScoocherWeakened"])
        self.assertNotIn("Scoocher", [e.name for e in variant.pool])
        self.assertEqual(base.pool, variant.pool)

        for index in range(base.games):
            base_names = [r.name for r in setup_game(base, index).racers]
            variant_names = [r.name for r in setup_game(variant, index).racers]
            self.assertEqual(
                [n if n != "Scoocher" else "ScoocherWeakened" for n in base_names],
                variant_names,
            )

    def test_exclude_and_only(self):
        pool, _, _ = roster.build_pool(exclude=["Scoocher", "mouth"])
        names = {e.name for e in pool}
        self.assertNotIn("Scoocher", names)
        self.assertNotIn("M.O.U.T.H.", names)

        pool, _, _ = roster.build_pool(only=["Hare", "Banana"])
        self.assertEqual([e.name for e in pool], ["Hare", "Banana"])

    def test_unknown_racer_suggests_names(self):
        with self.assertRaisesRegex(KeyError, "Did you mean"):
            roster.lookup("Scoocer")


class StatsTest(unittest.TestCase):
    def test_counts_are_consistent(self):
        config = make_config(games=400)
        summary = batch_summary(config)
        racers = summary["racers"]

        self.assertEqual(sum(r["games"] for r in racers), 400 * 7)
        self.assertEqual(sum(sum(r["place_counts"]) for r in racers), 400 * 7)
        self.assertLessEqual(sum(r["wins"] for r in racers), 400)
        for r in racers:
            lo, hi = r["win_rate_ci"]
            self.assertLessEqual(lo, r["win_rate"])
            self.assertLessEqual(r["win_rate"], hi)

    def test_errors_are_recorded_not_raised(self):
        boom = RacerEntry("Boom", 999, PowerRacer(BoomPower))
        pool, _, _ = roster.build_pool()
        config = BatchConfig(track=tracks.WILD_WILDS, pool=tuple(pool), focus=(boom,), games=20, seed=3)

        tally = Tally(config.places_to_award)
        for _, part, _ in run_batch(config, workers=1):
            tally.merge(part)

        self.assertEqual(tally.games, 0)
        self.assertEqual(len(tally.errors), 20)
        self.assertIn("boom", tally.errors[0]["error"])
        self.assertIn("Boom", tally.errors[0]["lineup"])


if __name__ == "__main__":
    unittest.main()
