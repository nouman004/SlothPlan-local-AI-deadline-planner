"""Run: python3 test_slothplan.py"""
from datetime import datetime, timedelta
from scheduler import plan, SPRINT

NOW = datetime(2026, 10, 21, 17, 0)
SUBS = [{"title": "Read spec", "minutes": 10}, {"title": "Dry run", "minutes": 45}, {"title": "Fix errors", "minutes": 30}]


def check(energy, hours):
    dl = NOW + timedelta(hours=hours)
    r = plan(SUBS, NOW, dl, energy=energy)
    if not r["feasible"]:
        assert r["slack_min"] < 0
        return r
    b = r["blocks"]
    assert b[0].start == NOW or r["slack_min"] == 0, "starts now"
    assert b[-1].end == dl, "ends at deadline"
    for x, y in zip(b, b[1:]):
        assert x.end == y.start, f"gap/overlap between {x.label} and {y.label}"
    assert sum(x.work_min for x in b) == r["work_min"], "work minutes preserved"
    assert b[-1].kind == "buffer" and b[-1].minutes >= 0
    assert all(x.minutes > 0 for x in b), "no zero-length blocks"
    labels = [x.label for x in b if x.kind == "work"]
    assert labels == [s["title"] for s in SUBS], f"order kept, no repeats: {labels}"
    return r


for e in range(1, 6):
    for h in (1, 2, 4, 8):
        check(e, h)
# infeasible case is honest
assert not plan(SUBS, NOW, NOW + timedelta(minutes=60), energy=3)["feasible"]
# lower energy never gives MORE rest
assert plan(SUBS, NOW, NOW + timedelta(hours=5), energy=1)["slack_min"] < plan(SUBS, NOW, NOW + timedelta(hours=5), energy=5)["slack_min"]
# correction factor scales work
assert plan(SUBS, NOW, NOW + timedelta(hours=5), correction=2.0)["work_min"] > plan(SUBS, NOW, NOW + timedelta(hours=5))["work_min"]
print("scheduler: all checks passed")
