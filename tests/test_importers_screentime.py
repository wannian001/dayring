"""The Screen Time importer against synthetic SEGB files built here (no real Biome data)."""
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dayring.config import Config
from dayring.importers import macos_screentime as st
from dayring.store import Store

TZ = "Australia/Melbourne"


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def focus_payload(bundle: str, entered: bool, at: datetime, kind: int = 1) -> bytes:
    name = bundle.encode()
    return (b"\x10" + varint(kind) + b"\x18" + varint(1 if entered else 0)
            + b"\x21" + struct.pack("<d", at.timestamp() - st.MAC_EPOCH)
            + b"\x32" + varint(len(name)) + name)


def segb(payloads, states=None) -> bytes:
    states = states or [1] * len(payloads)
    body = bytearray(b"SEGB" + struct.pack("<i", len(payloads)) + struct.pack("<d", 0.0))
    body += b"\x00" * (0x20 - len(body))
    index = []
    for payload, state in zip(payloads, states):
        start = len(body)
        body += struct.pack("<Ii", 0, 0) + payload
        index.append((start + 8 + len(payload) - 0x20, state))
        body += b"\x00" * ((-len(body)) % 4)
    body += b"\x00" * 64
    trailer = b"".join(struct.pack("<iid", end, state, 0.0) for end, state in reversed(index))
    return bytes(body + trailer)


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class ScreenTimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)
        self.root = self.tmp / "streams"
        local = self.root / st.STREAM / "local"
        phone = self.root / st.STREAM / "remote" / "PHONE-ID"
        local.mkdir(parents=True)
        phone.mkdir(parents=True)
        # 2026-10-12 00:00Z = 11:00 Melbourne
        mac_events = [
            focus_payload("com.apple.dt.Xcode", True, utc(2026, 10, 12, 0, 0, 10)),
            focus_payload("com.apple.Safari", True, utc(2026, 10, 12, 0, 20, 0)),       # ends Xcode
            focus_payload("com.apple.Safari", False, utc(2026, 10, 12, 0, 30, 0)),
            focus_payload("com.apple.loginwindow", True, utc(2026, 10, 12, 0, 30, 0)),  # locked: not usage
            focus_payload("com.apple.notificationcenterui", True, utc(2026, 10, 12, 1, 0), kind=3),
            focus_payload("com.apple.Terminal", True, utc(2026, 10, 12, 2, 0, 0)),      # left open 2 h: capped
            focus_payload("com.google.ios.youtube", True, utc(2026, 10, 12, 4, 0, 0)),
            focus_payload("com.google.ios.youtube", False, utc(2026, 10, 12, 5, 30, 0)),  # entertainment: no cap
            focus_payload("com.apple.Notes", True, utc(2026, 10, 12, 6, 0, 0)),
            focus_payload("com.apple.Notes", False, utc(2026, 10, 12, 6, 0, 20)),       # 20 s: rounds to zero
            focus_payload("org.example.unknownapp", True, utc(2026, 10, 12, 7, 0, 0)),
            focus_payload("org.example.unknownapp", False, utc(2026, 10, 12, 7, 10, 0)),
            focus_payload("com.apple.Safari", True, utc(2026, 10, 12, 8, 0, 0)),        # no end yet: dropped
        ]
        # a deleted entry (state 3) must be ignored
        (local / "100").write_bytes(segb(mac_events + [focus_payload("com.apple.Mail", True, utc(2026, 10, 12, 1, 0))],
                                         states=[1] * len(mac_events) + [3]))
        (local / "200").write_bytes(b"junk that is not a SEGB file")
        phone_events = [
            focus_payload("com.burbn.instagram", True, utc(2026, 10, 12, 10, 0, 0)),
            focus_payload("com.tencent.xinWeChat", True, utc(2026, 10, 12, 10, 5, 0)),
            focus_payload("com.tencent.xinWeChat", False, utc(2026, 10, 12, 10, 9, 0)),
            focus_payload("com.burbn.instagram", True, utc(2026, 9, 1, 0, 0, 0)),       # older than --days
        ]
        (phone / "1").write_bytes(segb(phone_events))
        self.sync_db = self.tmp / "sync.db"
        con = sqlite3.connect(str(self.sync_db))
        con.execute("create table DevicePeer (device_identifier STRING NOT NULL, ids_device_identifier STRING, "
                    "me BOOLEAN, name STRING, model STRING, platform INTEGER, last_sync_date INTEGER, "
                    "protocol_version INTEGER NOT NULL)")
        con.execute("insert into DevicePeer values ('PHONE-ID', NULL, 0, 'x', 'x', 2, 10, 1)")
        con.commit()
        con.close()
        self.now = utc(2026, 10, 12, 12, 0).timestamp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_import(self):
        return st.import_screentime(self.cfg, days=7, root=self.root, sync_db=self.sync_db,
                                    local_device="laptop", now=self.now)

    def test_sessions(self):
        summary = self.run_import()
        loaded = Store(self.cfg.data_dir).load("screen_sessions")
        self.assertEqual(loaded.problems, [])
        rows = [(r["device"], r["app"], r["category"], r["start"].strftime("%H:%M"), r["end"].strftime("%H:%M"))
                for r in loaded.rows]
        self.assertEqual(rows, [
            ("laptop", "Xcode", "work", "11:00", "11:20"),
            ("laptop", "Safari", "other", "11:20", "11:30"),
            ("laptop", "Terminal", "work", "13:00", "13:45"),
            ("laptop", "YouTube", "entertainment", "15:00", "16:30"),
            ("laptop", "unknownapp", "other", "18:00", "18:10"),
            ("phone", "Instagram", "social", "21:00", "21:05"),
            ("phone", "WeChat", "communication", "21:05", "21:09"),
        ])
        self.assertEqual(summary.imported, 7)
        self.assertTrue(any("not a SEGB" in n for n in summary.notes))

    def test_reimport_replaces_window_and_keeps_other_devices(self):
        self.cfg.data_dir.mkdir()
        (self.cfg.data_dir / "screen_sessions.csv").write_text(
            "start,end,device,app,category\n"
            "2026-10-01T09:00,2026-10-01T10:00,laptop,Old,work\n"         # before this import: kept
            "2026-10-12T11:00,2026-10-12T12:00,laptop,Stale,work\n"       # inside: replaced
            "2026-10-12T11:00,2026-10-12T12:00,desktop,Other,work\n",     # other device: kept
            encoding="utf-8")
        self.run_import()
        apps = [r["app"] for r in Store(self.cfg.data_dir).load("screen_sessions").rows]
        self.assertIn("Old", apps)
        self.assertIn("Other", apps)
        self.assertNotIn("Stale", apps)

    def test_user_categories_override(self):
        self.cfg.data_dir.mkdir()
        (self.cfg.data_dir / "screen_categories.json").write_text(json.dumps(
            {"apps": {"com.apple.Safari": "learning", "org.example.unknownapp": {"name": "Unknown", "category": "work"}}}),
            encoding="utf-8")
        self.run_import()
        rows = Store(self.cfg.data_dir).load("screen_sessions").rows
        self.assertEqual({r["app"]: r["category"] for r in rows}["Safari"], "learning")
        self.assertIn("Unknown", [r["app"] for r in rows])

    def test_categorizer_domains(self):
        categorizer = st.Categorizer.load()
        self.assertEqual(categorizer.category("www.youtube.com"), "entertainment")
        self.assertEqual(categorizer.category("https://github.com/x/y"), "work")
        self.assertEqual(categorizer.category("box.com"), "other")
        self.assertEqual(categorizer.category("Slack"), "communication")

    def test_missing_stream(self):
        with self.assertRaises(st.ScreenTimeError):
            st.import_screentime(self.cfg, root=self.tmp / "nowhere", sync_db=self.sync_db, local_device="laptop")

    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_permission_message(self):
        locked = self.root / st.STREAM
        os.chmod(locked, 0)
        try:
            with self.assertRaises(st.ScreenTimeError) as caught:
                st.import_screentime(self.cfg, root=self.root, sync_db=self.sync_db, local_device="laptop")
            self.assertIn("Full Disk Access", str(caught.exception))
        finally:
            os.chmod(locked, 0o755)


if __name__ == "__main__":
    unittest.main()
