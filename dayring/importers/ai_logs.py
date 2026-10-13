"""Claude Code and Codex logs on this computer -> ``ai_work`` and ``ai_prompts``.

What it reads (read-only)
    Claude Code: ``~/.claude/projects/<folder>/<session>.jsonl`` (the terminal and the desktop app's Code
    tab both write here); a subagent's log in ``<session>/subagents/`` counts into its parent session.
    Each model call is an ``assistant`` record with ``usage``; a call split over several records (one
    per content block) counts once, by message id and request id. Claude Code keeps about 30 days of
    logs, so import every few weeks for a continuous history.
    Codex: ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`` and ``~/.codex/archived_sessions/``. A
    ``token_count`` event is a model call, a ``task_started`` event the start of a turn, which is an
    instruction you gave.

What it keeps
    Times, the tool, a hashed session code, who started the session, call counts and output token
    totals. Never the text of a prompt or a reply, file contents, commands, paths or project names.
    Web and app chats (claude.ai, ChatGPT) leave no log on this computer and are not in here.

Who started it
    A Claude Code session whose first prompt is a scheduled task, or that ran from ``claude -p``
    (entrypoint ``sdk-cli``), is ``scheduled`` / ``script``; a Codex session from ``codex exec`` is
    ``script``; the rest are ``you``. Only yours count as your AI work on the page.

Work time
    Within one session, two calls no more than 5 minutes apart mean the agent was working between
    them; a longer gap is the agent waiting for you. One stretch of such calls becomes one ``ai_work``
    row with its exact working minutes; its start and end are written to the minute (rounded outward).
    A tool that runs for more than 5 minutes between two calls is missed, so this is a lower bound.
    A stretch of a single call has no length and is left out (its prompt still counts).

Instructions
    Claude Code: a ``user`` record marked as typed by a person (``turnOrigin`` / ``origin.kind`` =
    ``human``; older logs without these fields: text that is not a tool result and does not start
    with ``<``), outside subagents. Codex: one ``task_started`` per turn. Counted per minute.

Re-importing replaces the rows of each tool from the first stretch (or instruction) this import saw
onward, so rows older than the logs that are left are kept.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from ..config import Config
from ._common import Summary, merge_write, span, validate
from ..schema import TABLES

CLAUDE_DIR = Path.home() / ".claude" / "projects"
CODEX_DIRS = (Path.home() / ".codex" / "sessions", Path.home() / ".codex" / "archived_sessions")
GAP_S = 5 * 60  # two calls of one session at most this far apart: the agent was working between them

Call = Tuple[str, str, str, datetime, int]    # tool, session id, started_by, moment (UTC), output tokens
Prompt = Tuple[str, str, str, datetime]       # tool, session id, started_by, moment (UTC)


def session_code(tool: str, session_id: str) -> str:
    return hashlib.sha256(f"{tool}\n{session_id}".encode("utf-8")).hexdigest()[:12]


def _moment(value: object) -> Optional[datetime]:
    """An ISO time with an offset (or Z) as aware UTC; anything else is None."""
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    if "." in text:  # Python 3.9 reads at most 6 fraction digits
        head, rest = text.split(".", 1)
        n = len(rest) - len(rest.lstrip("0123456789"))  # the fraction's own digits, not the offset's
        text = f"{head}.{rest[:n][:6].ljust(6, '0')}{rest[n:]}" if n else text
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo else None


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _records(path: Path, problems: List[str]) -> Iterator[dict]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    yield item
    except OSError as error:
        problems.append(f"{path.name}: {error.strerror or error}")


# ---- Claude Code ------------------------------------------------------------------------------------

def _claude_started_by(path: Path, problems: List[str]) -> str:
    """From the session's first user record: a scheduled task, a script (claude -p), or you."""
    for item in _records(path, problems):
        if item.get("type") != "user":
            continue
        content = (item.get("message") or {}).get("content")
        if isinstance(content, list):
            content = " ".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
        if (isinstance(content, str) and "<scheduled-task" in content[:400]) or item.get("turnOrigin") == "scheduled":
            return "scheduled"
        if item.get("entrypoint") == "sdk-cli":
            return "script"
        return "you"
    return "you"


def _claude_is_prompt(item: dict) -> bool:
    """An instruction a person typed: not a tool result, a system reminder or a task notification."""
    if item.get("isSidechain") or item.get("isMeta"):
        return False
    origin = item.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if "turnOrigin" in item or kind:
        return item.get("turnOrigin") == "human" or kind == "human"
    content = (item.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.lstrip().startswith("<")
    if isinstance(content, list):
        types = {x.get("type") for x in content if isinstance(x, dict)}
        return "text" in types and "tool_result" not in types
    return False


def read_claude(root: Path, problems: List[str]) -> Tuple[List[Call], List[Prompt]]:
    calls: List[Call] = []
    prompts: List[Prompt] = []
    if not root.is_dir():
        return calls, prompts
    started: Dict[Path, str] = {}
    seen = set()
    for path in sorted(root.glob("**/*.jsonl")):
        subagent = path.parent.name == "subagents"
        parent = path.parent.parent.with_suffix(".jsonl") if subagent else path
        if parent not in started:
            started[parent] = _claude_started_by(parent, problems) if parent.is_file() else "you"
        who = started[parent]
        for item in _records(path, problems):
            kind = item.get("type")
            if kind not in ("user", "assistant"):
                continue
            moment, sid = _moment(item.get("timestamp")), item.get("sessionId")
            if moment is None or not isinstance(sid, str):
                continue
            if kind == "user":
                if not subagent and _claude_is_prompt(item):
                    prompts.append(("claude_code", sid, who, moment))
                continue
            message = item.get("message") or {}
            usage, model = message.get("usage"), message.get("model")
            if not isinstance(usage, dict) or not isinstance(model, str) or model.startswith("<"):
                continue  # "<synthetic>" records are not model calls
            key = (message.get("id"), item.get("requestId"))
            if not isinstance(key[0], str) or key in seen:
                continue
            seen.add(key)
            calls.append(("claude_code", sid, who, moment, _count(usage.get("output_tokens"))))
    return calls, prompts


# ---- Codex ------------------------------------------------------------------------------------------

def read_codex(roots: Iterable[Path], problems: List[str]) -> Tuple[List[Call], List[Prompt]]:
    calls: List[Call] = []
    prompts: List[Prompt] = []
    seen = set()  # the archive and the sessions folder may hold the same file
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("**/rollout-*.jsonl")):
            sid, who = None, "you"
            for item in _records(path, problems):
                kind = item.get("type")
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                if kind == "session_meta":
                    sid = payload.get("id") if isinstance(payload.get("id"), str) else sid
                    who = "script" if payload.get("source") == "exec" or payload.get("originator") == "codex_exec" else "you"
                    continue
                if kind != "event_msg" or sid is None:
                    continue
                moment = _moment(item.get("timestamp"))
                if moment is None:
                    continue
                if payload.get("type") == "task_started":
                    if ("p", sid, moment) not in seen:
                        seen.add(("p", sid, moment))
                        prompts.append(("codex", sid, who, moment))
                elif payload.get("type") == "token_count":
                    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                    last, total = info.get("last_token_usage"), info.get("total_token_usage")
                    if not isinstance(last, dict) or not isinstance(total, dict):
                        continue
                    key = ("c", sid, moment, _count(total.get("total_tokens")))
                    if key not in seen:
                        seen.add(key)
                        calls.append(("codex", sid, who, moment, _count(last.get("output_tokens"))))
    return calls, prompts


# ---- stretches and rows -------------------------------------------------------------------------------

def _local(moment: datetime, tz) -> datetime:
    return moment.astimezone(tz).replace(tzinfo=None) if tz is not None else moment.replace(tzinfo=None)


def work_rows(calls: List[Call], tz) -> List[dict]:
    """One row per stretch of calls of one session no more than GAP_S apart."""
    by_session: Dict[Tuple[str, str], List[Call]] = defaultdict(list)
    for call in calls:
        by_session[(call[0], call[1])].append(call)
    rows = []
    for (tool, sid), items in by_session.items():
        items.sort(key=lambda c: c[3])
        stretch = [items[0]]
        for prev, cur in zip(items, items[1:] + [None]):
            if cur is not None and (cur[3] - prev[3]).total_seconds() <= GAP_S:
                stretch.append(cur)
                continue
            first, last = stretch[0][3], stretch[-1][3]
            seconds = (last - first).total_seconds()
            if seconds > 0:
                start = _local(first, tz).replace(second=0, microsecond=0)
                end = _local(last, tz)
                end = end.replace(second=0, microsecond=0) + (timedelta(minutes=1) if end.second or end.microsecond else timedelta())
                if end <= start:
                    end = start + timedelta(minutes=1)
                rows.append({"start": start, "end": end, "tool": tool, "session": session_code(tool, sid),
                             "started_by": stretch[0][2], "minutes": round(seconds / 60, 2),
                             "calls": float(len(stretch)), "output_tokens": float(sum(c[4] for c in stretch))})
            if cur is not None:
                stretch = [cur]
    return rows


def prompt_rows(prompts: List[Prompt], tz) -> List[dict]:
    counts: Dict[tuple, int] = defaultdict(int)
    for tool, sid, who, moment in prompts:
        counts[(_local(moment, tz).replace(second=0, microsecond=0), tool, session_code(tool, sid), who)] += 1
    return [{"time": t, "tool": tool, "session": code, "started_by": who, "count": float(n)}
            for (t, tool, code, who), n in counts.items()]


def import_ai_logs(cfg: Config, claude_dir: Optional[Path] = None, codex_dirs: Optional[Iterable[Path]] = None,
                   days: Optional[int] = None, now: Optional[datetime] = None) -> Summary:
    claude_dir = Path(claude_dir) if claude_dir else CLAUDE_DIR
    codex_dirs = [Path(d) for d in codex_dirs] if codex_dirs else list(CODEX_DIRS)
    try:
        tz = cfg.tz
    except Exception:  # no tz database: keep UTC wall-clock times
        tz = None
    problems: List[str] = []
    c_calls, c_prompts = read_claude(claude_dir, problems)
    x_calls, x_prompts = read_codex(codex_dirs, problems)
    calls, prompts = c_calls + x_calls, c_prompts + x_prompts
    if not claude_dir.is_dir() and not any(d.is_dir() for d in codex_dirs):
        raise ValueError(f"found neither Claude Code logs ({claude_dir}) nor Codex logs ({', '.join(map(str, codex_dirs))})")
    if days is not None:
        since = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) - timedelta(days=days)
        calls = [c for c in calls if c[3] >= since]
        prompts = [p for p in prompts if p[3] >= since]

    summary = Summary(table="ai_work", source=f"{claude_dir}; {', '.join(map(str, codex_dirs))}")
    checked = []
    for i, row in enumerate(work_rows(calls, tz)):
        good = validate(TABLES["ai_work"], row, f"stretch {i + 1}", problems)
        if good:
            checked.append(good)
    pchecked = []
    for i, row in enumerate(prompt_rows(prompts, tz)):
        good = validate(TABLES["ai_prompts"], row, f"instruction minute {i + 1}", problems)
        if good:
            pchecked.append(good)

    # replace each tool's rows from the first one this import saw onward; older rows (logs since deleted) stay
    def dropper(rows: List[dict], column: str):
        first = {}
        for r in rows:
            first[r["tool"]] = min(first.get(r["tool"], r[column]), r[column])
        return lambda key, raw: key["tool"] in first and key[column] >= first[key["tool"]]

    path, total, notes = merge_write(cfg.data_dir, "ai_work", checked, drop=dropper(checked, "start"))
    _, ptotal, pnotes = merge_write(cfg.data_dir, "ai_prompts", pchecked, drop=dropper(pchecked, "time"))
    summary.path, summary.total, summary.imported = path, total, len(checked)
    summary.first, summary.last = span(checked, "start")
    summary.problems = problems
    mine = sum(r["minutes"] for r in checked if r["started_by"] == "you")
    summary.counts = {"claude_code_calls": len(c_calls), "codex_calls": len(x_calls),
                      "prompts": int(sum(r["count"] for r in pchecked))}
    summary.notes += notes + pnotes
    summary.notes.append(f"{len(c_calls)} Claude Code and {len(x_calls)} Codex model calls; "
                         f"{summary.counts['prompts']} instructions written to ai_prompts.csv ({ptotal} rows now)")
    summary.notes.append(f"{math.floor(mine / 60)}h {round(mine % 60)}m of AI work in sessions you started; "
                         "only times and counts were read, never what was said")
    return summary
