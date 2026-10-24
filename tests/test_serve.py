"""Tests for the results viewer's local API (python -m sim serve)."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.jobs import JobManager
from sim.serve import make_server


def write_run(results_dir, run_id, created):
    os.makedirs(os.path.join(results_dir, run_id))
    summary = {
        "manifest": {"created": created, "config": {"track": "wild"}},
        "totals": {"games": 10},
        "racers": [{"name": "Hare"}, {"name": "Banana"}],
    }
    with open(os.path.join(results_dir, run_id, "summary.json"), "w") as f:
        json.dump(summary, f)
    with open(os.path.join(results_dir, run_id, "racers.csv"), "w") as f:
        f.write("name\nHare\n")


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.results = os.path.join(cls.tmp.name, "results")
        write_run(cls.results, "older", "2026-01-01T00:00:00")
        write_run(cls.results, "newer", "2026-02-01T00:00:00")
        os.makedirs(os.path.join(cls.results, "not-a-run"))
        with open(os.path.join(cls.tmp.name, "secret.json"), "w") as f:
            f.write('{"secret": true}')

        cls.server = make_server(port=0, results_dir=cls.results, web_dir=os.path.join(cls.tmp.name, "dist"))
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as response:
            return response.status, response.headers, response.read()

    def assert_not_found(self, path):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get(path)
        with ctx.exception:
            self.assertEqual(ctx.exception.code, 404)

    def test_lists_runs_newest_first(self):
        _, _, body = self.get("/api/runs")
        runs = json.loads(body)
        self.assertEqual([r["id"] for r in runs], ["newer", "older"])
        self.assertEqual(runs[0]["racer_count"], 2)
        self.assertNotIn("racers", runs[0])

    def test_returns_one_run(self):
        _, _, body = self.get("/api/runs/older")
        self.assertEqual(json.loads(body)["manifest"]["created"], "2026-01-01T00:00:00")

    def test_downloads_only_known_files(self):
        status, headers, body = self.get("/api/runs/newer/files/racers.csv")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(body, b"name\nHare\n")
        self.assert_not_found("/api/runs/newer/files/head_to_head.csv")  # known name, missing file
        self.assert_not_found("/api/runs/newer/files/other.txt")

    def test_rejects_unknown_and_traversal_ids(self):
        for path in (
            "/api/runs/missing",
            "/api/runs/not-a-run",
            "/api/runs/..",
            "/api/runs/..%2Fsecret.json",
            "/api/runs/..%2F..%2Fetc",
            "/api/runs/newer%2F..%2F..%2Fsecret.json",
            "/api/runs/../files/summary.json",
            "/api/nothing",
        ):
            with self.subTest(path=path):
                self.assert_not_found(path)

    def test_explains_missing_build(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/")
        with ctx.exception:
            self.assertIn(b"npm run build", ctx.exception.read())


class JobsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.jobs = JobManager(cls.tmp.name, mp_context=None)
        cls.server = make_server(port=0, results_dir=cls.tmp.name, web_dir=cls.tmp.name, jobs=cls.jobs)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.jobs.shutdown()
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, path, body=None, headers=None, method=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as err:
            with err:
                raw = err.read()
            try:
                return err.code, json.loads(raw)
            except ValueError:
                return err.code, raw.decode(errors="replace")

    def test_roster(self):
        status, info = self.request("/api/roster")
        self.assertEqual(status, 200)
        racers = {r["name"]: r for r in info["racers"]}
        self.assertTrue(racers["Scoocher"]["default"])
        self.assertEqual(racers["ScoocherWeakened"], {"name": "ScoocherWeakened", "identifier": 55,
                                                      "default": False, "variant_of": "Scoocher"})
        self.assertIn("wild", [t["key"] for t in info["tracks"]])
        self.assertEqual(info["defaults"]["players"], 7)

    def test_start_a_run_and_see_it_listed(self):
        status, job = self.request("/api/jobs", {"games": 200, "seed": 5, "workers": 1, "label": "api"},
                                   headers={"Origin": "http://localhost:5199"})
        self.assertEqual(status, 202)
        self.assertIn(job["state"], ("queued", "running"))
        self.assertEqual(job["settings"]["seed"], 5)

        self.jobs.wait(job["id"], timeout=60)
        status, job = self.request(f"/api/jobs/{job['id']}")
        self.assertEqual((status, job["state"], job["done"], job["total"]), (200, "done", 200, 200))

        _, runs = self.request("/api/runs")
        self.assertIn(job["run_id"], [r["id"] for r in runs])
        _, jobs = self.request("/api/jobs")
        self.assertEqual(jobs[0]["id"], job["id"])

    def test_invalid_settings_are_explained(self):
        status, body = self.request("/api/jobs", {"focus": ["Nobody"]})
        self.assertEqual(status, 400)
        self.assertIn("Unknown racer 'Nobody'", body["error"])

        status, body = self.request("/api/jobs", b"{not json")
        self.assertEqual(status, 400)

    def test_cancel(self):
        status, job = self.request("/api/jobs", {"games": 2_000_000, "seed": 1, "workers": 1})
        self.assertEqual(status, 202)
        status, job = self.request(f"/api/jobs/{job['id']}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(self.jobs.wait(job["id"], timeout=60).state, "cancelled")
        self.assertEqual(self.request("/api/jobs/nope/cancel", {})[0], 404)

    def test_rejects_requests_a_web_page_could_forge(self):
        # Simple cross-site form posts can't set a JSON content type...
        status, _ = self.request("/api/jobs", b'{"games": 10}', headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        # ...a cross-origin script is turned away by its Origin...
        status, _ = self.request("/api/jobs", {"games": 10}, headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("/api/jobs", {"games": 10}, headers={"Origin": "null"})
        self.assertEqual(status, 403)
        # ...and a DNS-rebinding page arrives with its own host name.
        status, _ = self.request("/api/jobs", {"games": 10}, headers={"Host": "evil.example:8000"})
        self.assertEqual(status, 403)
        status, _ = self.request("/api/runs", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("/api/jobs", b"[" + b"0," * 40_000 + b"0]")
        self.assertEqual(status, 413)
        self.assertFalse(any(j.settings["games"] == 10 for j in self.jobs.list()))


if __name__ == "__main__":
    unittest.main()
