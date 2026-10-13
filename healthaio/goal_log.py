"""Goals set on the Goals page, and goals an assistant proposes, as an append-only log next to healthaio.toml.

The file is goals.jsonl, one JSON object per line:

    {"id": "3f9a1c2e", "at": "2026-10-13T23:40:00", "op": "set", "by": "you", "changes": {"food.kcal_max": 2200}}
    {"id": "b71d0e4a", "at": "...", "op": "propose", "by": "assistant", "changes": {"screen.entertainment_max_hours": 2.5},
     "note": "why, in a sentence"}
    {"id": "c0de5f17", "at": "...", "op": "accept", "by": "you", "ref": "b71d0e4a"}
    {"id": "9e2b6a03", "at": "...", "op": "decline", "by": "you", "ref": "b71d0e4a"}

healthaio.toml stays as you wrote it. A goal set here is laid over it each time a page is computed, and the latest
line for a field wins; null takes the field back to healthaio.toml (or to the guideline when the file has none).
Nothing is rewritten or deleted, so the file is also the history of every change.

A proposal changes nothing until you accept it. This is where an assistant plugs in: any agent that can run a
command reads `healthaio page goals` and writes `healthaio goal propose FIELD VALUE --note "..."`; you answer on the
Goals page (or with `healthaio goal accept ID`).
"""
import copy
import json
import secrets
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as config_mod

FILENAME = "goals.jsonl"
OPS = ("set", "propose", "accept", "decline")

# Every field a goal can set: its type and the range it must fall in. The keys are healthaio.toml's
# ([plan.food] kcal_max = food.kcal_max). weight.start_* are written for you when a weight goal starts here.
FIELDS: Dict[str, Dict[str, Any]] = {
    "sleep.bedtime": {"type": "clock"},
    "sleep.wake": {"type": "clock"},
    "sleep.target_hours": {"type": "number", "min": 4, "max": 12, "step": 0.25, "unit": "h"},
    "exercise.weekly_min": {"type": "number", "min": 0, "max": 2000, "step": 5, "unit": "min"},
    "exercise.strength_days": {"type": "int", "min": 0, "max": 7, "step": 1, "unit": "days"},
    "food.kcal_min": {"type": "number", "min": 800, "max": 6000, "step": 50, "unit": "kcal"},
    "food.kcal_max": {"type": "number", "min": 800, "max": 6000, "step": 50, "unit": "kcal"},
    "food.protein_g_per_kg": {"type": "number", "min": 0.5, "max": 3, "step": 0.1, "unit": "g_per_kg"},
    "food.last_meal_gap_h": {"type": "number", "min": 0, "max": 8, "step": 0.5, "unit": "h"},
    "weight.target_kg": {"type": "number", "min": 30, "max": 300, "step": 0.1, "unit": "kg"},
    "screen.work_min_hours": {"type": "number", "min": 0, "max": 16, "step": 0.5, "unit": "h"},
    "screen.entertainment_max_hours": {"type": "number", "min": 0, "max": 16, "step": 0.5, "unit": "h"},
}
HIDDEN = {"weight.start_kg": {"type": "number", "min": 30, "max": 300}, "weight.start_date": {"type": "date"}}


class GoalError(ValueError):
    """A change that cannot be written: an unknown field, a value out of range, a proposal already answered."""


@dataclass
class State:
    values: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # field -> {value, by, at, accepted}
    pending: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # proposal id -> its line, in order


def path(cfg: config_mod.Config) -> Path:
    return cfg.root / FILENAME


def read(cfg: config_mod.Config) -> List[Dict[str, Any]]:
    """Every readable line, in order. A line that is not a JSON object with a known op is skipped."""
    file = path(cfg)
    if not file.is_file():
        return []
    out = []
    for raw in file.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("op") in OPS:
            out.append(entry)
    return out


def replay(entries: List[Dict[str, Any]]) -> State:
    state = State()
    for e in entries:
        op = e["op"]
        if op in ("set", "propose") and not isinstance(e.get("changes"), dict):
            continue
        if op == "set":
            for name, value in e["changes"].items():
                if value is None:
                    state.values.pop(name, None)
                else:
                    state.values[name] = {"value": value, "by": e.get("by", "you"), "at": e.get("at"), "accepted": False}
        elif op == "propose":
            state.pending[str(e.get("id"))] = e
        elif op in ("accept", "decline"):
            proposal = state.pending.pop(str(e.get("ref")), None)
            if proposal and op == "accept":
                for name, value in proposal["changes"].items():
                    if value is None:
                        state.values.pop(name, None)
                    else:
                        state.values[name] = {"value": value, "by": proposal.get("by", "assistant"), "at": e.get("at"), "accepted": True}
    return state


def _set(cfg: config_mod.Config, name: str, value: Any) -> None:
    section, key = name.split(".", 1)
    if section == "sleep":
        setattr(cfg.sleep, key, config_mod._clock(value, name) if key in ("bedtime", "wake") else float(value))
    elif section == "exercise":
        setattr(cfg.exercise, key, int(value) if key == "strength_days" else float(value))
    elif section == "food":
        setattr(cfg.food, key, float(value))
        if key == "protein_g_per_kg":
            cfg.food.protein_g = None  # a target per kg set here replaces a fixed amount in the file
    elif section == "screen":
        setattr(cfg.screen, key, float(value))


def overlay(cfg: config_mod.Config, values: Dict[str, Any]) -> config_mod.Config:
    """A copy of cfg with the given field values laid over it (weight.* together: they make one plan)."""
    out = copy.deepcopy(cfg)
    for name, value in values.items():
        if name in FIELDS and not name.startswith("weight."):
            _set(out, name, value)
    target = values.get("weight.target_kg")
    if target is not None:
        if out.weight is not None:
            out.weight.target_kg = float(target)
        elif values.get("weight.start_kg") is not None and values.get("weight.start_date"):
            out.weight = config_mod.WeightPlan(start_date=date.fromisoformat(values["weight.start_date"]),
                                               start_kg=float(values["weight.start_kg"]), target_kg=float(target))
    return out


def apply(cfg: config_mod.Config) -> config_mod.Config:
    """cfg with every goal set here laid over it, and what was set and what waits for an answer attached."""
    state = replay(read(cfg))
    out = overlay(cfg, {k: v["value"] for k, v in state.values.items()})
    out.goals_set = state.values
    out.goals_proposed = list(state.pending.values())
    return out


def _check(name: str, value: Any) -> Any:
    spec = FIELDS.get(name) or HIDDEN.get(name)
    if spec is None:
        raise GoalError(f"unknown goal field: {name}")
    if value is None:
        return None
    kind = spec["type"]
    try:
        if kind == "clock":
            return config_mod._clock(value, name).strftime("%H:%M")  # anything but HH:MM raises
        if kind == "date":
            return config_mod._day(value, name).isoformat()
    except config_mod.ConfigError as error:
        raise GoalError(str(error)) from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GoalError(f"{name}: expected a number, got {value!r}")
    if kind == "int" and value != int(value):
        raise GoalError(f"{name}: expected a whole number, got {value!r}")
    if not spec["min"] <= value <= spec["max"]:
        raise GoalError(f"{name}: {value} is outside {spec['min']}–{spec['max']}")
    return int(value) if kind == "int" else value


def check(cfg: config_mod.Config, changes: Dict[str, Any]) -> Dict[str, Any]:
    """The changes, cleaned, if they leave a plan that makes sense; GoalError otherwise."""
    if not isinstance(changes, dict) or not changes:
        raise GoalError("nothing to change")
    clean = {name: _check(name, value) for name, value in changes.items()}
    applied = apply(cfg)
    current = {k: v["value"] for k, v in applied.goals_set.items()}
    if "weight.target_kg" in clean:
        if clean["weight.target_kg"] is None:  # back to the file: the start written with it goes too
            clean.update({"weight.start_kg": None, "weight.start_date": None})
        elif applied.weight is None and clean.get("weight.start_kg") is None:
            start = _latest_weight(cfg)
            if start is None:
                raise GoalError("weight.target_kg: no weight recorded yet to start the plan from")
            clean.update({"weight.start_kg": round(start[1], 1), "weight.start_date": start[0].isoformat()})
    after = dict(current)
    for name, value in clean.items():
        if value is None:
            after.pop(name, None)  # back to what the file says
        else:
            after[name] = value
    merged = overlay(cfg, after)
    food = merged.food
    if food.kcal_min is not None and food.kcal_max is not None and food.kcal_min > food.kcal_max:
        raise GoalError("food.kcal_min must not be above food.kcal_max")
    if merged.weight is not None and clean.get("weight.target_kg") is not None and merged.weight.target_kg >= merged.weight.start_kg:
        raise GoalError("weight.target_kg: the weight plan counts down; the target must be below the start weight "
                        f"({merged.weight.start_kg:g} kg)")
    return clean


def _latest_weight(cfg: config_mod.Config):
    """(day, 7-day average) of the latest weight on record, for a weight plan that starts here."""
    from .context import Context
    from .modules.body import avg7
    weights = {r["date"]: r["weight_kg"] for r in Context(cfg).store.rows("body_daily") if r.get("weight_kg") is not None}
    if not weights:
        return None
    day = max(weights)
    return day, avg7(weights, day) or weights[day]


def append(cfg: config_mod.Config, op: str, by: str = "you", changes: Optional[Dict[str, Any]] = None,
           ref: Optional[str] = None, note: Any = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Check one change and add it as a line at the end of goals.jsonl; returns the line."""
    if op not in OPS:
        raise GoalError(f"unknown op: {op}")
    entry: Dict[str, Any] = {"id": secrets.token_hex(4),
                             "at": (now or datetime.now(cfg.tz).replace(tzinfo=None)).isoformat(timespec="seconds"),
                             "op": op, "by": str(by or "you")[:40]}
    if op in ("set", "propose"):
        entry["changes"] = check(cfg, changes or {})
    else:
        pending = replay(read(cfg)).pending
        if str(ref) not in pending:
            raise GoalError(f"no open proposal with id {ref!r}")
        if op == "accept":
            check(cfg, pending[str(ref)]["changes"])  # still sensible against what is set now
        entry["ref"] = str(ref)
    if note:
        entry["note"] = note if isinstance(note, dict) else str(note)[:500]
    file = path(cfg)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def from_browser(cfg: config_mod.Config, request: Any, now: Optional[datetime] = None) -> Dict[str, Any]:
    """A change sent by the Goals page: set, accept or decline, always by you. Proposals come from assistants."""
    if not isinstance(request, dict):
        raise GoalError("expected a JSON object")
    op = request.get("op")
    if op == "set":
        return append(cfg, "set", "you", changes=request.get("changes"), now=now)
    if op in ("accept", "decline"):
        return append(cfg, op, "you", ref=request.get("id"), now=now)
    raise GoalError("op must be set, accept or decline")


# ---- the command line: `healthaio goal ...` ------------------------------------------------------------------

def _parse(pairs: List[str]) -> Dict[str, Any]:
    if len(pairs) % 2:
        raise GoalError("expected FIELD VALUE pairs, e.g. food.kcal_max 2200")
    out: Dict[str, Any] = {}
    for name, text in zip(pairs[::2], pairs[1::2]):
        try:
            out[name] = json.loads(text)  # numbers and null
        except ValueError:
            out[name] = text  # a clock, HH:MM
    return out


def run(args: Any, cfg: config_mod.Config) -> int:
    try:
        if args.goal_command == "list":
            applied = apply(cfg)
            rows = []
            for name in FIELDS:
                mine = applied.goals_set.get(name)
                rows.append({"field": name, "value": _now_value(applied, name),
                             "from": f"set here by {mine['by']}{' (accepted)' if mine['accepted'] else ''} {mine['at']}" if mine else "healthaio.toml"})
            if args.json:
                print(json.dumps({"fields": rows, "proposals": applied.goals_proposed}, ensure_ascii=False, indent=2))
                return 0
            for r in rows:
                print(f"{r['field']:32} {'-' if r['value'] is None else r['value']!s:8} {r['from']}")
            for p in applied.goals_proposed:
                changes = ", ".join(f"{k} → {v}" for k, v in p["changes"].items())
                print(f"\nproposal {p['id']} from {p.get('by')} ({p.get('at')}): {changes}" + (f"\n  {p['note']}" if p.get("note") else ""))
            return 0
        if args.goal_command in ("set", "propose"):
            by = "you" if args.goal_command == "set" else args.by
            entry = append(cfg, args.goal_command, by, changes=_parse(args.pairs), note=getattr(args, "note", None))
        else:
            entry = append(cfg, args.goal_command, "you", ref=args.id)
    except GoalError as error:
        print(f"healthaio goal: {error}", file=sys.stderr)
        return 2
    print(json.dumps(entry, ensure_ascii=False))
    return 0


def _now_value(cfg: config_mod.Config, name: str) -> Any:
    section, key = name.split(".", 1)
    if section == "weight":
        return cfg.weight.target_kg if cfg.weight else None
    value = getattr(getattr(cfg, section), key)
    return value.strftime("%H:%M") if hasattr(value, "strftime") else value
