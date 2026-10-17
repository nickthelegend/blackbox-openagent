"""A simulated pick-and-place arm that records BLACKBOX run logs.

The controller follows the same fetch sequence as REACH's job runner
(`../reach-amazon/reach/jobs.py`): hover over the item with the gripper open,
descend, close, lift, carry, then put it down and go home. Joint motion is
streamed at 25 Hz with per-joint speed caps, as in `reach/arm.py`, with an
acceleration limit added so the log has realistic accelerations.

Physics is deliberately small but honest about the things the explainer checks:
  * servos track the commanded pose with lag; a blocked joint stops while the
    command keeps going, so tracking error and motor current rise together
  * the gripper stops closing when it meets an object; it holds while
    grip force >= m (g + a) / (2 mu), and otherwise the object slips, falls,
    and the fingers close on nothing
  * perception labels look-alike objects ambiguously from far away and
    confidently up close

Scenarios: nominal, slip_grip, slip_rushed, collision, wrong_object, timeout.
Each run's ground truth goes in meta.truth, which the explainer never reads.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import kinematics as K
from .runlog import FORMAT, RunLog

DT = 1 / K.RATE
CAM_EVERY = 5  # camera at 5 Hz
G = 9.81
FORCE_PER_EFFORT = 9.6  # N of grip force at effort 1.0
AMP_PER_EFFORT = 1.0  # gripper motor current at effort 1.0, holding
STOP_ERR = 6.0  # deg of tracking error that trips a protective stop
TABLE_Z = 0.0

SCENARIOS = ["nominal", "slip_grip", "slip_rushed", "collision", "wrong_object", "timeout"]


class Abort(Exception):
    def __init__(self, kind: str, data: dict | None = None):
        super().__init__(kind)
        self.kind, self.data = kind, data or {}


@dataclass
class Obj:
    tid: str
    label: str
    color: str
    size: tuple[float, float, float]  # w, d, h (m)
    pos: np.ndarray  # centre
    mass: float
    mu: float = 0.5
    shape: str = "box"  # box | cylinder
    lookalike: str | None = None  # label perception confuses it with from far away
    known: bool = True  # in the planner's scene map
    held: bool = False
    vz: float = 0.0

    def contains(self, p: np.ndarray, pad: float = 0.0) -> bool:
        w, d, h = self.size
        return (abs(p[0] - self.pos[0]) <= w / 2 + pad and abs(p[1] - self.pos[1]) <= d / 2 + pad
                and abs(p[2] - self.pos[2]) <= h / 2 + pad)


CATALOG = {
    # label: (colour, size, mass kg, shape, friction)
    "pill_bottle": ("#e8e4da", (0.040, 0.040, 0.075), 0.06, "cylinder", 0.55),
    "vitamin_bottle": ("#e6e1d4", (0.040, 0.040, 0.078), 0.07, "cylinder", 0.55),
    "water_bottle": ("#7fb4d6", (0.055, 0.055, 0.110), 0.45, "cylinder", 0.50),
    "cup": ("#d9573b", (0.060, 0.060, 0.070), 0.09, "cylinder", 0.55),
    "sponge": ("#e2c13a", (0.070, 0.045, 0.030), 0.03, "box", 0.80),
    "cereal_box": ("#3f7f4e", (0.050, 0.120, 0.190), 0.38, "box", 0.45),
}


@dataclass
class Setup:
    name: str
    seed: int
    goal: dict
    objects: list[Obj]
    target_tid: str  # the object perception will pick (may be the wrong one)
    config: dict
    records: list[dict]
    truth: dict
    zones: dict = field(default_factory=lambda: {"tray": {"center": [0.045, -0.185], "size": [0.10, 0.08]}})


def _polar(r: float, deg: float, z: float) -> np.ndarray:
    a = math.radians(deg)
    return np.array([r * math.cos(a), r * math.sin(a), z])


def _obj(tid: str, label: str, r: float, deg: float, **kw) -> Obj:
    color, size, mass, shape, mu = CATALOG[label]
    return Obj(tid, label, color, size, _polar(r, deg, size[2] / 2), mass, mu, shape, **kw)


BASE_CONFIG = {
    "grip_effort": 0.6, "grip_effort_default": 0.6, "speed_scale": 1.0, "max_carry_accel": 2.5,
    "carry_clearance": 0.05, "protective_stop_deg": STOP_ERR,
    "planner_scene_saved": "2026-10-14T09:12:00Z",
}
BASE_RECORDS = [
    {"source": "maintenance", "date": "2026-09-30", "item": "gripper finger pads", "text": "Pads replaced. 214 grasp cycles since (rated 1500).", "cycles": 214, "rated": 1500},
    {"source": "maintenance", "date": "2026-10-02", "item": "shoulder servo", "text": "Encoder recalibrated, error < 0.3 deg.", "encoder_err_deg": 0.3},
    {"source": "changelog", "date": "2026-10-01", "item": "controller", "text": "v2.2: regrasp after an empty grasp, until the deadline."},
]


def scenario(name: str, seed: int = 0) -> Setup:
    """Build one scenario. The seed jitters positions and parameters so no two runs are identical."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; choose from {', '.join(SCENARIOS)}")
    rnd = random.Random(f"{name}:{seed}")
    j = lambda a: rnd.uniform(-a, a)  # noqa: E731
    ids = [f"obj{n}" for n in rnd.sample(range(1, 10), 5)]
    cfg = dict(BASE_CONFIG)
    recs = [dict(r) for r in BASE_RECORDS]
    deadline = 25.0
    goal_label = "pill_bottle"

    if name == "nominal":
        tgt = _obj(ids[0], "pill_bottle", 0.175 + j(0.02), 34 + j(6))
        objs = [tgt, _obj(ids[1], "cup", 0.16 + j(0.02), 80 + j(4)), _obj(ids[2], "sponge", 0.21 + j(0.01), -10 + j(3))]
        truth = {"outcome": "success", "cause": None, "root": None}
        pick = tgt
    elif name in ("slip_grip", "slip_rushed"):
        goal_label = "water_bottle"
        tgt = _obj(ids[0], "water_bottle", 0.17 + j(0.015), 34 + j(6))
        tgt.mass *= 1 + j(0.08)
        objs = [tgt, _obj(ids[1], "cup", 0.165 + j(0.02), 80 + j(4)), _obj(ids[2], "sponge", 0.21 + j(0.01), -10 + j(3))]
        if name == "slip_grip":
            cfg["grip_effort"] = round(0.30 + j(0.03), 2)
            recs.append({"source": "changelog", "date": "2026-10-09", "item": "config",
                         "text": f"grip_effort 0.6 -> {cfg['grip_effort']} so the gripper stops crushing paper cups (PR #212).",
                         "key": "grip_effort", "old": 0.6, "new": cfg["grip_effort"]})
            truth = {"outcome": "failure", "cause": "drop", "root": "low_grip_force"}
        else:
            cfg["speed_scale"] = round(2.4 + j(0.15), 2)
            recs.append({"source": "changelog", "date": "2026-10-11", "item": "config",
                         "text": f"speed_scale 1.0 -> {cfg['speed_scale']} to hit the 8 s cycle-time target.",
                         "key": "speed_scale", "old": 1.0, "new": cfg["speed_scale"]})
            truth = {"outcome": "failure", "cause": "drop", "root": "aggressive_motion"}
        pick = tgt
    elif name == "collision":
        tgt = _obj(ids[0], "pill_bottle", 0.18 + j(0.015), 40 + j(6))
        box = _obj(ids[1], "cereal_box", 0.195 + j(0.01), -32 + j(4), known=False)
        objs = [tgt, box, _obj(ids[2], "cup", 0.15 + j(0.02), 80 + j(4))]
        recs.append({"source": "changelog", "date": "2026-10-15", "item": "workcell",
                     "text": "Cereal box added to the bench for the pantry demo. Planner scene map not re-captured."})
        truth = {"outcome": "failure", "cause": "collision", "root": "unmodeled_obstacle"}
        pick = tgt
    elif name == "wrong_object":
        tgt = _obj(ids[0], "pill_bottle", 0.20 + j(0.012), 62 + j(5), lookalike="vitamin_bottle")
        decoy = _obj(ids[1], "vitamin_bottle", 0.165 + j(0.015), 28 + j(6), lookalike="pill_bottle")
        objs = [tgt, decoy, _obj(ids[2], "sponge", 0.21 + j(0.01), -10 + j(3))]
        truth = {"outcome": "failure", "cause": "wrong_object", "root": "perception_confusion"}
        pick = decoy
    else:  # timeout
        tgt = _obj(ids[0], "pill_bottle", 0.305 + j(0.02), 30 + j(10))
        objs = [tgt, _obj(ids[1], "cup", 0.16 + j(0.02), 80 + j(4)), _obj(ids[2], "sponge", 0.2 + j(0.01), 0 + j(4))]
        deadline = 18.0
        truth = {"outcome": "failure", "cause": "timeout", "root": "unreachable"}
        pick = tgt

    cfg["planner_objects"] = sorted(o.label for o in objs if o.known)
    goal = {"text": f"Put the {goal_label.replace('_', ' ')} in the tray", "target": goal_label,
            "destination": "tray", "deadline_s": deadline}
    return Setup(name, seed, goal, objs, pick.tid, cfg, recs, truth)


class Sim:
    def __init__(self, setup: Setup, render: bool = True, seed: int | None = None):
        self.setup = setup
        self.cfg = setup.config
        self.rng = np.random.default_rng(seed if seed is not None else setup.seed * 7919 + SCENARIOS.index(setup.name))
        self.objs = {o.tid: o for o in setup.objects}
        self.q = K.HOME.copy()
        self.qc = K.HOME.copy()
        self.v = np.zeros(6)
        self.g = float(K.HOME[5])
        self.gc = float(K.HOME[5])
        self.effort = 0.3
        self.held: Obj | None = None
        self.grasp_offset = np.zeros(3)
        self.slip_t = 0.0
        self.blocked = False
        self.t = 0.0
        self.n = 0
        self.rows: dict[str, list] = {k: [] for k in ("t", "q", "q_cmd", "current", "gripper", "gripper_cmd", "gripper_current", "tcp")}
        self.events: list[dict] = []
        self.tracks: dict[str, dict] = {o.tid: {"size": list(o.size), "color": o.color, "shape": o.shape, "xyz": [], "labels": []} for o in setup.objects}
        self.frames: list[tuple[float, bytes]] = []
        self.render = render
        self.tcp_hist: list[np.ndarray] = []
        self.approach: str | None = None  # object being reached for: exempt from collision checks
        self.stopped = False
        self.slipped = False  # fingers closed past a slipping object: no re-grab until they open

    # ---- recording --------------------------------------------------------------------------
    def event(self, kind: str, msg: str, **data) -> None:
        self.events.append({"t": round(self.t, 3), "kind": kind, "msg": msg, "data": data})

    def stage(self, msg: str) -> None:
        self.event("stage", msg)

    def _labels(self, o: Obj, tcp: np.ndarray, overhead: bool = False) -> list:
        """Label from the camera: the wrist view resolves look-alikes, the overhead view cannot."""
        near = not overhead and math.hypot(tcp[0] - o.pos[0], tcp[1] - o.pos[1]) < 0.07 and tcp[2] < o.pos[2] + o.size[2] / 2 + 0.11
        if o.lookalike and not near:
            # From the overhead view the two bottles differ only by a cap stripe.
            far_conf = {"pill_bottle": 0.49, "vitamin_bottle": 0.47}
            if o.label == "vitamin_bottle":
                top, tc, ru, rc = "pill_bottle", 0.52, "vitamin_bottle", 0.46
            else:
                top, tc, ru, rc = "pill_bottle", far_conf["pill_bottle"], "vitamin_bottle", far_conf["vitamin_bottle"]
            jit = float(self.rng.normal(0, 0.004))
            return [top, round(tc + jit, 3), ru, round(rc - jit, 3)]
        conf = 0.93 if near or not o.lookalike else 0.9
        return [o.label, round(conf + float(self.rng.normal(0, 0.01)), 3), o.lookalike or "unknown", round(0.04 + abs(float(self.rng.normal(0, 0.01))), 3)]

    def _record(self, cur: np.ndarray, tcp: np.ndarray) -> None:
        r = self.rows
        r["t"].append(round(self.t, 3))
        r["q"].append([round(x, 2) for x in self.q])
        r["q_cmd"].append([round(x, 2) for x in self.qc])
        r["current"].append([round(x, 3) for x in cur])
        r["gripper"].append(round(self.g, 2))
        r["gripper_cmd"].append(round(self.gc, 2))
        r["gripper_current"].append(round(self.gcur, 3))
        r["tcp"].append([round(x, 4) for x in tcp])
        if self.n % CAM_EVERY == 0:
            for o in self.objs.values():
                p = o.pos + self.rng.normal(0, 0.0015, 3)
                tr = self.tracks[o.tid]
                tr["xyz"].append([round(self.t, 3)] + [round(float(x), 4) for x in p])
                tr["labels"].append([round(self.t, 3)] + self._labels(o, tcp))
            if self.render:
                from .render import render_frame
                self.frames.append((round(self.t, 3), render_frame(self, tcp)))

    # ---- physics ------------------------------------------------------------------------------
    def tick(self) -> None:
        prev_q = self.q.copy()
        if not self.blocked:
            self.q = self.q + (self.qc - self.q) * 0.62 + self.rng.normal(0, 0.03, 6) * np.array([1, 1, 1, 1, 1, 0])
        else:
            self.q = self.q + self.rng.normal(0, 0.02, 6) * np.array([1, 1, 1, 1, 1, 0])
        self.q[5] = self.g
        tcp = K.fk(self.q)
        if not self.blocked and self._collides():
            self.blocked = True
            self.q = prev_q
            self.q[5] = self.g
            tcp = K.fk(self.q)

        # gripper
        step = 150 * DT
        if self.held is not None:
            w_open = K.width_to_opening(self.held.size[0])
            if self.gc > w_open + 1:  # opening: release
                self.g = min(self.gc, self.g + step)
                if self.g > w_open + 2:
                    self._release()
            else:
                self.g = w_open
        else:
            target = self.gc
            if target < self.g:
                cand = self._between_fingers(tcp)
                if cand is not None and not self.slipped and self.g - step <= K.width_to_opening(cand.size[0]):
                    self.g = K.width_to_opening(cand.size[0])
                    self._grab(cand, tcp)
                else:
                    self.g = max(target, self.g - step)
            else:
                self.g = min(target, self.g + step)
                self.slipped = False
        self.q[5] = self.g

        # acceleration of the fingertip (for the slip model), from the measured pose
        self.tcp_hist.append(tcp)
        acc = 0.0
        if len(self.tcp_hist) >= 3:
            a, b, c = self.tcp_hist[-3:]
            acc = float(np.linalg.norm((c - 2 * b + a) / DT ** 2))

        # held object: follows the fingers, or slips
        if self.held is not None:
            o = self.held
            o.pos = tcp + self.grasp_offset
            force = self.effort * FORCE_PER_EFFORT
            need = o.mass * (G + acc) / (2 * o.mu)
            lifted = o.pos[2] - o.size[2] / 2 > TABLE_Z + 0.003  # the table carries it until it is lifted
            self.slip_t = self.slip_t + DT if (force < need and lifted) else max(0.0, self.slip_t - DT)
            if self.slip_t > 0.08:
                self._drop()
        for o in self.objs.values():
            if not o.held and o.pos[2] > o.size[2] / 2 + 1e-4:
                o.vz -= G * DT
                o.pos[2] = max(o.size[2] / 2, o.pos[2] + o.vz * DT)
                if o.pos[2] <= o.size[2] / 2 + 1e-4:
                    o.vz = 0.0

        # currents: gravity + acceleration + tracking-error load per joint motor
        err = np.abs(self.qc - self.q)[:5]
        vel = (self.q - prev_q)[:5] / DT
        load = np.array([0.05, 0.55, 0.35, 0.12, 0.03])
        held_m = self.held.mass if self.held else 0.0
        cur = (0.12 + load * (1 + 1.6 * held_m) + 0.0025 * np.abs(vel) + 0.22 * err + self.rng.normal(0, 0.012, 5))
        cur = np.clip(cur, 0, 2.6)
        if self.held is not None:
            self.gcur = self.effort * AMP_PER_EFFORT + float(self.rng.normal(0, 0.01))
        else:
            moving = abs(self.g - self.gc) > 0.5
            self.gcur = (0.09 if not moving else 0.18) + float(self.rng.normal(0, 0.006))

        self._record(cur, tcp)
        self.t += DT
        self.n += 1

        if np.max(err) > self.cfg["protective_stop_deg"] and not self.stopped:
            jn = int(np.argmax(err))
            self.stopped = True
            raise Abort("protective_stop", {"joint": K.JOINTS[jn], "error_deg": round(float(err[jn]), 2)})
        if self.t >= self.setup.goal["deadline_s"] and not self.stopped:
            self.stopped = True
            raise Abort("deadline", {"deadline_s": self.setup.goal["deadline_s"]})

    def _arm_points(self) -> list[np.ndarray]:
        c = K.chain(self.q)
        pts = [c["wrist"], c["tip"], (c["elbow"] + c["wrist"]) / 2, (c["wrist"] + c["tip"]) / 2]
        if self.held is not None:
            h = self.held
            for dx in (-1, 1):
                for dy in (-1, 1):
                    pts.append(h.pos + np.array([dx * h.size[0] / 2, dy * h.size[1] / 2, -h.size[2] / 2]))
        return pts

    def _collides(self) -> bool:
        for o in self.objs.values():
            if o.held or o.tid == self.approach:
                continue
            if any(o.contains(p, 0.005) for p in self._arm_points()):
                self.event_contact = o.tid
                return True
        return False

    def _between_fingers(self, tcp: np.ndarray) -> Obj | None:
        for o in self.objs.values():
            if o.held:
                continue
            if math.hypot(tcp[0] - o.pos[0], tcp[1] - o.pos[1]) < 0.015 and abs(tcp[2] - o.pos[2]) < o.size[2] / 2:
                return o
        return None

    def _grab(self, o: Obj, tcp: np.ndarray) -> None:
        o.held = True
        self.held = o
        self.grasp_offset = o.pos - tcp
        self.slip_t = 0.0

    def _release(self) -> None:
        if self.held is not None:
            self.approach = self.held.tid  # the fingers start out around it: not a collision
            self.held.held = False
            self.held.vz = 0.0
            self.held = None

    def _drop(self) -> None:
        self._release()
        self.slipped = True

    # ---- motion ---------------------------------------------------------------------------------
    def move(self, target, speed: float = 1.0) -> None:
        target = np.clip(np.asarray(target, float), K.LO, K.HI)
        target[5] = self.gc
        vmax = K.VMAX * speed * self.cfg["speed_scale"]
        amax = vmax * 3.5 * self.cfg["speed_scale"]  # same path in less time: acceleration grows with speed squared
        for _ in range(int(30 / DT)):
            err = target - self.qc
            err[5] = 0
            if np.all(np.abs(err) < 0.08):
                self.qc[:5] = target[:5]
                self.v[:] = 0
                break
            # decelerate in time, never overshoot in one tick
            vstar = np.sign(err) * np.minimum(np.minimum(vmax, np.sqrt(2 * amax * np.abs(err))), np.abs(err) / DT)
            self.v = self.v + np.clip(vstar - self.v, -amax * DT, amax * DT)
            self.v[5] = 0
            self.qc = self.qc + self.v * DT
            self.tick()
        for _ in range(4):  # settle
            self.tick()

    def grip(self, opening: float, effort: float | None = None) -> None:
        if effort is not None:
            self.effort = effort
        self.gc = float(opening)
        self.qc[5] = self.gc
        last = None
        for _ in range(int(1.2 / DT)):
            self.tick()
            if last is not None and abs(self.g - last) < 0.05:
                break
            last = self.g
        for _ in range(3):
            self.tick()

    def wait(self, s: float) -> None:
        for _ in range(int(s / DT)):
            self.tick()

    # ---- the task ---------------------------------------------------------------------------------
    def perceive(self) -> dict:
        """Pick the track whose label best matches the goal target, as the overhead camera sees it now."""
        tcp = K.fk(self.q)
        # The scenario decides which object perception lands on (normally the right one).
        o = self.objs[self.setup.target_tid]
        top, conf, ru, rconf = self._labels(o, tcp, overhead=True)
        self.event("perceive", f"found {top.replace('_', ' ')} ({conf:.2f})", track=o.tid, label=top, conf=conf,
                   runner_up=ru, runner_conf=rconf, xyz=[round(float(x), 4) for x in o.pos])
        return {"obj": o}

    def run(self) -> RunLog:
        s, cfg = self.setup, self.cfg
        dest = s.zones[s.goal["destination"]]
        name = s.goal["target"].replace("_", " ")
        open_w = float(K.HI[5])
        try:
            self.wait(0.4)
            self.stage(f"looking for the {name}")
            self.wait(0.3)
            o = self.perceive()["obj"]
            known_h = max(ob.size[2] for ob in self.objs.values() if ob.label in cfg["planner_objects"])
            carry_z = known_h + cfg["carry_clearance"] + 0.02
            grasp = o.pos.copy()
            qg, ok = K.ik(*grasp, gripper=open_w)
            self.event("plan", f"grasp at {math.hypot(grasp[0], grasp[1]) * 100:.1f} cm, carry height {carry_z * 100:.0f} cm",
                       track=o.tid, grasp_xyz=[round(float(x), 4) for x in grasp], reachable=ok, carry_z=round(carry_z, 3))
            attempts = 0
            while True:
                attempts += 1
                self.approach = o.tid
                self.stage(f"reaching for the {name}" if attempts == 1 else f"regrasp attempt {attempts}")
                qh, _ = K.ik(grasp[0], grasp[1], max(carry_z, grasp[2] + 0.08), gripper=open_w)
                self.grip(open_w, 0.3)
                self.move(qh)
                self.move(qg, speed=0.5)
                self.stage(f"picking up the {name}")
                self.grip(0, cfg["grip_effort"])
                if self.held is None:
                    self.event("grasp_empty", f"gripper closed to {self.g:.1f} deg with nothing in it", opening=round(float(self.g), 2), attempt=attempts)
                    self.move(qh, speed=0.6)
                    continue  # v2.2 controller: regrasp until it holds something or the deadline stops it
                self.event("grasp", f"holding at {self.g:.1f} deg opening", opening=round(float(self.g), 2), track=self.held.tid)
                break
            self.move(qh, speed=0.6)
            self.approach = None
            self.stage(f"carrying it to the {s.goal['destination']}")
            cx, cy = dest["center"]
            qph, _ = K.ik(cx, cy, carry_z, gripper=0)
            self.move(qph)
            self.stage("placing it")
            hz = (self.held.size[2] / 2 + 0.012) if self.held else 0.05
            qp, _ = K.ik(cx, cy, hz, gripper=0)
            self.move(qp, speed=0.5)
            self.stage("letting go")
            self.grip(open_w, 0.3)
            self.move(qph, speed=0.7)
            self.stage("going home")
            self.move(K.HOME)
            self.wait(0.3)
        except Abort as a:
            self.event(a.kind, "protective stop: joint tracking error too high" if a.kind == "protective_stop" else "deadline reached, task abandoned", **a.data)
            self.stopped = True
            self.v[:] = 0
            self.qc = self.q.copy()
            hold = 0.8
            for _ in range(int(hold / DT)):
                try:
                    self.tick()
                except Abort:
                    pass
        self._goal_check()
        return self.to_log()

    def _goal_check(self) -> None:
        z = self.setup.zones[self.setup.goal["destination"]]
        (cx, cy), (w, d) = z["center"], z["size"]
        inside = [o.label for o in self.objs.values() if abs(o.pos[0] - cx) <= w / 2 and abs(o.pos[1] - cy) <= d / 2]
        met = self.setup.goal["target"] in inside
        self.event("goal_check", "goal met" if met else "goal not met", met=met, contents=inside)
        self.stage("done")

    def to_log(self) -> RunLog:
        s = self.setup
        data = {
            "format": FORMAT,
            "id": f"{s.name}-{s.seed:03d}",
            "robot": {"model": "thenar-so101-sim", "joints": K.JOINTS, "lo": K.LO.tolist(), "hi": K.HI.tolist(),
                      "links_m": {"base_h": K.BASE_H, "upper_arm": K.L1, "forearm": K.L2, "hand": K.L3},
                      "grip_width_max_m": K.GRIP_W_MAX, "gripper_force_per_amp_n": FORCE_PER_EFFORT / AMP_PER_EFFORT, "vmax_deg_s": K.VMAX.tolist()},
            "goal": s.goal,
            "rate_hz": K.RATE,
            "series": self.rows,
            "camera": {"rate_hz": K.RATE / CAM_EVERY, "frames": [{"t": t, "file": f"frames/{i:04d}.jpg"} for i, (t, _) in enumerate(self.frames)],
                       "name": "cam0 (overhead, fixed)", "intrinsics": _intrinsics()},
            "tracks": self.tracks,
            "zones": s.zones,
            "events": self.events,
            "config": s.config,
            "objects_db": {k: {"mass_kg": v[2], "mu": v[4]} for k, v in CATALOG.items()},
            "records": s.records,
            "meta": {"simulated": True, "seed": s.seed, "scenario": s.name, "truth": s.truth},
        }
        if [e for e in self.events if e["kind"] == "goal_check"][-1]["data"]["met"]:
            data["meta"]["truth"] = {"outcome": "success", "cause": None, "root": None}  # the fault did not bite this time
        log = RunLog(data)
        log._frames = self.frames
        return log


def _intrinsics() -> dict:
    from .render import CAM, FOCAL, H, LOOK, W
    return {"pos": CAM.tolist(), "look": LOOK.tolist(), "up": [0, 0, 1], "focal_px": FOCAL, "w": W, "h": H}


def simulate(name: str, seed: int = 0, render: bool = True) -> RunLog:
    return Sim(scenario(name, seed), render=render).run()


def save_run(log: RunLog, folder: Path) -> Path:
    folder = Path(folder)
    log.save(folder)
    frames = getattr(log, "_frames", [])
    if frames:
        (folder / "frames").mkdir(exist_ok=True)
        for i, (_, jpg) in enumerate(frames):
            (folder / "frames" / f"{i:04d}.jpg").write_bytes(jpg)
    return folder
