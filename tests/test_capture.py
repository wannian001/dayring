"""Packages from the iPhone app (docs/CAPTURE.md): checking, storing once, and the same rows as an export."""
import copy
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from healthaio import capture, state
from healthaio.config import Config
from healthaio.importers import apple_health

FIXTURE = Path(__file__).parent / "fixtures" / "capture" / "health_3days.json"
TZ = "Australia/Melbourne"


def package() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def body(data: dict) -> bytes:
    return json.dumps(data).encode("utf-8")


def table(folder: Path, name: str) -> list:
    path = folder / "data" / f"{name}.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="healthaio-capture-"))
        self.cfg = Config(root=self.folder, data_dir=self.folder / "data", timezone=TZ)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)


class Validate(unittest.TestCase):
    def test_the_fixture_is_valid_and_keeps_every_field_it_reads(self):
        clean = capture.validate(package())
        self.assertEqual(len(clean["records"]), len(package()["records"]))
        self.assertEqual(clean["workouts"][0]["events"][1]["type"], "HKWorkoutEventTypeResume")
        self.assertEqual(clean["records"][1]["metadata"], {"HKTimeZone": "Australia/Melbourne"})

    def test_fields_the_server_does_not_read_are_dropped(self):
        data = package()
        data["records"][0]["metadata"] = {"HKTimeZone": "Australia/Melbourne", "HKDeviceName": "Sam's iPhone"}
        data["records"][0]["sourceVersion"] = "27.0"
        data["extra"] = {"anything": 1}
        clean = capture.validate(data)
        self.assertEqual(clean["records"][0]["metadata"], {"HKTimeZone": "Australia/Melbourne"})
        self.assertNotIn("sourceVersion", clean["records"][0])
        self.assertNotIn("extra", clean)

    def test_refused(self):
        cases = {
            "schema": lambda d: d.update(schema="something-else"),
            "package_id": lambda d: d.update(package_id="../escape"),
            "kind": lambda d: d.update(kind="checkin"),
            "window": lambda d: d["window"].update(start_date="2026-10-09"),  # five days
            "backwards": lambda d: d["window"].update(start_date="2026-10-14"),
            "type": lambda d: d["records"][0].update(type="HKQuantityTypeIdentifierBloodGlucose"),
            "time": lambda d: d["records"][0].update(startDate="yesterday"),
            "value": lambda d: d["records"][0].pop("value"),
            "control": lambda d: d["records"][0].update(sourceName="a\nb"),
        }
        for name, change in cases.items():
            data = package()
            change(data)
            with self.assertRaises(capture.CaptureError, msg=name):
                capture.validate(data)

    def test_xml_reads_back_with_the_export_reader(self):
        xml = capture.to_xml(capture.validate(package()))
        self.assertTrue(xml.startswith(b"<?xml"))
        self.assertIn(b'<ExportDate value="2026-10-13 21:05:10 +1100"', xml)
        self.assertIn(b'<MetadataEntry key="HKFoodType" value="Chicken salad"', xml)


class Receive(Base):
    def test_projected_once_and_the_same_package_again_gets_the_same_receipt(self):
        status, receipt = capture.receive(self.cfg, body(package()), {"id": "d_1"})
        self.assertEqual((status, receipt["status"]), (200, "projected"))
        self.assertEqual(receipt["rows"], {"body_daily": 3, "workouts": 2, "meals": 1})
        landed = state.folder(self.cfg) / receipt["file"]
        self.assertTrue(landed.is_file())
        self.assertEqual(json.loads(landed.read_text())["package_id"], package()["package_id"])
        again = capture.receive(self.cfg, body(package()), {"id": "d_1"})[1]
        self.assertEqual(again["landed_at"], receipt["landed_at"])
        self.assertEqual(capture.lookup(self.cfg, package()["package_id"])["status"], "projected")
        self.assertEqual(capture.lookup(self.cfg, "never-sent")["status"], "not_found")

    def test_same_id_other_content_is_a_conflict(self):
        capture.receive(self.cfg, body(package()), None)
        other = package()
        other["records"][0]["value"] = "1"
        with self.assertRaises(capture.Conflict):
            capture.receive(self.cfg, body(other), None)

    def test_a_refused_package_leaves_nothing(self):
        bad = package()
        bad["schema"] = "nope"
        with self.assertRaises(capture.CaptureError):
            capture.receive(self.cfg, body(bad), None)
        self.assertFalse((state.folder(self.cfg) / "capture").exists())
        self.assertEqual(table(self.folder, "body_daily"), [])

    def test_same_rows_as_importing_the_same_samples_as_an_export(self):
        capture.receive(self.cfg, body(package()), None)
        other = Path(tempfile.mkdtemp(prefix="healthaio-export-"))
        try:
            xml = other / "export.xml"
            xml.write_bytes(capture.to_xml(capture.validate(package())))
            apple_health.import_apple_health(xml, Config(root=other, data_dir=other / "data", timezone=TZ))
            for name in ("body_daily", "workouts", "meals"):
                self.assertEqual(table(self.folder, name), table(other, name), name)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_rows(self):
        capture.receive(self.cfg, body(package()), None)
        days = {r["date"]: r for r in table(self.folder, "body_daily")}
        self.assertEqual(sorted(days), ["2026-10-11", "2026-10-12", "2026-10-13"])
        self.assertEqual(days["2026-10-11"]["steps"], "6000")      # watch and phone counted the same hour once
        self.assertEqual(days["2026-10-11"]["sleep_min"], "450")
        self.assertEqual(days["2026-10-13"]["complete"], "0")      # the day of the read is not over
        self.assertEqual(days["2026-10-12"]["complete"], "1")
        workouts = table(self.folder, "workouts")
        self.assertEqual([(w["start"], w["end"]) for w in workouts],
                         [("2026-10-12T07:00", "2026-10-12T07:10"), ("2026-10-12T07:12", "2026-10-12T07:34")])
        self.assertEqual(table(self.folder, "meals")[0]["source"], "MyFitnessPal")

    def test_only_the_window_is_written(self):
        data = package()
        # a nap the evening before the window: it would file a short "night" under 2026-10-10
        data["records"].append({"type": "HKCategoryTypeIdentifierSleepAnalysis", "sourceName": "Apple Watch",
                                "device": "Watch", "startDate": "2026-10-10 18:30:00 +1100",
                                "endDate": "2026-10-10 19:10:00 +1100",
                                "value": "HKCategoryValueSleepAnalysisAsleepCore"})
        capture.receive(self.cfg, body(data), None)
        self.assertNotIn("2026-10-10", {r["date"] for r in table(self.folder, "body_daily")})

    def test_later_window_keeps_earlier_days_and_typed_cells(self):
        capture.receive(self.cfg, body(package()), None)
        path = self.folder / "data" / "body_daily.csv"
        lines = path.read_text().splitlines()
        header = lines[0].split(",")
        row = lines[1].split(",")
        row[header.index("waist_cm")] = "80"
        lines[1] = ",".join(row)  # waist typed by hand on 2026-10-11
        path.write_text("\n".join(lines) + "\n")
        later = package()
        later["package_id"] = "ios-later"
        later["window"].update(start_date="2026-10-12", query_start="2026-10-11 18:00:00 +1100")
        later["records"] = [r for r in later["records"] if not r["startDate"].startswith("2026-10-11 0")
                            and not r["startDate"].startswith("2026-10-10")]
        capture.receive(self.cfg, body(later), None)
        days = {r["date"]: r for r in table(self.folder, "body_daily")}
        self.assertEqual(days["2026-10-11"]["waist_cm"], "80")     # outside the new window: untouched
        self.assertEqual(days["2026-10-11"]["steps"], "6000")

    def test_a_deleted_workout_leaves_the_table(self):
        capture.receive(self.cfg, body(package()), None)
        later = package()
        later["package_id"] = "ios-deleted-run"
        later["workouts"] = [dict(later["workouts"][0], workoutActivityType="HKWorkoutActivityTypeWalking",
                                  startDate="2026-10-13 18:00:00 +1100", endDate="2026-10-13 18:20:00 +1100",
                                  duration="20", events=[])]
        capture.receive(self.cfg, body(later), None)
        self.assertEqual([w["type"] for w in table(self.folder, "workouts")], ["walking"])

    def test_a_package_that_could_not_be_written_is_tried_again(self):
        original = capture.project
        capture.project = lambda cfg, pkg: (_ for _ in ()).throw(OSError("disk full"))
        try:
            receipt = capture.receive(self.cfg, body(package()), None)[1]
        finally:
            capture.project = original
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("disk full", receipt["error"])
        self.assertEqual(capture.retry_pending(self.cfg), 1)
        self.assertEqual(capture.lookup(self.cfg, package()["package_id"])["status"], "projected")
        self.assertEqual(len(table(self.folder, "body_daily")), 3)

    def test_too_big(self):
        with self.assertRaises(capture.CaptureError):
            capture.receive(self.cfg, b" " * (capture.MAX_BYTES + 1), None)

    def test_receipt_files_are_private(self):
        receipt = capture.receive(self.cfg, body(copy.deepcopy(package())), None)[1]
        landed = state.folder(self.cfg) / receipt["file"]
        self.assertEqual(landed.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
