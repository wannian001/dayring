"""`healthaio collect` and `status` (what the Mac app runs and shows), and reading the iPhone app's signature."""
import json
import plistlib
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from healthaio import collect, iphone
from healthaio.config import Config
from healthaio.importers import macos_screentime


class Collect(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="healthaio-collect-"))
        self.cfg = Config(root=self.folder, data_dir=self.folder / "data", timezone="Australia/Melbourne")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_a_failing_source_is_reported_and_saved(self):
        denied = macos_screentime.ScreenTimeError(macos_screentime.FDA_MESSAGE)
        with mock.patch("sys.platform", "darwin"), \
                mock.patch.object(macos_screentime, "import_screentime", side_effect=denied):
            result = collect.collect(self.cfg)
        self.assertFalse(result["ok"])
        (screen,) = result["sources"]
        self.assertEqual((screen["name"], screen["ok"]), ("macos-screentime", False))
        self.assertIn("Full Disk Access", screen["message"])
        self.assertIn("Health AIO Mac app", screen["message"])
        saved = json.loads((self.folder / ".healthaio" / "collect.json").read_text())
        self.assertEqual(saved["sources"][0]["ok"], False)

    def test_screen_time_is_only_read_on_a_mac(self):
        with mock.patch("sys.platform", "linux"):
            result = collect.collect(self.cfg)
        self.assertIn("only be read on a Mac", result["sources"][0]["message"])

    def test_status_has_everything_the_mac_app_shows(self):
        (self.folder / "data").mkdir()
        (self.folder / "data" / "body_daily.csv").write_text("date,steps\n2026-10-12,10\n2026-10-13,20\n2026-10-01,5\n")
        with mock.patch.object(iphone, "reason", return_value="no_xcode"):
            data = collect.status(self.cfg)
        for key in ("version", "config", "data_dir", "timezone", "port", "collect", "devices", "latest",
                    "full_disk_access", "iphone", "update"):
            self.assertIn(key, data)
        self.assertEqual(data["latest"]["body_daily"], "2026-10-13")
        self.assertIsNone(data["latest"]["meals"])
        self.assertEqual(data["iphone"]["reason"], "no_xcode")


class Signature(unittest.TestCase):
    def test_expiry_is_read_from_the_profile_inside_its_signed_wrapper(self):
        folder = Path(tempfile.mkdtemp(prefix="healthaio-app-"))
        try:
            app = folder / "HealthAIO.app"
            app.mkdir()
            plist = plistlib.dumps({"ExpirationDate": datetime(2026, 10, 20, 10, 0), "Name": "x"})
            (app / "embedded.mobileprovision").write_bytes(b"0\x80\x06\x09*\x86H\x86\xf7" + plist + b"\x00\xa0\x82signature")
            self.assertEqual(iphone.expiry(app), datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc))
            (app / "embedded.mobileprovision").write_bytes(b"garbage")
            self.assertIsNone(iphone.expiry(app))
            self.assertIsNone(iphone.expiry(folder / "missing.app"))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_renew_explains_what_is_missing(self):
        folder = Path(tempfile.mkdtemp(prefix="healthaio-renew-"))
        try:
            cfg = Config(root=folder, data_dir=folder / "data")
            for why, words in (("no_xcode", "Xcode"), ("no_team", "Local.xcconfig"), ("not_macos", "Mac")):
                with mock.patch.object(iphone, "reason", return_value=why):
                    result = iphone.renew(cfg)
                self.assertFalse(result["ok"])
                self.assertIn(words, result["message"])
                self.assertEqual(result["reason"], why)
            with mock.patch.object(iphone, "reason", return_value="no_xcode"):
                self.assertEqual(iphone.start_background(cfg), {"started": False, "reason": "no_xcode"})
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_team_comes_from_local_xcconfig_only(self):
        folder = Path(tempfile.mkdtemp(prefix="healthaio-ios-"))
        try:
            with mock.patch.object(iphone, "IOS", folder):
                self.assertIsNone(iphone.team())
                (folder / "Local.xcconfig").write_text("HEALTHAIO_BUNDLE_ID = org.example.me.healthaio\nHEALTHAIO_TEAM =\n")
                self.assertIsNone(iphone.team())
                (folder / "Local.xcconfig").write_text("HEALTHAIO_TEAM = ABCDE12345\n")
                self.assertIsNone(iphone.team())  # the example's placeholder, copied unchanged
                (folder / "Local.xcconfig").write_text("HEALTHAIO_TEAM = QWERT67890\n")
                self.assertEqual(iphone.team(), "QWERT67890")
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
