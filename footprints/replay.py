"""E1: replay collusion.wiki in time order through Footprints and score it against the dataset's labels.

Labels (page_family) are used only for evaluation, never as detector input.
"""
from __future__ import annotations

import gzip
import json
import os
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from .data import path_for
from .detector import Footprints
from .events import Event
from .metrics import bootstrap_auroc, tpr_at_fpr

TASK_PREFIXES = ("datausa", "oecd", "ihme", "aihw", "nyc", "vermont", "mixed-task")
UNLABELLED = {"unknown", "off_store_unclassified", "source-or-unclassified"}
COORD = {"relay-coordination", "source-cache-url-list", "loop-chain-infrastructure"}


def _rows(name: str):
    with gzip.open(path_for("collusion_wiki", name), "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _ts(s) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        t = pd.to_datetime(s, utc=True, errors="coerce")
        return None if pd.isna(t) else t.timestamp()


def wiki_events() -> list[Event]:
    evs: list[Event] = []
    for r in _rows("revisions.jsonl.gz"):
        ts = _ts(r.get("time"))
        if ts is None:
            continue
        hunks = r.get("hunks") or []
        ops = [h.get("op") for h in hunks if isinstance(h, dict)]
        label = r.get("label") or f"ip16:{r.get('ip16')}"
        evs.append(Event(ts=ts, principal=label, action="write", obj=r["page_key"], namespace=r.get("wiki") or "",
                         nbytes=int(r.get("body_len") or 0), append=(bool(ops) and all(o == "insert" for o in ops)),
                         meta={"ip16": r.get("ip16")}))
    for r in _rows("events.jsonl.gz"):
        if r.get("event_type") == "delete" and r.get("page_key"):
            ts = _ts(r.get("time"))
            if ts is not None:
                evs.append(Event(ts=ts, principal=r.get("actor_label") or "admin", action="delete",
                                 obj=r["page_key"], namespace=r.get("wiki") or ""))
    evs.sort(key=lambda e: e.ts)
    return evs


def multiwriter_rule(evs: list[Event]) -> dict[str, float]:
    """Baseline from the pilot: alert when >=3 names and >=3 writer switches hit a page within 24 h."""
    seen: dict[str, list] = {}
    fired: dict[str, float] = {}
    for e in evs:
        if e.action != "write":
            continue
        lst = seen.setdefault(e.obj, [])
        lst.append((e.ts, e.principal))
        if e.obj in fired:
            continue
        labs = [p for t, p in lst if e.ts - t <= 86400]
        if len(set(labs)) >= 3 and sum(a != b for a, b in zip(labs, labs[1:])) >= 3:
            fired[e.obj] = e.ts
    return fired


def run(threshold: float = 6.0, tune_days: float = 10.0, out_dir: str = "outputs") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    pages = pd.DataFrame(list(_rows("pages.jsonl.gz")))
    fam = dict(zip(pages.page_key, pages.page_family))
    method = dict(zip(pages.page_key, pages.page_family_method))
    evs = wiki_events()
    t0 = evs[0].ts

    det = Footprints(threshold=threshold)
    det.run(evs)
    scores = det.object_scores()
    first_write = {}
    for e in evs:
        if e.action == "write":
            first_write.setdefault(e.obj, e.ts)

    # page-level evaluation, overall and on held-out days (pages first written after the tuning window)
    df = pd.DataFrame({"page_key": list(scores), "score": list(scores.values())})
    df["family"] = df.page_key.map(fam)
    df["method"] = df.page_key.map(method)
    df["first_ts"] = df.page_key.map(first_write)
    df = df[df.family.notna() & ~df.family.isin(UNLABELLED)]
    df["relay"] = (df.family == "relay-coordination").astype(int)
    df["heldout"] = df.first_ts > t0 + tune_days * 86400

    def evaluate(d: pd.DataFrame, y_col: str) -> dict:
        a, lo, hi = bootstrap_auroc(d[y_col], d.score)
        return {"n": int(len(d)), "positives": int(d[y_col].sum()), "auroc": round(a, 3),
                "auroc_95ci": [round(lo, 3), round(hi, 3)], "tpr_at_1pct_fpr": round(tpr_at_fpr(d[y_col], d.score, 0.01), 3),
                "tpr_at_5pct_fpr": round(tpr_at_fpr(d[y_col], d.score, 0.05), 3)}

    task_or_coord = df[df.family.isin(COORD) | df.family.str.startswith(TASK_PREFIXES)].copy()
    task_or_coord["coord"] = task_or_coord.family.isin(COORD).astype(int)
    no_timing_labels = df[df.method != "temporal-or-coordination-unresolved"]

    # threshold tuned on the tuning window only: keep FPR on non-relay pages <= 5%
    tune = df[~df.heldout]
    neg = tune[tune.relay == 0].score
    tuned_thr = float(np.quantile(neg, 0.95)) if len(neg) else threshold

    # alert timing
    alerts = pd.DataFrame([a.__dict__ for a in det.alerts])
    relay_pages = {k for k, v in fam.items() if v == "relay-coordination"}
    first_relay = min(first_write[k] for k in relay_pages if k in first_write)
    relay_alerts = alerts[alerts.obj.isin(relay_pages)] if len(alerts) else alerts
    rule = multiwriter_rule(evs)
    rule_relay = [t for k, t in rule.items() if k in relay_pages]

    res = {
        "events": len(evs), "pages_scored": len(scores), "threshold": threshold,
        "relay_vs_rest_all": evaluate(df, "relay"),
        "relay_vs_rest_heldout": evaluate(df[df.heldout], "relay"),
        "relay_vs_rest_without_timing_labels": evaluate(no_timing_labels, "relay"),
        "coordination_vs_task": evaluate(task_or_coord, "coord"),
        "tuned_threshold_on_first_days": round(tuned_thr, 3), "tune_days": tune_days,
        "first_relay_page_utc": pd.to_datetime(first_relay, unit="s", utc=True).isoformat(),
        "footprints": {
            "alerts": int(len(alerts)),
            "relay_pages_alerted": int(len(relay_alerts)), "relay_pages_total": len(relay_pages),
            "hours_to_first_relay_alert": round((relay_alerts.ts.min() - first_relay) / 3600, 2) if len(relay_alerts) else None,
            "alerts_per_day_median": float(alerts.assign(d=(alerts.ts // 86400)).groupby("d").size().median()) if len(alerts) else 0,
        },
        "baseline_multiwriter_rule": {
            "alerts": len(rule), "relay_pages_alerted": len(rule_relay),
            "hours_to_first_relay_alert": round((min(rule_relay) - first_relay) / 3600, 2) if rule_relay else None,
        },
        "coordinator_candidates_by_outflow": det.role_map(5),
        "alert_families": Counter(fam.get(k) for k in alerts.obj).most_common(8) if len(alerts) else [],
    }
    if len(alerts):
        alerts["utc"] = pd.to_datetime(alerts.ts, unit="s", utc=True)
        alerts["family"] = alerts.obj.map(fam)
        alerts.to_csv(os.path.join(out_dir, "e1_alerts.csv"), index=False)
    with open(os.path.join(out_dir, "e1_results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    return res
