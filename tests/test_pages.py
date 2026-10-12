"""Every page builds from the demo person, stays JSON-clean, and keeps the rules it promises."""
import json
import re
import math
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

from dayring import config, demo, stats
from dayring.context import Context
from dayring.modules import PAGES, plans, static_params
from dayring.server import make_handler, payload
from dayring.store import write_table

TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)


def walk(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)
    else:
        yield value


class DemoPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dayring-test-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:  # Python 3.9/3.10 without tomli: same settings as JSON
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo dayring.toml")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_page_builds_and_is_json_clean(self):
        for name in PAGES:
            data = payload(self.cfg, name, None, NOW)
            text = json.dumps(data, default=str)
            self.assertNotIn("NaN", text, name)
            for v in walk(data):
                if isinstance(v, float):
                    self.assertTrue(math.isfinite(v), name)

    def test_demo_is_deterministic(self):
        again = Path(tempfile.mkdtemp(prefix="dayring-test-"))
        try:
            demo.generate(again, TODAY, NOW)
            for f in ("body_daily.csv", "screen_sessions.csv"):
                self.assertEqual((self.tmp / "data" / f).read_bytes(), (again / "data" / f).read_bytes(), f)
        finally:
            shutil.rmtree(again, ignore_errors=True)

    def test_today_marks_the_unfinished_day(self):
        data = payload(self.cfg, "today", None, NOW)
        steps = next(m for m in data["activity"] if m["key"] == "steps")
        self.assertTrue(steps["partial"])
        self.assertIsNone(steps["band"])  # a half-day is never compared with whole days

    def test_look_back_uses_only_the_past(self):
        day = (TODAY - timedelta(days=5)).isoformat()
        data = payload(self.cfg, "today", day, NOW)
        self.assertTrue(data["looking_back"])
        for m in data["recovery"]["metrics"]:
            for point in m["series"]:
                self.assertLessEqual(point["date"], day)

    def test_wake_shift_never_moves_later(self):
        ctx = Context(self.cfg, now=NOW)
        ladder = plans.alarms(ctx, TODAY)
        self.assertTrue(ladder)
        minutes = [int(x["alarm"][:2]) * 60 + int(x["alarm"][3:]) for x in ladder]
        for a, b, day in zip(minutes, minutes[1:], ladder):
            self.assertLessEqual(b, a)
            self.assertEqual(b < a, bool(day["on_time"]) and a > 7 * 60 + 30)

    def test_screen_time_counts_overlap_once(self):
        folder = Path(tempfile.mkdtemp(prefix="dayring-test-"))
        try:
            write_table(folder, "screen_sessions", [
                {"start": datetime(2026, 1, 1, 10, 0), "end": datetime(2026, 1, 1, 11, 0), "device": "laptop", "app": "Docs", "category": "work"},
                {"start": datetime(2026, 1, 1, 10, 30), "end": datetime(2026, 1, 1, 10, 45), "device": "phone", "app": "Reddit", "category": "social"},
            ])
            cfg = config.Config(root=folder, data_dir=folder, devices=["phone", "laptop"])
            sd = Context(cfg, now=datetime(2026, 1, 2, 9, 0)).screen_days()[date(2026, 1, 1)]
            self.assertEqual(sd.total, 60)
            self.assertEqual(sd.by_category["social"], 15)
            self.assertEqual(sd.by_category["work"], 45)
            self.assertEqual(sd.longest_focus, 30)  # a 15-minute scroll breaks the stretch
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_static_params_render(self):
        ctx = Context(self.cfg, now=NOW)
        for name in PAGES:
            for param in static_params(name, ctx):
                payload(self.cfg, name, param, NOW)


class Stats(unittest.TestCase):
    def test_typical_excludes_the_day_itself(self):
        values = {date(2026, 1, 1) + timedelta(days=k): float(k) for k in range(40)}
        band = stats.typical(values, date(2026, 2, 9))
        self.assertEqual(band["days"], 28)
        self.assertLess(band["q3"], 39)

    def test_unknown_is_not_zero(self):
        self.assertIsNone(stats.classify(None, {"q1": 1, "q3": 2, "median": 1.5}))
        self.assertEqual(stats.tone(None, "higher"), "neutral")

    def test_bh_is_monotone(self):
        adjusted = stats.benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
        self.assertEqual(len(adjusted), 4)
        self.assertTrue(all(0 <= p <= 1 for p in adjusted))
        self.assertLessEqual(adjusted[0], adjusted[2])


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dayring-test-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli")
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.cfg, lambda: NOW))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        return urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10)

    def test_pages_and_assets(self):
        self.assertIn(b"dayring", self.get("/").read())
        self.assertEqual(json.loads(self.get("/api/today").read())["page"], "today")
        self.assertEqual(json.loads(self.get("/api/settings").read())["demo"], True)
        self.assertIn("javascript", self.get("/js/app.js").headers["Content-Type"])

    def test_rejects_traversal_and_bad_params(self):
        for path in ("/../dayring.toml", "/%2e%2e/dayring.toml", "/api/nope", "/api/today?day=../../x"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get(path)
            self.assertIn(caught.exception.code, (400, 404))


class StaticBuild(unittest.TestCase):
    def test_build(self):
        tmp = Path(tempfile.mkdtemp(prefix="dayring-test-"))
        try:
            try:
                cfg = config.load(demo.generate(tmp / "demo", TODAY, NOW))
            except config.ConfigError:
                self.skipTest("needs Python 3.11+ or tomli")
            from dayring.build_static import build
            out = build(cfg, tmp / "site", now=NOW)
            self.assertIn('data-static="true"', (out / "index.html").read_text())
            self.assertTrue((out / "api" / "today.json").is_file())
            self.assertTrue((out / "api" / f"today@{(TODAY - timedelta(days=1)).isoformat()}.json").is_file())
            self.assertTrue((out / ".nojekyll").is_file())
            # every script and stylesheet URL carries the build's content hash, imports included
            index = (out / "index.html").read_text()
            version = re.search(r'data-build="([0-9a-f]{10})"', index).group(1)
            self.assertIn(f'js/app.js?v={version}"', index)
            self.assertIn(f'css/app.css?v={version}"', index)
            for js in (out / "js").rglob("*.js"):
                for spec in re.findall(r'from\s+"(\.{1,2}/[^"]+)"', js.read_text()):
                    self.assertTrue(spec.endswith(f"?v={version}"), f"{js.name}: {spec}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
