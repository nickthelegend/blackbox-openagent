# BLACKBOX: submission kit

**Event:** Open Agent Hackathon 2026, Track 2 "The Agent That Can Explain Why", plus the *Best use of NVIDIA Nemotron* prize.
**Window:** Oct 22 00:00 to Oct 27 23:45 UTC. Rules and sources are in `RESEARCH.md`.

## Pre-existing code: decide before Oct 22

The rules (§4) say: *"Work committed before the window opens is not eligible, except for clearly declared pre-existing components."* Everything in this repo was committed on Oct 17, 2026, so it counts as pre-existing. There are three honest options:

1. **Track 2, with the current repo declared as pre-existing (recommended).**
   - In the submission form, declare the following as pre-existing: the simulator, the log format, the check library, the investigator and the UI.
   - Build these during the window. They are also the parts the rules require:
     - the Meterless/Nemotron integration, run live
     - the Zetaris data source
     - the Nemotron VLM frame reader
     - real-arm logs from a Thenar or SO-101 arm
     - a judge-facing upload flow
   - Risk: judges may score mainly the in-window work.
2. **Wildcard "Bring Your Own Project".** It exists for exactly this case and is "scored on the new work". Prizes are smaller ($1,000 / $600 / $400). The Nemotron prize is separate and should still be open to the entry (**UNVERIFIED**).
3. **Start fresh on Oct 22** and rebuild in a new repo, using this one only as a reference. This costs time on the lowest-priority project in the wave.

Whichever you pick, don't hide anything. Declare it plainly.

## Short description (for the form, ~100 words)

> BLACKBOX is a flight recorder for robots. When a robot arm fails a task, its agent investigates the run like an accident examiner. It proposes hypotheses (slip, collision, wrong object, unreachable target), compiles each into a check over the recorded telemetry, camera tracks, config history and maintenance log, and runs it. Hypotheses the data refutes are stamped REFUTED and stay on the sheet. Survivors are re-run on a successful run as a negative control. The verdict may only cite evidence a check produced. Click any claim and the timeline, the camera frame and the source document jump to the moment that proves it. Nemotron proposes hypotheses and writes the verdict; the checks decide.

## Long description (for the README or deck)

**Problem.**
- Robot-learning teams record thousands of episodes, and many fail.
- Finding out *why* means scrubbing video and joint plots by hand, or asking a VLM that returns plausible prose nobody can check.
- Commercial tools now cite timestamps, but a citation isn't a test. The claim can still be wrong.

**What BLACKBOX does.** It treats an explanation as a series of experiments:

1. **Propose.** The agent (Nemotron, or an offline rules engine) picks hypotheses from a library of 20 executable checks. Nemotron may also write new threshold checks over named channels.
2. **Test.** Each check runs against the log. Before it runs, it states what result would refute it.
3. **Refine.** Kept hypotheses open "why?" follow-ups. For a slip: grip force against the object's catalogued weight, then the config change that lowered it, while worn pads are ruled out by the maintenance log.
4. **Control.** Every kept hypothesis is re-run on a nominal, successful run. If it fires there too, it is not specific and is demoted.
5. **Verdict.**
   - A claim survives only if it cites evidence that a check produced.
   - A cause can't rest on a refuted hypothesis.
   - The bundle can be re-verified with one command.

**Results on the simulator.** Six demo runs cover five failure modes plus a nominal control:

| Run | Failure | Explanation |
|---|---|---|
| slip_grip-000 | Slip | grip effort cut by a config change |
| slip_rushed-000 | Slip | aggressive acceleration after a speed change |
| collision-000 | Collision | an obstacle missing from the planner's map |
| wrong_object-000 | Wrong object | a look-alike chosen by a 0.07 confidence margin |
| timeout-000 | Timeout | target out of reach, 4 empty grasps |
| nominal-000 | — | 5 failure hypotheses tested, none fired |

Across 120 seeded runs (20 per scenario) the offline engine named the simulator's true root cause every time. The checks were written against this simulator, so this proves the pipeline end to end, not generalization.

## Video script (≤ 3:00)

The rules allow 1–4 minutes. The video **must show the Zetaris and Meterless integration**: the beats marked ★ need the in-window work.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:12 | Camera frames of the arm lifting a water bottle; the bottle stays on the table while the arm carries on. | "This robot just failed. The arm lifted, the bottle didn't, and the controller never noticed." |
| 0:12–0:25 | The BLACKBOX UI loads the slip run: the strip, the red failure box at 8.6 s, the headline. | "BLACKBOX is a flight recorder for robots. It doesn't guess why a run failed. It runs experiments on the log." |
| 0:25–0:55 | Slowly scroll the hypothesis tree, so the stamps land: REFUTED on collision and wrong object, HOLDS on the slip. | "Each hypothesis is a check with a refutation condition written before it runs. Collision: no joint ever stalled, refuted. Wrong object: the camera says it's the water bottle, refuted. Slip: the fingers closed from 48 to 0 degrees on a closed command and grip current collapsed. It holds." |
| 0:55–1:25 | Click E13 (grip current): the playhead sweeps, a bracket lands on the Grip lane. Click the changelog chip: the PR #212 document slip lights up. | "Why did it slip? Grip force 2.7 newtons, while a 0.45 kg bottle needs 4.4. Why so low? Click: a config change cut grip effort on October 9 to stop crushing paper cups. Worn pads? The maintenance log says 214 of 1,500 cycles. Refuted." |
| 1:25–1:45 | Point at "Silent on the nominal control run" under each kept hypothesis. | "Every surviving hypothesis is re-run on a good run. If it fires there too, it doesn't explain this failure, and it's demoted." |
| 1:45–2:10 | Quick cuts: collision run (red ring on the cereal box in the camera frame), wrong-object run (0.52 vs 0.46 margin), timeout run (four empty grasps). | "Same examiner, different failures. An unmapped obstacle. A look-alike bottle chosen by a 0.07 margin. A target 29 cm out when the arm reaches 25." |
| 2:10–2:35 ★ | Terminal: `BLACKBOX_BACKEND=llm` with the Meterless base URL; Nemotron's proposals stream in, including one custom threshold check; one claim rejected for a bogus citation. Zetaris query returning maintenance records. | "Nemotron, served through Meterless, proposes hypotheses and writes the verdict. It can even invent new checks. But it can't cite evidence that no check produced: this claim was dropped. The maintenance and config history come from Zetaris, where the fleet's records live." |
| 2:35–2:52 | Terminal: `python -m blackbox verify … → VERIFIED`. Then edit one value in the log and re-run: `MISMATCH`. | "And every verdict is a proof bundle. Re-run it and get the same answer. Touch the log and it knows." |
| 2:52–3:00 | The strip with the red box, the BLACKBOX mark. | "BLACKBOX. Not a plausible story. An audited one." |

## Your TODOs (in order)

- [ ] **Register by Oct 22, 23:59 UTC** (hard deadline) at https://hackathon.genai.works/event/open-agent-hackathon-2026.
- [ ] **Choose the pre-existing-code route** (top of this file) before writing any in-window code.
- [ ] **Ask the organizers** (hackathons@genai.works or Discord):
  - Does Nemotron through Meterless count for the Nemotron prize?
  - Which Nemotron models count?
  - Can the Nemotron prize go to a Wildcard entry?
- [ ] **Get keys and accounts.** Nothing has been called with a paid key.
  - An NVIDIA API key from build.nvidia.com, for a fallback path.
  - Meterless (Nightshift, free web edition).
  - Zetaris access (watch the Data Day recording on the academy page).
- [ ] **Install Cursor and use it for in-window development.** The rules require it, so screenshot your usage for the written explanation.
- [ ] **First live Nemotron run.** Expect 2–5 calls per run:
  ```bash
  BLACKBOX_BACKEND=llm BLACKBOX_LLM_BASE_URL=<meterless url> BLACKBOX_LLM_API_KEY=<key> python -m blackbox explain web/data/slip_grip-000
  ```
- [ ] **Optional, strongest proof:** record 2–3 real failed runs on the Thenar or SO-101 arm into the `blackbox.run/1` format.
- [ ] **Record the video** (script above). Make the slide deck. Write the sponsor-tech explanation (Zetaris, Meterless, Cursor, NVIDIA).
- [ ] **Make the repo public at submission** and push. Nothing has been pushed yet.
- [ ] **Submit early.** Ties go to the earlier submission.

## Sponsor-tech explanation (draft, finish after the window work)

- **NVIDIA Nemotron:**
  - The investigator's LLM backend is OpenAI-compatible and defaults to `nvidia/nemotron-3.5-lightning-30b-a3b` at `https://integrate.api.nvidia.com/v1`.
  - Nemotron chooses which hypotheses to test, may write new threshold checks, and drafts the verdict.
  - Every draft passes a citation gate before it reaches the user.
  - *(Planned in the window: `nemotron-3-nano-omni` reads the camera frame at the failure moment, as a hypothesis source, never as proof.)*
- **Meterless:** *(in-window)* the same backend pointed at a Meterless endpoint, so the model is chosen per step: Lightning for proposing, Super for the verdict.
- **Zetaris:** *(in-window)* fleet maintenance logs, config changelogs and the object catalogue, served through Zetaris as live data sources instead of fields copied into the log.
- **Cursor:** *(in-window)* development environment for the in-window work.
