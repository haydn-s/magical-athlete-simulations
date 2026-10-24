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
        self.assertIn(b"npm run build", ctx.exception.read())


if __name__ == "__main__":
    unittest.main()
