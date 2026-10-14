"""AI work: Claude Code and Codex logs -> ai_work / ai_prompts, and the AI work page.

Rules under test (healthaio/importers/ai_logs.py, healthaio/context.py, healthaio/modules/ai.py):
- only times and counts leave the logs: no prompt or reply text, no session id in the clear, no path;
- two calls of one session at most 5 minutes apart are work in between; a longer gap is waiting; a call split over
  several records counts once; a subagent's calls count into its parent session;
- a scheduled task and claude -p / codex exec are not "you"; only typed instructions count as instructions;
- re-importing gives the same rows and keeps older rows the logs no longer hold; --days limits the window;
- a stretch's minutes are spread over the hours it covers, across midnight too, and add back up;
- the page compares your AI work with your normal, works the two ratios out from 7-day totals, never colours the
  AI numbers, and counts deadlines marked submitted or done as what came out.
"""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config
from healthaio.context import Context
from healthaio.importers.ai_logs import import_ai_logs, session_code
from healthaio.modules import PAGES
from healthaio.modules import ai as ai_page
from healthaio.modules import data as data_page
from healthaio.store import write_table

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "healthaio" / "web"
SECRET = "please refactor the secret-project billing module"


def z(day: int, hour: int, minute: int, second: int = 0) -> str:
    """A UTC log time in October 2026 (Melbourne is UTC+11 then)."""
    return datetime(2026, 10, day, hour, minute, second).strftime("%Y-%m-%dT%H:%M:%S.123Z")


def assistant(sid: str, at: str, msg: str, req: str, out: int = 100) -> dict:
    return {"type": "assistant", "sessionId": sid, "timestamp": at, "requestId": req,
            "message": {"id": msg, "model": "claude-test", "usage": {"input_tokens": 5, "output_tokens": out},
                        "content": [{"type": "text", "text": SECRET}]}}


def user(sid: str, at: str, text: str, **extra) -> dict:
    return {"type": "user", "sessionId": sid, "timestamp": at, "uuid": f"u-{at}", "message": {"content": text}, **extra}


def write_jsonl(path: Path, items) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(i) for i in items) + "\n", encoding="utf-8")


class Logs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-ai-"))
        self.claude = self.tmp / "claude" / "projects"
        self.codex = self.tmp / "codex" / "sessions"
        self.data = self.tmp / "data"
        self.data.mkdir()
        self.cfg = Config(root=self.tmp, data_dir=self.data, timezone="Australia/Melbourne")
        # a session you started: a typed instruction, calls 0, 1 and 2 minutes in (the 1-minute one split over two
        # records), a 10-minute wait, then two calls 2 minutes apart; a tool result is not an instruction
        write_jsonl(self.claude / "proj" / "s1.jsonl", [
            user("s1", z(5, 1, 0), SECRET, turnOrigin="human"),
            assistant("s1", z(5, 1, 0, 10), "m1", "r1"),
            assistant("s1", z(5, 1, 1, 10), "m2", "r2"), assistant("s1", z(5, 1, 1, 10), "m2", "r2", out=0),
            assistant("s1", z(5, 1, 2, 10), "m3", "r3"),
            user("s1", z(5, 1, 3), [{"type": "tool_result", "content": SECRET}], turnOrigin="tool"),
            user("s1", z(5, 1, 12), "and now the tests", turnOrigin="human"),
            assistant("s1", z(5, 1, 12, 30), "m4", "r4"), assistant("s1", z(5, 1, 14, 30), "m5", "r5"),
        ])
        # its subagent, working at the same time: counts into s1, and its own "user" records are no instructions
        write_jsonl(self.claude / "proj" / "s1" / "subagents" / "agent-a.jsonl", [
            user("s1", z(5, 1, 0, 30), "subagent brief", turnOrigin="human"),
            assistant("s1", z(5, 1, 2, 40), "m6", "r6"), assistant("s1", z(5, 1, 4, 40), "m7", "r7"),
        ])
        # a scheduled task: not yours
        write_jsonl(self.claude / "proj" / "s2.jsonl", [
            user("s2", z(5, 15, 0), "<scheduled-task name=nightly>do it</scheduled-task>"),
            assistant("s2", z(5, 15, 0, 5), "n1", "q1"), assistant("s2", z(5, 15, 3, 5), "n2", "q2"),
        ])
        # Codex: a turn you started with two calls, and a codex exec session (a script)
        write_jsonl(self.codex / "2026" / "10" / "05" / "rollout-a.jsonl", [
            {"type": "session_meta", "payload": {"id": "c1", "source": "cli"}},
            {"type": "event_msg", "timestamp": z(5, 3, 0), "payload": {"type": "task_started"}},
            {"type": "event_msg", "timestamp": z(5, 3, 1), "payload": {"type": "token_count", "info": {
                "last_token_usage": {"output_tokens": 40}, "total_token_usage": {"total_tokens": 100}}}},
            {"type": "event_msg", "timestamp": z(5, 3, 4), "payload": {"type": "token_count", "info": {
                "last_token_usage": {"output_tokens": 60}, "total_token_usage": {"total_tokens": 200}}}},
        ])
        write_jsonl(self.codex / "2026" / "10" / "05" / "rollout-b.jsonl", [
            {"type": "session_meta", "payload": {"id": "c2", "source": "exec"}},
            {"type": "event_msg", "timestamp": z(5, 4, 0), "payload": {"type": "task_started"}},
            {"type": "event_msg", "timestamp": z(5, 4, 1), "payload": {"type": "token_count", "info": {
                "last_token_usage": {"output_tokens": 1}, "total_token_usage": {"total_tokens": 1}}}},
            {"type": "event_msg", "timestamp": z(5, 4, 3), "payload": {"type": "token_count", "info": {
                "last_token_usage": {"output_tokens": 1}, "total_token_usage": {"total_tokens": 2}}}},
        ])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_import(self, **kw):
        return import_ai_logs(self.cfg, claude_dir=self.claude, codex_dirs=[self.codex], **kw)

    def rows(self, name):
        return Context(self.cfg, now=datetime(2026, 10, 12, 9)).store.rows(name)

    def test_stretches_minutes_and_who(self):
        self.run_import()
        work = sorted(self.rows("ai_work"), key=lambda r: (r["start"], r["tool"]))
        mine = [r for r in work if r["started_by"] == "you"]
        # s1 with its subagent: 12:00:10 .. 12:04:40 is one stretch (gaps of 1–2 minutes), then 12:12:30 .. 12:14:30
        s1 = [r for r in mine if r["tool"] == "claude_code"]
        self.assertEqual([(r["start"], r["end"]) for r in s1], [(datetime(2026, 10, 5, 12, 0), datetime(2026, 10, 5, 12, 5)),
                                                                 (datetime(2026, 10, 5, 12, 12), datetime(2026, 10, 5, 12, 15))])
        self.assertAlmostEqual(s1[0]["minutes"], 4.5)
        self.assertAlmostEqual(s1[1]["minutes"], 2.0)
        self.assertEqual(s1[0]["calls"], 5)          # m1, m2 (twice in the log), m3, m6, m7
        self.assertEqual(s1[0]["session"], session_code("claude_code", "s1"))
        codex = [r for r in work if r["tool"] == "codex"]
        self.assertEqual([(r["started_by"], r["minutes"]) for r in codex], [("you", 3.0), ("script", 2.0)])
        scheduled = [r for r in work if r["started_by"] == "scheduled"]
        self.assertEqual([(r["start"].hour, r["minutes"]) for r in scheduled], [(2, 3.0)])  # 15:00 UTC = 02:00 next day
        self.assertEqual(scheduled[0]["start"].date(), date(2026, 10, 6))

    def test_only_typed_instructions_count(self):
        self.run_import()
        prompts = sorted((r["time"], r["tool"], r["started_by"], r["count"]) for r in self.rows("ai_prompts"))
        self.assertEqual(prompts, [(datetime(2026, 10, 5, 12, 0), "claude_code", "you", 1),
                                   (datetime(2026, 10, 5, 12, 12), "claude_code", "you", 1),
                                   (datetime(2026, 10, 5, 14, 0), "codex", "you", 1),
                                   (datetime(2026, 10, 5, 15, 0), "codex", "script", 1)])

    def test_nothing_said_and_no_ids_leave_the_logs(self):
        self.run_import()
        for name in ("ai_work.csv", "ai_prompts.csv"):
            text = (self.data / name).read_text(encoding="utf-8")
            for leak in (SECRET, "and now the tests", "subagent brief", "nightly", "proj", str(self.tmp)):
                self.assertNotIn(leak, text, (name, leak))
            self.assertNotRegex(text, r"(^|,)(s1|s2|c1|c2),", name)  # session ids only as a hash

    def test_reimport_is_stable_and_keeps_rows_the_logs_lost(self):
        self.run_import()
        first = (self.data / "ai_work.csv").read_text(encoding="utf-8")
        self.run_import()
        self.assertEqual((self.data / "ai_work.csv").read_text(encoding="utf-8"), first)
        # an older row the logs no longer hold (Claude Code keeps about 30 days) stays
        old = {"start": datetime(2026, 8, 1, 9), "end": datetime(2026, 8, 1, 10), "tool": "claude_code", "session": "old",
               "started_by": "you", "minutes": 50.0, "calls": 120.0, "output_tokens": 9000.0}
        write_table(self.data, "ai_work", self.rows("ai_work") + [old])
        self.run_import()
        self.assertIn("old", [r["session"] for r in self.rows("ai_work")])

    def test_days_limits_the_window(self):
        summary = self.run_import(days=1, now=datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc))  # from 5 Oct 02:00 UTC
        sessions = {r["session"] for r in self.rows("ai_work")}
        self.assertNotIn(session_code("claude_code", "s1"), sessions)   # 01:00–01:15 UTC: before the window
        self.assertIn(session_code("codex", "c1"), sessions)
        self.assertIn("never what was said", " ".join(summary.lines()))

    def test_no_logs_at_all_is_a_clear_error(self):
        with self.assertRaises(ValueError):
            import_ai_logs(self.cfg, claude_dir=self.tmp / "none", codex_dirs=[self.tmp / "none2"])


class Days(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-ai-days-"))
        (self.tmp / "data").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_stretch_over_midnight_is_split_and_adds_up(self):
        write_table(self.tmp / "data", "ai_work", [
            {"start": datetime(2026, 10, 5, 23, 40), "end": datetime(2026, 10, 6, 0, 20), "tool": "claude_code", "session": "a",
             "started_by": "you", "minutes": 30.0, "calls": 60.0, "output_tokens": 1.0},
            {"start": datetime(2026, 10, 8, 9, 0), "end": datetime(2026, 10, 8, 9, 10), "tool": "codex", "session": "b",
             "started_by": "script", "minutes": 10.0, "calls": 9.0, "output_tokens": 1.0}])
        write_table(self.tmp / "data", "ai_prompts", [{"time": datetime(2026, 10, 5, 23, 39), "tool": "claude_code", "session": "a",
                                                       "started_by": "you", "count": 2.0}])
        ctx = Context(Config(root=self.tmp, data_dir=self.tmp / "data", timezone="Australia/Melbourne"), now=datetime(2026, 10, 9, 9))
        days = ctx.ai_days()
        self.assertAlmostEqual(days[date(2026, 10, 5)].you, 15.0)  # 20 of the 40 rounded minutes before midnight
        self.assertAlmostEqual(days[date(2026, 10, 6)].you, 15.0)
        self.assertAlmostEqual(days[date(2026, 10, 5)].by_hour[23]["you"], 15.0)
        self.assertEqual(days[date(2026, 10, 5)].prompts, 2)
        self.assertEqual(days[date(2026, 10, 7)].you, 0)            # in between, no AI use: a real zero
        self.assertEqual(days[date(2026, 10, 8)].other, 10.0)       # a script is never yours
        self.assertEqual(days[date(2026, 10, 8)].you, 0)
        self.assertIn(date(2026, 10, 8), ctx.ai_known_days())
        self.assertNotIn(date(2026, 10, 4), days)                   # before the first record: unknown
        # imports stopped: the last day was probably cut off, so it is not compared
        later = Context(Config(root=self.tmp, data_dir=self.tmp / "data", timezone="Australia/Melbourne"), now=datetime(2026, 10, 20, 9))
        self.assertNotIn(date(2026, 10, 8), later.ai_known_days())


class DemoPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-ai-demo-"))
        cls.now = datetime(2026, 10, 12, 18, 40)
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, cls.now.date(), cls.now))
        except config.ConfigError:  # Python 3.9/3.10 without tomli
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo healthaio.toml")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def ctx(self):
        return Context(self.cfg, now=self.now)

    def test_latest_page(self):
        ctx = self.ctx()
        p = PAGES["ai"](ctx)
        json.dumps(p)
        S = p["span"]
        self.assertFalse(p["empty"])
        self.assertEqual(S["n"], 7)
        self.assertEqual(S["to"], "2026-10-11")
        days = [d for d in S["days"]]
        ai = [d["ai"] for d in days if d["ai"] is not None]
        self.assertAlmostEqual(S["avg"]["ai"], sum(ai) / len(ai))
        both = [d for d in days if d["ai"] is not None and d["prompts"] is not None]
        self.assertAlmostEqual(S["avg"]["per_prompt"], sum(d["ai"] for d in both) / sum(d["prompts"] for d in both))
        both = [d for d in days if d["ai"] is not None and d["focus"] is not None]
        self.assertAlmostEqual(S["avg"]["leverage"], sum(d["ai"] for d in both) / sum(d["focus"] for d in both) * 100)
        self.assertEqual(set(S["metrics"]), set(ai_page.KEYS))
        for key in ("ai", "prompts", "per_prompt", "leverage"):
            self.assertEqual(S["metrics"][key]["tone"], "neutral", key)  # usage is input: never better or worse
        self.assertTrue(all(m["clear"] for m in S["changes"]))
        self.assertEqual(len(p["history"]), ai_page.HISTORY)
        self.assertEqual(len(p["weeks"]), ai_page.WEEKS)
        # the average hour adds up to the average day
        self.assertAlmostEqual(sum(h["you"] for h in S["by_hour"]), S["avg"]["ai"], places=6)
        self.assertAlmostEqual(sum(h["prompts"] for h in S["by_hour"]), S["avg"]["prompts"], places=6)
        # what came out: deadlines marked submitted or done, by due date
        done = [r for r in ctx.store.rows("deadlines") if r["status"] in ("submitted", "done")]
        w = p["weeks"][-1]
        self.assertEqual(w["done"], sum(1 for r in done if w["from"] <= r["due"].date().isoformat() <= w["to"]))

    def test_steps_and_static_pages(self):
        ctx = self.ctx()
        p = PAGES["ai"](ctx)
        self.assertIsNotNone(p["prev"])
        earlier = PAGES["ai"](ctx, p["prev"])
        self.assertEqual(earlier["day"], p["prev"])
        self.assertEqual(earlier["next"], p["newest"])
        params = ai_page.static_params(ctx)
        self.assertEqual(params[0], None)
        self.assertIn(p["prev"], params)

    def test_data_page_lists_ai_only_when_there_is_a_file(self):
        keys = [s["key"] for s in data_page.build(self.ctx())["streams"]]
        self.assertIn("ai", keys)
        tmp = Path(tempfile.mkdtemp(prefix="healthaio-ai-none-"))
        try:
            (tmp / "data").mkdir()
            ctx = Context(Config(root=tmp, data_dir=tmp / "data", timezone="Australia/Melbourne"), now=self.now)
            self.assertNotIn("ai", [s["key"] for s in data_page.build(ctx)["streams"]])
            self.assertTrue(PAGES["ai"](ctx)["empty"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Wiring(unittest.TestCase):
    def test_menu_and_words(self):
        app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('import ai from "./pages/ai.js";', app)
        self.assertIn('["time", "nav.time_tab"], ["ai", "nav.ai"]', app)
        self.assertNotIn('"ai"', re.search(r"const NAV\s*=\s*\[([^\]]*)\]", app).group(1))  # a page of the Daily life item
        page = (WEB / "js" / "pages" / "ai.js").read_text(encoding="utf-8")
        i18n = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
        used = set(re.findall(r't\("((?:ai|time|act|cat|chg|nav)\.[\w.]+)"', page))
        used |= {f"ai.m.{k}" for k in ai_page.KEYS} | {f"ai.note.{k}" for k in ai_page.KEYS} | {"nav.time_tab", "nav.ai", "data.s.ai"}
        for key in used:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)

    def test_the_importer_is_on_the_command_line(self):
        cli = (ROOT / "healthaio" / "importers" / "cli.py").read_text(encoding="utf-8")
        self.assertIn('sub.add_parser("ai-logs"', cli)
        self.assertIn("ai-logs", (ROOT / "docs" / "IMPORTERS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
