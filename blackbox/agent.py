"""The investigator: hypothesise, test against the log, keep or kill, then explain.

    observe   summarise the log (duration, events, config) for the backend
    propose   the backend picks hypotheses to test from the check library (an LLM may
              also write threshold checks over named channels)
    test      every proposed hypothesis is run as code against the log
    refine    kept hypotheses open their child hypotheses ("why did that happen?")
    control   every kept hypothesis is re-run on a nominal run; one that also fires there
              is not specific to this failure and is demoted to inconclusive
    verdict   the backend writes claims; a claim survives only if it cites evidence that a
              check produced, and a cause can only cite a kept hypothesis

Two backends: `RulesBackend` (deterministic, offline) and `LLMBackend` (any
OpenAI-compatible endpoint; NVIDIA Nemotron by default), chosen by BLACKBOX_BACKEND.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import checks as C
from .runlog import RunLog

FORMAT = "blackbox.explain/1"
KEPT, KILLED, OPEN = "kept", "killed", "inconclusive"
STATUS = {C.SUPPORTED: KEPT, C.REFUTED: KILLED, C.INCONCLUSIVE: OPEN}
SYMPTOM_ORDER = ["collision", "drop", "wrong_object", "timeout", "empty_grasp"]

FIXES = {
    "collision.unmodeled_obstacle": "Re-capture the planner's scene map whenever the bench changes, or plan carry height from the live camera tracks, not the saved map.",
    "collision.known_obstacle": "Raise carry clearance above the tallest mapped object on the path.",
    "drop.low_grip_force": "Set grip effort per object from its catalogued weight instead of one global value.",
    "drop.low_grip_force.config_change": "Revert grip_effort to its default for heavy items; keep the low setting only for objects flagged fragile.",
    "drop.aggressive_motion": "Cap carry acceleration to what the grip can withstand for the held object's weight.",
    "drop.aggressive_motion.config_change": "Roll speed_scale back, or raise it only for empty-gripper moves where nothing can slip.",
    "wrong_object.perception_confusion": "Refuse to grasp when the top two labels are within 0.15; take a close-range look first.",
    "timeout.unreachable": "Check reach before the first attempt and ask for the object to be moved instead of regrasping until the deadline.",
    "empty_grasp.missed_position": "After an empty grasp, re-perceive from close range before retrying the same pose.",
}


@dataclass
class Node:
    id: str
    parent: str | None
    statement: str
    test: str
    refute_if: str
    status: str = OPEN
    result: str = C.INCONCLUSIVE
    summary: str = ""
    measured: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    round: int = 0
    proposed_by: str = "rules"
    why: str = ""
    control: dict | None = None
    custom: dict | None = None

    def view(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ---- backends ------------------------------------------------------------------------------------

class RulesBackend:
    """Tests every hypothesis the library offers at each level. Deterministic and offline."""

    name = "rules"
    model = None

    def propose(self, brief: dict, frontier: list[C.Check], tested: list[Node]) -> list[dict]:
        return [{"check": c.id, "why": "standard check for this symptom"} for c in frontier]

    def write(self, inv: "Investigation") -> dict:
        return rules_verdict(inv)


class LLMError(RuntimeError):
    pass


class LLMBackend:
    """Any OpenAI-compatible chat endpoint. Defaults to NVIDIA's hosted Nemotron.

    BLACKBOX_LLM_BASE_URL  default https://integrate.api.nvidia.com/v1 (a Meterless gateway works too)
    BLACKBOX_LLM_API_KEY   or NVIDIA_API_KEY
    BLACKBOX_LLM_MODEL     default nvidia/nemotron-3.5-lightning-30b-a3b
    """

    name = "llm"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None, timeout: float = 90):
        self.base_url = (base_url or os.environ.get("BLACKBOX_LLM_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("BLACKBOX_LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
        self.model = model or os.environ.get("BLACKBOX_LLM_MODEL") or "nvidia/nemotron-3.5-lightning-30b-a3b"
        self.timeout = timeout
        self.calls = 0

    def chat(self, system: str, user: str) -> dict:
        body = {"model": self.model, "temperature": 0.2, "max_tokens": 2000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise LLMError(f"LLM call failed: {e}") from e
        self.calls += 1
        text = out["choices"][0]["message"].get("content") or ""
        return parse_json(text)

    def propose(self, brief: dict, frontier: list[C.Check], tested: list[Node]) -> list[dict]:
        sys = ("You investigate why a robot run failed. You may only learn things by running checks against the log. "
               "Pick which hypotheses to test next from the list (by id), and you may add up to 2 custom threshold checks "
               "over these channels: " + ", ".join(sorted(C.CHANNELS)) + ". Reply with JSON only: "
               '{"run": [{"check": "<id>", "why": "<one line>"}], "custom": [{"statement": "...", "channel": "...", "op": "<|>", "value": 0.0, "t0": null, "t1": null, "why": "..."}]}')
        user = json.dumps({"run_brief": brief,
                           "already_tested": [{"id": n.id, "status": n.status, "result": n.summary} for n in tested],
                           "available_checks": [{"id": c.id, "hypothesis": c.statement, "measures": c.test, "refuted_if": c.refute_if} for c in frontier]})
        out = self.chat(sys, user)
        picks = [{"check": p.get("check"), "why": p.get("why", "")} for p in out.get("run", []) if isinstance(p, dict)]
        for cu in out.get("custom", [])[:2]:
            if isinstance(cu, dict):
                picks.append({"custom": cu, "why": cu.get("why", "")})
        return picks

    def write(self, inv: "Investigation") -> dict:
        sys = ("Write the verdict on why this robot run failed (or confirm it succeeded). Use only the tested results given. "
               "Every claim must cite evidence ids (E1, E2...) from those results. A 'cause' or 'finding' claim may only rest on kept hypotheses; "
               "a 'ruled_out' claim on killed ones. Keep each claim to one or two sentences with the measured numbers. Reply with JSON only: "
               '{"headline": "<one sentence>", "claims": [{"kind": "outcome|finding|cause|ruled_out|fix", "text": "...", "cites": ["E1"]}]}')
        user = json.dumps({"goal": inv.log.goal, "results": [{"id": n.id, "parent": n.parent, "hypothesis": n.statement, "status": n.status,
                                                               "result": n.summary, "evidence": n.evidence} for n in inv.nodes],
                           "evidence": inv.ctx.evidence})
        return self.chat(sys, user)


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (tolerates code fences and thinking text)."""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise LLMError(f"no JSON object in reply: {text[:200]!r}")
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"bad JSON in reply: {e}") from e


def backend_from_env() -> RulesBackend | LLMBackend:
    return LLMBackend() if os.environ.get("BLACKBOX_BACKEND", "rules").lower() in ("llm", "nemotron") else RulesBackend()


# ---- the investigation ------------------------------------------------------------------------------

class Investigation:
    def __init__(self, log: RunLog, backend=None, controls: list[RunLog] | None = None, max_rounds: int = 4):
        self.log = log.without_truth()  # ground truth never reaches the investigator
        self.backend = backend or RulesBackend()
        self.controls = [c.without_truth() for c in (controls or [])]
        self.max_rounds = max_rounds
        self.ctx = C.Ctx(self.log)
        self.nodes: list[Node] = []
        self.trace: list[dict] = []
        self._custom_n = 0
        self.writer = self.backend.name

    def note(self, step: str, msg: str, **kw) -> None:
        self.trace.append({"step": step, "msg": msg, **kw})

    def brief(self) -> dict:
        lg = self.log
        return {"goal": lg.goal, "duration_s": round(lg.duration, 2), "config": lg.config,
                "events": [{"t": e["t"], "kind": e["kind"], "msg": e["msg"]} for e in lg.events],
                "records": lg.records, "camera_tracks": {tid: self.ctx.best_label(tid)[0] for tid in lg.tracks}}

    def _run(self, chk: C.Check, rnd: int, by: str, why: str) -> Node:
        t0 = time.perf_counter()
        r = chk.run(self.ctx)
        n = Node(chk.id, chk.parent, chk.statement, chk.test, chk.refute_if, STATUS[r.status], r.status, r.summary,
                 r.measured, r.evidence, rnd, by, why)
        self.nodes.append(n)
        self.note("test", f"{chk.id}: {r.status}", ms=round((time.perf_counter() - t0) * 1000, 2))
        return n

    def _run_custom(self, cu: dict, parent: str | None, rnd: int, why: str) -> Node | None:
        try:
            ch, op, val = cu["channel"], cu["op"], float(cu["value"])
        except (KeyError, TypeError, ValueError):
            self.note("reject", f"custom check malformed: {cu}")
            return None
        if ch not in C.CHANNELS or op not in ("<", ">"):
            self.note("reject", f"custom check on unknown channel/op: {ch} {op}")
            return None
        self._custom_n += 1
        cid = f"custom.{self._custom_n}"
        t0, t1 = cu.get("t0"), cu.get("t1")
        r = C.run_threshold(self.ctx, ch, op, val, t0, t1)
        stmt = str(cu.get("statement") or f"{ch} {op} {val}")[:200]
        n = Node(cid, parent, stmt, f"threshold: {ch} {op} {val}", f"{ch} never goes {op} {val} for 0.08 s in the window",
                 STATUS[r.status], r.status, r.summary, r.measured, r.evidence, rnd, self.backend.name, why,
                 custom={"channel": ch, "op": op, "value": val, "t0": t0, "t1": t1})
        self.nodes.append(n)
        self.note("test", f"{cid} ({ch} {op} {val}): {r.status}")
        return n

    def run(self) -> dict:
        t_start = time.perf_counter()
        lg = self.log
        self.note("observe", f"{lg.id}: {lg.duration:.1f} s, {len(lg.events)} events, {len(lg.frames())} frames, {len(lg.tracks)} camera tracks, {len(lg.records)} records")
        brief = self.brief()
        # goal.met always runs first: it decides whether there is a failure to explain
        goal = self._run(C.CHECKS["goal.met"], 0, "investigator", "decides whether there is a failure to explain")
        frontier = [c for c in C.children(None) if c.id != "goal.met"]
        parent_of_custom: str | None = None
        for rnd in range(self.max_rounds):
            if not frontier:
                break
            try:
                picks = self.backend.propose(brief, frontier, self.nodes)
            except LLMError as e:
                self.note("fallback", f"{e}; testing every hypothesis instead")
                picks = RulesBackend().propose(brief, frontier, self.nodes)
            allowed = {c.id: c for c in frontier}
            ran = set()
            self.note("propose", f"round {rnd + 1}: {len(picks)} hypotheses proposed by {self.backend.name}")
            for p in picks:
                if "custom" in p:
                    self._run_custom(p["custom"], parent_of_custom, rnd + 1, p.get("why", ""))
                    continue
                cid = p.get("check")
                if cid not in allowed:
                    self.note("reject", f"{cid!r} is not an available check this round")
                    continue
                if cid in ran:
                    continue
                ran.add(cid)
                self._run(allowed[cid], rnd + 1, self.backend.name, p.get("why", ""))
            kept = [n for n in self.nodes if n.round == rnd + 1 and n.status == KEPT and not n.id.startswith("custom.")]
            frontier = [c for k in kept for c in C.children(k.id)]
            parent_of_custom = kept[0].id if kept else None
            if kept:
                self.note("refine", f"kept {', '.join(k.id for k in kept)}; asking why ({len(frontier)} follow-up hypotheses)")
        self._controls()
        verdict = self._verdict(goal)
        self.note("done", f"{len(self.nodes)} hypotheses tested, {sum(n.status == KILLED for n in self.nodes)} killed",
                  ms=round((time.perf_counter() - t_start) * 1000, 1))
        return self._package(goal, verdict)

    def _controls(self) -> None:
        if not self.controls:
            return
        cctx = [(c, C.Ctx(c)) for c in self.controls]
        for n in self.nodes:
            if n.id == "goal.met" or n.status != KEPT:
                continue
            res = []
            for clog, cc in cctx:
                if n.custom:
                    r = C.run_threshold(cc, n.custom["channel"], n.custom["op"], n.custom["value"], n.custom["t0"], n.custom["t1"])
                else:
                    r = C.CHECKS[n.id].run(cc)
                res.append({"run": clog.id, "result": r.status, "summary": r.summary})
            fired = [x for x in res if x["result"] == C.SUPPORTED]
            n.control = {"runs": res, "specific": not fired}
            if fired:
                n.status = OPEN
                n.summary += f" But the same check also fires on nominal run {fired[0]['run']}, so it does not single out this failure."
            self.note("control", f"{n.id}: {'silent' if not fired else 'FIRES'} on {len(res)} nominal run(s)")

    def _verdict(self, goal: Node) -> dict:
        try:
            raw = self.backend.write(self)
            v = validate_verdict(raw, self)
            if not v["claims"]:
                raise LLMError("no claim survived citation checks")
            return v
        except (LLMError, KeyError, TypeError, ValueError) as e:
            self.note("fallback", f"verdict from {self.backend.name} rejected ({e}); rules writer used")
            self.writer = "rules"
            return validate_verdict(rules_verdict(self), self)

    def _package(self, goal: Node, verdict: dict) -> dict:
        moment = failure_moment(self)
        cause = primary_cause(self)
        return {
            "format": FORMAT,
            "run": self.log.id,
            "run_sha256": self.log.sha256(),
            "backend": {"name": self.backend.name, "model": getattr(self.backend, "model", None), "writer": self.writer},
            "outcome": "success" if goal.status == KEPT else "failure",
            "headline": verdict["headline"],
            "cause": cause,
            "failure_moment": moment,
            "claims": verdict["claims"],
            "hypotheses": [n.view() for n in self.nodes],
            "evidence": self.ctx.evidence,
            "trace": self.trace,
            "stats": {"tested": len(self.nodes), "kept": sum(n.status == KEPT for n in self.nodes),
                      "killed": sum(n.status == KILLED for n in self.nodes), "inconclusive": sum(n.status == OPEN for n in self.nodes),
                      "controls": [c.id for c in self.controls]},
            "proof": {"run_sha256": self.log.sha256(), "checks": [
                {"id": n.id, "version": C.CHECKS[n.id].version if n.id in C.CHECKS else "threshold", "params": n.custom,
                 "result": n.result, "measured": n.measured, "evidence": n.evidence} for n in self.nodes]},
        }


def explain(log: RunLog, backend=None, controls: list[RunLog] | None = None) -> dict:
    return Investigation(log, backend or backend_from_env(), controls).run()


# ---- verdicts ------------------------------------------------------------------------------------------

def _node(inv: Investigation, cid: str) -> Node | None:
    return next((n for n in inv.nodes if n.id == cid), None)


def primary_cause(inv: Investigation) -> dict:
    g = _node(inv, "goal.met")
    if g and g.status == KEPT:
        return {"symptom": None, "root": None, "chain": []}
    sym = next((s for s in SYMPTOM_ORDER if (n := _node(inv, s)) and n.status == KEPT), None)

    def down(cid: str | None) -> list[str]:
        out = []
        while cid:
            cid = next((n.id for n in inv.nodes if n.parent == cid and n.status == KEPT and not n.id.startswith("custom.")), None)
            if cid:
                out.append(cid)
        return out

    chain = [sym] + down(sym) if sym else []
    # A timeout is explained through its empty grasps: deadline <- grasps closed on air <- closed short <- out of reach.
    if sym == "timeout" and (n := _node(inv, "empty_grasp")) and n.status == KEPT:
        chain = ["timeout", "empty_grasp"] + down("empty_grasp") + down("timeout")
    root = next((c for c in reversed(chain) if c in FIXES and not c.endswith(".config_change")), chain[-1] if chain else None)
    return {"symptom": sym, "root": root, "chain": chain}


def failure_moment(inv: Investigation) -> dict | None:
    cause = primary_cause(inv)
    sym = cause["symptom"]
    if not sym:
        return None
    n = _node(inv, sym)
    m = n.measured
    if sym == "collision":
        st = inv.ctx.events("protective_stop")
        return {"t0": m.get("t0"), "t1": st[0]["t"] if st else m.get("t1"), "label": "contact"}
    if sym == "drop":
        return {"t0": m.get("t_slip"), "t1": round(m.get("t_slip", 0) + 0.5, 2), "label": "slip"}
    if sym == "wrong_object":
        g = inv.ctx.events("grasp")
        p = inv.ctx.events("perceive")
        return {"t0": p[0]["t"] if p else None, "t1": g[0]["t"] if g else None, "label": "wrong pick"}
    if sym in ("timeout", "empty_grasp"):
        em = inv.ctx.events("grasp_empty")
        d = inv.ctx.events("deadline")
        return {"t0": em[0]["t"] - 0.6 if em else None, "t1": d[0]["t"] if d else (em[-1]["t"] if em else None), "label": "missed grasps"}
    return None


def _short(n: Node) -> str:
    return n.statement.rstrip(".").lower()


def rules_verdict(inv: Investigation) -> dict:
    goal = _node(inv, "goal.met")
    cause = primary_cause(inv)
    claims = [{"kind": "outcome", "text": goal.summary, "cites": goal.evidence[:4], "hypothesis": "goal.met"}]
    if goal.status == KEPT:
        killed = [n for n in inv.nodes if n.status == KILLED and n.parent is None]
        for n in killed:
            claims.append({"kind": "ruled_out", "text": f"Not {_short(n)}: {n.summary}", "cites": n.evidence[:3], "hypothesis": n.id})
        head = f"Run succeeded: {goal.summary[0].lower()}{goal.summary[1:]} {len(killed)} failure hypotheses were tested and none fired."
        return {"headline": head, "claims": claims}
    chain = [_node(inv, c) for c in cause["chain"]]
    for i, n in enumerate(chain):
        claims.append({"kind": "finding" if i == 0 else "cause", "text": n.summary, "cites": n.evidence[:5], "hypothesis": n.id})
    in_chain = set(cause["chain"])
    for n in inv.nodes:
        if n.status == KILLED and n.id != "goal.met" and (n.parent is None or n.parent in in_chain):
            claims.append({"kind": "ruled_out", "text": f"Not {_short(n)}: {n.summary}", "cites": n.evidence[:3], "hypothesis": n.id})
    for cid in reversed(cause["chain"]):
        if cid in FIXES:
            claims.append({"kind": "fix", "text": FIXES[cid], "cites": _node(inv, cid).evidence[:3], "hypothesis": cid})
            break
    return {"headline": headline(inv, cause), "claims": claims}


def headline(inv: Investigation, cause: dict) -> str:
    sym, chain = cause["symptom"], cause["chain"]
    m = lambda cid: (_node(inv, cid).measured if _node(inv, cid) else {})  # noqa: E731
    tgt = inv.log.goal["target"].replace("_", " ")
    if sym == "collision" and "collision.unmodeled_obstacle" in chain:
        x = m("collision.unmodeled_obstacle")
        return f"The arm hit the {x['object'].replace('_', ' ')} at {x['t_contact']:.1f} s: it was on the bench but missing from the planner's scene map."
    if sym == "drop" and "drop.low_grip_force" in chain:
        x = m("drop.low_grip_force")
        extra = f", after grip_effort was cut to {m('drop.low_grip_force.config_change')['grip_effort']}" if "drop.low_grip_force.config_change" in chain else ""
        return f"The {tgt} slipped out at {m('drop')['t_slip']:.1f} s: {x['grip_force_n']:.1f} N of grip for a load that needs {x['needed_n']:.1f} N{extra}."
    if sym == "drop" and "drop.aggressive_motion" in chain:
        x = m("drop.aggressive_motion")
        extra = f" after speed_scale was raised to {x['speed_scale']}" if "drop.aggressive_motion.config_change" in chain else ""
        return f"The {tgt} slipped out at {m('drop')['t_slip']:.1f} s when the arm accelerated at {x['peak_accel']:.1f} m/s^2{extra}, past the {x['limit']} m/s^2 carry limit."
    if sym == "wrong_object" and "wrong_object.perception_confusion" in chain:
        x = m("wrong_object.perception_confusion")
        return f"The arm delivered the {x['close_label'].replace('_', ' ')}, not the {tgt}: perception chose a look-alike by a {x['margin']:.2f} confidence margin."
    if sym == "timeout" and "timeout.unreachable" in chain:
        x = m("timeout.unreachable")
        k = m("empty_grasp").get("empty_grasps", 0)
        return f"The run timed out: the {tgt} sat {x['distance_m'] * 100:.0f} cm out, beyond the arm's {x['max_reach_m'] * 100:.0f} cm reach, so {k} grasps closed on air."
    if chain:
        return _node(inv, chain[-1]).summary
    return "The goal was not met and no tested hypothesis explains why."


def validate_verdict(raw: dict, inv: Investigation) -> dict:
    """Keep only claims whose citations point at evidence a check produced; causes may only rest on kept hypotheses."""
    ev_ids = {e["id"] for e in inv.ctx.evidence}
    owner: dict[str, set[str]] = {}
    for n in inv.nodes:
        for e in n.evidence:
            owner.setdefault(e, set()).add(n.status)
    head = str(raw.get("headline") or "").strip()
    out = []
    for c in raw.get("claims", []):
        if not isinstance(c, dict):
            continue
        kind = c.get("kind", "finding")
        cites = [e for e in c.get("cites", []) if e in ev_ids]
        if kind in ("finding", "cause"):
            cites = [e for e in cites if KEPT in owner.get(e, set())]
        elif kind == "ruled_out":
            cites = [e for e in cites if KILLED in owner.get(e, set())]
        text = str(c.get("text", "")).strip()
        if not cites or not text:
            inv.note("reject", f"claim dropped (no valid evidence): {text[:80]!r}")
            continue
        out.append({"kind": kind, "text": text, "cites": cites, **({"hypothesis": c["hypothesis"]} if "hypothesis" in c else {})})
    if not head:
        raise LLMError("verdict has no headline")
    return {"headline": head, "claims": out}


# ---- proof: re-run every check and compare ---------------------------------------------------------------

def verify(explanation: dict, log: RunLog) -> dict:
    """Re-run the checks recorded in an explanation, in order, and compare results and measurements."""
    lg = log.without_truth()
    problems = []
    if lg.sha256() != explanation["proof"]["run_sha256"]:
        problems.append("log hash differs from the one the explanation was made from")
    ctx = C.Ctx(lg)
    for rec in explanation["proof"]["checks"]:
        if rec["id"] in C.CHECKS:
            chk = C.CHECKS[rec["id"]]
            if chk.version != rec["version"]:
                problems.append(f"{rec['id']}: check code changed ({rec['version']} -> {chk.version})")
            r = chk.run(ctx)
        elif rec.get("params"):
            p = rec["params"]
            r = C.run_threshold(ctx, p["channel"], p["op"], p["value"], p.get("t0"), p.get("t1"))
        else:
            problems.append(f"{rec['id']}: unknown check")
            continue
        if r.status != rec["result"]:
            problems.append(f"{rec['id']}: {rec['result']} -> {r.status}")
        if json.loads(json.dumps(r.measured)) != rec["measured"]:
            problems.append(f"{rec['id']}: measurements differ")
        if r.evidence != rec["evidence"]:
            problems.append(f"{rec['id']}: evidence differs")
    return {"ok": not problems, "checks": len(explanation["proof"]["checks"]), "problems": problems}
