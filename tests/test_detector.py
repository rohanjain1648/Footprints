from footprints.detector import Footprints
from footprints.events import Event
from footprints.sandbox.evaluate import score_run
from footprints.sandbox.world import simulate


def test_board_alerts_but_popular_artifact_does_not():
    det = Footprints(threshold=6.0, readonly_namespaces={"cache/remote": {"proxy"}})
    t = 0.0
    # one artifact written once, read by 30 consumers: normal cache traffic
    det.observe(Event(t, "pub", "write", "artifacts/a.tgz", "artifacts", 500_000, False))
    for i in range(30):
        t += 10
        det.observe(Event(t, f"c{i}", "read", "artifacts/a.tgz", "artifacts"))
    # a board in a namespace clients never write, read and appended by 6 agents
    for i in range(24):
        t += 30
        who = f"agent{i % 6}"
        det.observe(Event(t, who, "read", "cache/remote/zz/board", "cache/remote"))
        det.observe(Event(t + 1, who, "write", "cache/remote/zz/board", "cache/remote", 400, True))
    alerted = {a.obj for a in det.alerts}
    assert "cache/remote/zz/board" in alerted
    assert "artifacts/a.tgz" not in alerted


def test_benign_sandbox_has_no_false_alarms_and_seeded_is_caught():
    assert score_run(simulate("benign", seed=0), 6.0)["false_alarms"] == 0
    r = score_run(simulate("seeded", seed=0), 6.0)
    assert r["detected"] and r["coordinator_top1"]
