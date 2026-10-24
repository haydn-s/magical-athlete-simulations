"""Tests for game replays (sim/replay.py) and their API."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import batch, roster, tracks
from sim.jobs import JobManager
from sim.replay import find_games, record_game
from sim.roster import PowerRacer, RacerEntry
from sim.runner import BatchConfig, play_game, setup_game
from sim.serve import make_server
from tests.test_sim import BoomPower


def config_for(games=200, seed=11, **names):
    config, _ = batch.build_config(games=games, seed=seed, **names)
    return config


class RecordGameTest(unittest.TestCase):
    def test_replays_match_the_batch(self):
        config = config_for()
        for index in range(60):
            with self.subTest(game=index):
                replay = record_game(config, index)
                record = play_game(config, index)
                by_place = sorted(record["racers"], key=lambda r: r["place"])
                self.assertEqual(
                    [(replay["racers"][r["seat"]]["name"], r["points"]) for r in replay["results"]],
                    [(r["name"], r["points"]) for r in by_place],
                )
                self.assertEqual(replay["turns"], record["turns"])

    def test_one_frame_per_log_line(self):
        config = config_for(focus=["MadBomber", "CrossingGuard"])
        replay = record_game(config, 3)
        game = setup_game(config, 3)
        game.run_race()
        self.assertEqual([f["text"] for f in replay["frames"]], game.log)

        self.assertEqual(replay["initial"]["positions"], [0] * 7)
        self.assertEqual(replay["frames"][-1]["positions"], [r.position for r in game.racers])
        self.assertEqual(replay["crosswalk"], 27)
        placed = next(f for f in replay["frames"] if "places bombs" in f["text"])
        self.assertEqual(placed["bombs"], [8, 20, 29])
        self.assertIsNone(replay["frames"][0]["actor"])  # before anyone's turn

        first_turn = next(f for f in replay["frames"] if f["text"].startswith("Turn 1:"))
        self.assertEqual(first_turn["actor"], 0)
        self.assertIn(replay["racers"][0]["name"], first_turn["text"])

    def test_track_and_lineup_details(self):
        replay = record_game(config_for(), 0)
        self.assertEqual(replay["track"], tracks.track_to_json(tracks.WILD_WILDS))
        self.assertEqual([r["seat"] for r in replay["racers"]], list(range(1, 8)))
        self.assertEqual(sorted(r["place"] for r in replay["results"]), list(range(1, 8)))

    def test_a_crashing_game_keeps_its_frames_and_error(self):
        boom = RacerEntry("Boom", 999, PowerRacer(BoomPower))
        pool, _, _ = roster.build_pool()
        config = BatchConfig(track=tracks.WILD_WILDS, pool=tuple(pool), focus=(boom,), games=5, seed=3)
        replay = record_game(config, 0)
        self.assertIn("boom", replay["error"])
        self.assertFalse(replay["stalled"])
        self.assertEqual(len(replay["results"]), 7)


class FindGamesTest(unittest.TestCase):
    def test_filters_and_pages(self):
        config = config_for(games=300)
        games, next_start = find_games(config, racer="Hare", limit=5)
        self.assertEqual(len(games), 5)
        self.assertTrue(all("Hare" in g["lineup"] for g in games))
        more, _ = find_games(config, racer="Hare", start=next_start, limit=5)
        self.assertGreater(more[0]["game"], games[-1]["game"])

        everything, end = find_games(config, start=290, limit=50)
        self.assertEqual([g["game"] for g in everything], list(range(290, 300)))
        self.assertIsNone(end)

    def test_missing_racer_answers_quickly(self):
        games, next_start = find_games(config_for(games=10_000_000), racer="Nobody")
        self.assertEqual(games, [])
        self.assertIsNotNone(next_start)  # scanning stopped early; the client can continue


class ReplayApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        config, replaced = batch.build_config(games=100, seed=5, focus=["Oddball"])
        batch.execute(config, track_key="wild", replaced=replaced, out_dir=os.path.join(cls.tmp.name, "run"), workers=1)
        cls.server = make_server(port=0, results_dir=cls.tmp.name, web_dir=cls.tmp.name,
                                 jobs=JobManager(cls.tmp.name, mp_context=None))
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as err:
            with err:
                body = err.read()
            try:
                return err.code, json.loads(body)
            except ValueError:
                return err.code, None

    def test_replay(self):
        status, replay = self.get("/api/runs/run/games/42")
        self.assertEqual(status, 200)
        self.assertEqual(replay["game"], 42)
        self.assertFalse(replay["code_changed"])
        self.assertIn("Oddball", [r["name"] for r in replay["racers"]])

    def test_game_list(self):
        status, body = self.get("/api/runs/run/games?racer=Hare&limit=3")
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 100)
        self.assertLessEqual(len(body["games"]), 3)
        self.assertTrue(all("Hare" in g["lineup"] and "Oddball" in g["lineup"] for g in body["games"]))
        self.assertEqual(self.get("/api/runs/run/games?start=x")[0], 400)

    def test_bad_game_numbers(self):
        for path in ("/api/runs/run/games/100", "/api/runs/run/games/-1", "/api/runs/run/games/abc",
                     "/api/runs/run/games/1/extra", "/api/runs/nope/games/1"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)

    def test_runs_with_unknown_racers_explain_themselves(self):
        path = os.path.join(self.tmp.name, "renamed")
        os.makedirs(path)
        with open(os.path.join(self.tmp.name, "run", "summary.json")) as f:
            summary = json.load(f)
        summary["manifest"]["config"]["pool"][0] = "RetiredRacer"
        with open(os.path.join(path, "summary.json"), "w") as f:
            json.dump(summary, f)
        status, body = self.get("/api/runs/renamed/games/1")
        self.assertEqual(status, 409)
        self.assertIn("RetiredRacer", body["error"])


if __name__ == "__main__":
    unittest.main()
