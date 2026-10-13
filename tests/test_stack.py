"""Devices at once: every device in use counts its own minutes (context.StackDay, the Time page's card).

Rules under test (healthaio/context.py, healthaio/modules/time.py, healthaio/config.py):
- two devices in use at the same minute count two minutes; clock time still counts the minute once;
- an AI agent app in front on a computer while another device is in use is taken out (the agent works, you are
  on the other device), but not when the agent is the only thing in use, and not when every device in use is one;
- one app open on several devices at the same minute is one thing, counted on the first device in the priority list;
- screens at once = device time / clock time, kept in hundredths; the span's ratio is its device time over its
  clock time; it needs 0.1 (a day) or 0.05 (7 days) outside its band and ranks by the minutes it means;
- the longest stretch on one thing is one app on one device with nothing else in use, and survives a pause
  (or something else) of up to 3 minutes;
- [devices] computers and agent_apps can be set in healthaio.toml;
- the menu is a sidebar: every item has a glyph the kit draws, and a folded sidebar is applied before first paint.
"""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config
from healthaio.config import Config, ConfigError
from healthaio.context import Context
from healthaio.modules import time as time_page
from healthaio.store import write_table

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "healthaio" / "web"
DAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 12, 18, 40)


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute)


def session(device: str, app: str, category: str, start: datetime, minutes: float):
    return {"start": start, "end": start + timedelta(minutes=minutes), "device": device, "app": app, "category": category}


class StackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-stack-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def day(self, *sessions, **cfg):
        data = self.tmp / "data"
        data.mkdir(exist_ok=True)
        write_table(data, "screen_sessions", list(sessions))
        ctx = Context(Config(root=self.tmp, data_dir=data, timezone="Australia/Melbourne",
                             devices=["phone", "tablet", "laptop", "desktop"], **cfg), now=NOW)
        return ctx.stack_days()[DAY], ctx.screen_days()[DAY]


class DeviceTime(StackCase):
    def test_two_devices_at_once_count_twice_and_the_clock_once(self):
        st, sd = self.day(session("tablet", "YouTube", "entertainment", at(20), 60),
                          session("phone", "Instagram", "social", at(20, 15), 30))
        self.assertEqual(sd.total, 60)            # the clock: each minute once
        self.assertEqual(st.clock, 60)
        self.assertEqual(st.stacked, 90)          # devices at once: the tablet's 60 and the phone's 30
        self.assertAlmostEqual(st.ratio, 1.5)
        self.assertEqual(st.multi, 30)
        self.assertEqual(st.by_device, {"tablet": 60, "phone": 30})
        self.assertEqual(st.by_part, {"fun": 90})
        self.assertEqual(st.by_hour[20], {"tablet": {"fun": 60}, "phone": {"fun": 30}})
        self.assertEqual(st.agent, 0)

    def test_an_agent_on_the_laptop_while_you_are_on_the_phone_is_taken_out(self):
        st, sd = self.day(session("laptop", "Claude", "work", at(14), 60),
                          session("phone", "Reddit", "social", at(14, 20), 30))
        self.assertEqual(st.agent, 30)            # the 30 minutes the phone was in use
        self.assertEqual(st.agent_by_hour[14], 30)
        self.assertEqual(st.stacked, 60)          # the laptop's 30 alone and the phone's 30
        self.assertEqual(st.by_device, {"laptop": 30, "phone": 30})
        self.assertEqual(st.multi, 0)
        self.assertAlmostEqual(st.ratio, 1.0)

    def test_an_agent_alone_is_you_working_with_it(self):
        st, _ = self.day(session("laptop", "Claude", "work", at(9), 45))
        self.assertEqual((st.stacked, st.agent), (45, 0))

    def test_agents_on_every_device_in_use_are_not_taken_out(self):
        # someone is at one of them: taking both out would leave minutes on a screen with nobody counted
        st, _ = self.day(session("laptop", "Terminal", "work", at(9), 30),
                         session("desktop", "Codex", "work", at(9), 30))
        self.assertEqual((st.stacked, st.agent), (60, 0))

    def test_an_agent_on_a_phone_is_not_an_agent_working_alone(self):
        st, _ = self.day(session("phone", "ChatGPT", "work", at(9), 20),
                         session("laptop", "Slack", "communication", at(9), 20))
        self.assertEqual((st.stacked, st.agent), (40, 0))  # a phone locks itself: in front means in hand

    def test_agent_apps_and_computers_follow_the_settings(self):
        st, _ = self.day(session("laptop", "Claude", "work", at(14), 60),
                         session("phone", "Reddit", "social", at(14), 60), agent_apps=["Xcode"])
        self.assertEqual((st.stacked, st.agent), (120, 0))
        st, _ = self.day(session("tablet", "Claude", "work", at(14), 60),
                         session("phone", "Reddit", "social", at(14), 60), computers=["tablet"])
        self.assertEqual((st.stacked, st.agent), (60, 60))

    def test_one_app_on_two_devices_is_one_thing_on_the_first_device(self):
        st, _ = self.day(session("laptop", "WhatsApp", "communication", at(11), 20),
                         session("phone", "whatsapp", "communication", at(11, 10), 20))  # names compare without case
        self.assertEqual(st.stacked, 30)
        self.assertEqual(st.by_device, {"laptop": 10, "phone": 20})  # the overlap goes to the phone, first in the list
        self.assertEqual(st.multi, 0)


class OneThing(StackCase):
    def test_the_longest_stretch_survives_a_short_pause_and_names_its_app(self):
        st, _ = self.day(session("tablet", "Kindle", "learning", at(3, 42), 50),
                         session("tablet", "Kindle", "learning", at(4, 35), 30),   # back after a 3-minute pause
                         session("laptop", "Docs", "work", at(10), 40))
        self.assertEqual(st.single, 83)           # 50 + the 3-minute pause + 30
        self.assertEqual((st.single_app, st.single_device, st.single_start), ("Kindle", "tablet", 3 * 60 + 42))

    def test_a_longer_pause_ends_it(self):
        st, _ = self.day(session("tablet", "Kindle", "learning", at(3), 50),
                         session("tablet", "Kindle", "learning", at(3, 54), 30))  # 4 minutes away
        self.assertEqual(st.single, 50)

    def test_a_second_device_is_not_one_thing(self):
        st, _ = self.day(session("laptop", "Docs", "work", at(10), 60),
                         session("phone", "Messages", "communication", at(10, 20), 10))
        self.assertEqual(st.single, 30)           # the 30 minutes after the phone went away (not the first 20)
        self.assertEqual(st.single_start, 10 * 60 + 30)


class RatioAsAChange(unittest.TestCase):
    def test_the_ratio_needs_a_tenth_and_ranks_by_the_minutes_it_means(self):
        band = {"q1": 110.0, "median": 112.0, "q3": 114.0, "days": 20}
        just = time_page.compare("ratio", 120.0, band, time_page.min_width("ratio", False), clock=500)
        self.assertEqual(just["state"], "high")
        self.assertFalse(just["clear"])           # 0.06 past a 0.04 band: under the 0.1 a day needs
        clear = time_page.compare("ratio", 130.0, band, time_page.min_width("ratio", False), clock=500)
        self.assertTrue(clear["clear"])
        self.assertEqual(clear["tone"], "bad")    # more screens at once is worse
        self.assertAlmostEqual(clear["size"], 18 / 100 * 500)  # 0.18 over 500 minutes of screens = 90 device minutes
        week = time_page.compare("ratio", 120.0, band, time_page.min_width("ratio", True), clock=500)
        self.assertTrue(week["clear"])            # a 7-day average needs only 0.05
        fun = time_page.compare("fun", 260.0, {"q1": 180.0, "median": 200.0, "q3": 220.0}, 15)
        self.assertEqual(fun["size"], 60)
        self.assertEqual(time_page.standout([fun, clear])["key"], "ratio")

    def test_the_week_normal_is_device_time_over_clock_time(self):
        first = date(2026, 10, 5)
        days = [first - timedelta(days=k) for k in range(1, 40)]
        # long days at 1.5 (900 device minutes in 600 on the clock), short days at 1.0 (100 in 100), alternating
        stacked = {d: 900.0 if d.day % 2 else 100.0 for d in days}
        clock = {d: 600.0 if d.day % 2 else 100.0 for d in days}
        band = time_page.typical_week_ratio(stacked, clock, first)
        self.assertIsNotNone(band)
        # 7 days hold 3 or 4 long ones: 3100/2200 or 3900/2700, never the mean of daily ratios (1.21 or 1.29)
        for k in ("q1", "median", "q3"):
            self.assertGreaterEqual(band[k], 3100 / 2200 * 100 - 1e-9)
            self.assertLessEqual(band[k], 3900 / 2700 * 100 + 1e-9)


class Settings(unittest.TestCase):
    def test_devices_computers_and_agent_apps(self):
        tmp = Path(tempfile.mkdtemp(prefix="healthaio-cfg-"))
        try:
            path = tmp / "healthaio.json"
            path.write_text(json.dumps({"devices": {"priority": ["phone", "laptop"], "computers": ["laptop"],
                                                    "agent_apps": ["Claude"]}}), encoding="utf-8")
            cfg = config.load(path)
            self.assertEqual((cfg.devices, cfg.computers, cfg.agent_apps), (["phone", "laptop"], ["laptop"], ["Claude"]))
            self.assertIn("Codex", config.load(None).agent_apps)  # sensible defaults without a file
            path.write_text(json.dumps({"devices": {"agent_apps": "Claude"}}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_example_settings_name_both(self):
        text = (ROOT / "examples" / "healthaio.example.toml").read_text(encoding="utf-8")
        self.assertIn("computers = [", text)
        self.assertIn("agent_apps = [", text)


class Sidebar(unittest.TestCase):
    def test_every_menu_item_has_a_glyph_the_kit_draws(self):
        app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
        icons = (WEB / "js" / "icons.js").read_text(encoding="utf-8")
        nav = re.findall(r'"(\w+)"', re.search(r"const NAV\s*=\s*\[([^\]]*)\]", app).group(1))
        glyphs = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"const NAV_ICON\s*=\s*\{([^}]*)\}", app).group(1)))
        self.assertEqual(sorted(glyphs), sorted(nav))
        for glyph in list(glyphs.values()) + ["sidebar"]:
            self.assertRegex(icons, rf"\b{glyph}: '<", glyph)

    def test_the_shell_is_a_sidebar_folded_before_first_paint(self):
        index = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('<header class="side"></header>', index)
        self.assertNotIn('class="top"', index)
        self.assertIn('localStorage.getItem("healthaio.side") === "folded"', index)
        app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('store.set("side"', app)
        i18n = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
        for key in ("ui.fold", "ui.unfold"):
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)

    def test_time_page_words_are_in_both_languages(self):
        page = (WEB / "js" / "pages" / "time.js").read_text(encoding="utf-8")
        i18n = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
        used = set(re.findall(r't\("((?:time|act|chg)\.[\w.]+)"', page))
        self.assertIn("time.stack", used)
        for key in used | {f"act.{k}" for k in ("stacked", "ratio", "single")}:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)


if __name__ == "__main__":
    unittest.main()
