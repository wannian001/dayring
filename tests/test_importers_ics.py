import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from dayring.config import Config
from dayring.importers import ics
from dayring.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "calendar.ics"
TZ = "Australia/Melbourne"
WINDOW = (datetime(2026, 7, 1), datetime(2027, 1, 1))


def expand(**kwargs):
    cfg = Config(root=Path("."), data_dir=Path("."), timezone=TZ)
    return ics.expand(ics.read_ics(FIXTURE), cfg.tz, WINDOW[0], WINDOW[1], **kwargs)


def by_title(rows, title):
    return [r for r in rows if r["title"] == title]


class IcsExpandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.problems, cls.notes = expand()

    def test_count(self):
        self.assertEqual(len(self.rows), 21)
        self.assertEqual(self.problems, [])

    def test_weekly_rrule_exdate_override(self):
        lectures = by_title(self.rows, "SUBJ10001 Lecture")
        starts = [r["start"] for r in lectures]
        self.assertEqual(len(lectures), 9)  # 12 - EXDATE - moved - cancelled
        self.assertNotIn(datetime(2026, 8, 10, 10, 0), starts)   # EXDATE
        self.assertNotIn(datetime(2026, 8, 17, 10, 0), starts)   # cancelled override
        self.assertNotIn(datetime(2026, 8, 12, 10, 0), starts)   # moved
        self.assertEqual(starts[0], datetime(2026, 8, 3, 10, 0))
        self.assertEqual(starts[-1], datetime(2026, 9, 9, 10, 0))
        self.assertEqual(lectures[0]["end"], datetime(2026, 8, 3, 11, 0))
        self.assertEqual(lectures[0]["location"], "Old Building, Theatre 1")
        self.assertEqual(lectures[0]["kind"], "class")
        moved = by_title(self.rows, "SUBJ10001 Lecture (moved)")
        self.assertEqual([(r["start"], r["end"], r["location"]) for r in moved],
                         [(datetime(2026, 8, 12, 14, 0), datetime(2026, 8, 12, 15, 0), "Online")])

    def test_until_and_duration_across_dst(self):
        gym = by_title(self.rows, "Gym session")
        self.assertEqual([(r["start"], r["end"]) for r in gym],
                         [(datetime(2026, 9, 29, 7, 0), datetime(2026, 9, 29, 8, 0)),
                          (datetime(2026, 10, 6, 7, 0), datetime(2026, 10, 6, 8, 0))])
        self.assertEqual(gym[0]["kind"], "training")

    def test_utc_recurrence_converted_to_local(self):
        sync = by_title(self.rows, "Team sync")
        self.assertEqual([r["start"] for r in sync],
                         [datetime(2026, 9, 28, 10, 0), datetime(2026, 10, 5, 11, 0), datetime(2026, 10, 12, 11, 0)])
        self.assertEqual(sync[0]["kind"], "other")

    def test_tzids(self):
        self.assertEqual(by_title(self.rows, "SUBJ20002 Tutorial")[0]["start"], datetime(2026, 10, 14, 18, 0))
        self.assertEqual(by_title(self.rows, "Career workshop")[0]["start"], datetime(2026, 10, 15, 13, 0))
        self.assertEqual(by_title(self.rows, "Lunch with friends")[0]["start"], datetime(2026, 10, 16, 12, 0))

    def test_floating_daily_interval(self):
        labs = by_title(self.rows, "Practical lab")
        self.assertEqual([r["start"] for r in labs],
                         [datetime(2026, 10, 20, 9, 0), datetime(2026, 10, 22, 9, 0), datetime(2026, 10, 24, 9, 0)])
        self.assertEqual(labs[0]["kind"], "class")

    def test_cancelled_and_all_day_skipped(self):
        self.assertEqual(by_title(self.rows, "Cancelled seminar"), [])
        self.assertEqual(by_title(self.rows, "Public holiday"), [])
        self.assertTrue(any("all-day" in n for n in self.notes))

    def test_all_day_kept_on_request(self):
        rows, _, _ = expand(include_all_day=True)
        holiday = by_title(rows, "Public holiday")
        self.assertEqual([(r["start"], r["end"]) for r in holiday],
                         [(datetime(2026, 11, 3, 0, 0), datetime(2026, 11, 3, 23, 59))])

    def test_forced_kind(self):
        rows, _, _ = expand(kind="work")
        self.assertEqual({r["kind"] for r in rows}, {"work"})

    def test_window(self):
        cfg = Config(root=Path("."), data_dir=Path("."), timezone=TZ)
        rows, _, _ = ics.expand(ics.read_ics(FIXTURE), cfg.tz, datetime(2026, 10, 1), datetime(2026, 10, 13))
        self.assertEqual(sorted({r["title"] for r in rows}), ["Gym session", "Team sync"])


class IcsUnitTest(unittest.TestCase):
    def test_unfold_and_escape(self):
        lines = ics.unfold("SUMMARY:Hello\r\n  world\r\nX:1\r\n")
        self.assertEqual(lines, ["SUMMARY:Hello world", "X:1"])
        self.assertEqual(ics.unescape(r"a\, b\; c\nd\\e"), "a, b; c\nd\\e")

    def test_duration(self):
        self.assertEqual(ics.parse_duration("PT1H30M").total_seconds(), 5400)
        self.assertEqual(ics.parse_duration("P1W2D").days, 9)

    def test_classify(self):
        rules = ics.DEFAULT_KIND_RULES
        self.assertEqual(ics.classify("COMP10001/Tutorial-01", rules), "class")
        self.assertEqual(ics.classify("Lectures week 3", rules), "class")
        self.assertEqual(ics.classify("Morning running", rules), "training")
        self.assertEqual(ics.classify("Collaboration meeting", rules), "other")

    def test_open_ended_rule_from_long_ago(self):
        text = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nDTSTART:19900101T080000\nDTEND:19900101T083000\n"
                "RRULE:FREQ=DAILY\nSUMMARY:Stretch\nEND:VEVENT\nEND:VCALENDAR\n")
        cfg = Config(root=Path("."), data_dir=Path("."), timezone=TZ)
        rows, problems, _ = ics.expand(text, cfg.tz, datetime(2026, 10, 1), datetime(2026, 10, 4))
        self.assertEqual([r["start"] for r in rows],
                         [datetime(2026, 10, d, 8, 0) for d in (1, 2, 3)])

    def test_weekly_interval_byday(self):
        text = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:y\nDTSTART:20261005T090000\nDTEND:20261005T100000\n"
                "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH;COUNT=4\nSUMMARY:Seminar\nEND:VEVENT\nEND:VCALENDAR\n")
        cfg = Config(root=Path("."), data_dir=Path("."), timezone=TZ)
        rows, _, _ = ics.expand(text, cfg.tz, *WINDOW)
        self.assertEqual([r["start"].date() for r in rows],
                         [date(2026, 10, 5), date(2026, 10, 8), date(2026, 10, 19), date(2026, 10, 22)])


class IcsImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_import_and_reimport(self):
        self.cfg.data_dir.mkdir()
        (self.cfg.data_dir / "events.csv").write_text(
            "start,end,title,kind,location\n"
            "2026-09-30T07:00,2026-09-30T08:00,Gym session,training,\n"    # old time, same calendar: removed
            "2026-09-30T18:00,2026-09-30T19:00,Choir,personal,Hall\n",     # another source: kept
            encoding="utf-8")
        summary = ics.import_ics(FIXTURE, self.cfg, today=date(2026, 10, 12))
        self.assertEqual(summary.imported, 21)
        loaded = Store(self.cfg.data_dir).load("events")
        self.assertEqual(loaded.problems, [])
        titles = [r["title"] for r in loaded.rows]
        self.assertIn("Choir", titles)
        self.assertNotIn(datetime(2026, 9, 30, 7, 0), [r["start"] for r in loaded.rows])
        self.assertEqual(len(loaded.rows), 22)
        again = ics.import_ics(FIXTURE, self.cfg, today=date(2026, 10, 12))
        self.assertEqual(again.total, 22)


if __name__ == "__main__":
    unittest.main()
