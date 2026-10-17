import copy
import json

import pytest

from blackbox import checks as C
from blackbox.agent import KEPT, KILLED, Investigation, RulesBackend, explain, verify
from blackbox.cli import EXPECT_ROOT
from blackbox.runlog import RunLog
from conftest import run

FAILURES = ["slip_grip", "slip_rushed", "collision", "wrong_object", "timeout"]


@pytest.mark.parametrize("name", FAILURES)
@pytest.mark.parametrize("seed", range(3))
def test_finds_the_true_root_cause(name, seed, control):
    log = run(name, seed)
    x = explain(log, RulesBackend(), [control])
    assert x["outcome"] == "failure"
    assert x["cause"]["root"] == EXPECT_ROOT[log.data["meta"]["truth"]["root"]]


def test_success_run_is_explained_as_success(control):
    x = explain(run("nominal", 1), RulesBackend(), [control])
    assert x["outcome"] == "success"
    assert x["cause"]["root"] is None
    assert all(h["status"] == KILLED for h in x["hypotheses"] if h["id"] != "goal.met")


def test_never_reads_ground_truth(control):
    log = run("collision", 2)
    poisoned = RunLog(copy.deepcopy(log.data))
    poisoned.data["meta"]["truth"] = {"outcome": "success", "cause": None, "root": "drop.low_grip_force"}
    a = explain(log, RulesBackend(), [control])
    b = explain(poisoned, RulesBackend(), [control])
    assert a["claims"] == b["claims"] and a["cause"] == b["cause"]


@pytest.mark.parametrize("name", FAILURES + ["nominal"])
def test_every_claim_rests_on_executed_evidence(name, control):
    x = explain(run(name, 0), RulesBackend(), [control])
    ev = {e["id"]: e for e in x["evidence"]}
    status_of = {}
    for h in x["hypotheses"]:
        for e in h["evidence"]:
            status_of.setdefault(e, set()).add(h["status"])
    assert x["claims"]
    for c in x["claims"]:
        assert c["cites"], c
        assert all(e in ev for e in c["cites"])
        if c["kind"] in ("finding", "cause"):
            assert all(KEPT in status_of[e] for e in c["cites"])
        if c["kind"] == "ruled_out":
            assert all(KILLED in status_of[e] for e in c["cites"])
    for e in ev.values():  # evidence windows lie inside the run
        if e["t0"] is not None:
            assert -0.5 <= e["t0"] <= e["t1"] <= run(name, 0).duration + 0.5


def test_hypotheses_declare_refutation_before_running():
    for chk in C.CHECKS.values():
        assert chk.statement and chk.test and chk.refute_if


def test_killed_hypotheses_are_kept_in_the_tree(control):
    x = explain(run("slip_grip", 0), RulesBackend(), [control])
    killed = {h["id"] for h in x["hypotheses"] if h["status"] == KILLED}
    assert {"collision", "wrong_object", "drop.aggressive_motion", "drop.worn_pads"} <= killed


def test_children_only_open_under_kept_parents(control):
    x = explain(run("wrong_object", 0), RulesBackend(), [control])
    status = {h["id"]: h["status"] for h in x["hypotheses"]}
    for h in x["hypotheses"]:
        if h.get("parent"):
            assert status[h["parent"]] == KEPT


def test_negative_control_demotes_unspecific_hypotheses():
    # Use another slip run as the "nominal" control: the slip check fires there too, so it is not specific.
    x = explain(run("slip_grip", 0), RulesBackend(), [run("slip_grip", 1)])
    drop = next(h for h in x["hypotheses"] if h["id"] == "drop")
    assert drop["status"] == "inconclusive"
    assert drop["control"]["specific"] is False


def test_kept_hypotheses_are_silent_on_the_nominal_control(control):
    x = explain(run("collision", 0), RulesBackend(), [control])
    kept = [h for h in x["hypotheses"] if h["status"] == KEPT and h["id"] != "goal.met"]
    assert kept and all(h["control"]["specific"] for h in kept)


def test_proof_bundle_reproduces_and_detects_tampering(tmp_path, control):
    from blackbox.sim import save_run
    log = run("slip_rushed", 0)
    folder = save_run(log, tmp_path / log.id)
    x = explain(RunLog.load(folder), RulesBackend(), [control])
    assert verify(x, RunLog.load(folder))["ok"]
    d = json.loads((folder / "run.json").read_text())
    d["series"]["gripper_current"] = [v * 3 for v in d["series"]["gripper_current"]]
    (folder / "run.json").write_text(json.dumps(d))
    r = verify(x, RunLog.load(folder))
    assert not r["ok"]
    assert any("hash" in p for p in r["problems"])


def test_trace_records_each_step(control):
    inv = Investigation(run("timeout", 0), RulesBackend(), [control])
    inv.run()
    steps = [t["step"] for t in inv.trace]
    for s in ("observe", "propose", "test", "refine", "control", "done"):
        assert s in steps
