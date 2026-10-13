"""A stand-in for `python -m healthaio` that answers the Mac app's commands with made-up data (development only).

Run the app against it instead of the real CLI:

    HEALTHAIO_CLI="python3 /absolute/path/to/mac/tools/fake_healthaio.py" \\
        "mac/build/Health AIO.app/Contents/MacOS/HealthAIO" -configPath /tmp/demo/healthaio.toml

It prints the JSON shapes listed under "The commands it relies on" in mac/README.md. State is kept in a small JSON file
(FAKE_HEALTHAIO_STATE, default: fake-healthaio.json in the temp folder), so pairing adds a device, renewing moves the
signature date and updating changes the version. Knobs, all optional:

    FAKE_UPDATE=0.3.1        offer this version as an update (default: no update)
    FAKE_EXPIRES_DAYS=5      days of signature left the first time the state is made (default 5)
    FAKE_DELAY=2             seconds that collect, update and renew take (default 1)
    FAKE_FAIL=collect,renew  these commands fail (JSON with ok false, exit 2)
    FAKE_GARBAGE=status      these commands print a traceback and no JSON (exit 1)
    FAKE_SERVE_EXIT=1        serve exits after a second, to watch the app's back-off
    FAKE_FDA=0               report Full Disk Access as missing
"""
import json
import os
import random
import signal
import sys
import tempfile
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.3.0"


def now():
    return datetime.now().astimezone().replace(microsecond=0)


def iso(dt):
    return dt.isoformat()


def env_list(name):
    return {x.strip() for x in os.environ.get(name, "").split(",") if x.strip()}


def state_path():
    return os.environ.get("FAKE_HEALTHAIO_STATE") or os.path.join(tempfile.gettempdir(), "fake-healthaio.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        days = float(os.environ.get("FAKE_EXPIRES_DAYS", "5"))
        installed = now() - timedelta(days=7 - days)
        return {
            "version": VERSION,
            "collect": None,
            "devices": [{"id": "fake-device-1", "name": "iPhone", "paired_at": iso(now() - timedelta(days=3)),
                         "last_seen": iso(now() - timedelta(minutes=20))}],
            "renew": {"at": iso(installed), "ok": True, "expires_at": iso(installed + timedelta(days=7)),
                      "version": VERSION, "message": "Installed on iPhone"},
            "pair": None,
            "update_checked_at": None,
        }


def save_state(state):
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, state_path())


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def delay():
    time.sleep(float(os.environ.get("FAKE_DELAY", "1")))


def update_info(state, checked=True):
    latest = os.environ.get("FAKE_UPDATE") or state["version"]
    available = latest != state["version"]
    return {"current": state["version"], "latest": latest, "update_available": available,
            "url": "https://github.com/wannian001/proactive-health-aio/releases/tag/v" + latest,
            "notes": "Made-up notes for %s.\nA second line.\nA third line." % latest if available else "",
            "checked_at": state.get("update_checked_at") if not checked else iso(now()),
            "install": "git", "can_update": True, "reason": None}


def iphone(state):
    return {"can_renew": True, "reason": None, "running": False, "last": state.get("renew")}


def serve(args):
    port = 8790
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    host = "0.0.0.0" if "--lan" in args else "127.0.0.1"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"app": "healthaio", "fake": True, "version": VERSION}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *a):
            sys.stderr.write("fake serve: " + (fmt % a) + "\n")

    if os.environ.get("FAKE_SERVE_EXIT") == "1":
        print("fake serve: exiting on purpose", flush=True)
        time.sleep(1)
        sys.exit(1)
    server = ThreadingHTTPServer((host, port), Handler)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print("Health AIO (fake) on http://%s:%d" % ("localhost" if host == "127.0.0.1" else host, port), flush=True)
    server.serve_forever()


def main(argv):
    if "--config" in argv:
        i = argv.index("--config")
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        sys.exit("usage: fake_healthaio.py [--config FILE] COMMAND …")
    command = argv[0]
    words = " ".join(a for a in argv if not a.startswith("-"))
    if command in env_list("FAKE_GARBAGE") or words in env_list("FAKE_GARBAGE"):
        sys.stderr.write("Traceback (most recent call last):\n  File \"fake\", line 1\nRuntimeError: made-up failure\n")
        sys.exit(1)
    failing = command in env_list("FAKE_FAIL") or words in env_list("FAKE_FAIL")
    state = load_state()

    if command == "serve":
        serve(argv[1:])
    elif command == "collect":
        delay()
        fda = os.environ.get("FAKE_FDA", "1") != "0" and not failing
        result = {"ok": fda, "at": iso(now()), "sources": [
            {"name": "macos-screentime", "ok": fda,
             "message": "412 sessions on 3 devices" if fda else "Full Disk Access is needed to read Screen Time."},
            {"name": "ai-logs", "ok": True, "message": "38 sessions"}]}
        state["collect"] = result
        save_state(state)
        out(result, 0 if result["ok"] else 2)
    elif command == "status":
        out({"version": state["version"], "config": "healthaio.toml", "data_dir": "data", "timezone": "Australia/Melbourne",
             "port": 8790, "collect": state["collect"], "devices": state["devices"],
             "latest": {"body_daily": now().date().isoformat(), "screen_sessions": now().strftime("%Y-%m-%dT%H:%M")},
             "full_disk_access": os.environ.get("FAKE_FDA", "1") != "0",
             "iphone": iphone(state), "update": update_info(state, checked=False)})
    elif command == "pair":
        code = "%08d" % random.randrange(10 ** 8)
        state["pair"] = {"code": code, "expires_at": iso(now() + timedelta(minutes=10))}
        save_state(state)
        url = "http://192.168.1.20:8790"
        out({"code": code, "expires_at": state["pair"]["expires_at"], "urls": [url, "http://10.0.0.20:8790"],
             "link": "healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=" + code,
             "server_running": True, "server_lan": True})
    elif command == "devices":
        if len(argv) > 1 and argv[1] == "revoke":
            before = len(state["devices"])
            state["devices"] = [] if "--all" in argv else [d for d in state["devices"] if d["id"] not in argv]
            save_state(state)
            out({"ok": True, "revoked": before - len(state["devices"])})
        out({"devices": state["devices"]})
    elif command == "update":
        if "--check" in argv:
            info = update_info(state)
            state["update_checked_at"] = info["checked_at"]
            save_state(state)
            out(info)
        delay()
        latest = os.environ.get("FAKE_UPDATE") or state["version"]
        if failing:
            out({"ok": False, "from": state["version"], "to": latest, "method": "git",
                 "changed": {"mac_app": False, "ios_app": False}, "message": "git pull failed (made up)."}, 2)
        old, state["version"] = state["version"], latest
        save_state(state)
        out({"ok": True, "from": old, "to": latest, "method": "git", "changed": {"mac_app": True, "ios_app": True},
             "message": "Updated with git."})
    elif command == "iphone":
        if len(argv) > 1 and argv[1] == "renew":
            delay()
            if failing:
                out({"ok": False, "at": iso(now()), "expires_at": None, "version": state["version"], "device": "iPhone",
                     "message": "No iPhone found on a cable or the same Wi-Fi (made up)."}, 2)
            state["renew"] = {"at": iso(now()), "ok": True, "expires_at": iso(now() + timedelta(days=7)),
                              "version": state["version"], "message": "Installed on iPhone"}
            save_state(state)
            out({"ok": True, "at": state["renew"]["at"], "expires_at": state["renew"]["expires_at"],
                 "version": state["version"], "device": "iPhone", "message": "Installed on iPhone"})
        out(iphone(state))
    else:
        sys.exit("fake_healthaio: unknown command %r" % command)


if __name__ == "__main__":
    main(sys.argv[1:])
