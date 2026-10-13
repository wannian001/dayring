"""Pairing, tokens, who may reach `serve --lan`, and the routes the iPhone app uses (docs/CAPTURE.md)."""
import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from healthaio import capture, iphone, phone, server, update
from healthaio.config import Config

FIXTURE = Path(__file__).parent / "fixtures" / "capture" / "health_3days.json"


def make_cfg(folder: Path) -> Config:
    return Config(root=folder, data_dir=folder / "data", timezone="Australia/Melbourne")


class Pairing(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="healthaio-pair-"))
        self.cfg = make_cfg(self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_a_code_pairs_once_and_only_hashes_are_kept(self):
        code = phone.open_code(self.cfg)["code"]
        self.assertRegex(code, r"^\d{8}$")
        tokens = phone.pair(self.cfg, code, "iPhone", "app-1")
        stored = (self.folder / ".healthaio" / "devices.json").read_text()
        self.assertNotIn(tokens["capture_token"], stored)
        self.assertNotIn(tokens["read_token"], stored)
        self.assertFalse((self.folder / ".healthaio" / "pairing.json").exists())  # the code is gone once used
        with self.assertRaises(phone.NoCode):
            phone.pair(self.cfg, code, "iPhone", "app-2")  # used up
        self.assertEqual(phone.authenticate(self.cfg, tokens["capture_token"], "capture")["name"], "iPhone")
        self.assertIsNone(phone.authenticate(self.cfg, tokens["capture_token"], "read"))  # each token has one job
        self.assertIsNotNone(phone.authenticate(self.cfg, tokens["read_token"], "read"))
        self.assertIsNone(phone.authenticate(self.cfg, "made-up", "capture"))
        self.assertEqual(set(phone.devices(self.cfg)[0]), {"id", "name", "paired_at", "last_seen"})

    def test_five_wrong_codes_close_it(self):
        code = phone.open_code(self.cfg)["code"]
        wrong = f"{(int(code) + 1) % 10 ** 8:08d}"
        for _ in range(4):
            with self.assertRaises(phone.WrongCode):
                phone.pair(self.cfg, wrong, "iPhone", "x")
        with self.assertRaises(phone.WrongCode):
            phone.pair(self.cfg, wrong, "iPhone", "x")
        with self.assertRaises(phone.NoCode):
            phone.pair(self.cfg, code, "iPhone", "x")

    def test_pairing_the_same_app_again_replaces_it_and_revoke_cuts_off(self):
        first = phone.pair(self.cfg, phone.open_code(self.cfg)["code"], "iPhone", "app-1")
        second = phone.pair(self.cfg, phone.open_code(self.cfg)["code"], "iPhone", "app-1")
        self.assertEqual(len(phone.devices(self.cfg)), 1)
        self.assertIsNone(phone.authenticate(self.cfg, first["capture_token"], "capture"))
        self.assertEqual(phone.revoke(self.cfg, second["device_id"]), 1)
        self.assertIsNone(phone.authenticate(self.cfg, second["capture_token"], "capture"))

    def test_an_expired_code(self):
        code = phone.open_code(self.cfg)["code"]
        path = self.folder / ".healthaio" / "pairing.json"
        data = json.loads(path.read_text())
        data["expires_at"] = "2020-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data))
        with self.assertRaises(phone.NoCode):
            phone.pair(self.cfg, code, "iPhone", "x")

    def test_link(self):
        self.assertEqual(phone.pair_link("http://192.168.1.20:8790", "01234567"),
                         "healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=01234567")


class Network(unittest.TestCase):
    def test_sources(self):
        for ok in ("127.0.0.1", "::1", "192.168.1.20", "10.0.0.5", "172.20.1.1", "100.101.1.2", "fe80::1",
                   "fd7a:115c:a1e0::1", "::ffff:192.168.1.20"):
            self.assertTrue(phone.allowed_source(ok), ok)
        for bad in ("8.8.8.8", "172.32.0.1", "100.128.0.1", "2001:4860::8888", "::ffff:8.8.8.8", "nonsense"):
            self.assertFalse(phone.allowed_source(bad), bad)

    def test_host_header(self):
        for ok in ("127.0.0.1:8790", "localhost:8790", "192.168.1.20:8790", "[fe80::1]:8790", "macbook.local:8790",
                   "macbook.tail1234.ts.net"):
            self.assertTrue(phone.host_ok(ok), ok)
        for bad in (None, "", "evil.example.com", "evil.example.com:8790", "localhost.evil.com"):
            self.assertFalse(phone.host_ok(bad), bad)


class Routes(unittest.TestCase):
    """A real server on 127.0.0.1; `remote` makes it treat the caller as another device on the home network."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="healthaio-routes-"))
        self.cfg = make_cfg(self.folder)
        self.httpd = server.Server(("127.0.0.1", 0), server.make_handler(self.cfg, lan=True))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.remote = mock.patch.object(phone, "is_loopback", return_value=False)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.folder, ignore_errors=True)

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        sent = {"Host": f"127.0.0.1:{self.port}", **({"Content-Type": "application/json"} if data else {}),
                **(headers or {})}
        conn.request(method, path, body=data, headers=sent)
        answer = conn.getresponse()
        raw = answer.read()
        conn.close()
        try:
            return answer.status, json.loads(raw)
        except ValueError:
            return answer.status, raw

    def paired(self):
        code = phone.open_code(self.cfg)["code"]
        status, tokens = self.call("POST", "/capture/v1/pair", {"code": code, "device_name": "iPhone", "device_id": "a"})
        self.assertEqual(status, 200)
        return tokens

    def test_hello_needs_no_token_and_says_lan(self):
        with self.remote:
            status, hello = self.call("GET", "/capture/v1/hello")
        self.assertEqual(status, 200)
        self.assertEqual((hello["app"], hello["protocol"], hello["lan"]), ("healthaio", 1, True))

    def test_another_device_needs_its_tokens(self):
        with self.remote:
            tokens = self.paired()
            self.assertEqual(self.call("GET", "/api/settings")[0], 401)
            self.assertEqual(self.call("GET", "/")[0], 401)
            cookie = {"Cookie": f"healthaio_read={tokens['read_token']}"}
            self.assertEqual(self.call("GET", "/api/settings", headers=cookie)[0], 200)
            self.assertEqual(self.call("GET", "/", headers=cookie)[0], 200)
            self.assertEqual(self.call("GET", "/api/settings",
                                       headers={"Cookie": f"healthaio_read={tokens['capture_token']}"})[0], 401)
            self.assertEqual(self.call("POST", "/capture/v1/packages", FIXTURE.read_bytes())[0], 401)
            bearer = {"Authorization": f"Bearer {tokens['capture_token']}"}
            status, receipt = self.call("POST", "/capture/v1/packages", FIXTURE.read_bytes(), bearer)
            self.assertEqual((status, receipt["status"]), (200, "projected"))
            status, found = self.call("GET", f"/capture/v1/packages/{receipt['package_id']}", headers=bearer)
            self.assertEqual(found["status"], "projected")
            status, info = self.call("GET", "/capture/v1/status", headers=bearer)
            self.assertEqual(info["latest"]["body_daily"], "2026-10-13")
            self.assertEqual(info["device"]["name"], "iPhone")
            self.assertEqual(self.call("GET", "/capture/v1/status",
                                       headers={"Authorization": f"Bearer {tokens['read_token']}"})[0], 401)

    def test_this_computer_needs_no_token(self):
        self.assertEqual(self.call("GET", "/api/settings")[0], 200)
        self.assertEqual(self.call("POST", "/capture/v1/packages", FIXTURE.read_bytes())[1]["status"], "projected")

    def test_web_pages_cannot_write_and_other_hosts_are_refused(self):
        status, _ = self.call("POST", "/capture/v1/packages", FIXTURE.read_bytes(), {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.call("GET", "/api/settings", headers={"Host": "evil.example.com"})[0], 403)
        self.assertEqual(self.call("POST", "/capture/v1/packages", b"x", {"Content-Type": "text/plain"})[0], 415)

    def test_the_panel_in_a_paired_phone_may_set_a_goal(self):
        goal = {"op": "set", "changes": {"food.kcal_max": 2100}}
        page = {"Origin": f"http://127.0.0.1:{self.port}"}
        with self.remote:
            tokens = self.paired()
            self.assertEqual(self.call("POST", "/api/goals", goal, page)[0], 403)  # no read token: not the panel
            cookie = {**page, "Cookie": f"healthaio_read={tokens['read_token']}"}
            self.assertEqual(self.call("POST", "/api/goals", goal, cookie)[0], 200)
            self.assertEqual(self.call("POST", "/api/goals", goal,
                                       {"Cookie": f"healthaio_read={tokens['read_token']}"})[0], 403)  # no Origin

    def test_bad_package_and_conflict(self):
        bad = json.loads(FIXTURE.read_text())
        bad["window"]["start_date"] = "2026-10-01"
        status, answer = self.call("POST", "/capture/v1/packages", bad)
        self.assertEqual(status, 400)
        self.assertIn("window", answer["error"])
        self.call("POST", "/capture/v1/packages", FIXTURE.read_bytes())
        other = json.loads(FIXTURE.read_text())
        other["records"].pop()
        self.assertEqual(self.call("POST", "/capture/v1/packages", other)[0], 409)

    def test_wrong_code(self):
        phone.open_code(self.cfg)
        with self.remote:
            status, answer = self.call("POST", "/capture/v1/pair", {"code": "00000000", "device_name": "x"})
        self.assertEqual(status, 403)
        self.assertIn("code", answer["error"])

    def test_renew_says_why_it_cannot(self):
        with mock.patch.object(iphone, "reason", return_value="no_xcode"):
            status, answer = self.call("POST", "/capture/v1/renew", {})
            self.assertEqual((status, answer["reason"]), (503, "no_xcode"))
            status, answer = self.call("GET", "/capture/v1/renew")
            self.assertEqual((answer["can_renew"], answer["reason"]), (False, "no_xcode"))

    def test_update_only_from_this_computers_own_page(self):
        origin = {"Origin": f"http://127.0.0.1:{self.port}"}
        self.assertEqual(self.call("POST", "/api/update", {})[0], 403)  # no Origin: not a page
        with self.remote:
            self.assertEqual(self.call("POST", "/api/update", {}, origin)[0], 403)  # a phone
        done = threading.Event()
        with mock.patch.object(update, "apply", side_effect=lambda cfg: done.set() or {"ok": False, "message": "x"}):
            self.assertEqual(self.call("POST", "/api/update", {}, origin)[0], 202)
            self.assertTrue(done.wait(5))
        self.assertEqual(self.call("GET", "/api/version")[1]["current"], update.__version__)


class Restart(unittest.TestCase):
    def test_restart_runs_the_same_command_again(self):
        with mock.patch("os.execv") as execv, mock.patch("sys.argv", ["/x/healthaio/__main__.py", "serve", "--lan"]):
            server.restart()
        args = execv.call_args[0][1]
        self.assertEqual(args[1:], ["-m", "healthaio", "serve", "--lan"])


if __name__ == "__main__":
    unittest.main()
