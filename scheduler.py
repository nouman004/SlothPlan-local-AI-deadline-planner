"""Deterministic scheduling. No LLM here on purpose: models are bad at time math."""
from dataclasses import dataclass
from datetime import datetime, timedelta

SPRINT = {1: (20, 8), 2: (25, 7), 3: (30, 5), 4: (40, 5), 5: (50, 5)}  # energy -> (sprint, break)
PACE = {1: 1.25, 2: 1.1, 3: 1.0, 4: 1.0, 5: 1.0}  # tired people also work slower
SMALL_LEFTOVER = 10  # finish a task instead of breaking for <=10 min of leftovers


@dataclass
class Block:
    kind: str            # "work" | "rest" | "buffer"
    label: str
    start: datetime
    end: datetime
    work_min: int = 0
    breaks: int = 0      # short breaks folded inside a work block

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def _layout(subtasks, sprint, brk):
    """Walk the subtasks in order, cutting sprints. Returns [(kind, label, minutes)]."""
    segs, in_sprint = [], 0
    for i, s in enumerate(subtasks):
        remaining, last = s["minutes"], i == len(subtasks) - 1
        while remaining > 0:
            chunk = min(remaining, sprint - in_sprint)
            if 0 < remaining - chunk <= SMALL_LEFTOVER:
                chunk = remaining
            segs.append(("work", s["title"], chunk))
            remaining -= chunk
            in_sprint += chunk
            if in_sprint >= sprint and not (remaining == 0 and last):
                segs.append(("rest", "Short break", brk))
                in_sprint = 0
    return segs


def plan(subtasks, now, deadline, energy=3, buffer_pct=0.25, correction=1.0):
    """subtasks: [{"title": str, "minutes": int}] in the order they must be done."""
    if not subtasks:
        raise ValueError("no subtasks")
    k = correction * PACE[energy]
    subs = [dict(s, minutes=max(5, round(s["minutes"] * k))) for s in subtasks]
    work = sum(s["minutes"] for s in subs)
    buffer = round(work * buffer_pct)
    sprint, brk = SPRINT[energy]
    segs = _layout(subs, sprint, brk)
    break_min = sum(m for kind, _, m in segs if kind == "rest")
    needed = work + break_min + buffer
    available = int((deadline - now).total_seconds() // 60)
    slack = available - needed

    res = {"work_min": work, "buffer_min": buffer, "break_min": break_min,
           "needed_min": needed, "available_min": available, "slack_min": slack,
           "feasible": slack >= 0, "blocks": [], "start_by": None, "subtasks": subs}
    if slack < 0:
        return res

    start_by = now + timedelta(minutes=slack)
    res["start_by"] = start_by
    blocks = []
    if slack > 0:
        blocks.append(Block("rest", "Guilt-free rest", now, start_by))
    t, cur = start_by, None
    for i, (kind, label, m) in enumerate(segs):
        if kind == "work":
            if cur and cur.label == label:
                cur.end = t + timedelta(minutes=m)
                cur.work_min += m
            else:
                cur = Block("work", label, t, t + timedelta(minutes=m), work_min=m)
                blocks.append(cur)
        else:
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if cur and nxt and nxt[0] == "work" and nxt[1] == cur.label:
                cur.end = t + timedelta(minutes=m)   # break sits inside the task
                cur.breaks += 1
            else:
                blocks.append(Block("rest", "Short break", t, t + timedelta(minutes=m)))
                cur = None
        t += timedelta(minutes=m)
    blocks.append(Block("buffer", "Buffer (stuff WILL go wrong)", t, deadline))
    res["blocks"] = blocks
    return res