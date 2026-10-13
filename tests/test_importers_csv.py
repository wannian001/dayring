import argparse
import contextlib
import io
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from healthaio.config import Config
from healthaio.importers import cli, csv_map
from healthaio.store import Store

FIXTURES = Path(__file__).parent / "fixtures"


class CsvMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone="Australia/Melbourne")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_parse_mapping(self):
        self.assertEqual(csv_map.parse_mapping(["Date=date,Weight (kg)=weight_kg", "Waist, cm=waist_cm"]),
                         {"Date": "date", "Weight (kg)": "weight_kg", "Waist, cm": "waist_cm"})
        with self.assertRaises(csv_map.MappingError):
            csv_map.parse_mapping(["no mapping here"])

    def test_bad_rows_reported_with_lines(self):
        summary = csv_map.import_csv("body_daily", FIXTURES / "weights.csv", self.cfg,
                                     ["Date=date,Weight (kg)=weight_kg,Waist=waist_cm"])
        self.assertEqual(summary.imported, 2)
        self.assertEqual(len(summary.problems), 3)
        self.assertTrue(summary.problems[0].startswith("line 3:"))
        self.assertTrue(summary.problems[1].startswith("line 5:"))
        self.assertTrue(summary.problems[2].startswith("line 6:"))
        rows = Store(self.cfg.data_dir).by_date("body_daily")
        self.assertEqual(rows[date(2026, 10, 1)]["weight_kg"], 75.4)
        self.assertEqual(rows[date(2026, 10, 1)]["waist_cm"], 81)
        self.assertIsNone(rows[date(2026, 10, 3)]["waist_cm"])
        self.assertTrue(any("Notes" in n for n in summary.notes))

    def test_date_format_delimiter_and_merge(self):
        self.cfg.data_dir.mkdir()
        (self.cfg.data_dir / "body_daily.csv").write_text("date,weight_kg\n2026-10-05,99\n2026-09-01,76\n",
                                                          encoding="utf-8")
        summary = csv_map.import_csv("body_daily", FIXTURES / "weights_dmy.csv", self.cfg,
                                     ["Day=date,Kilos=weight_kg"], date_format="%d/%m/%Y")
        self.assertEqual(summary.imported, 1)       # "74,8" is not a number
        self.assertEqual(len(summary.problems), 1)
        rows = Store(self.cfg.data_dir).by_date("body_daily")
        self.assertEqual(rows[date(2026, 10, 6)]["weight_kg"], 74.7)
        self.assertEqual(rows[date(2026, 10, 5)]["weight_kg"], 99)   # bad new row did not replace it
        self.assertEqual(rows[date(2026, 9, 1)]["weight_kg"], 76)

    def test_required_column_missing(self):
        path = self.tmp / "no_date.csv"
        path.write_text("Day,Weight (kg)\n2026-10-01,75\n", encoding="utf-8")
        with self.assertRaises(csv_map.MappingError):
            csv_map.import_csv("body_daily", path, self.cfg, ["Weight (kg)=weight_kg"])
        # a header that already has the schema name needs no mapping
        summary = csv_map.import_csv("body_daily", FIXTURES / "weights.csv", self.cfg, ["Weight (kg)=weight_kg"])
        self.assertEqual(summary.imported, 2)
        with self.assertRaises(csv_map.MappingError):
            csv_map.import_csv("body_daily", FIXTURES / "weights.csv", self.cfg, ["Date=nope"])

    def test_screen_sessions_category_filled(self):
        path = self.tmp / "aw.csv"
        path.write_text("timestamp,end,device,app\n2026-10-12T09:00,2026-10-12T09:30,desktop,www.youtube.com\n",
                        encoding="utf-8")
        csv_map.import_csv("screen_sessions", path, self.cfg, ["timestamp=start"])
        rows = Store(self.cfg.data_dir).load("screen_sessions").rows
        self.assertEqual(rows[0]["category"], "entertainment")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone="Australia/Melbourne")
        parser = argparse.ArgumentParser(prog="healthaio")
        cli.add_parsers(parser.add_subparsers(dest="command"))
        self.parser = parser

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, *argv):
        args = self.parser.parse_args(list(argv))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run(args, self.cfg)
        return code, out.getvalue(), err.getvalue()

    def test_csv_and_health_commands(self):
        code, out, _ = self.run_cli("import", "csv", "body_daily", str(FIXTURES / "weights.csv"),
                                    "--map", "Date=date,Weight (kg)=weight_kg")
        self.assertEqual(code, 0)
        self.assertIn("2 rows imported", out)
        self.assertIn("line 3", out)
        code, out, _ = self.run_cli("import", "apple-health", str(FIXTURES / "apple_health_export.xml"))
        self.assertEqual(code, 0)
        self.assertIn("5 rows imported, 2026-10-04 to 2026-10-12", out)

    def test_ics_command_with_kind(self):
        code, out, _ = self.run_cli("import", "ics", str(FIXTURES / "calendar.ics"), "--kind", "class",
                                    "--days-back", "3650", "--days-ahead", "3650")
        self.assertEqual(code, 0)
        self.assertEqual({r["kind"] for r in Store(self.cfg.data_dir).rows("events")}, {"class"})

    def test_error_is_a_message(self):
        code, _, err = self.run_cli("import", "apple-health", str(self.tmp / "missing.zip"))
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)


if __name__ == "__main__":
    unittest.main()
