"""One event schema for every source: wiki replays, cache sandboxes, real access logs.

The detector sees only these fields. It never sees content, page names or message text.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Iterator

ACTIONS = ("write", "read", "delete")


@dataclass
class Event:
    ts: float                 # unix seconds
    principal: str            # who acted (agent name, account, or ip prefix)
    action: str               # write | read | delete
    obj: str                  # object id (page key, cache path); an opaque id to the detector
    namespace: str            # resource the object lives in (wiki, cache namespace)
    nbytes: int = 0           # size after the write
    append: bool | None = None  # True if the write only added content
    run_id: str = ""
    meta: dict = field(default_factory=dict)  # source extras (ip16, labels); never used for scoring

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True)

    @staticmethod
    def from_dict(d: dict) -> "Event":
        return Event(**{k: d[k] for k in Event.__dataclass_fields__ if k in d})


def write_jsonl(events: Iterable[Event], path: str) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(e.to_json() + "\n")
            n += 1
    return n


def read_jsonl(path: str) -> Iterator[Event]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield Event.from_dict(json.loads(line))
