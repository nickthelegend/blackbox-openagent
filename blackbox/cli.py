"""BLACKBOX command line.

    python -m blackbox simulate collision --seed 3 --out runs/
    python -m blackbox explain runs/collision-003 [--control runs/nominal-000] [--backend rules|llm]
    python -m blackbox verify runs/collision-003/explain.json
    python -m blackbox eval --seeds 20          # accuracy against simulator ground truth (rules backend)
    python -m blackbox demo                     # rebuild web/data: demo runs + explanations for the UI
    python -m blackbox serve [--port 8730]      # serve the web UI
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

from .agent import LLMBackend, RulesBackend, explain, verify
from .runlog import RunLog
from .sim import SCENARIOS, save_run, simulate

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
EXPECT_ROOT = {
    "low_grip_force": "drop.low_grip_force", "aggressive_motion": "drop.aggressive_motion",
    "unmodeled_obstacle": "collision.unmodeled_obstacle", "perception_confusion": "wrong_object.perception_confusion",
    "unreachable": "timeout.unreachable",
}
DEMO = [("slip_grip", 0), ("collision", 0), ("wrong_object", 0), ("slip_rushed", 0), ("timeout", 0), ("nominal", 0)]
CONTROL_SEED = 100


def _backend(name: str | None):
    if name in ("llm", "nemotron"):
        return LLMBackend()
    if name == "rules":
        return RulesBackend()
    from .agent import backend_from_env
    return backend_from_env()


def cmd_simulate(a) -> None:
    log = simulate(a.scenario, a.seed, render=not a.no_frames)
    out = save_run(log, Path(a.out) / log.id)
    print(out)


def cmd_explain(a) -> None:
    log = RunLog.load(a.run)
    controls = [RunLog.load(c) for c in a.control] if a.control else [simulate("nominal", CONTROL_SEED, render=False)]
    x = explain(log, _backend(a.backend), controls)
    out = Path(a.run) / "explain.json" if Path(a.run).is_dir() else Path(a.run).parent / "explain.json"
    out.write_text(json.dumps(x, indent=1))
    print(x["headline"])
    for c in x["claims"]:
        print(f"  [{c['kind']}] {c['text']}  ({', '.join(c['cites'])})")
    print(out)


def cmd_verify(a) -> None:
    p = Path(a.explanation)
    x = json.loads(p.read_text())
    log = RunLog.load(p.parent)
    r = verify(x, log)
    print(("VERIFIED" if r["ok"] else "MISMATCH") + f": {r['checks']} checks re-run against {x['run']} ({x['run_sha256'][:12]})")
    for prob in r["problems"]:
        print("  -", prob)
    sys.exit(0 if r["ok"] else 1)


def evaluate(seeds: int, scenarios=SCENARIOS) -> dict:
    control = simulate("nominal", CONTROL_SEED, render=False)
    rows, confusion = [], Counter()
    t0 = time.perf_counter()
    for name in scenarios:
        for seed in range(seeds):
            log = simulate(name, seed, render=False)
            truth = log.data["meta"]["truth"]
            x = explain(log, RulesBackend(), [control])
            want = EXPECT_ROOT.get(truth["root"]) if truth["outcome"] == "failure" else None
            got = x["cause"]["root"]
            ok = (x["outcome"] == truth["outcome"]) and (got == want)
            confusion[(name, got)] += 1
            rows.append({"run": log.id, "truth": truth, "outcome": x["outcome"], "root": got, "ok": ok})
    n = len(rows)
    return {"runs": n, "correct": sum(r["ok"] for r in rows), "accuracy": round(sum(r["ok"] for r in rows) / n, 3),
            "seconds": round(time.perf_counter() - t0, 1), "confusion": {f"{k[0]} -> {k[1]}": v for k, v in sorted(confusion.items(), key=str)},
            "misses": [r for r in rows if not r["ok"]]}


def cmd_eval(a) -> None:
    r = evaluate(a.seeds)
    print(f"{r['correct']}/{r['runs']} runs explained correctly ({r['accuracy'] * 100:.1f}%) in {r['seconds']} s")
    for k, v in r["confusion"].items():
        print(f"  {k}: {v}")
    for m in r["misses"]:
        print("  miss:", m)
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1))


def build_demo(out: Path = WEB / "data", seeds_eval: int = 0) -> list[dict]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    control = simulate("nominal", CONTROL_SEED, render=False)
    index = []
    for name, seed in DEMO:
        log = simulate(name, seed)
        folder = save_run(log, out / log.id)
        x = explain(RunLog.load(folder), RulesBackend(), [control])
        (folder / "explain.json").write_text(json.dumps(x, separators=(",", ":")))
        index.append({"id": log.id, "scenario": name, "goal": log.goal["text"], "outcome": x["outcome"], "headline": x["headline"],
                      "duration": round(log.duration, 2), "symptom": x["cause"]["symptom"], "root": x["cause"]["root"],
                      "tested": x["stats"]["tested"], "killed": x["stats"]["killed"], "frames": len(log.frames())})
        print(f"{log.id}: {x['headline']}")
    meta = {"runs": index, "control": control.id, "generated": time.strftime("%Y-%m-%d"), "simulated": True}
    if seeds_eval:
        r = evaluate(seeds_eval)
        meta["eval"] = {k: r[k] for k in ("runs", "correct", "accuracy")}
    (out / "index.json").write_text(json.dumps(meta, indent=1))
    return index


def cmd_demo(a) -> None:
    build_demo(seeds_eval=a.eval)


def cmd_serve(a) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    with http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler) as srv:
        print(f"BLACKBOX on http://127.0.0.1:{a.port}")
        srv.serve_forever()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="blackbox", description="Flight recorder for robots: explains why a run failed, with evidence.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("scenario", choices=SCENARIOS)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", default="runs")
    s.add_argument("--no-frames", action="store_true")
    s.set_defaults(fn=cmd_simulate)
    s = sub.add_parser("explain")
    s.add_argument("run")
    s.add_argument("--control", action="append")
    s.add_argument("--backend", choices=["rules", "llm"])
    s.set_defaults(fn=cmd_explain)
    s = sub.add_parser("verify")
    s.add_argument("explanation")
    s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("eval")
    s.add_argument("--seeds", type=int, default=10)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("demo")
    s.add_argument("--eval", type=int, default=20, help="seeds per scenario for the accuracy figure (0 to skip)")
    s.set_defaults(fn=cmd_demo)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8730)
    s.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    a.fn(a)
