"""Tests for runs started from the web viewer (sim/jobs.py)."""
import argparse
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import batch, cli
from sim.jobs import JobError, JobManager, parse_request


def runs_in(folder):
    """Run folders only (results/ also holds the hidden .jobs.json history)."""
    return sorted(name for name in os.listdir(folder) if not name.startswith("."))


def cli_config(argv, games):
    parser = argparse.ArgumentParser()
    cli.add_config_args(parser)
    return cli.config_from_args(parser.parse_args(argv), games)


class ParseRequestTest(unittest.TestCase):
    def test_defaults(self):
        settings, config, replaced = parse_request({})
        self.assertEqual((settings["games"], settings["track"], settings["players"], settings["places"]),
                         (10_000, "wild", 7, 2))
        self.assertIsInstance(settings["seed"], int)  # a random seed is fixed at submit time
        self.assertEqual(config.seed, settings["seed"])
        self.assertEqual(replaced, [])

    def test_matches_the_cli(self):
        request = {"games": 500, "seed": 9, "track": "mild", "players": 6, "places": 3,
                   "focus": ["ScoocherWeakened"], "exclude": ["Hare", "mouth"], "include": []}
        _, config, replaced = parse_request(request)
        expected, expected_replaced = cli_config(
            ["--seed", "9", "--track", "mild", "--players", "6", "--places", "3",
             "--focus", "ScoocherWeakened", "--exclude", "Hare,mouth"], 500)
        self.assertEqual(config, expected)
        self.assertEqual(replaced, expected_replaced)

    def test_rejects_bad_requests(self):
        cases = {
            "Expected a JSON object": [],
            "Unknown setting: gamez": {"gamez": 10},
            "games must be a whole number": {"games": "10"},
            "games must be between": {"games": 0},
            "players must be a whole number": {"players": True},
            "Unknown racer 'Nobody'": {"focus": ["Nobody"]},
            "Unknown track": {"track": "moon"},
            "focus must be a list": {"focus": "Hare"},
            "Scoring places must be between 1 and 5": {"players": 5, "places": 6},
            "Need 7 racers from the pool": {"only": ["Hare", "Banana"]},
            "label must be text": {"label": "x" * 61},
            "save_games must be true or false": {"save_games": "yes"},
        }
        for message, request in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(JobError, message):
                    parse_request(request)


class JobManagerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.results = self.tmp.name
        self.manager = JobManager(self.results, mp_context=None)

    def tearDown(self):
        self.manager.shutdown()
        self.tmp.cleanup()

    def test_runs_a_job_to_completion(self):
        job = self.manager.submit({"games": 300, "seed": 4, "label": "from ui", "workers": 1, "focus": ["Oddball"]})
        self.manager.wait(job.id, timeout=60)

        self.assertEqual(job.state, "done", job.error)
        self.assertEqual(job.done, 300)
        self.assertEqual(runs_in(self.results), [job.run_id])
        self.assertTrue(job.run_id.endswith("_from-ui"), job.run_id)
        self.assertEqual(job.command, "python -m sim run -n 300 --seed 4 --focus Oddball --label 'from ui'")

        with open(os.path.join(self.results, job.run_id, "summary.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["manifest"]["label"], "from ui")
        self.assertEqual(summary["manifest"]["command"], job.command)
        self.assertEqual(summary["totals"]["games"], 300)

        # Same numbers as running the equivalent CLI command.
        config, replaced = cli_config(["--seed", "4", "--focus", "Oddball"], 300)
        expected, _ = batch.execute(config, track_key="wild", replaced=replaced, workers=1)
        self.assertEqual(summary["racers"], json.loads(json.dumps(expected["racers"])))

    def test_runs_one_job_at_a_time_in_order(self):
        first = self.manager.submit({"games": 200, "seed": 1, "workers": 1})
        second = self.manager.submit({"games": 200, "seed": 2, "workers": 1})
        self.manager.wait(second.id, timeout=60)
        self.assertEqual((first.state, second.state), ("done", "done"))
        self.assertLessEqual(first.finished, second.started)
        self.assertEqual([j.id for j in self.manager.list()], [second.id, first.id])

    def test_cancel_running_job_keeps_no_results(self):
        job = self.manager.submit({"games": 2_000_000, "seed": 1, "workers": 1})
        deadline = time.time() + 30
        while job.done == 0 and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(job.state, "running")
        self.manager.cancel(job.id)
        self.manager.wait(job.id, timeout=60)
        self.assertEqual(job.state, "cancelled")
        self.assertLess(job.done, 2_000_000)
        self.assertEqual(runs_in(self.results), [])

    def test_cancel_queued_job(self):
        blocker = self.manager.submit({"games": 2_000_000, "seed": 1, "workers": 1})
        queued = self.manager.submit({"games": 100, "seed": 2, "workers": 1})
        self.manager.cancel(queued.id)
        self.assertEqual(queued.state, "cancelled")
        self.manager.cancel(blocker.id)
        self.manager.wait(blocker.id, timeout=60)
        self.assertEqual(queued.done, 0)
        self.assertEqual(runs_in(self.results), [])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores folder permissions")
    def test_failed_job_reports_error(self):
        job = self.manager.submit({"games": 50, "seed": 1, "workers": 1})
        self.manager.wait(job.id, timeout=60)
        self.assertEqual(job.state, "done")

        os.chmod(self.results, 0o500)  # results folder can't be written
        try:
            job = self.manager.submit({"games": 50, "seed": 1, "workers": 1, "label": "blocked"})
            self.manager.wait(job.id, timeout=60)
        finally:
            os.chmod(self.results, 0o700)
        self.assertEqual(job.state, "failed")
        self.assertIn("PermissionError", job.error)


class JobHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.results = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def restart(self, previous):
        previous.shutdown()
        return JobManager(self.results, mp_context=None)

    def test_jobs_survive_a_restart(self):
        manager = JobManager(self.results, mp_context=None)
        job = manager.submit({"games": 100, "seed": 1, "workers": 1, "label": "kept"})
        manager.wait(job.id, timeout=60)

        manager = self.restart(manager)
        self.assertEqual(manager.list(), [])  # nothing is running in the new session...
        [entry] = manager.snapshots()  # ...but the finished job is remembered
        self.assertEqual((entry["id"], entry["state"], entry["run_id"], entry["label"]),
                         (job.id, "done", job.run_id, "kept"))
        self.assertEqual(manager.snapshot(job.id)["done"], 100)
        self.assertEqual(manager.cancel(job.id)["state"], "done")  # finished jobs can't be cancelled
        manager.shutdown()

    def test_unfinished_jobs_come_back_interrupted(self):
        # The server stopped mid-run, leaving a half-written folder next to a finished run.
        os.makedirs(os.path.join(self.results, "half-written"))
        os.makedirs(os.path.join(self.results, "finished"))
        open(os.path.join(self.results, "finished", "summary.json"), "w").close()
        with open(os.path.join(self.results, ".jobs.json"), "w") as f:
            json.dump([
                {"id": "abc", "state": "running", "done": 500, "total": 1000, "remaining_sec": 3, "folder": "half-written"},
                {"id": "def", "state": "running", "folder": "finished"},
                {"id": "ghi", "state": "running", "folder": "../escape"},
            ], f)

        manager = JobManager(self.results, mp_context=None)
        entries = manager.snapshots()
        self.assertEqual([e["state"] for e in entries], ["interrupted"] * 3)
        self.assertIn("server stopped", entries[0]["error"])
        self.assertIsNone(entries[0]["remaining_sec"])
        self.assertEqual(runs_in(self.results), ["finished"])  # only the half-written folder is removed
        manager.shutdown()

    def test_progress_is_saved_while_running(self):
        from sim import jobs
        manager = JobManager(self.results, mp_context=None)
        original, jobs.SAVE_PROGRESS_EVERY = jobs.SAVE_PROGRESS_EVERY, 0
        try:
            job = manager.submit({"games": 2_000_000, "seed": 1, "workers": 1})
            deadline = time.time() + 30
            while job.done < 1000 and time.time() < deadline:
                time.sleep(0.01)
            with open(os.path.join(self.results, ".jobs.json")) as f:
                saved = json.load(f)[0]
            self.assertEqual(saved["state"], "running")
            self.assertGreater(saved["done"], 0)
            self.assertTrue(saved["folder"])
        finally:
            jobs.SAVE_PROGRESS_EVERY = original
            manager.cancel(job.id)
            manager.wait(job.id, timeout=60)
            manager.shutdown()

    def test_clear_finished_keeps_active_jobs(self):
        manager = JobManager(self.results, mp_context=None)
        done = manager.submit({"games": 50, "seed": 1, "workers": 1})
        manager.wait(done.id, timeout=60)
        running = manager.submit({"games": 2_000_000, "seed": 2, "workers": 1})

        self.assertEqual(manager.clear_finished(), 1)
        self.assertEqual([e["id"] for e in manager.snapshots()], [running.id])
        manager.cancel(running.id)
        manager.wait(running.id, timeout=60)

        manager = self.restart(manager)
        self.assertEqual([e["state"] for e in manager.snapshots()], ["cancelled"])
        manager.shutdown()

    def test_unreadable_history_is_ignored(self):
        with open(os.path.join(self.results, ".jobs.json"), "w") as f:
            f.write("{not json")
        manager = JobManager(self.results, mp_context=None)
        self.assertEqual(manager.snapshots(), [])
        job = manager.submit({"games": 50, "seed": 1, "workers": 1})
        manager.wait(job.id, timeout=60)
        with open(os.path.join(self.results, ".jobs.json")) as f:
            self.assertEqual([e["id"] for e in json.load(f)], [job.id])
        manager.shutdown()


class SpawnedWorkersTest(unittest.TestCase):
    def test_parallel_job_from_a_background_thread(self):
        with tempfile.TemporaryDirectory() as results:
            manager = JobManager(results, mp_context="spawn")
            try:
                job = manager.submit({"games": 1000, "seed": 3, "workers": 2})
                manager.wait(job.id, timeout=120)
                self.assertEqual(job.state, "done", job.error)
            finally:
                manager.shutdown()

            config, replaced = cli_config(["--seed", "3"], 1000)
            expected, _ = batch.execute(config, track_key="wild", replaced=replaced, workers=1)
            with open(os.path.join(results, job.run_id, "summary.json")) as f:
                self.assertEqual(json.load(f)["racers"], json.loads(json.dumps(expected["racers"])))


if __name__ == "__main__":
    unittest.main()
