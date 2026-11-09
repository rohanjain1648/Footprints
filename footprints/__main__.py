"""CLI: python -m footprints {data,replay,sandbox,all}"""
from __future__ import annotations

import argparse
import json


def main() -> None:
    p = argparse.ArgumentParser(prog="footprints")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("data", help="download datasets and pin SHA-256")
    d.add_argument("--source", action="append", choices=["collusion_wiki", "swarm_traces"])
    r = sub.add_parser("replay", help="E1: replay collusion.wiki")
    r.add_argument("--threshold", type=float, default=6.0)
    r.add_argument("--tune-days", type=float, default=10.0)
    s = sub.add_parser("sandbox", help="E3 scripted: benign, seeded, adaptive runs")
    s.add_argument("--seeds", type=int, default=5)
    s.add_argument("--threshold", type=float, default=6.0)
    sub.add_parser("all", help="data + replay + sandbox")
    a = p.parse_args()

    if a.cmd in ("data", "all"):
        from .data import download
        download(getattr(a, "source", None))
    if a.cmd in ("replay", "all"):
        from .replay import run
        res = run(threshold=getattr(a, "threshold", 6.0), tune_days=getattr(a, "tune_days", 10.0))
        print(json.dumps(res, indent=2, default=str))
    if a.cmd in ("sandbox", "all"):
        from .sandbox.evaluate import run_all
        res = run_all(seeds=getattr(a, "seeds", 5), threshold=getattr(a, "threshold", 6.0))
        print(json.dumps(res["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()
