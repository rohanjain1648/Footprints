"""Download the public datasets and pin their SHA-256 on first use.

Datasets are attacker-produced, untrusted input: we only parse them as JSON and never execute anything.
The repo ships no data; run `python -m footprints data`.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CHECKSUMS = os.path.join(ROOT, "data", "checksums.json")

CW = "https://collusion.wiki/explorer/download/"
SOURCES = {
    "collusion_wiki": {
        f: CW + f
        for f in [
            "manifest.json.gz",
            "pages.jsonl.gz",
            "revisions.jsonl.gz",
            "events.jsonl.gz",
            "labels.jsonl.gz",
            "links.jsonl.gz",
        ]
    },
    "swarm_traces": {"redacted.jsonl.gz": "https://swarmtraces.org/data/final/redacted.jsonl.gz"},
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_for(source: str, name: str) -> str:
    return os.path.join(RAW, source, name)


def download(sources: list[str] | None = None, force: bool = False) -> None:
    sums = json.load(open(CHECKSUMS)) if os.path.exists(CHECKSUMS) else {}
    for source, files in SOURCES.items():
        if sources and source not in sources:
            continue
        os.makedirs(os.path.join(RAW, source), exist_ok=True)
        for name, url in files.items():
            dest = path_for(source, name)
            key = f"{source}/{name}"
            if force or not os.path.exists(dest):
                print(f"downloading {url}")
                req = urllib.request.Request(url, headers={"User-Agent": "footprints-research/0.1"})
                with urllib.request.urlopen(req, timeout=300) as r, open(dest + ".part", "wb") as f:
                    f.write(r.read())
                os.replace(dest + ".part", dest)
            digest = sha256(dest)
            if key in sums and sums[key] != digest:
                raise SystemExit(f"SHA-256 mismatch for {key}: the upstream file changed. "
                                 f"Delete data/checksums.json entry only if you mean to accept it.")
            sums.setdefault(key, digest)
            print(f"ok {key} {digest[:16]}")
    with open(CHECKSUMS, "w") as f:
        json.dump(sums, f, indent=2, sort_keys=True)
