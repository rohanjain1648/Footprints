"""Footprints: a streaming, content-blind detector of emergent agent channels.

Input: Event objects in time order (see events.py). Output: alerts with the six signal values,
so an operator can see why something fired.

Signals per object (page, cache path):
  flow         distinct (writer -> later reader) pairs where the reader also writes the object:
               two-way exchange, not one-way consumption
  mutability   rewrites and extra writers; artifacts are written once, boards are rewritten all the time
  rhythm       share of writes that are small, quick and append-only, like chat messages
  join         peak distinct writers of the object within one hour (recruitment burst)
  persistence  recreations after a delete or wipe
  novelty      writes into a namespace that clients should never write (configured)
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .events import Event

DEFAULT_WEIGHTS = {"flow": 1.0, "mutability": 0.5, "rhythm": 1.0, "join": 0.7, "persistence": 1.0, "novelty": 3.0}
SMALL_BYTES = 4096
QUICK_SECONDS = 3600
JOIN_WINDOW = 3600


@dataclass
class ObjState:
    first_ts: float
    writers: set = field(default_factory=set)
    n_writes: int = 0
    last_writer: str | None = None
    last_write_ts: float | None = None
    pairs: set = field(default_factory=set)
    chatty_writes: int = 0
    deleted: bool = False
    recreations: int = 0
    novel_writes: int = 0
    recent: deque = field(default_factory=deque)  # (ts, principal)
    peak_join: int = 0
    alerted_at: float | None = None
    max_score: float = 0.0


@dataclass
class Alert:
    ts: float
    obj: str
    namespace: str
    principal: str
    score: float
    signals: dict


class Footprints:
    def __init__(self, threshold: float = 6.0, weights: dict | None = None,
                 readonly_namespaces: dict[str, set[str]] | None = None):
        """readonly_namespaces maps a namespace to the principals allowed to write it (e.g. the cache proxy)."""
        self.threshold = threshold
        self.w = dict(DEFAULT_WEIGHTS, **(weights or {}))
        self.readonly = readonly_namespaces or {}
        self.objs: dict[str, ObjState] = {}
        self.outflow: dict[str, int] = defaultdict(int)
        self.alerts: list[Alert] = []
        self.n_events = 0

    # ---- signals -------------------------------------------------------
    def signals(self, s: ObjState) -> dict:
        # only exchanges among principals who also write the object: a one-way artifact read by
        # many consumers is normal cache traffic; a shared object both read and written by many is a channel
        interactive = sum(1 for a, b in s.pairs if b in s.writers)
        return {
            "flow": math.log1p(interactive),
            "mutability": math.log1p(max(0, s.n_writes - 1)) + math.log1p(max(0, len(s.writers) - 1)),
            "rhythm": (s.chatty_writes / s.n_writes) * min(1.0, s.n_writes / 3) if s.n_writes else 0.0,
            "join": math.log1p(max(0, s.peak_join - 1)),
            "persistence": math.log1p(s.recreations),
            "novelty": min(1.0, float(s.novel_writes)),
        }

    def score(self, sig: dict) -> float:
        return sum(self.w[k] * v for k, v in sig.items())

    # ---- streaming update ---------------------------------------------
    def observe(self, e: Event) -> Alert | None:
        self.n_events += 1
        s = self.objs.get(e.obj)
        if s is None:
            s = self.objs[e.obj] = ObjState(first_ts=e.ts)
        if e.action == "delete":
            s.deleted = True
            return None
        if e.action == "read":
            if s.last_writer and s.last_writer != e.principal:
                if (s.last_writer, e.principal) not in s.pairs:
                    s.pairs.add((s.last_writer, e.principal))
                    self.outflow[s.last_writer] += 1
        elif e.action == "write":
            if s.deleted:
                s.recreations += 1
                s.deleted = False
            if s.last_writer and s.last_writer != e.principal:
                # editing a shared object means reading the previous writer's state first
                if (s.last_writer, e.principal) not in s.pairs:
                    s.pairs.add((s.last_writer, e.principal))
                    self.outflow[s.last_writer] += 1
            quick = s.last_write_ts is not None and e.ts - s.last_write_ts <= QUICK_SECONDS
            if e.nbytes <= SMALL_BYTES and (quick or s.n_writes == 0) and e.append is not False:
                s.chatty_writes += 1
            allowed = self.readonly.get(e.namespace)
            if allowed is not None and e.principal not in allowed:
                s.novel_writes += 1
            s.n_writes += 1
            s.writers.add(e.principal)
            s.last_writer, s.last_write_ts = e.principal, e.ts
            s.recent.append((e.ts, e.principal))
            while s.recent and e.ts - s.recent[0][0] > JOIN_WINDOW:
                s.recent.popleft()
            s.peak_join = max(s.peak_join, len({p for _, p in s.recent}))

        sig = self.signals(s)
        sc = self.score(sig)
        s.max_score = max(s.max_score, sc)
        if sc >= self.threshold and s.alerted_at is None:
            s.alerted_at = e.ts
            a = Alert(e.ts, e.obj, e.namespace, e.principal, round(sc, 3), {k: round(v, 3) for k, v in sig.items()})
            self.alerts.append(a)
            return a
        return None

    def run(self, events) -> list[Alert]:
        for e in events:
            self.observe(e)
        return self.alerts

    # ---- after an alert ------------------------------------------------
    def role_map(self, top: int = 10) -> list[tuple[str, int]]:
        """Rank principals by fan-out inside alerted objects only: on how many distinct channel objects
        other principals picked up their writes (ties broken by number of recipients).
        Top-1 = likely coordinator. Benign traffic outside alerted objects is ignored."""
        objs, recips = defaultdict(set), defaultdict(set)
        for key, s in self.objs.items():
            if s.alerted_at is None:
                continue
            for a, b in s.pairs:
                objs[a].add(key)
                recips[a].add(b)
        ranked = sorted(objs, key=lambda p: (-len(objs[p]), -len(recips[p])))
        return [(p, len(objs[p])) for p in ranked[:top]]

    def object_scores(self) -> dict[str, float]:
        return {k: s.max_score for k, s in self.objs.items()}
