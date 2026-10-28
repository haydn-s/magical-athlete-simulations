"""Tests for setting overrides (sim/settings.py) and parameter sweeps (sim/sweep.py)."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Powers
from sim import batch, settings, sweep
from sim.jobs import JobError, JobManager, parse_request
from sim.replay import record_game
from sim.runner import play_game
from sim.serve import make_server
from sim.settings import SettingError
from tests.test_sim import batch_summary


def sisyphus(summary):
    return next(r for r in summary["racers"] if r["name"] == "Sisyphus")


class ParseTest(unittest.TestCase):
    def test_values(self):
        cases = [
            ("3", 4, [3]),
            ("2,4,6", 4, [2, 4, 6]),
            ("2..6", 4, [2, 3, 4, 5, 6]),
            ("0..20:5", 4, [0, 5, 10, 15, 20]),
            ("2, 2, 3", 4, [2, 3]),
            ("0.5..1.5:0.25", 1.0, [0.5, 0.75, 1.0, 1.25, 1.5]),
            ("true,no", True, [True, False]),
        ]
        for text, current, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(settings.parse_values(text, current, "X"), expected)

    def test_bad_values(self):
        for text, current, message in [
            ("6..2", 4, "runs backwards"),
            ("1..9:0", 4, "step .* must be positive"),
            ("1..99", 4, "the limit is 50"),
            ("two", 4, "isn't a whole number"),
            ("maybe", True, "isn't true or false"),
            ("", 4, "at least one value"),
        ]:
            with self.subTest(text=text):
                with self.assertRaisesRegex(SettingError, message):
                    settings.parse_values(text, current, "X")

    def test_assignments(self):
        self.assertEqual(settings.parse_assignment("Sisyphus.STARTING_POINTS=3"),
                         ("SisyphusPower", "STARTING_POINTS", [3], "Sisyphus"))
        self.assertEqual(settings.parse_assignment("SisyphusPower.STARTING_POINTS=2..3"),
                         ("SisyphusPower", "STARTING_POINTS", [2, 3], None))
        for text, message in [
            ("Sisyphus.STARTING_POINT=3", "Did you mean: STARTING_POINTS"),
            ("Hare.SPEED=3", "HarePower has no setting 'SPEED'. It has no settings yet"),
            ("Nobody.X=1", "Unknown power or racer"),
            ("STARTING_POINTS=3", "write settings as Racer.SETTING=value"),
            ("Sisyphus.owner=3", "has no setting 'owner'"),
        ]:
            with self.subTest(text=text):
                with self.assertRaisesRegex(SettingError, message):
                    settings.parse_assignment(text)

    def test_check_override_types(self):
        self.assertEqual(settings.check_override("SisyphusPower", "STARTING_POINTS", 3.0), ("SisyphusPower", "STARTING_POINTS", 3))
        for value in (2.5, True, "3"):
            with self.subTest(value=value):
                with self.assertRaises(SettingError):
                    settings.check_override("SisyphusPower", "STARTING_POINTS", value)

    def test_lists_tunables(self):
        names = {(c, k) for c, k, _, _ in settings.tunables()}
        self.assertIn(("SisyphusPower", "STARTING_POINTS"), names)
        self.assertIn(("SuckerfishPower", "MIN_RIDE_DISTANCE"), names)


class OverrideTest(unittest.TestCase):
    def test_applied_restores_the_class(self):
        with settings.applied([("SisyphusPower", "STARTING_POINTS", 9)]):
            self.assertEqual(Powers.SisyphusPower.STARTING_POINTS, 9)
        self.assertEqual(Powers.SisyphusPower.STARTING_POINTS, 4)
        with self.assertRaises(RuntimeError):
            with settings.applied([("SisyphusPower", "STARTING_POINTS", 9)]):
                raise RuntimeError
        self.assertEqual(Powers.SisyphusPower.STARTING_POINTS, 4)

    def test_overrides_change_results_and_reach_workers(self):
        base, _ = batch.build_config(games=300, seed=3, focus=["Sisyphus"])
        changed, _ = batch.build_config(games=300, seed=3, focus=["Sisyphus"],
                                        overrides=[("SisyphusPower", "STARTING_POINTS", 0)])
        before = sisyphus(batch_summary(base))
        after = batch_summary(changed, workers=1)
        self.assertGreater(before["pts_per_game"] - sisyphus(after)["pts_per_game"], 3)
        self.assertEqual(after, batch_summary(changed, workers=2, chunk_size=70))
        self.assertEqual(Powers.SisyphusPower.STARTING_POINTS, 4)  # the parent process was never changed

    def test_replays_and_saved_runs_keep_overrides(self):
        config, _ = batch.build_config(games=50, seed=4, focus=["Sisyphus"],
                                       overrides=[("SisyphusPower", "STARTING_POINTS", 1)])
        rebuilt = batch.config_from_json(batch.config_to_json(config, "wild", []))
        self.assertEqual(rebuilt.overrides, (("SisyphusPower", "STARTING_POINTS", 1),))

        with settings.applied(config.overrides):
            record = play_game(config, 7)
        replay = record_game(rebuilt, 7)
        seat = next(r["seat"] for r in record["racers"] if r["name"] == "Sisyphus")
        self.assertEqual(next(r["points"] for r in replay["results"] if r["seat"] == seat - 1),
                         next(r["points"] for r in record["racers"] if r["name"] == "Sisyphus"))

        data = batch.config_to_json(config, "wild", [])
        data["overrides"][0]["power"] = "RetiredPower"
        with self.assertRaises(SettingError):
            batch.config_from_json(data)

    def test_job_requests_accept_overrides(self):
        settings_, config, _ = parse_request({"games": 10, "seed": 1, "overrides": [
            {"power": "SisyphusPower", "setting": "STARTING_POINTS", "value": 2}]})
        self.assertEqual(config.overrides, (("SisyphusPower", "STARTING_POINTS", 2),))
        self.assertEqual(settings_["overrides"], [{"power": "SisyphusPower", "setting": "STARTING_POINTS", "value": 2}])
        for bad in ([{"power": "SisyphusPower", "setting": "NOPE", "value": 2}], [{"power": "X"}], "x"):
            with self.subTest(bad=bad):
                with self.assertRaises(JobError):
                    parse_request({"overrides": bad})

    def test_job_command_includes_overrides(self):
        with tempfile.TemporaryDirectory() as results:
            manager = JobManager(results, mp_context=None)
            job = manager.submit({"games": 20, "seed": 1, "overrides": [
                {"power": "SisyphusPower", "setting": "STARTING_POINTS", "value": 2}]})
            self.assertIn("--set SisyphusPower.STARTING_POINTS=2", job.command)
            manager.wait(job.id, timeout=60)
            self.assertEqual(job.state, "done", job.error)
            manager.shutdown()


class SweepTest(unittest.TestCase):
    def test_plan_adds_the_current_value(self):
        assignment = settings.parse_assignment("Sisyphus.STARTING_POINTS=2,6")
        points, baseline = sweep.plan([assignment])
        self.assertEqual([p[0][2] for p in points], [2, 4, 6])
        self.assertEqual(baseline, 1)
        with self.assertRaisesRegex(SettingError, "set twice"):
            sweep.plan([assignment, assignment])
        big = settings.parse_assignment("Sisyphus.STARTING_POINTS=0..9")
        other = settings.parse_assignment("Suckerfish.MIN_RIDE_DISTANCE=0..9")
        with self.assertRaisesRegex(SettingError, "at most 50"):
            sweep.plan([big, other])

    def test_paired_difference(self):
        result = sweep.paired_difference([0, 1, 2, 3], [1, 1, 2, 5])
        self.assertEqual((result["games"], result["changed"], result["delta"]), (4, 2, 0.75))
        self.assertLess(result["ci"][0], 0.75)
        self.assertIsNone(sweep.paired_difference([0], [1]))

    def test_runs_a_sweep(self):
        with tempfile.TemporaryDirectory() as results:
            result = sweep.run_sweep(
                assignments=[settings.parse_assignment("Sisyphus.STARTING_POINTS=1")],
                games=200, seed=5, workers=2, results_dir=results, label="chips",
            )
            self.assertTrue(result["complete"])
            self.assertEqual(result["auto_focus"], ["Sisyphus"])
            self.assertEqual([p["label"] for p in result["points"]], ["STARTING_POINTS=1", "STARTING_POINTS=4"])
            low, current = result["points"]
            self.assertTrue(current["current"])
            self.assertEqual(current["paired"]["Sisyphus"]["pts"]["delta"], 0)
            self.assertLess(low["paired"]["Sisyphus"]["pts"]["delta"], -2)
            self.assertTrue(low["paired"]["Sisyphus"]["pts"]["significant"])
            self.assertFalse(result["no_effect"])
            self.assertIsNone(result["best"]["Sisyphus"]["parity"])  # chips don't change who wins

            with open(os.path.join(results, result["id"], "sweep.json")) as f:
                self.assertEqual(json.load(f), result)
            run = batch.load_summary(os.path.join(results, low["run_id"]))
            self.assertEqual(run["manifest"]["sweep"], {"id": result["id"], "point": 0})
            self.assertEqual(run["manifest"]["config"]["overrides"],
                             [{"power": "SisyphusPower", "setting": "STARTING_POINTS", "value": 1}])
            self.assertIn("--set SisyphusPower.STARTING_POINTS=1", run["manifest"]["command"])

    def test_flags_settings_with_no_effect(self):
        with tempfile.TemporaryDirectory() as results:
            result = sweep.run_sweep(
                assignments=[settings.parse_assignment("MadBomber.NUM_BOMBS=1")],
                games=100, seed=5, workers=1, results_dir=results,
            )
        self.assertTrue(result["no_effect"])


class SweepApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sweep = sweep.run_sweep(assignments=[settings.parse_assignment("Sisyphus.STARTING_POINTS=3")],
                                    games=100, seed=2, workers=1, results_dir=cls.tmp.name)
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
                return err.code, None

    def test_lists_and_serves_sweeps(self):
        status, sweeps = self.get("/api/sweeps")
        self.assertEqual(status, 200)
        self.assertEqual([(s["id"], s["points"]) for s in sweeps], [(self.sweep["id"], 2)])
        status, body = self.get(f"/api/sweeps/{self.sweep['id']}")
        self.assertEqual(body["points"][0]["run_id"], self.sweep["points"][0]["run_id"])
        status, roster = self.get("/api/roster")
        self.assertIn("STARTING_POINTS", [s["setting"] for s in roster["settings"]])

    def test_sweep_runs_are_normal_runs(self):
        run_id = self.sweep["points"][0]["run_id"]
        status, summary = self.get(f"/api/runs/{run_id}")
        self.assertEqual(status, 200)
        status, replay = self.get(f"/api/runs/{run_id}/games/3")
        self.assertEqual(status, 200)

    def test_rejects_bad_ids(self):
        for path in ("/api/sweeps/missing", "/api/sweeps/..", "/api/sweeps/..%2Fx", "/api/sweeps/.jobs.json"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)


if __name__ == "__main__":
    unittest.main()
