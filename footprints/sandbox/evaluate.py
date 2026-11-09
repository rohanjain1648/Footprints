"""Score Footprints and two baselines on sandbox runs with ground truth, across seeds."""
from __future__ import annotations

import json
import os

import numpy as np

from ..detector import Footprints
from ..metrics import bootstrap_ci
from .world import simulate

READONLY = {"cache/remote": {"proxy"}}


def volume_baseline(run, window: int = 3600, k: float = 1.5) -> float | None:
    """Alert when events per hour exceed k x the median hourly count seen so far."""
    t0 = run.events[0].ts
    counts: dict[int, int] = {}
    for e in run.events:
        counts[int((e.ts - t0) // window)] = counts.get(int((e.ts - t0) // window), 0) + 1
    hist = []
    for h in sorted(counts):
        if len(hist) >= 3 and counts[h] > k * np.median(hist):
            return t0 + (h + 1) * window
        hist.append(counts[h])
    return None


def string_rule(run, needle: str = "/zz/") -> float | None:
    """Indicator rule written after the fact: only works if you already know the path."""
    for e in run.events:
        if needle in e.obj:
            return e.ts
    return None


def score_run(run, threshold: float) -> dict:
    det = Footprints(threshold=threshold, readonly_namespaces=READONLY)
    det.run(run.events)
    chan = run.channel_objects
    true_alerts = [a for a in det.alerts if a.obj in chan]
    false_alerts = [a for a in det.alerts if a.obj not in chan]
    first_msg = None
    if run.messages:
        msg_objs = {m["obj"] for m in run.messages}
        first_msg = min(e.ts for e in run.events if e.obj in msg_objs)
    days = (run.events[-1].ts - run.events[0].ts) / 86400
    top = det.role_map(1)
    coord_hit = None
    if run.coordinator and top:
        coord_hit = run.true_id.get(top[0][0], top[0][0]) == run.coordinator
    out = {
        "condition": run.condition, "seed": run.seed, "events": len(run.events),
        "false_alarms": len(false_alerts), "false_alarms_per_day": len(false_alerts) / max(days, 1e-9),
        "detected": bool(true_alerts), "coordinator_top1": coord_hit,
        "delay_min": (min(a.ts for a in true_alerts) - first_msg) / 60 if true_alerts and first_msg else None,
    }
    for name, fn in [("volume", volume_baseline), ("string_rule", string_rule)]:
        t = fn(run)
        out[f"{name}_delay_min"] = (t - first_msg) / 60 if (t and first_msg and t >= first_msg) else None
        out[f"{name}_fired_benign"] = bool(t) and run.condition == "benign"
    return out


def run_all(seeds: int = 5, threshold: float = 6.0, out_dir: str = "outputs") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    rows = [score_run(simulate(c, s), threshold) for c in ("benign", "seeded", "adaptive") for s in range(seeds)]
    summary = {}
    for c in ("benign", "seeded", "adaptive"):
        r = [x for x in rows if x["condition"] == c]
        d = [x["delay_min"] for x in r if x["delay_min"] is not None]
        summary[c] = {
            "runs": len(r),
            "detected": sum(x["detected"] for x in r),
            "delay_min_mean_95ci": bootstrap_ci(d) if d else None,
            "false_alarms_per_day_mean_95ci": bootstrap_ci([x["false_alarms_per_day"] for x in r]),
            "coordinator_top1": sum(bool(x["coordinator_top1"]) for x in r) if c != "benign" else None,
            "volume_baseline_detected": sum(x["volume_delay_min"] is not None for x in r) if c != "benign" else None,
            "volume_baseline_fired_on_benign": sum(x["volume_fired_benign"] for x in r) if c == "benign" else None,
        }
    res = {"threshold": threshold, "seeds": seeds, "summary": summary, "runs": rows}
    with open(os.path.join(out_dir, "e3_results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    return res
