"""The update check against GitHub (a stand-in server here) and what `healthaio update` may and may not do."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from healthaio import update
from healthaio.config import Config, ConfigError, load


class FakeGitHub(BaseHTTPRequestHandler):
    release = None             # dict, or None for "no releases yet" (404)
    tags = []
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        FakeGitHub.calls.append(self.path)
        if self.path.endswith("/releases/latest"):
            body, status = (FakeGitHub.release, 200) if FakeGitHub.release else ({"message": "Not Found"}, 404)
        elif "/tags" in self.path:
            body, status = [{"name": t} for t in FakeGitHub.tags], 200
        else:
            body, status = {}, 404
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class Versions(unittest.TestCase):
    def test_order(self):
        self.assertTrue(update.newer("v0.3.10", "0.3.9"))
        self.assertTrue(update.newer("0.4.0", "0.3.99"))
        self.assertFalse(update.newer("v0.3.0", "0.3.0"))
        self.assertFalse(update.newer("0.4.0-rc1", "0.4.0"))
        self.assertTrue(update.newer("0.4.0", "0.4.0-rc1"))
        self.assertFalse(update.newer(None, "0.3.0"))
        self.assertFalse(update.newer("latest", "0.3.0"))


class Check(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp(prefix="healthaio-cache-")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        FakeGitHub.release, FakeGitHub.tags, FakeGitHub.calls = None, [], []
        self.patches = [mock.patch.dict(os.environ, {"HEALTHAIO_CACHE_DIR": self.cache}),
                        mock.patch.object(update, "API", f"http://127.0.0.1:{self.httpd.server_address[1]}/repos/x/y"),
                        mock.patch.object(update, "__version__", "0.3.0"),
                        mock.patch.object(update, "_blocker", return_value=None)]
        for p in self.patches:
            p.start()
        os.environ.pop("HEALTHAIO_NO_UPDATE_CHECK", None)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.cache, ignore_errors=True)

    def test_a_newer_release(self):
        FakeGitHub.release = {"tag_name": "v0.3.1", "html_url": "https://github.com/x/y/releases/tag/v0.3.1",
                              "body": "Faster pages."}
        info = update.check()
        self.assertEqual((info["latest"], info["update_available"], info["notes"]), ("0.3.1", True, "Faster pages."))
        self.assertTrue(info["can_update"])
        self.assertEqual(update.cached()["latest"], "0.3.1")  # the pages read this, without going online

    def test_asks_at_most_once_in_twenty_hours(self):
        FakeGitHub.release = {"tag_name": "v0.3.0"}
        update.check()
        update.check()
        self.assertEqual(len(FakeGitHub.calls), 1)
        update.check(force=True)
        self.assertEqual(len(FakeGitHub.calls), 2)

    def test_tags_when_there_are_no_releases(self):
        FakeGitHub.tags = ["v0.2.0", "v0.3.2", "v0.3.10", "nightly"]
        info = update.check()
        self.assertEqual(info["latest"], "0.3.10")
        self.assertIn("/tree/v0.3.10", info["url"])

    def test_nothing_published_yet(self):
        info = update.check()
        self.assertEqual((info["latest"], info["update_available"]), (None, False))

    def test_offline_keeps_what_it_knew(self):
        FakeGitHub.release = {"tag_name": "v0.3.1"}
        update.check()
        with mock.patch.object(update, "API", "http://127.0.0.1:9/none"):
            info = update.check(force=True)
        self.assertEqual(info["latest"], "0.3.1")
        self.assertIn("could not reach GitHub", info["reason"])

    def test_turned_off(self):
        with mock.patch.dict(os.environ, {"HEALTHAIO_NO_UPDATE_CHECK": "1"}):
            info = update.check(force=True)
        self.assertEqual((info["reason"], FakeGitHub.calls), ("off", []))
        cfg = Config(root=Path(self.cache), data_dir=Path(self.cache))
        cfg.check_updates = False
        self.assertEqual(update.check(cfg, force=True)["reason"], "off")
        self.assertEqual(FakeGitHub.calls, [])

    def test_apply_does_nothing_when_up_to_date(self):
        FakeGitHub.release = {"tag_name": "v0.3.0"}
        result = update.apply()
        self.assertTrue(result["ok"])
        self.assertEqual(result["to"], "0.3.0")

    def test_apply_refuses_a_copy_it_cannot_update(self):
        FakeGitHub.release = {"tag_name": "v0.4.0"}
        with mock.patch.object(update, "_blocker", return_value="this copy has changes of your own"):
            result = update.apply()
        self.assertFalse(result["ok"])
        self.assertIn("changes of your own", result["message"])


@unittest.skipUnless(shutil.which("git"), "needs git")
class GitCopy(unittest.TestCase):
    """A stand-in for GitHub (a folder with tags), a copy cloned at v0.3.0, and `update` moving it to v0.3.1."""

    def git(self, folder, *args):
        return subprocess.run(["git", "-C", str(folder), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                               "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                              capture_output=True, text=True, check=True).stdout

    def version(self, folder, number):
        (folder / "healthaio").mkdir(exist_ok=True)
        (folder / "healthaio" / "__init__.py").write_text(f'__version__ = "{number}"\n')

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-git-"))
        self.origin, self.copy = self.tmp / "origin", self.tmp / "copy"
        self.origin.mkdir()
        self.git(self.origin, "init", "-q", "-b", "main")
        self.version(self.origin, "0.3.0")
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-q", "-m", "0.3.0")
        self.git(self.origin, "tag", "v0.3.0")
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.copy)], check=True, capture_output=True)
        self.version(self.origin, "0.3.1")
        (self.origin / "ios").mkdir()
        (self.origin / "ios" / "App.swift").write_text("// new\n")
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-q", "-m", "0.3.1")
        self.git(self.origin, "tag", "v0.3.1")
        self.patches = [mock.patch.object(update, "ROOT", self.copy), mock.patch.object(update, "__version__", "0.3.0"),
                        mock.patch.object(update, "_latest", return_value={"latest": "0.3.1", "url": "u", "notes": ""}),
                        mock.patch.dict(os.environ, {"HEALTHAIO_CACHE_DIR": str(self.tmp / "cache")})]
        for p in self.patches:
            p.start()
        os.environ.pop("HEALTHAIO_NO_UPDATE_CHECK", None)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_moves_to_the_release_tag_and_says_what_changed(self):
        result = update.apply()
        self.assertTrue(result["ok"], result["message"])
        self.assertEqual((result["from"], result["to"], result["method"]), ("0.3.0", "0.3.1", "git"))
        self.assertEqual(result["changed"], {"mac_app": False, "ios_app": True})
        self.assertIn('"0.3.1"', (self.copy / "healthaio" / "__init__.py").read_text())

    def test_never_over_your_own_changes(self):
        (self.copy / "healthaio" / "__init__.py").write_text('__version__ = "0.3.0"  # mine\n')
        info = update.check(force=True)
        self.assertFalse(info["can_update"])
        self.assertIn("changes of your own", info["reason"])
        self.assertFalse(update.apply()["ok"])
        self.assertIn("# mine", (self.copy / "healthaio" / "__init__.py").read_text())

    def test_never_over_your_own_commits(self):
        (self.copy / "notes.txt").write_text("mine\n")
        self.git(self.copy, "add", ".")
        self.git(self.copy, "commit", "-q", "-m", "mine")
        result = update.apply()
        self.assertFalse(result["ok"])
        self.assertIn("commits of its own", result["message"])
        self.assertTrue((self.copy / "notes.txt").is_file())


class Settings(unittest.TestCase):
    def test_config_keys(self):
        folder = Path(tempfile.mkdtemp(prefix="healthaio-cfg-"))
        try:
            path = folder / "healthaio.toml"
            path.write_text('[collect]\nsources = ["macos-screentime", "ai-logs"]\n[updates]\ncheck = false\n')
            cfg = load(path)
            self.assertEqual((cfg.collect_sources, cfg.check_updates), (["macos-screentime", "ai-logs"], False))
            path.write_text('[collect]\nsources = ["everything"]\n')
            with self.assertRaises(ConfigError):
                load(path)
            path.write_text('[healthaio]\ntimezone = "UTC"\n')
            cfg = load(path)
            self.assertEqual((cfg.collect_sources, cfg.check_updates), (["macos-screentime"], True))
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
