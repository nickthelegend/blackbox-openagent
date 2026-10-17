# Product

<!-- impeccable:product-schema 1 -->

> Inferred from the explicit brief (WAVE1-PITCHES.md, JUDGE-REPORT.md and the session brief of Oct 17, 2026). No interview round was answered before this was written; facts marked *(inferred)* need the user's confirmation.

## Platform

web

## Stack

Python 3 package (`blackbox/`) with pytest; a small standard-library HTTP server serves one static `web/index.html` (no build step), matching the sibling wave-1 projects (Quiver, REACH). *(inferred from the brief: "Python with pytest" + premium web UI)*

## Users

- **Primary:** hackathon judges for the Open Agent Hackathon 2026, Track 2 "Agent That Can Explain Why" and the NVIDIA Nemotron prize. They watch a ≤3 min video, then open the live demo for a minute or two and click around.
- **Product user** *(inferred)*: a robot-learning engineer at a lab or a teleop-data company (ThenarLabs' own verifier is the origin) who has hundreds of failed episodes and needs to know *why* each failed without scrubbing every video.

## Product Purpose

BLACKBOX is a flight recorder for robot runs. Given one run log (goal, joint states over time, gripper, camera frames, events), an agent forms hypotheses about why the run failed, actually executes a check for each against the log, kills the ones the data refutes, and returns a verdict in which every claim links to the timestamped log evidence it rests on. Success: a judge can click any sentence of the verdict and land on the exact moment in the video and joint plots that proves it.

## Positioning

Prior systems (REFLECT, CoRL 2023; NVIDIA AHA, 2024) *narrate* failures with an LLM or VLM. BLACKBOX's explanations are *falsifiable*: each hypothesis is a runnable check over the log, its result is shown, and a claim without an executed check cannot appear in the verdict. Auditable, not plausible.

## Operating Context

- Runs come from a simulated 6-joint arm (the Thenar/SO-101 pose convention reused from `../reach-amazon/reach/arm.py`) producing successful and failed episodes: grasp slip, collision, wrong object, timeout.
- Offline-first: a deterministic rules backend works with no network; an OpenAI-compatible LLM backend (NVIDIA Nemotron via build.nvidia.com) sits behind an environment variable and must never be called without the user's go-ahead.
- Demo machine is a 16 GB Mac; everything must stay light.

## Capabilities and Constraints

- Log format: JSON run file; joints sampled at a fixed rate; camera frames as small rendered images; discrete events (grasp, contact, drop, timeout).
- The agent's output is a hypothesis tree: each node has a statement, the check it ran, the measured result, a status (kept / killed / inconclusive) and evidence spans `[t0, t1]` on named channels.
- Build window Oct 22–27, 2026 (rules on pre-existing code to be confirmed in RESEARCH.md).

## Brand Commitments

Name: BLACKBOX (an aviation flight-recorder metaphor). Built by nickthelegend / ThenarLabs. No other assets exist yet.

## Evidence on Hand

- All runs are **synthetic** (simulated arm). The UI must label them as simulated.
- No real-robot logs, user quotes, accuracy numbers or customers exist. Do not invent any. An accuracy figure may only come from running the explainer over the simulator's ground-truth labels.

## Product Principles

1. No claim without an executed check: every sentence of a verdict links to evidence.
2. Show the killed hypotheses too; ruling things out is half the explanation.
3. Evidence is a moment in time: every link moves the timeline.
4. Works offline first; the LLM improves wording and hypotheses, never replaces the checks.
5. Lean and demo-first: lowest-priority project in the wave, so scope stays tight.

## Accessibility & Inclusion

No product-specific requirement established; meet WCAG AA contrast and full keyboard operation of the timeline.
