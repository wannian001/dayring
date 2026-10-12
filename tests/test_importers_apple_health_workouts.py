"""workouts.csv from Apple Health: pauses, copies across apps and time zones, odd dates, and re-imports
that must not lose rows the importer did not write."""
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from dayring.config import Config
from dayring.context import Context
from dayring.importers import apple_health
from dayring.modules import time as time_page
from dayring.store import Store, write_table

TZ = "Australia/Melbourne"
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_AU">\n <ExportDate value="{export}"/>\n'


def workout(kind, start, end, duration, source="Sam's Apple Watch", zone=None, inner=""):
    meta = f'<MetadataEntry key="HKTimeZone" value="{zone}"/>' if zone else ""
    return (f' <Workout workoutActivityType="HKWorkoutActivityType{kind}" duration="{duration}" durationUnit="min" '
            f'sourceName="{source}" startDate="{start}" endDate="{end}">{meta}{inner}</Workout>\n')


def event(kind, when):
    return f'<WorkoutEvent type="HKWorkoutEventType{kind}" date="{when}" duration="0" durationUnit="min"/>'


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dayring-ahw-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)
        self.cfg.data_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_import(self, body, export="2026-10-12 14:30:00 +1100"):
        path = self.tmp / "export.xml"
        path.write_text(HEAD.format(export=export) + body + "</HealthData>\n", encoding="utf-8")
        return apple_health.import_apple_health(path, self.cfg)

    def rows(self):
        loaded = Store(self.cfg.data_dir).load("workouts")
        self.assertEqual(loaded.problems, [])
        return [(r["start"], r["end"], r["type"], r["source"], r["kcal"]) for r in loaded.rows]


class Pauses(Case):
    def test_paused_workout_counts_the_minutes_moving(self):
        pauses = event("Pause", "2026-10-11 09:30:00 +1100") + event("Resume", "2026-10-11 10:00:00 +1100") + \
            event("MotionPaused", "2026-10-11 10:20:00 +1100") + event("MotionResumed", "2026-10-11 10:20:20 +1100") + \
            '<WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="1046" unit="kJ"/>'
        summary = self.run_import(workout("Walking", "2026-10-11 09:00:00 +1100", "2026-10-11 10:30:00 +1100", 60,
                                          zone=TZ, inner=pauses))
        self.assertEqual(summary.problems, [])
        rows = self.rows()
        self.assertEqual([(r[0], r[1]) for r in rows], [(datetime(2026, 10, 11, 9), datetime(2026, 10, 11, 9, 30)),
                                                        (datetime(2026, 10, 11, 10), datetime(2026, 10, 11, 10, 30))])
        self.assertAlmostEqual(rows[0][4], 250, places=0)  # kJ -> kcal, on the first stretch
        self.assertIsNone(rows[1][4])
        self.assertTrue(any("1 workouts" in n and "2 rows" in n for n in summary.notes), summary.notes)
        body = Store(self.cfg.data_dir).by_date("body_daily")
        self.assertEqual(body[date(2026, 10, 11)]["workout_min"], 60)

        ctx = Context(self.cfg, now=datetime(2026, 10, 12, 18, 40))
        self.assertEqual(ctx.time_days()[date(2026, 10, 11)].total("exercise"), 60)  # as on Today, not 90
        listed = time_page._workouts(ctx, date(2026, 10, 11), date(2026, 10, 11))
        self.assertEqual(len(listed), 1)  # one workout in the list, with its moving minutes
        self.assertEqual((listed[0]["start"], listed[0]["minutes"]), ("2026-10-11T09:00", 60))

    def test_duration_shorter_than_its_span_without_pause_events(self):
        self.run_import(workout("TraditionalStrengthTraining", "2026-10-11 17:00:00 +1100",
                                "2026-10-11 18:00:00 +1100", 45))
        self.assertEqual([(r[0], r[1]) for r in self.rows()],
                         [(datetime(2026, 10, 11, 17), datetime(2026, 10, 11, 17, 45))])


class Copies(Case):
    def test_copy_in_another_time_zone_is_written_once_in_the_configured_zone(self):
        # the same run: the watch says Shanghai, Strava wrote no zone; one row, in Melbourne time like screens
        self.run_import(workout("Running", "2026-09-01 06:00:00 +1000", "2026-09-01 06:30:00 +1000", 30,
                                zone="Asia/Shanghai") +
                        workout("Running", "2026-09-01 06:00:00 +1000", "2026-09-01 06:31:00 +1000", 31, source="Strava"))
        self.assertEqual(self.rows(), [(datetime(2026, 9, 1, 6), datetime(2026, 9, 1, 6, 30), "running",
                                        "Sam's Apple Watch", None)])
        ctx = Context(self.cfg, now=datetime(2026, 9, 3, 9))
        self.assertEqual(ctx.time_days()[date(2026, 9, 1)].total("exercise"), 30)


class Reimport(Case):
    def test_rows_from_other_sources_survive(self):
        write_table(self.cfg.data_dir, "workouts", [
            {"start": datetime(2019, 6, 1, 7), "end": datetime(2019, 6, 1, 8), "type": "swimming", "source": "typed by hand"},
            {"start": datetime(2019, 6, 2, 7), "end": datetime(2019, 6, 2, 8), "type": "running", "source": "Sam's Apple Watch"},
            {"start": datetime(2026, 6, 15, 18), "end": datetime(2026, 6, 15, 19, 30), "type": "football", "source": "typed by hand"},
            {"start": datetime(2026, 7, 2, 7), "end": datetime(2026, 7, 2, 8), "type": "cycling", "source": "Garmin", "kcal": 640},
            {"start": datetime(2026, 8, 20, 18), "end": datetime(2026, 8, 20, 19), "type": "football", "source": ""},
            # the export's own run, also mapped in from the Garmin CSV: a copy
            {"start": datetime(2026, 10, 11, 7, 1), "end": datetime(2026, 10, 11, 7, 29), "type": "run", "source": "Garmin"},
            # an Apple Watch workout deleted in Health since the last import: the export no longer has it
            {"start": datetime(2026, 9, 9, 12), "end": datetime(2026, 9, 9, 12, 30), "type": "walking", "source": "Sam's Apple Watch"},
        ])
        body = (workout("Running", "2026-05-01 07:00:00 +1000", "2026-05-01 07:30:00 +1000", 30, zone=TZ) +
                workout("Running", "2026-10-11 07:00:00 +1100", "2026-10-11 07:30:00 +1100", 30, zone=TZ) +
                workout("Other", "1970-01-01 10:00:00 +1000", "1970-01-01 10:30:00 +1000", 30))  # epoch junk
        for _ in range(2):  # and the same again: nothing changes
            summary = self.run_import(body)
        rows = self.rows()
        self.assertEqual([(r[0], r[2], r[3]) for r in rows], [
            (datetime(2019, 6, 1, 7), "swimming", "typed by hand"),
            (datetime(2019, 6, 2, 7), "running", "Sam's Apple Watch"),     # outside the export's range
            (datetime(2026, 5, 1, 7), "running", "Sam's Apple Watch"),
            (datetime(2026, 6, 15, 18), "football", "typed by hand"),
            (datetime(2026, 7, 2, 7), "cycling", "Garmin"),
            (datetime(2026, 8, 20, 18), "football", None),
            (datetime(2026, 10, 11, 7), "running", "Sam's Apple Watch"),
        ])
        self.assertEqual(rows[4][4], 640)
        self.assertTrue(any("before 2000" in n for n in summary.notes), summary.notes)
        first = [n for n in summary.notes if n.startswith("workouts.csv: replaced")]
        self.assertEqual(len(first), 1)
        self.assertIn("kept 4 row(s) from other sources", first[0])


class OddTimes(Case):
    def test_end_is_always_after_start(self):
        # Melbourne, 5 Apr 2026, 03:00 +1100 -> 02:00 +1000: a 40-minute ride across it; a 36-second tap; a 20-second one
        self.run_import(workout("Cycling", "2026-04-05 02:40:00 +1100", "2026-04-05 02:20:00 +1000", 40) +
                        workout("Yoga", "2026-04-05 07:12:05 +1000", "2026-04-05 07:12:41 +1000", 0.6) +
                        workout("Other", "2026-04-05 09:00:05 +1000", "2026-04-05 09:00:25 +1000", 0.33),
                        export="2026-04-06 09:00:00 +1000")
        rows = self.rows()
        self.assertEqual(len(rows), 2)  # the 20-second one is left out
        for start, end, *_ in rows:
            self.assertGreater(end, start)
        ride = rows[0]
        self.assertEqual(ride[0], datetime(2026, 4, 5, 2, 40))
        ctx = Context(self.cfg, now=datetime(2026, 4, 6, 9))
        self.assertEqual(ctx.time_days()[date(2026, 4, 5)].total("exercise"), 40 + 1)

    def test_check_reports_backwards_rows(self):
        (self.cfg.data_dir / "workouts.csv").write_text(
            "start,end,type,source,kcal\n2026-04-05T02:40,2026-04-05T02:20,running,x,\n"
            "2026-04-06T07:00,2026-04-06T07:30,running,x,\n", encoding="utf-8")
        loaded = Store(self.cfg.data_dir).load("workouts")
        self.assertEqual(len(loaded.rows), 1)
        self.assertEqual([(p.line, p.column) for p in loaded.problems], [(2, "end")])


if __name__ == "__main__":
    unittest.main()
