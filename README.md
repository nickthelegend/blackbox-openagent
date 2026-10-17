# BLACKBOX

A flight recorder for robots. When a robot run fails, BLACKBOX's agent investigates it like an accident examiner: it proposes hypotheses, **runs each one as a check against the recorded log**, kills the ones the data refutes, and returns a verdict where every claim links to the moment of the run that proves it.

Built for the **Open Agent Hackathon 2026**: Track 2, "The Agent That Can Explain Why", plus the NVIDIA Nemotron prize. See [`SUBMISSION.md`](SUBMISSION.md) for the submission kit and its open decisions, and [`RESEARCH.md`](RESEARCH.md) for the rules, Nemotron access and prior art.

> All runs in this repo are **simulated**: a 6-joint arm with the same joint layout as the Thenar / SO-101 arm.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m blackbox demo      # simulate 6 runs, explain them, write web/data/
.venv/bin/python -m blackbox serve     # http://127.0.0.1:8730
.venv/bin/python -m pytest -q          # 63 tests
```

In the UI:
- Pick a run along the top.
- Drag the chart strip (or use ← →) to scrub. The joint plots and the camera frame move together.
- Press **F** to jump to the failure moment.
- Click any evidence chip (`E7`). The playhead jumps there, the lane gets a red bracket, the object is circled in the camera frame, and cited documents (config, changelog, maintenance log) light up.

## How it explains a failure

```
observe  -> propose -> test -> refine -> control -> verdict
           (backend)   (code)  (why?)   (nominal run) (citation gate)
```

- **Hypotheses are code.** [`blackbox/checks.py`](blackbox/checks.py) holds 20 checks. Each one states, before it runs, what it measures and what result would refute it. Running it returns supported / refuted / inconclusive, the numbers it measured, and evidence spans (a channel plus a time window, or a document).
- **Refuted hypotheses stay on the sheet**, stamped with the number that killed them.
- **Negative control.** Every kept hypothesis is re-run on a nominal, successful run. If it fires there too, it is demoted to *open*, because it does not single out this failure.
- **Citation gate.** A verdict claim survives only if it cites evidence a check produced. A *cause* may cite only kept hypotheses, and a *ruled out* claim only killed ones. The same gate applies to the LLM.
- **Proof bundle.** `explain.json` records the log's sha256, each check's code version, and its results. Re-run everything with:

  ```bash
  .venv/bin/python -m blackbox verify web/data/slip_grip-000/explain.json   # VERIFIED / MISMATCH
  ```

### Backends

| | |
|---|---|
| `rules` (default) | Deterministic and offline. Tests every hypothesis at each level. |
| `llm` | Any OpenAI-compatible endpoint. NVIDIA Nemotron by default. Picks which hypotheses to test, may write new threshold checks over named channels, and drafts the verdict. Unknown checks are rejected. If the model is unreachable or returns bad JSON, the rules backend takes over, and the trace records it. |

```bash
BLACKBOX_BACKEND=llm \
BLACKBOX_LLM_BASE_URL=https://integrate.api.nvidia.com/v1 \   # or a Meterless endpoint
BLACKBOX_LLM_API_KEY=nvapi-... \                              # or NVIDIA_API_KEY
BLACKBOX_LLM_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b \
.venv/bin/python -m blackbox explain web/data/collision-000
```

The tests cover the LLM path against a local fake server, so they make no network calls and no paid calls.

## The run log (`blackbox.run/1`)

A run is a folder holding `run.json` and `frames/*.jpg`. The full schema is in [`blackbox/runlog.py`](blackbox/runlog.py).

| Section | Contents |
|---|---|
| `goal` | text, target object, destination zone, deadline |
| `series` | 25 Hz: measured and commanded joints, joint motor currents, gripper opening and command, grip current, fingertip position |
| `camera` | 5 Hz frames, plus the camera's intrinsics (so the UI can circle tracked objects) |
| `tracks` | perception tracks per object: position and label confidence over time |
| `events` | controller stages, grasp, empty grasp, protective stop, deadline, goal check |
| `config`, `records`, `objects_db` | controller settings, maintenance log and config changelog, object catalogue |
| `meta.truth` | simulator ground truth. **The investigator never sees it** (`test_never_reads_ground_truth`). |

## The simulator

[`blackbox/sim.py`](blackbox/sim.py) reuses REACH's joint model (`../reach-amazon/reach/arm.py`: joint order, home pose, speed caps, 25 Hz) and its fetch sequence (`reach/jobs.py`: hover, descend, close, lift, carry, place, home). The physics it adds:

- Servos lag their command. A blocked joint stalls while its command moves on.
- The gripper holds while force ≥ m(g+a)/(2μ). Otherwise the object slips and the fingers close on nothing.
- Perception confuses look-alikes from overhead and resolves them up close.
- [`blackbox/render.py`](blackbox/render.py) draws the camera frames from the same state.

| Scenario | What goes wrong | Root cause BLACKBOX should find |
|---|---|---|
| `slip_grip` | the bottle stays on the table when the arm lifts | grip force below the bottle's weight; grip_effort cut by a config change |
| `slip_rushed` | the bottle flies out mid-carry | acceleration over the carry limit; speed_scale raised |
| `collision` | protective stop during the carry | a cereal box on the bench, missing from the planner's scene map |
| `wrong_object` | the vitamin bottle is delivered | perception picked a look-alike by a 0.07 margin |
| `timeout` | four empty grasps, then the deadline | target 29 cm out; the arm reaches 25 cm |
| `nominal` | nothing | none: success, all failure hypotheses refuted |

### Accuracy, honestly

```bash
.venv/bin/python -m blackbox eval --seeds 20
```

This reported **120/120** seeded runs explained with the simulator's true root cause. The checks were written against this simulator, so the score shows the pipeline is consistent end to end. It is **not** evidence that BLACKBOX generalizes. That needs real-arm logs.

## Layout

```
blackbox/   runlog.py  kinematics.py  sim.py  render.py  checks.py  agent.py  cli.py
tests/      63 tests: log format, simulator, checks, investigator, LLM backend (fake server), CLI
web/        index.html (single file, no build step) + data/ (generated by `blackbox demo`)
```

MIT licensed.
