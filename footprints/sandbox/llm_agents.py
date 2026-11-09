"""E3 with real LLM agents (to build next): same world, same event log, agents instead of scripts.

Plan:
  - Each agent gets tools: cache_get(path), cache_put(path, text), cache_list(prefix), submit(answer).
  - Tasks: some solvable, some impossible (the pressure behind the July 2026 swarm).
  - Conditions: benign (no hint), seeded (one agent's prompt says the cache can carry notes),
    emergent (no hint, impossible tasks), adaptive (agents told a monitor watches the cache).
  - Every tool call becomes an Event (see events.py); the harness also logs who-read-whose-write
    as ground truth in a separate file the detector never sees.
  - No network: the tools are in-process functions over a dict. Never give agents a shell.

Fill in `call_model` for whichever API the team has keys for, using one cheap tool-calling model
for every run. Keep temperature, model id and seed in the run config so runs can be replayed.
"""
from __future__ import annotations


def call_model(messages: list[dict], tools: list[dict]) -> dict:  # pragma: no cover
    raise NotImplementedError("wire this to your model API; see the module docstring")
