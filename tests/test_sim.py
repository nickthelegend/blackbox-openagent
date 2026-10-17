import numpy as np
import pytest

from blackbox import kinematics as K
from blackbox.sim import SCENARIOS, simulate
from conftest import run


def kinds(log):
    return [e["kind"] for e in log.events]


def goal_met(log):
    return [e for e in log.events if e["kind"] == "goal_check"][-1]["data"]["met"]


def test_ik_fk_roundtrip():
    for r, deg in [(0.13, 20), (0.18, -40), (0.22, 60)]:
        x, y = r * np.cos(np.radians(deg)), r * np.sin(np.radians(deg))
        q, ok = K.ik(x, y, 0.04)
        assert ok
        assert np.allclose(K.fk(q), [x, y, 0.04], atol=1e-4)
    _, ok = K.ik(0.32, 0, 0.04)
    assert not ok


def test_deterministic_per_seed():
    a, b = simulate("slip_grip", 3, render=False), simulate("slip_grip", 3, render=False)
    assert a.data["series"] == b.data["series"]
    assert simulate("slip_grip", 4, render=False).data["series"] != a.data["series"]


@pytest.mark.parametrize("seed", range(3))
def test_nominal_succeeds(seed):
    log = run("nominal", seed)
    assert goal_met(log)
    assert "protective_stop" not in kinds(log) and "deadline" not in kinds(log)


@pytest.mark.parametrize("seed", range(3))
def test_slip_runs_drop_the_bottle(seed):
    for name in ("slip_grip", "slip_rushed"):
        log = run(name, seed)
        assert "grasp" in kinds(log)
        g, gc = log.s("gripper"), log.s("gripper_cmd")
        k = log.idx([e for e in log.events if e["kind"] == "grasp"][0]["t"])
        # fingers close past the object while still commanded closed
        assert ((g[k:] < 3) & (gc[k:] < 1)).any()
        assert not goal_met(log)


@pytest.mark.parametrize("seed", range(3))
def test_collision_trips_protective_stop(seed):
    log = run("collision", seed)
    assert "protective_stop" in kinds(log)
    assert "cereal_box" not in log.config["planner_objects"]


@pytest.mark.parametrize("seed", range(3))
def test_wrong_object_puts_the_lookalike_in_the_tray(seed):
    log = run("wrong_object", seed)
    contents = [e for e in log.events if e["kind"] == "goal_check"][-1]["data"]["contents"]
    assert contents == ["vitamin_bottle"]


@pytest.mark.parametrize("seed", range(3))
def test_timeout_regrasps_until_deadline(seed):
    log = run("timeout", seed)
    assert kinds(log).count("grasp_empty") >= 2
    assert "deadline" in kinds(log)


def test_every_scenario_records_ground_truth():
    for name in SCENARIOS:
        t = run(name, 0).data["meta"]["truth"]
        assert t["outcome"] == ("success" if name == "nominal" else "failure")
