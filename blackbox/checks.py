"""The hypothesis library: every hypothesis BLACKBOX can hold is a check that runs on the log.

A check declares, before it runs, what it measures and what result would refute it.
Running it returns a status (supported / refuted / inconclusive), the numbers it
measured, and evidence: spans of the log (channel + time window) or documents
(config, records, goal) that the numbers came from. The agent may only state what a
check returned, so every sentence of a verdict can be traced back to a span of the log.
"""

from __future__ import annotations

import hashlib
import inspect
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .runlog import RunLog

SUPPORTED, REFUTED, INCONCLUSIVE = "supported", "refuted", "inconclusive"


# ---- evidence and derived signals ------------------------------------------------------------

class Ctx:
    """Derived signals over one log, plus the evidence registry the checks write into."""

    def __init__(self, log: RunLog):
        self.log = log
        self.t = log.t
        self.dt = float(np.median(np.diff(self.t)))
        self.joints = log.data["robot"]["joints"]
        self.q, self.qc = log.s("q"), log.s("q_cmd")
        self.err = np.abs(self.qc - self.q)[:, :5]
        self.cur = log.s("current")
        self.g, self.gc, self.gcur = log.s("gripper"), log.s("gripper_cmd"), log.s("gripper_current")
        self.tcp = log.s("tcp")
        d2 = np.zeros_like(self.tcp)
        d2[1:-1] = (self.tcp[2:] - 2 * self.tcp[1:-1] + self.tcp[:-2]) / self.dt ** 2
        a = np.linalg.norm(d2, axis=1)
        self.acc = np.convolve(a, np.ones(3) / 3, mode="same")
        self.goal = log.goal
        self.target = log.goal["target"]
        self.evidence: list[dict] = []
        self._keys: dict[tuple, str] = {}
        self.stages = []
        st = [e for e in log.events if e["kind"] == "stage"]
        for i, e in enumerate(st):
            self.stages.append((e["t"], st[i + 1]["t"] if i + 1 < len(st) else log.duration, e["msg"]))

    # evidence -------------------------------------------------------------------------------
    def ev(self, source: str, channel: str, t0: float | None, t1: float | None, value: str, note: str) -> str:
        r = lambda x: None if x is None else round(float(x), 2)  # noqa: E731
        key = (source, channel, r(t0), r(t1), value)
        if key in self._keys:
            return self._keys[key]
        eid = f"E{len(self.evidence) + 1}"
        self._keys[key] = eid
        self.evidence.append({"id": eid, "source": source, "channel": channel, "t0": r(t0), "t1": r(t1), "value": value, "note": note})
        return eid

    # helpers --------------------------------------------------------------------------------
    def i(self, t: float) -> int:
        return self.log.idx(t)

    def events(self, kind: str) -> list[dict]:
        return [e for e in self.log.events if e["kind"] == kind]

    def stage_at(self, t: float) -> str:
        for t0, t1, msg in self.stages:
            if t0 <= t < t1:
                return msg
        return self.stages[-1][2] if self.stages else ""

    def track(self, tid: str) -> tuple[np.ndarray, np.ndarray]:
        xyz = self.log.track_xyz(tid)
        return xyz[:, 0], xyz[:, 1:]

    def track_at(self, tid: str, t: float) -> np.ndarray:
        tt, xyz = self.track(tid)
        return xyz[int(np.argmin(np.abs(tt - t)))]

    def best_label(self, tid: str) -> tuple[str, float, float]:
        """The most confident label perception ever gave this track: (label, conf, t)."""
        best = max(self.log.tracks[tid]["labels"], key=lambda r: r[2])
        return best[1], best[2], best[0]

    def label_at(self, tid: str, t: float) -> list:
        labs = self.log.tracks[tid]["labels"]
        return min(labs, key=lambda r: abs(r[0] - t))

    def tracks_labelled(self, label: str) -> list[str]:
        return [tid for tid in self.log.tracks if self.best_label(tid)[0] == label]

    def spans(self, mask: np.ndarray, min_len: int = 1) -> list[tuple[float, float]]:
        out, start = [], None
        for k, m in enumerate(mask):
            if m and start is None:
                start = k
            if (not m or k == len(mask) - 1) and start is not None:
                end = k if m else k - 1
                if end - start + 1 >= min_len:
                    out.append((float(self.t[start]), float(self.t[end])))
                start = None
        return out

    def stall(self) -> np.ndarray:
        """Per tick and joint: the command is moving (>8 deg/s) but the joint is not (<20% of that), with >2.5 deg error."""
        vq = np.abs(np.gradient(self.q[:, :5], self.t, axis=0))
        vc = np.abs(np.gradient(self.qc[:, :5], self.t, axis=0))
        return (vc > 8) & (vq < 0.2 * vc) & (self.err > 2.5)

    def held_track(self) -> tuple[str | None, float | None]:
        g = self.events("grasp")
        if not g:
            return None, None
        return g[0]["data"].get("track") or self.nearest_track(g[0]["t"]), g[0]["t"]

    def nearest_track(self, t: float) -> str | None:
        p = self.tcp[self.i(t)]
        best = min(self.log.tracks, key=lambda tid: np.linalg.norm(self.track_at(tid, t) - p))
        return best

    def max_reach(self, z: float) -> float:
        L = self.log.data["robot"]["links_m"]
        reach = L["upper_arm"] + L["forearm"]
        dz = z + L["hand"] - L["base_h"]
        return math.sqrt(max(0.0, reach ** 2 - dz ** 2))

    def grip_force(self, amps: float) -> float:
        return float(amps) * self.log.data["robot"].get("gripper_force_per_amp_n", 9.6)

    def slip_onset(self) -> float | None:
        """First time after a grasp that the fingers, still commanded closed, closed past the object."""
        g = self.events("grasp")
        if not g:
            return None
        t0, width = g[0]["t"], g[0]["data"]["opening"]
        k0 = self.i(t0)
        for k in range(k0, len(self.t)):
            if self.gc[k] > 5:  # commanded open: a release, not a slip
                return None
            if self.g[k] < width - 4:
                return float(self.t[k])
        return None


# ---- the library ---------------------------------------------------------------------------------

@dataclass
class Result:
    status: str
    summary: str
    measured: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


@dataclass
class Check:
    id: str
    parent: str | None
    statement: str  # the hypothesis, in words
    test: str  # what the check measures
    refute_if: str  # declared before running: the result that kills the hypothesis
    fn: Callable[[Ctx], Result]

    @property
    def version(self) -> str:
        return hashlib.sha1(inspect.getsource(self.fn).encode()).hexdigest()[:10]

    def run(self, ctx: Ctx) -> Result:
        try:
            return self.fn(ctx)
        except Exception as e:  # noqa: BLE001 - a broken check must not end the investigation
            return Result(INCONCLUSIVE, f"check could not run: {e}")


CHECKS: dict[str, Check] = {}


def check(id: str, parent: str | None, statement: str, test: str, refute_if: str):
    def deco(fn):
        CHECKS[id] = Check(id, parent, statement, test, refute_if, fn)
        return fn
    return deco


def children(parent: str | None) -> list[Check]:
    return [c for c in CHECKS.values() if c.parent == parent]


def fmt_t(t: float) -> str:
    return f"{t:.2f} s"


# goal ---------------------------------------------------------------------------------------------

@check("goal.met", None, "The goal was achieved.",
       "Where the camera last saw every object labelled as the target, and whether that is inside the destination zone.",
       "No object labelled as the target is inside the destination zone in the last camera frame.")
def _goal_met(c: Ctx) -> Result:
    zone = c.log.zones[c.goal["destination"]]
    (cx, cy), (w, d) = zone["center"], zone["size"]
    t_end = c.log.frames()[-1]["t"] if c.log.frames() else c.track(next(iter(c.log.tracks)))[0][-1]
    inside = []
    for tid in c.log.tracks:
        p = c.track_at(tid, t_end)
        if abs(p[0] - cx) <= w / 2 and abs(p[1] - cy) <= d / 2:
            inside.append((tid, c.best_label(tid)[0]))
    targets = c.tracks_labelled(c.target)
    ev = [c.ev("goal", "goal", None, None, c.goal["text"], f"target = {c.target}, destination = {c.goal['destination']}")]
    for tid in targets:
        p = c.track_at(tid, t_end)
        ev.append(c.ev("camera", f"track.{tid}", t_end - 0.4, t_end, f"{c.target} at ({p[0]:.3f}, {p[1]:.3f}) m",
                       f"last camera position of the {c.target.replace('_', ' ')}"))
    zone_txt = ", ".join(lbl for _, lbl in inside) or "nothing"
    ev.append(c.ev("camera", "frame", t_end - 0.4, t_end, f"{c.goal['destination']} holds: {zone_txt}", "last camera frame"))
    gc = c.events("goal_check")
    if gc:
        ev.append(c.ev("events", "event.goal_check", gc[-1]["t"], gc[-1]["t"], gc[-1]["msg"], "the controller's own end-of-task check"))
    met = any(lbl == c.target for _, lbl in inside)
    m = {"zone_contents": [lbl for _, lbl in inside], "target_tracks": targets}
    if met:
        return Result("supported", f"The {c.target.replace('_', ' ')} is in the {c.goal['destination']} at the end of the run.", m, ev)
    return Result("refuted", f"The {c.goal['destination']} holds {zone_txt}; the {c.target.replace('_', ' ')} is not in it.", m, ev)


# symptoms -----------------------------------------------------------------------------------------

@check("timeout", None, "The run ran out of time.",
       "Whether the controller hit the goal's deadline before finishing.",
       "The run ended before the deadline with no deadline event.")
def _timeout(c: Ctx) -> Result:
    dl = c.goal["deadline_s"]
    ev = [c.ev("goal", "goal.deadline_s", None, None, f"deadline {dl:.0f} s", "from the goal")]
    d = c.events("deadline")
    if d:
        ev.append(c.ev("events", "event.deadline", d[0]["t"], d[0]["t"], d[0]["msg"], "controller event"))
        return Result(SUPPORTED, f"The {dl:.0f} s deadline passed at {fmt_t(d[0]['t'])} and the task was abandoned.", {"deadline_s": dl, "t": d[0]["t"]}, ev)
    return Result(REFUTED, f"The run ended at {fmt_t(c.log.duration)}, inside its {dl:.0f} s deadline.", {"deadline_s": dl, "duration_s": round(c.log.duration, 2)}, ev)


@check("collision", None, "The arm hit something.",
       "Whether a joint stalled (measured speed near zero) while its command kept moving, building tracking error, and whether its motor current rose with it. Lag at high speed builds error too, but the joint keeps moving.",
       "No joint stalls with more than 2.5 deg of tracking error while its command is moving.")
def _collision(c: Ctx) -> Result:
    stall = c.stall()
    if not stall.any():
        j = int(np.argmax(c.err.max(axis=0)))
        peak = float(c.err[:, j].max())
        e = c.ev("telemetry", f"err.{c.joints[j]}", c.t[0], c.t[-1], f"max tracking error {peak:.1f} deg, joint never stalled", "commanded vs measured, whole run")
        lag = " (lag at speed: the joint kept moving)" if peak > 2.5 else ""
        return Result(REFUTED, f"No joint ever stalled against its command; the largest tracking error was {peak:.1f} deg on the {c.joints[j]}{lag}.",
                      {"peak_err_deg": round(peak, 2), "joint": c.joints[j], "stalled": False}, [e])
    k0 = int(np.argmax(stall.any(axis=1)))
    j = int(np.argmax(stall[k0]))
    name = c.joints[j]
    k1 = k0
    while k1 + 1 < len(c.t) and c.err[k1 + 1, j] > 1.0:
        k1 += 1
    s0, s1 = float(c.t[max(0, k0 - 1)]), float(c.t[k1])
    peak = float(c.err[k0:k1 + 1, j].max())
    base = float(np.median(c.cur[:, j]))
    cpk = float(c.cur[k0:k1 + 1, j].max())
    ev = [c.ev("telemetry", f"err.{name}", s0, s1, f"{name} stalled; tracking error up to {peak:.1f} deg", "commanded vs measured position"),
          c.ev("telemetry", f"current.{name}", s0, s1, f"{name} motor current {cpk:.2f} A (median {base:.2f} A)", "motor current")]
    st = c.events("protective_stop")
    if st:
        ev.append(c.ev("events", "event.protective_stop", st[0]["t"], st[0]["t"], st[0]["msg"], "controller event"))
    m = {"peak_err_deg": round(peak, 2), "joint": name, "current_peak_a": round(cpk, 2), "current_median_a": round(base, 2), "t0": round(s0, 2), "t1": round(s1, 2), "stalled": True}
    if peak > 4 and cpk > 1.5 * base:
        return Result(SUPPORTED, f"At {fmt_t(s0)}, during '{c.stage_at(s0)}', the {name} stopped dead while its command kept moving: tracking error rose to {peak:.1f} deg and its motor current climbed to {cpk:.2f} A.", m, ev)
    return Result(INCONCLUSIVE, f"The {name} stalled briefly ({peak:.1f} deg) without the current rise a hard contact causes.", m, ev)


@check("drop", None, "The object slipped out of the gripper.",
       "After the grasp, whether the fingers (still commanded closed) closed past the object, and whether the object's camera track fell away from the fingertip.",
       "The gripper opening stays at the object's width from the grasp until the gripper is commanded open.")
def _drop(c: Ctx) -> Result:
    g = c.events("grasp")
    if not g:
        return Result(REFUTED, "The gripper never held anything, so nothing could slip.", {}, [])
    tg, width = g[0]["t"], g[0]["data"]["opening"]
    tid = g[0]["data"].get("track") or c.nearest_track(tg)
    ev = [c.ev("events", "event.grasp", tg, tg, g[0]["msg"], "controller event")]
    ts = c.slip_onset()
    if ts is None:
        rel = next((float(c.t[k]) for k in range(c.i(tg), len(c.t)) if c.gc[k] > 5), c.log.duration)
        ev.append(c.ev("telemetry", "gripper", tg, rel, f"opening held at {width:.1f} deg", "gripper opening while carrying"))
        return Result(REFUTED, f"The gripper held the object at {width:.1f} deg from {fmt_t(tg)} until it was told to open at {fmt_t(rel)}.", {"held_deg": width}, ev)
    k = c.i(ts)
    k_closed = next((kk for kk in range(k, len(c.t)) if c.g[kk] < 3), len(c.t) - 1)
    tc = float(c.t[k_closed])
    cur_hold = float(np.median(c.gcur[c.i(tg) + 2:k])) if k > c.i(tg) + 2 else float(c.gcur[k])
    cur_after = float(np.median(c.gcur[k_closed:min(len(c.t), k_closed + 15)]))
    tt, xyz = c.track(tid)
    after = tt >= ts
    sep = np.array([np.linalg.norm(xyz[n] - c.tcp[c.i(tt[n])]) for n in range(len(tt))])
    sep_after = float(sep[after].max()) if after.any() else 0.0
    t_sep = float(tt[after][int(np.argmax(sep[after] > 0.03))]) if after.any() and (sep[after] > 0.03).any() else ts
    lbl = c.best_label(tid)[0]
    ev += [c.ev("telemetry", "gripper", ts, tc, f"opening {width:.1f} -> {c.g[k_closed]:.1f} deg, command unchanged", "fingers closed past the object"),
           c.ev("telemetry", "gripper_current", ts, tc + 0.4, f"{cur_hold:.2f} A -> {cur_after:.2f} A", "grip current fell: nothing to squeeze"),
           c.ev("camera", f"track.{tid}", ts, min(c.log.duration, t_sep + 1.0), f"{lbl} {sep_after * 100:.0f} cm from the fingertip", "camera: object left the fingers")]
    m = {"t_slip": round(ts, 2), "held_deg": width, "closed_deg": round(float(c.g[k_closed]), 1), "hold_current_a": round(cur_hold, 2),
         "after_current_a": round(cur_after, 2), "max_separation_m": round(sep_after, 3), "track": tid, "stage": c.stage_at(ts)}
    if sep_after > 0.03:
        return Result(SUPPORTED, f"At {fmt_t(ts)}, during '{c.stage_at(ts)}', the fingers closed from {width:.0f} to {c.g[k_closed]:.0f} deg on a closed command, grip current fell from {cur_hold:.2f} to {cur_after:.2f} A, and the camera saw the {lbl.replace('_', ' ')} {sep_after * 100:.0f} cm away from the fingertip.", m, ev)
    return Result(INCONCLUSIVE, "The fingers closed further, but the camera does not show the object leaving them.", m, ev)


@check("wrong_object", None, "The arm moved a different object than the goal named.",
       "Which camera track was in the fingers at the grasp, and what perception called it at close range.",
       "The grasped track's confident label is the goal's target.")
def _wrong_object(c: Ctx) -> Result:
    tid, tg = c.held_track()
    if tid is None:
        return Result(REFUTED, "Nothing was ever grasped.", {}, [])
    lbl, conf, tl = c.best_label(tid)
    ev = [c.ev("events", "event.grasp", tg, tg, f"grasped track {tid}", "controller event"),
          c.ev("camera", f"track.{tid}", tl, tl, f"{tid} = {lbl} ({conf:.2f})", "perception's most confident label for the grasped track")]
    m = {"track": tid, "label": lbl, "conf": conf, "target": c.target}
    if lbl != c.target and conf >= 0.8:
        return Result(SUPPORTED, f"The object in the fingers at {fmt_t(tg)} was the {lbl.replace('_', ' ')} ({conf:.2f} at close range), not the {c.target.replace('_', ' ')}.", m, ev)
    if lbl == c.target:
        return Result(REFUTED, f"The grasped object is the {lbl.replace('_', ' ')} ({conf:.2f}), the goal's target.", m, ev)
    return Result(INCONCLUSIVE, f"The grasped object read as {lbl} but only at {conf:.2f} confidence.", m, ev)


@check("empty_grasp", None, "The gripper closed on nothing.",
       "Whether a grasp closed the fingers fully (below 3 deg) right after reaching for the object.",
       "Every grasp stopped on an object (opening above 3 deg).")
def _empty(c: Ctx) -> Result:
    em = c.events("grasp_empty")
    if not em:
        ev = []
        g = c.events("grasp")
        if g:
            ev.append(c.ev("events", "event.grasp", g[0]["t"], g[0]["t"], g[0]["msg"], "controller event"))
        return Result(REFUTED, "Every grasp stopped on an object.", {"empty_grasps": 0}, ev)
    ev = [c.ev("events", "event.grasp_empty", e["t"], e["t"], e["msg"], f"attempt {e['data'].get('attempt')}") for e in em]
    close = c.spans((c.g < 3) & (c.gc < 3))
    for a, b in close[:4]:
        ev.append(c.ev("telemetry", "gripper", a, b, "fingers fully closed", "gripper opening below 3 deg"))
    return Result(SUPPORTED, f"The gripper closed on nothing {len(em)} times (first at {fmt_t(em[0]['t'])}).", {"empty_grasps": len(em), "first_t": em[0]["t"]}, ev)


# collision: why ------------------------------------------------------------------------------------

def _contact(c: Ctx) -> tuple[float, int] | None:
    stall = c.stall()
    if not stall.any():
        return None
    k0 = int(np.argmax(stall.any(axis=1)))
    return float(c.t[max(0, k0 - 1)]), int(np.argmax(stall[k0]))


@check("collision.unmodeled_obstacle", "collision", "Something the planner did not know about was in the arm's path.",
       "Which camera-tracked object was touching the arm at the moment of contact, and whether the planner's scene map lists it.",
       "No tracked object is within 3 cm of the arm at contact, or the one that is appears in config.planner_objects.")
def _unmodeled(c: Ctx) -> Result:
    hit = _contact(c)
    if hit is None:
        return Result(INCONCLUSIVE, "No contact moment to inspect.", {}, [])
    t0, _ = hit
    p = c.tcp[c.i(t0)]
    near = []
    held, _ = c.held_track()
    for tid, tr in c.log.tracks.items():
        if tid == held:
            continue
        o = c.track_at(tid, t0)
        w, d, h = tr["size"]
        dx = max(0.0, abs(p[0] - o[0]) - w / 2)
        dy = max(0.0, abs(p[1] - o[1]) - d / 2)
        dz = max(0.0, p[2] - (o[2] + h / 2) - 0.05)  # held objects hang ~5 cm below the fingertip
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 0.03:
            near.append((dist, tid))
    planner = c.log.config.get("planner_objects", [])
    ev = [c.ev("telemetry", "tcp.z", t0 - 0.3, t0 + 0.3, f"fingertip at ({p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f}) m", "arm position at contact"),
          c.ev("config", "config.planner_objects", None, None, ", ".join(planner), "objects in the planner's scene map")]
    if not near:
        return Result(REFUTED, "No tracked object was near the arm at contact.", {"t_contact": round(t0, 2)}, ev)
    dist, tid = min(near)
    lbl = c.best_label(tid)[0]
    o = c.track_at(tid, t0)
    top = o[2] + c.log.tracks[tid]["size"][2] / 2
    ev.append(c.ev("camera", f"track.{tid}", t0 - 0.4, t0 + 0.4, f"{lbl}, {c.log.tracks[tid]['size'][2] * 100:.0f} cm tall, {dist * 100:.1f} cm from the arm", "camera track at contact"))
    plan = c.events("plan")
    carry = plan[0]["data"].get("carry_z") if plan else None
    if plan:
        ev.append(c.ev("events", "event.plan", plan[0]["t"], plan[0]["t"], plan[0]["msg"], "the plan's carry height"))
    recs = [r for r in c.log.records if lbl.replace("_", " ") in r["text"].lower()]
    for r in recs:
        ev.append(c.ev("records", f"records.{r['source']}", None, None, f"{r['date']}: {r['text']}", f"{r['source']} record"))
    m = {"t_contact": round(t0, 2), "object": lbl, "track": tid, "in_planner_map": lbl in planner, "object_top_m": round(float(top), 3), "carry_z_m": carry}
    if lbl not in planner:
        why = f" The workcell log says: \"{recs[0]['text']}\"" if recs else ""
        return Result(SUPPORTED, f"At {fmt_t(t0)} the arm was touching the {lbl.replace('_', ' ')} ({top * 100:.0f} cm tall); the planner's scene map does not list it, so the carry height of {carry * 100 if carry else 0:.0f} cm was planned without it.{why}", m, ev)
    return Result(REFUTED, f"The arm touched the {lbl.replace('_', ' ')}, but the planner knew about it.", m, ev)


@check("collision.known_obstacle", "collision", "The planner knew the object but planned too low.",
       "Whether the object at the contact point is listed in config.planner_objects.",
       "The object at contact is missing from the planner's scene map (then the plan never had a chance).")
def _known(c: Ctx) -> Result:
    r = _unmodeled(c)
    if r.status == INCONCLUSIVE or "object" not in r.measured:
        return Result(INCONCLUSIVE, "No object identified at the contact point.", r.measured, r.evidence)
    lbl = r.measured["object"]
    if r.measured["in_planner_map"]:
        return Result(SUPPORTED, f"The {lbl.replace('_', ' ')} is in the planner's map, yet the carry path still hit it.", r.measured, r.evidence)
    return Result(REFUTED, f"The {lbl.replace('_', ' ')} is not in the planner's scene map, so planning height could not account for it.", r.measured, r.evidence)


@check("collision.sensor_glitch", "collision", "It was a sensor glitch, not a real contact.",
       "Whether motor current rose together with the tracking error (a glitch moves the reading without adding load).",
       "Motor current on the lagging joint rose to at least 1.5x its median during the error.")
def _glitch(c: Ctx) -> Result:
    hit = _contact(c)
    if hit is None:
        return Result(INCONCLUSIVE, "No tracking error to inspect.", {}, [])
    t0, j = hit
    name = c.joints[j]
    k0 = c.i(t0)
    k1 = min(len(c.t) - 1, k0 + 25)
    base = float(np.median(c.cur[:, j]))
    peak = float(c.cur[k0:k1 + 1, j].max())
    recs = [r for r in c.log.records if "encoder" in r["text"].lower()]
    ev = [c.ev("telemetry", f"current.{name}", t0, float(c.t[k1]), f"{name} current {base:.2f} -> {peak:.2f} A", "load on the motor during the error")]
    for r in recs:
        ev.append(c.ev("records", f"records.{r['source']}", None, None, f"{r['date']}: {r['text']}", "maintenance record"))
    m = {"joint": name, "current_median_a": round(base, 2), "current_peak_a": round(peak, 2), "ratio": round(peak / max(base, 1e-6), 2)}
    if peak >= 1.5 * base:
        return Result(REFUTED, f"The {name} motor current rose {peak / base:.1f}x (to {peak:.2f} A) with the error: the motor was pushing against something real.", m, ev)
    return Result(SUPPORTED, f"The {name} reading jumped without any rise in motor current.", m, ev)


# drop: why ------------------------------------------------------------------------------------------

def _held_props(c: Ctx) -> tuple[str, float, float]:
    tid, _ = c.held_track()
    lbl = c.best_label(tid)[0] if tid else c.target
    db = c.log.objects_db.get(lbl, {})
    return lbl, float(db.get("mass_kg", 0.2)), float(db.get("mu", 0.5))


@check("drop.low_grip_force", "drop", "Grip force was too low for the object's weight.",
       "Grip force from the gripper motor current while holding, against the force needed to hold the object's catalogued weight at rest: m g / (2 mu).",
       "Grip force is at least the static requirement.")
def _low_force(c: Ctx) -> Result:
    g = c.events("grasp")
    ts = c.slip_onset()
    if not g or ts is None:
        return Result(INCONCLUSIVE, "No slip to explain.", {}, [])
    tg = g[0]["t"]
    amps = float(np.median(c.gcur[c.i(tg) + 2:c.i(ts)])) if c.i(ts) > c.i(tg) + 2 else float(c.gcur[c.i(ts)])
    force = c.grip_force(amps)
    lbl, m_kg, mu = _held_props(c)
    need = m_kg * 9.81 / (2 * mu)
    ev = [c.ev("telemetry", "gripper_current", tg, ts, f"{amps:.2f} A = {force:.1f} N grip", "grip current while holding"),
          c.ev("records", "objects_db", None, None, f"{lbl}: {m_kg:.2f} kg, friction {mu:.2f}", "object catalogue"),
          c.ev("config", "config.grip_effort", None, None, f"grip_effort {c.log.config.get('grip_effort')}", "controller setting")]
    m = {"grip_force_n": round(force, 2), "needed_n": round(need, 2), "ratio": round(force / need, 2), "mass_kg": m_kg}
    if force < need:
        return Result(SUPPORTED, f"The gripper squeezed with {force:.1f} N; holding a {m_kg:.2f} kg {lbl.replace('_', ' ')} still needs {need:.1f} N. It could not have held it once lifted.", m, ev)
    return Result(REFUTED, f"{force:.1f} N of grip is {force / need:.2f}x the {need:.1f} N needed to hold it still.", m, ev)


@check("drop.aggressive_motion", "drop", "The arm accelerated too hard while carrying.",
       "Peak fingertip acceleration in the 0.5 s before the slip, against the controller's carry limit and the acceleration this grip can withstand: 2 mu F / m - g.",
       "Peak acceleration before the slip stays under config.max_carry_accel.")
def _aggressive(c: Ctx) -> Result:
    ts = c.slip_onset()
    g = c.events("grasp")
    if ts is None or not g:
        return Result(INCONCLUSIVE, "No slip to explain.", {}, [])
    k0, k1 = c.i(ts - 0.5), c.i(ts)
    kk = k0 + int(np.argmax(c.acc[k0:k1 + 1]))
    peak = float(c.acc[kk])
    lim = float(c.log.config.get("max_carry_accel", 2.5))
    tg = g[0]["t"]
    amps = float(np.median(c.gcur[c.i(tg) + 2:c.i(ts)])) if c.i(ts) > c.i(tg) + 2 else float(c.gcur[c.i(ts)])
    lbl, m_kg, mu = _held_props(c)
    a_star = 2 * mu * c.grip_force(amps) / m_kg - 9.81
    ev = [c.ev("telemetry", "tcp.accel", ts - 0.5, ts, f"peak {peak:.1f} m/s² at {c.t[kk]:.2f} s", "fingertip acceleration before the slip"),
          c.ev("config", "config.max_carry_accel", None, None, f"max_carry_accel {lim} m/s², speed_scale {c.log.config.get('speed_scale')}", "controller settings")]
    m = {"peak_accel": round(peak, 2), "limit": lim, "withstand": round(a_star, 2), "speed_scale": c.log.config.get("speed_scale")}
    if peak > lim and peak > 0.85 * a_star:
        return Result(SUPPORTED, f"The fingertip accelerated at {peak:.1f} m/s² just before the slip, above the {lim} m/s² carry limit and about what this grip can withstand ({a_star:.1f} m/s²).", m, ev)
    return Result(REFUTED, f"Peak acceleration before the slip was {peak:.1f} m/s², under the {lim} m/s² carry limit.", m, ev)


@check("drop.low_grip_force.config_change", "drop.low_grip_force", "A config change lowered the grip.",
       "config.grip_effort against its default, and the changelog entry that set it.",
       "grip_effort is at its default, or no changelog entry changed it.")
def _grip_cfg(c: Ctx) -> Result:
    cfg = c.log.config
    cur, dflt = cfg.get("grip_effort"), cfg.get("grip_effort_default")
    recs = [r for r in c.log.records if r.get("key") == "grip_effort"]
    ev = [c.ev("config", "config.grip_effort", None, None, f"grip_effort {cur} (default {dflt})", "controller setting")]
    for r in recs:
        ev.append(c.ev("records", "records.changelog", None, None, f"{r['date']}: {r['text']}", "config changelog"))
    m = {"grip_effort": cur, "default": dflt, "changelog": [r["date"] for r in recs]}
    if cur is not None and dflt is not None and cur < dflt and recs:
        return Result(SUPPORTED, f"grip_effort was cut from {dflt} to {cur} on {recs[-1]['date']}: \"{recs[-1]['text']}\"", m, ev)
    return Result(REFUTED, f"grip_effort is {cur}, its default.", m, ev)


@check("drop.worn_pads", "drop.low_grip_force", "Worn finger pads lost their friction.",
       "Grasp cycles on the finger pads since replacement, against their rated life, from the maintenance log.",
       "The pads are within their rated cycles.")
def _pads(c: Ctx) -> Result:
    recs = [r for r in c.log.records if r["source"] == "maintenance" and "pad" in r.get("item", "")]
    if not recs:
        return Result(INCONCLUSIVE, "No maintenance record for the finger pads.", {}, [])
    r = recs[-1]
    ev = [c.ev("records", "records.maintenance", None, None, f"{r['date']}: {r['text']}", "maintenance log")]
    m = {"cycles": r.get("cycles"), "rated": r.get("rated")}
    if r.get("cycles", 0) < r.get("rated", 1):
        return Result(REFUTED, f"The pads have {r['cycles']} of {r['rated']} rated cycles; they are nearly new.", m, ev)
    return Result(SUPPORTED, f"The pads are past their rated life ({r['cycles']} of {r['rated']} cycles).", m, ev)


@check("drop.aggressive_motion.config_change", "drop.aggressive_motion", "A config change sped the arm up.",
       "config.speed_scale against 1.0, and the changelog entry that set it.",
       "speed_scale is 1.0, or no changelog entry changed it.")
def _speed_cfg(c: Ctx) -> Result:
    cur = c.log.config.get("speed_scale", 1.0)
    recs = [r for r in c.log.records if r.get("key") == "speed_scale"]
    ev = [c.ev("config", "config.speed_scale", None, None, f"speed_scale {cur}", "controller setting")]
    for r in recs:
        ev.append(c.ev("records", "records.changelog", None, None, f"{r['date']}: {r['text']}", "config changelog"))
    m = {"speed_scale": cur, "changelog": [r["date"] for r in recs]}
    if cur > 1.0 and recs:
        return Result(SUPPORTED, f"speed_scale was raised to {cur} on {recs[-1]['date']}: \"{recs[-1]['text']}\" Accelerations grow with the square of it.", m, ev)
    return Result(REFUTED, f"speed_scale is {cur}.", m, ev)


# wrong object: why ------------------------------------------------------------------------------------

@check("wrong_object.perception_confusion", "wrong_object", "Perception mistook a look-alike for the target.",
       "At the moment perception chose the object, how far its label confidence was from the runner-up, and what the same track read as up close.",
       "The choice had a clear margin (>= 0.15), or the close-range label agrees with the target.")
def _confusion(c: Ctx) -> Result:
    p = c.events("perceive")
    tid, tg = c.held_track()
    if not p or tid is None:
        return Result(INCONCLUSIVE, "No perception event to inspect.", {}, [])
    d = p[0]["data"]
    margin = d["conf"] - d["runner_conf"]
    lbl, conf, tl = c.best_label(tid)
    ev = [c.ev("events", "event.perceive", p[0]["t"], p[0]["t"], f"chose {d['track']} as {d['label']} {d['conf']:.2f} vs {d['runner_up']} {d['runner_conf']:.2f}", "perception's choice, from the overhead view"),
          c.ev("camera", f"track.{tid}", tl - 0.2, tl + 0.2, f"same track up close: {lbl} {conf:.2f}", "close-range label")]
    m = {"chosen_conf": d["conf"], "runner_up": d["runner_up"], "runner_conf": d["runner_conf"], "margin": round(margin, 3), "close_label": lbl, "close_conf": conf}
    if margin < 0.15 and lbl != c.target:
        return Result(SUPPORTED, f"Perception picked {d['track']} as the {d['label'].replace('_', ' ')} with {d['conf']:.2f} against {d['runner_conf']:.2f} for {d['runner_up'].replace('_', ' ')}, a {margin:.2f} margin. Up close the same track read {lbl.replace('_', ' ')} at {conf:.2f}.", m, ev)
    return Result(REFUTED, f"Perception's choice had a {margin:.2f} margin and the close-range label is {lbl}.", m, ev)


@check("wrong_object.target_absent", "wrong_object", "The target was not on the bench.",
       "Whether any other camera track carries the target's label.",
       "Some other track is labelled as the target.")
def _absent(c: Ctx) -> Result:
    held, _ = c.held_track()
    others = [tid for tid in c.tracks_labelled(c.target) if tid != held]
    if others:
        tid = others[0]
        lbl, conf, tl = c.best_label(tid)
        p = c.track_at(tid, tl)
        e = c.ev("camera", f"track.{tid}", c.t[0], c.log.duration, f"{tid} = {lbl} ({conf:.2f}) at ({p[0]:.3f}, {p[1]:.3f}) m, never touched", "camera track")
        return Result(REFUTED, f"The {c.target.replace('_', ' ')} was on the bench the whole time ({tid}), untouched.", {"track": tid}, [e])
    return Result(SUPPORTED, f"No other track was ever labelled {c.target}.", {}, [])


@check("wrong_object.goal_misread", "wrong_object", "The controller was told to fetch a different object.",
       "The label perception searched for, against the goal's target.",
       "Perception searched for the goal's target.")
def _misread(c: Ctx) -> Result:
    p = c.events("perceive")
    if not p:
        return Result(INCONCLUSIVE, "No perception event.", {}, [])
    sought = p[0]["data"]["label"]
    ev = [c.ev("goal", "goal", None, None, c.goal["text"], f"target = {c.target}"),
          c.ev("events", "event.perceive", p[0]["t"], p[0]["t"], p[0]["msg"], "what perception looked for")]
    if sought == c.target:
        return Result(REFUTED, f"Perception searched for '{sought}', exactly the goal's target.", {"sought": sought}, ev)
    return Result(SUPPORTED, f"Perception searched for '{sought}' but the goal says '{c.target}'.", {"sought": sought}, ev)


# timeout / empty grasp: why -------------------------------------------------------------------------------

@check("timeout.unreachable", "timeout", "The target was out of the arm's reach.",
       "The target's distance from the base axis, from its camera track, against the arm's maximum reach at that height (link lengths in the log).",
       "The target is within reach.")
def _unreachable(c: Ctx) -> Result:
    tids = c.tracks_labelled(c.target)
    if not tids:
        return Result(INCONCLUSIVE, "The target was never tracked.", {}, [])
    tid = tids[0]
    tt, xyz = c.track(tid)
    p = xyz.mean(axis=0)
    r = math.hypot(p[0], p[1])
    reach = c.max_reach(p[2])
    d = np.linalg.norm(c.tcp - p, axis=1)
    k = int(np.argmin(d))
    ev = [c.ev("camera", f"track.{tid}", tt[0], tt[-1], f"{c.target} {r * 100:.1f} cm from the base axis", "camera track"),
          c.ev("records", "robot.links_m", None, None, f"max reach {reach * 100:.1f} cm at {p[2] * 100:.0f} cm height", "arm geometry in the log"),
          c.ev("telemetry", "tcp.z", float(c.t[k]) - 0.3, float(c.t[k]) + 0.3, f"closest fingertip approach {d[k] * 100:.1f} cm", "nearest the fingers ever came")]
    plan = c.events("plan")
    if plan and plan[0]["data"].get("reachable") is False:
        ev.append(c.ev("events", "event.plan", plan[0]["t"], plan[0]["t"], f"{plan[0]['msg']} (planner flagged it unreachable)", "plan event"))
    m = {"distance_m": round(r, 3), "max_reach_m": round(reach, 3), "closest_m": round(float(d[k]), 3)}
    if r > reach:
        return Result(SUPPORTED, f"The {c.target.replace('_', ' ')} sat {r * 100:.1f} cm from the base axis; the arm reaches {reach * 100:.1f} cm at that height. The fingertip never got closer than {d[k] * 100:.1f} cm.", m, ev)
    return Result(REFUTED, f"The target at {r * 100:.1f} cm is inside the {reach * 100:.1f} cm reach.", m, ev)


@check("timeout.slow_motion", "timeout", "The arm moved too slowly to finish in time.",
       "config.speed_scale, which scales every joint's speed cap.",
       "speed_scale is at least 0.9.")
def _slow(c: Ctx) -> Result:
    s = c.log.config.get("speed_scale", 1.0)
    e = c.ev("config", "config.speed_scale", None, None, f"speed_scale {s}", "controller setting")
    if s >= 0.9:
        return Result(REFUTED, f"The arm ran at speed_scale {s}: full speed.", {"speed_scale": s}, [e])
    return Result(SUPPORTED, f"The arm ran at speed_scale {s}.", {"speed_scale": s}, [e])


@check("timeout.target_moved", "timeout", "The target moved, so each grasp arrived where it used to be.",
       "How far the target's camera track moved over the run.",
       "The target moved less than 1.5 cm.")
def _moved(c: Ctx) -> Result:
    tids = c.tracks_labelled(c.target)
    if not tids:
        return Result(INCONCLUSIVE, "The target was never tracked.", {}, [])
    tt, xyz = c.track(tids[0])
    mv = float(np.linalg.norm(xyz[:, :2] - xyz[0, :2], axis=1).max())
    e = c.ev("camera", f"track.{tids[0]}", tt[0], tt[-1], f"moved {mv * 100:.1f} cm over the run", "camera track")
    if mv < 0.015:
        return Result(REFUTED, f"The {c.target.replace('_', ' ')} stayed put (moved {mv * 100:.1f} cm).", {"moved_m": round(mv, 3)}, [e])
    return Result(SUPPORTED, f"The target moved {mv * 100:.1f} cm.", {"moved_m": round(mv, 3)}, [e])


@check("empty_grasp.missed_position", "empty_grasp", "The fingers closed away from the object.",
       "Horizontal distance from the fingertip to the target's camera track each time the gripper closed on nothing.",
       "The fingertip was within 2 cm of the target at every empty close.")
def _missed(c: Ctx) -> Result:
    em = c.events("grasp_empty")
    tids = c.tracks_labelled(c.target)
    if not em or not tids:
        return Result(INCONCLUSIVE, "No empty grasp to inspect.", {}, [])
    off = []
    ev = []
    for e in em[:3]:
        p = c.tcp[c.i(e["t"])]
        o = c.track_at(tids[0], e["t"])
        dxy = math.hypot(p[0] - o[0], p[1] - o[1])
        off.append(dxy)
        ev.append(c.ev("telemetry", "tcp.z", e["t"] - 0.4, e["t"], f"fingertip {dxy * 100:.1f} cm from the {c.target.replace('_', ' ')}", "fingertip vs camera track at the close"))
    m = {"offsets_m": [round(x, 3) for x in off]}
    if min(off) > 0.02:
        return Result(SUPPORTED, f"Each time, the fingers closed {min(off) * 100:.1f} to {max(off) * 100:.1f} cm short of the {c.target.replace('_', ' ')}.", m, ev)
    return Result(REFUTED, f"The fingers closed within {min(off) * 100:.1f} cm of the target.", m, ev)


# ---- custom checks (for the LLM backend): a threshold over a named channel -------------------------------

CHANNELS = {
    "gripper": lambda c: c.g, "gripper_cmd": lambda c: c.gc, "gripper_current": lambda c: c.gcur,
    "tcp.z": lambda c: c.tcp[:, 2], "tcp.accel": lambda c: c.acc,
    **{f"err.{j}": (lambda c, n=n: c.err[:, n]) for n, j in enumerate(["base", "shoulder", "elbow", "wrist_flex", "wrist_roll"])},
    **{f"current.{j}": (lambda c, n=n: c.cur[:, n]) for n, j in enumerate(["base", "shoulder", "elbow", "wrist_flex", "wrist_roll"])},
    **{f"q.{j}": (lambda c, n=n: c.q[:, n]) for n, j in enumerate(["base", "shoulder", "elbow", "wrist_flex", "wrist_roll"])},
}


def run_threshold(c: Ctx, channel: str, op: str, value: float, t0: float | None = None, t1: float | None = None, min_s: float = 0.08) -> Result:
    """Supported when `channel op value` holds for at least min_s inside [t0, t1]."""
    if channel not in CHANNELS:
        return Result(INCONCLUSIVE, f"unknown channel {channel!r}")
    if op not in ("<", ">"):
        return Result(INCONCLUSIVE, f"unknown op {op!r}")
    x = CHANNELS[channel](c)
    win = np.ones(len(c.t), bool)
    if t0 is not None:
        win &= c.t >= t0
    if t1 is not None:
        win &= c.t <= t1
    hold = ((x < value) if op == "<" else (x > value)) & win
    spans = [s for s in c.spans(hold) if s[1] - s[0] >= min_s]
    w0, w1 = (t0 if t0 is not None else float(c.t[0])), (t1 if t1 is not None else float(c.t[-1]))
    m = {"channel": channel, "op": op, "value": value, "spans": [[round(a, 2), round(b, 2)] for a, b in spans]}
    if spans:
        a, b = spans[0]
        e = c.ev("telemetry", channel, a, b, f"{channel} {op} {value} for {b - a:.2f} s", "custom threshold check")
        return Result(SUPPORTED, f"{channel} {op} {value} from {fmt_t(a)} to {fmt_t(b)}.", m, [e])
    e = c.ev("telemetry", channel, w0, w1, f"{channel} never {op} {value}", "custom threshold check")
    return Result(REFUTED, f"{channel} never went {op} {value} in that window.", m, [e])
