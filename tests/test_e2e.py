"""
End-to-end check of `python -m sim serve` with the built viewer.

Starts the real server as a subprocess, loads the app, launches a run through the
API (with spawned worker processes, as in normal use) and reads its results back.
Skipped when web/dist hasn't been built, unless REQUIRE_E2E=1 (set in CI).
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_INDEX = os.path.join(ROOT, "web", "dist", "index.html")
REQUIRED = os.environ.get("REQUIRE_E2E") == "1"


@unittest.skipUnless(os.path.isfile(DIST_INDEX) or REQUIRED, "web/dist not built (cd web && npm run build)")
class ServeEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(DIST_INDEX), "web/dist/index.html is missing")
        self.results = tempfile.TemporaryDirectory()
        self.server = subprocess.Popen(
            [sys.executable, "-m", "sim", "serve", "--port", "0", "--results", self.results.name],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        line = self.server.stdout.readline()
        match = re.search(r"http://127\.0\.0\.1:(\d+)", line)
        self.assertIsNotNone(match, f"unexpected server output: {line!r}")
        self.base = f"http://127.0.0.1:{match.group(1)}"

    def tearDown(self):
        if self.server.poll() is None:
            self.server.kill()
            self.server.wait(timeout=10)
        self.server.stdout.close()
        self.results.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return response.status, response.read()

    def post(self, path, body):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Origin": self.base},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())

    def test_launch_a_run_and_view_it(self):
        status, page = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'<div id="root">', page)
        for asset in re.findall(rb'(?:src|href)="\./(assets/[^"]+)"', page):
            self.assertEqual(self.get("/" + asset.decode())[0], 200)

        roster = json.loads(self.get("/api/roster")[1])
        self.assertIn("Scoocher", [r["name"] for r in roster["racers"]])

        status, job = self.post("/api/jobs", {"games": 2000, "seed": 3, "label": "e2e", "focus": ["Oddball"]})
        self.assertEqual(status, 202)

        deadline = time.time() + 120
        while job["state"] in ("queued", "running"):
            self.assertLess(time.time(), deadline, f"job still {job['state']}")
            time.sleep(0.2)
            job = json.loads(self.get(f"/api/jobs/{job['id']}")[1])
        self.assertEqual(job["state"], "done", job["error"])

        runs = json.loads(self.get("/api/runs")[1])
        self.assertEqual([r["id"] for r in runs], [job["run_id"]])
        summary = json.loads(self.get(f"/api/runs/{job['run_id']}")[1])
        self.assertEqual(summary["totals"]["games"], 2000)
        self.assertEqual(summary["manifest"]["config"]["focus"], ["Oddball"])
        self.assertEqual(summary["manifest"]["command"], job["command"])

        replay = json.loads(self.get(f"/api/runs/{job['run_id']}/games/7")[1])
        self.assertEqual(replay["game"], 7)
        self.assertFalse(replay["code_changed"])
        self.assertIn("Oddball", [r["name"] for r in replay["racers"]])
        self.assertTrue(replay["frames"])

        self.server.send_signal(signal.SIGINT)
        self.assertEqual(self.server.wait(timeout=20), 0)


if __name__ == "__main__":
    unittest.main()
