"""A made-up person, so the dashboard can be tried without anyone's real data.

Sam is a graduate student in Melbourne: four courses, a night-owl sleep that a
wake-time plan is slowly pulling earlier, a weight plan that started seven weeks
ago, and the screen habits of most students. Everything is generated from a
fixed seed relative to "today", so the same day always gives the same numbers.
Nothing here is a real measurement; every page shows a "demo data" badge.
"""
import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .store import write_table

SEED = 20261012
BODY_DAYS = 420
SCREEN_DAYS = 120

COURSES = [  # code, name, weekly slots: (weekday 0=Mon, start, minutes, kind word, room)
    ("HCI 610", "Interaction Design", [(0, "10:00", 120, "Lecture", "Arts West 153"),
                                       (2, "14:00", 90, "Studio", "Design Hub 2.12")]),
    ("STAT 520", "Applied Statistics", [(1, "09:00", 60, "Lecture", "Old Quad 101"),
                                        (3, "09:00", 60, "Lecture", "Old Quad 101"),
                                        (3, "15:00", 60, "Tutorial", "Peter Hall G03")]),
    ("INFO 540", "Data Visualisation", [(1, "13:00", 120, "Lecture", "Online"),
                                        (4, "11:00", 90, "Workshop", "Melbourne Connect 3.05")]),
    ("SWEN 530", "Software Process", [(0, "16:00", 60, "Lecture", "Elisabeth Murdoch B117"),
                                      (2, "10:00", 120, "Tutorial", "Doug McDonell 7.02")]),
]

DEADLINES = [  # days from today, hh:mm, course, title, weight %, note
    (-44, "23:59", "STAT 520", "Assignment 1: Regression report", 15, "PDF, 6 pages"),
    (-30, "17:00", "HCI 610", "Design brief", 10, "Individual"),
    (-23, "23:59", "INFO 540", "Assignment 1: Dashboard critique", 20, "1,500 words"),
    (-12, "23:59", "SWEN 530", "Sprint 1 review", 10, "Team of 5"),
    (-3, "23:59", "STAT 520", "Assignment 2: Mixed models", 15, "R Markdown + PDF"),
    (2, "15:00", "HCI 610", "Usability test plan", 15, "Group of 4"),
    (4, "23:59", "SWEN 530", "Sprint 2 demo video", 5, "8–10 minutes"),
    (6, "23:59", "INFO 540", "Assignment 2: Interactive prototype", 30, "Shiny or Tableau"),
    (11, "23:59", "SWEN 530", "Team reflection", 10, "2,000 words"),
    (11, "23:59", "HCI 610", "Peer review", None, "Not graded, required"),
    (17, "23:59", "STAT 520", "Assignment 3: Case study", 20, "Pairs"),
    (23, "09:00", "HCI 610", "Final portfolio", 40, "Individual"),
    (29, "13:15", "STAT 520", "Final exam", 50, "2 hours, closed book"),
    (33, "09:00", "SWEN 530", "Final exam", 50, "Multiple choice + short answer"),
    (36, "13:15", "INFO 540", "Final exam", 40, "Hurdle 40%"),
]

TRAINING = {"mon": "Strength · upper body 50 min", "wed": "Easy run 30 min",
            "fri": "Strength · lower body 50 min", "sat": "Long walk 60 min"}
WORKOUT_DAYS = {0: ("strength training", 50), 2: ("running", 32), 4: ("strength training", 50), 5: ("walking", 62)}
WORKOUT_AT = {"strength training": "17:30", "running": "18:40", "walking": "11:00", "cycling": "16:10"}  # usual start

APPS = {  # category: [(device, app, weight)]
    "work": [("laptop", "VS Code", 4), ("laptop", "Figma", 2), ("laptop", "Google Docs", 3),
             ("laptop", "RStudio", 3), ("laptop", "Terminal", 1), ("laptop", "Claude", 2)],
    "learning": [("laptop", "canvas.lms.edu", 3), ("laptop", "Lecture recordings", 2), ("tablet", "Notability", 2)],
    "communication": [("laptop", "Slack", 3), ("phone", "WhatsApp", 3), ("laptop", "Mail", 2), ("phone", "Messages", 1)],
    "entertainment": [("tablet", "YouTube", 4), ("laptop", "youtube.com", 2), ("tablet", "Netflix", 2),
                      ("laptop", "Steam", 1), ("phone", "Spotify", 1)],
    "social": [("phone", "Instagram", 4), ("phone", "Reddit", 3), ("phone", "X", 2), ("phone", "TikTok", 2)],
    "other": [("laptop", "Finder", 2), ("phone", "Maps", 1), ("phone", "Banking", 1), ("laptop", "Settings", 1)],
}
# a second device in use at the same time (Sam.overlaps): what the phone does while the laptop or tablet is on
PHONE_ON_THE_SIDE = [("social", "Instagram", 4), ("social", "Reddit", 3), ("social", "TikTok", 2),
                     ("communication", "WhatsApp", 3), ("communication", "Messages", 1)]
# the week before deadlines: group chats about the work, open beside it
CRUNCH_SIDE = [("communication", "WhatsApp", 5), ("communication", "Messages", 1), ("social", "Instagram", 1)]
AGENT_APPS = ("Claude", "Terminal")  # an agent can run on its own here while Sam is on another device
EDITOR_AGENT = {"VS Code": 0.7, "RStudio": 0.25}  # how often a session in the editor has an agent working in it


def _hm(text: str) -> time:
    hour, minute = text.split(":")
    return time(int(hour), int(minute))


def _at(day: date, minutes_from_midnight: float) -> datetime:
    return datetime.combine(day, time()) + timedelta(minutes=round(minutes_from_midnight))


class Sam:
    def __init__(self, today: date, now: Optional[datetime] = None):
        self.today = today
        self.now = now or datetime.combine(today, time(18, 40))
        self.rng = random.Random(SEED + today.toordinal())
        self.shift_start = today - timedelta(days=12)
        self.weight_start = today - timedelta(days=49)
        self.semester_start = today - timedelta(days=70)
        self.semester_end = today + timedelta(days=40)
        self.workouts: List[Dict] = []

    # ---- sleep -------------------------------------------------------------------------------
    def alarm_for(self, day: date, on_time: Dict[date, bool]) -> Optional[float]:
        """The wake-shift rule: one 15-minute step earlier after each on-time morning, never later."""
        if day < self.shift_start:
            return None
        alarm = 10 * 60 + 30
        d = self.shift_start
        while d < day:
            if on_time.get(d):
                alarm = max(7 * 60 + 30, alarm - 15)
            d += timedelta(days=1)
        return alarm

    def nights(self) -> Dict[date, Tuple[datetime, datetime, float]]:
        rng = self.rng
        out: Dict[date, Tuple[datetime, datetime, float]] = {}
        on_time: Dict[date, bool] = {}
        start = self.today - timedelta(days=BODY_DAYS - 1)
        for k in range(BODY_DAYS):
            day = start + timedelta(days=k)
            if rng.random() < 0.035:  # watch left on the charger
                continue
            weekend = day.weekday() >= 5
            alarm = self.alarm_for(day, on_time)
            if alarm is None:
                wake = 10 * 60 + 20 + (55 if weekend else 0) + rng.gauss(0, 50)
            else:
                late = rng.random() < 0.3
                wake = alarm + (rng.uniform(20, 95) if late else rng.uniform(-10, 12))
                on_time[day] = not late and wake <= alarm + 15
            duration = max(4.2, min(10.5, rng.gauss(7.45 if not weekend else 8.1, 0.85)))
            if alarm is not None:  # an earlier alarm cuts sleep until bedtime catches up
                duration -= max(0.0, (10 * 60 + 30 - alarm) / 60) * 0.35
            end = _at(day, wake)
            begin = end - timedelta(hours=duration)
            out[day] = (begin, end, duration)
        return out

    # ---- body --------------------------------------------------------------------------------
    def body(self) -> List[Dict]:
        rng = self.rng
        nights = self.nights()
        rows: List[Dict] = []
        start = self.today - timedelta(days=BODY_DAYS - 1)
        hrv_noise = 0.0
        weight = 81.6
        trained_yesterday = False
        for k in range(BODY_DAYS):
            day = start + timedelta(days=k)
            night = nights.get(day)
            sleep_h = night[2] if night else None
            hrv_noise = 0.62 * hrv_noise + rng.gauss(0, 3.6)
            seasonal = 2.2 * math.sin(k / 41.0)
            hrv = 44 + seasonal + hrv_noise + (1.1 * (sleep_h - 7.4) if sleep_h else 0) - (1.6 if trained_yesterday else 0)
            if rng.random() < 0.05:
                hrv -= rng.uniform(5, 11)  # a late night out
            rhr = 61.5 - 0.09 * (hrv - 44) - (0.45 * (sleep_h - 7.4) if sleep_h else 0) + rng.gauss(0, 1.2)
            plan = WORKOUT_DAYS.get(day.weekday())
            did = plan is not None and rng.random() < 0.74
            if not did and plan is None and rng.random() < 0.06:
                plan, did = ("cycling", 40), True
            campus = day.weekday() <= 4 and self.semester_start <= day <= self.semester_end
            steps = max(800.0, rng.gauss(8600 if campus else 5600, 2300) + (3500 if did and plan[0] in ("running", "walking") else 0))
            exercise = max(0.0, rng.gauss(14, 7) + (plan[1] * rng.uniform(0.7, 1.0) if did else 0))
            complete = day != self.today
            row = {"date": day, "complete": complete}
            if night:
                begin, end, duration = night
                row.update(sleep_min=round(duration * 60), in_bed_min=round(duration * 60 + rng.uniform(12, 42)),
                           sleep_start=begin, sleep_end=end)
            if rng.random() > 0.03:
                row["hrv_ms"] = round(max(18.0, hrv), 1)
                row["resting_hr"] = round(rhr, 1)
            if complete:
                minutes = round(plan[1] * rng.uniform(0.85, 1.15)) if did else 0
                row.update(steps=round(steps), exercise_min=max(round(exercise), minutes),
                           workout_min=minutes, workout_type=plan[0] if did else None)
                if did:  # the same workout with its clock time, as Apple Fitness records it
                    hh, mm = map(int, WORKOUT_AT[plan[0]].split(":"))
                    begin = datetime.combine(day, time(hh, mm)) + timedelta(minutes=rng.randint(-25, 35))
                    self.workouts.append({"start": begin, "end": begin + timedelta(minutes=minutes), "type": plan[0],
                                          "source": "Apple Watch", "kcal": round(minutes * rng.uniform(5.5, 8.5))})
            else:
                share = (self.now.hour * 60 + self.now.minute - 600) / 840
                row.update(steps=round(steps * max(0.05, share)), exercise_min=round(exercise * max(0.0, share)))
            # weight: drifting before the plan, ~0.6% a week down after it
            if day < self.weight_start:
                weight += rng.gauss(0.004, 0.09)
                weighed = rng.random() < 0.3
            else:
                weight -= weight * 0.0062 / 7 * rng.uniform(0.2, 1.8)
                weighed = rng.random() < 0.8
            if weighed:
                row["weight_kg"] = round(weight + rng.gauss(0, 0.32), 1)
            if day >= self.weight_start and day.weekday() == 6:
                row["waist_cm"] = round(92.5 - (day - self.weight_start).days * 0.045 + rng.gauss(0, 0.4), 1)
            trained_yesterday = did and plan[0] == "strength training"
            rows.append(row)
        return rows

    def self_report(self, body: List[Dict]) -> List[Dict]:
        rng = random.Random(SEED + 7)
        notes = ["Slept through", "Heavy legs after the gym", "Groggy, alarm too early", "Good focus in the morning",
                 "Too much coffee", "Calm day", "Stayed up for the deadline", "Felt fresh after the run"]
        out = []
        for row in body[-150:]:
            if rng.random() > 0.55:
                continue
            sleep = (row.get("sleep_min") or 420) / 60
            energy = max(0, min(5, round(2.4 + 0.5 * (sleep - 7.2) + rng.gauss(0, 0.8))))
            focus = max(0, min(5, round(2.6 + 0.3 * (sleep - 7.2) + rng.gauss(0, 0.9))))
            out.append({"date": row["date"], "energy": energy, "focus": focus,
                        "note": rng.choice(notes) if rng.random() < 0.35 else None})
        return out

    # ---- calendar ----------------------------------------------------------------------------
    def events(self) -> List[Dict]:
        out = []
        day = self.semester_start
        midterm = self.semester_start + timedelta(days=42)  # one teaching-free week
        while day <= self.semester_end - timedelta(days=12):
            if not (midterm <= day < midterm + timedelta(days=7)):
                for code, name, slots in COURSES:
                    for weekday, start, minutes, word, room in slots:
                        if day.weekday() == weekday:
                            begin = datetime.combine(day, _hm(start))
                            out.append({"start": begin, "end": begin + timedelta(minutes=minutes),
                                        "title": f"{code} {word}", "kind": "class", "location": room})
            day += timedelta(days=1)
        for offset, start, minutes, title in [(1, "18:30", 120, "Dinner with flatmates"), (5, "10:00", 90, "Farmers market"),
                                              (8, "12:00", 60, "Career fair")]:
            begin = datetime.combine(self.today + timedelta(days=offset), _hm(start))
            out.append({"start": begin, "end": begin + timedelta(minutes=minutes), "title": title,
                        "kind": "personal", "location": None})
        return out

    def deadlines(self) -> List[Dict]:
        out = []
        for offset, hhmm, group, title, weight, note in DEADLINES:
            due = datetime.combine(self.today + timedelta(days=offset), _hm(hhmm))
            status = "submitted" if offset < 0 else ("todo" if offset > 0 else "todo")
            out.append({"due": due, "title": title, "group": group, "weight_pct": weight,
                        "status": status, "note": note})
        return out

    # ---- screen ------------------------------------------------------------------------------
    def screen(self, body: List[Dict], events: List[Dict]) -> List[Dict]:
        rng = random.Random(SEED + 11)
        by_day = {row["date"]: row for row in body}
        classes: Dict[date, List[Tuple[datetime, datetime]]] = {}
        for e in list(events) + list(self.workouts):
            classes.setdefault(e["start"].date(), []).append((e["start"], e["end"]))
        out: List[Dict] = []
        for k in range(SCREEN_DAYS - 1, -1, -1):
            day = self.today - timedelta(days=k)
            wake_row, next_row = by_day.get(day, {}), by_day.get(day + timedelta(days=1), {})
            wake = wake_row.get("sleep_end") or datetime.combine(day, time(10, 30))
            bed = next_row.get("sleep_start") or datetime.combine(day + timedelta(days=1), time(1, 45))
            stop = min(bed, self.now) if day == self.today else bed
            busy = classes.get(day, [])
            deadline_crunch = any(0 <= (self.today + timedelta(days=d[0]) - day).days <= 2 for d in DEADLINES)
            t = wake + timedelta(minutes=rng.uniform(1, 6))
            while t < stop:
                if any(a <= t < b for a, b in busy):
                    t = max(b for a, b in busy if a <= t < b) + timedelta(minutes=rng.uniform(3, 12))
                    continue
                minutes_left = (stop - t).total_seconds() / 60
                hour = t.hour + t.minute / 60
                before_bed = minutes_left < 60
                if before_bed:
                    weights = {"social": 5, "entertainment": 4, "communication": 1.5, "other": 0.5}
                elif hour < 12:
                    weights = {"social": 2.5, "communication": 2, "work": 2, "learning": 1.5, "other": 1}
                elif hour < 18:
                    weights = {"work": 5 + (3 if deadline_crunch else 0), "learning": 2.5, "communication": 2,
                               "social": 1.5, "entertainment": 1, "other": 0.8}
                else:
                    weights = {"work": 2 + (4 if deadline_crunch else 0), "entertainment": 4.5, "social": 2.5,
                               "communication": 1.5, "learning": 0.8, "other": 0.5}
                category = rng.choices(list(weights), list(weights.values()))[0]
                device, app, _ = rng.choices(APPS[category], [w for _, _, w in APPS[category]])[0]
                length = {"work": rng.expovariate(1 / 32), "learning": rng.expovariate(1 / 26),
                          "entertainment": rng.expovariate(1 / 34), "social": rng.expovariate(1 / 11),
                          "communication": rng.expovariate(1 / 5), "other": rng.expovariate(1 / 4)}[category]
                length = max(1.0, min(length, 150.0, minutes_left))
                end = t + timedelta(minutes=length)
                out.append({"start": t, "end": end, "device": device, "app": app, "category": category})
                gap = rng.expovariate(1 / 7) if rng.random() < 0.8 else rng.uniform(20, 75)  # meals, walks, away
                t = end + timedelta(minutes=gap)
        return out + self.overlaps(out)

    def overlaps(self, sessions: List[Dict]) -> List[Dict]:
        """A second device at the same time, on top of the one-at-a-time sessions above (its own random
        stream, so those stay the same): the phone while a video plays on the tablet, the phone while an
        agent runs on the laptop, quick checks during work (more of them in the week before deadlines),
        and now and then the same video left open on the laptop too (one thing on two devices)."""
        rng = random.Random(SEED + 12)
        out: List[Dict] = []

        def side(start: datetime, end: datetime, device: str = "phone", pick=PHONE_ON_THE_SIDE) -> None:
            if end - start < timedelta(minutes=1):
                return
            category, app, _ = rng.choices(pick, [w for _, _, w in pick])[0]
            out.append({"start": start, "end": end, "device": device, "app": app, "category": category})

        for s in sessions:
            length = (s["end"] - s["start"]).total_seconds() / 60
            if length < 6 or s["device"] == "phone":
                continue
            crunch = (self.today - s["start"].date()).days < 7  # deadlines in the coming days: more phone checks
            if s["device"] == "laptop" and s["app"] in AGENT_APPS and rng.random() < 0.75:
                start = s["start"] + timedelta(minutes=length * rng.uniform(0.1, 0.3))  # set the agent going, then scroll
                end = start + timedelta(minutes=length * rng.uniform(0.45, 0.65))
                if rng.random() < 0.6:
                    side(start, end)
                else:
                    side(start, end, "tablet", [("entertainment", "YouTube", 3), ("entertainment", "Netflix", 1)])
            elif s["device"] == "tablet" and s["category"] == "entertainment" and rng.random() < 0.8:
                t = s["start"] + timedelta(minutes=rng.uniform(1, 6))
                while t < s["end"] - timedelta(minutes=3):  # scrolling the phone with a video on
                    end = min(s["end"], t + timedelta(minutes=rng.uniform(4, 14)))
                    side(t, end)
                    t = end + timedelta(minutes=rng.uniform(3, 12))
                if s["app"] == "YouTube" and rng.random() < 0.15:  # the same video open on the laptop too
                    out.append({"start": s["start"], "end": s["start"] + timedelta(minutes=min(length, rng.uniform(5, 15))),
                                "device": "laptop", "app": "YouTube", "category": "entertainment"})
            elif s["device"] == "laptop" and s["category"] in ("work", "learning", "entertainment"):
                busy = crunch and s["category"] != "entertainment"
                chance = 0.45 if s["category"] == "entertainment" else 0.9 if busy else 0.4
                t = s["start"] + timedelta(minutes=rng.uniform(2, 8))
                while t < s["end"] - timedelta(minutes=2):
                    if rng.random() < chance:
                        end = min(s["end"], t + timedelta(minutes=rng.uniform(3, 12) if busy else rng.uniform(2, 9)))
                        side(t, end, pick=CRUNCH_SIDE if busy else PHONE_ON_THE_SIDE)
                        t = end
                    t += timedelta(minutes=rng.uniform(3, 9) if busy else rng.uniform(5, 14))
        return out

    # ---- AI agents ---------------------------------------------------------------------------
    def ai(self, sessions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Claude Code and Codex for Sam (ai_work, ai_prompts): whenever Sam is in Claude or the terminal on the
        laptop, and in most coding sessions in VS Code (the agent in the editor), an instruction every few minutes,
        each followed by a few minutes of the agent working (it keeps going when Sam picks up the phone); now and
        then a second session at once; some nights a scheduled task."""
        rng = random.Random(SEED + 13)
        work: List[Dict] = []
        prompts: Dict[tuple, float] = {}

        def code(n: int) -> str:
            return f"demo{n:06d}"

        def stretch(start: datetime, minutes: float, tool: str, session: str, who: str) -> None:
            end = start + timedelta(minutes=minutes)
            calls = max(2.0, round(minutes * rng.uniform(2, 5)))
            work.append({"start": start.replace(second=0, microsecond=0), "end": (end + timedelta(seconds=59)).replace(second=0, microsecond=0),
                         "tool": tool, "session": session, "started_by": who, "minutes": round(minutes, 2),
                         "calls": calls, "output_tokens": round(calls * rng.uniform(300, 1200))})

        n = 0
        for s in sessions:
            if s["device"] != "laptop" or not (s["app"] in AGENT_APPS or (s["app"] in EDITOR_AGENT and rng.random() < EDITOR_AGENT[s["app"]])):
                continue
            length = (s["end"] - s["start"]).total_seconds() / 60
            if length < 4:
                continue
            n += 1
            tool = "claude_code" if s["app"] == "Claude" or rng.random() < 0.7 else "codex"
            session = code(n)
            t = s["start"] + timedelta(minutes=rng.uniform(0.3, 1.5))
            while t < s["end"]:
                key = (t.replace(second=0, microsecond=0), tool, session)
                prompts[key] = prompts.get(key, 0) + 1
                busy = rng.uniform(3, 13)
                stretch(t + timedelta(seconds=20), busy, tool, session, "you")
                t += timedelta(minutes=busy + rng.uniform(1, 6))  # reading what it did, then the next ask
            if rng.random() < 0.25:  # a second session at once: the other agent on another part of the work
                n += 1
                other = "codex" if tool == "claude_code" else "claude_code"
                start = s["start"] + timedelta(minutes=rng.uniform(1, 4))
                prompts[(start.replace(second=0, microsecond=0), other, code(n))] = 1
                stretch(start + timedelta(seconds=30), min(length, rng.uniform(8, 30)), other, code(n), "you")
        for k in range(SCREEN_DAYS - 1, 0, -1):  # some nights a scheduled task (a nightly summary)
            if rng.random() < 0.45:
                n += 1
                night = datetime.combine(self.today - timedelta(days=k), time(2, 10)) + timedelta(minutes=rng.uniform(0, 20))
                stretch(night, rng.uniform(5, 14), "claude_code", code(n), "scheduled")
        rows = [{"time": t, "tool": tool, "session": session, "started_by": "you", "count": float(c)}
                for (t, tool, session), c in prompts.items() if t <= self.now]
        return [w for w in work if w["end"] <= self.now + timedelta(minutes=1) or w["start"] < self.now], rows


def demo_config(today: date) -> str:
    shift = today - timedelta(days=12)
    weight = today - timedelta(days=49)
    training = "\n".join(f'{day} = "{text}"' for day, text in TRAINING.items())
    return f"""# Demo settings for a made-up person. Copy examples/dayring.example.toml for your own.
[dayring]
data_dir = "data"
timezone = "Australia/Melbourne"
locale = "en"
title = "dayring"
demo = true

[devices]
priority = ["phone", "tablet", "laptop"]

[plan.sleep]
target_hours = 8
bedtime = "23:30"
wake = "07:30"

[plan.wake_shift]
start = "{shift.isoformat()}"
first_alarm = "10:30"
final_alarm = "07:30"
step_min = 15
grace_min = 15

[plan.weight]
start_date = "{weight.isoformat()}"
start_kg = 81.2
target_kg = 75
weekly_loss_pct = [0.5, 1.0]

[plan.training]
{training}

[plan.screen]
entertainment_max_hours = 3
work_min_hours = 4
"""


def generate(out: Path, today: Optional[date] = None, now: Optional[datetime] = None) -> Path:
    """Write a complete demo folder (dayring.toml + data/*.csv) and return the config path."""
    today = today or date.today()
    out = Path(out)
    data = out / "data"
    sam = Sam(today, now)
    body = sam.body()
    events = sam.events()
    write_table(data, "body_daily", body)
    write_table(data, "self_report", sam.self_report(body))
    write_table(data, "events", events)
    write_table(data, "deadlines", sam.deadlines())
    write_table(data, "workouts", sam.workouts)
    sessions = sam.screen(body, events)
    write_table(data, "screen_sessions", sessions)
    work, prompts = sam.ai(sessions)
    write_table(data, "ai_work", work)
    write_table(data, "ai_prompts", prompts)
    config = out / "dayring.toml"
    config.write_text(demo_config(today), encoding="utf-8")
    return config
