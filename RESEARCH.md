# BLACKBOX: research notes

Compiled **Oct 17, 2026**, read-only: nothing was signed up for, and no paid API was called. Every claim has a source. **UNVERIFIED** marks anything that no primary source confirms (forum posts, vendor marketing, my inferences). Re-check the official page on Oct 21–22, because the rules have already changed once (an older listing had Oct 15–20).

## 1. The hackathon: Open Agent Hackathon 2026

**Official page:** https://hackathon.genai.works/event/open-agent-hackathon-2026
- Run by GenAI.Works on its own platform, not Devpost or lablab.
- Sponsors: NVIDIA, Zetaris, SpaceX AI and Meterless. A university notice also lists Bright Data and Cursor ([UFSM, Oct 9](https://www.ufsm.br/unidades-universitarias/ct/2026/10/09/open-agent-hackathon-2026-prorrogacao-inscricoes)).
- Online, free, 144 hours. Teams of 1–5, aged 16+. The team locks when the first submission is created.
- Judges named on the page:
  - Michael Hay (CTO, Zetaris)
  - Michael Armentano (SpaceXAI)
  - Sam Cummings, Shestakov Vladyslav and Remus Ranca (GenAI Works)
- No NVIDIA judge is listed.

### Dates (all UTC, official page)

| | When |
|---|---|
| Build window opens | **Oct 22, 2026 00:00** |
| Registration closes (hard) | **Oct 22, 2026 23:59** |
| Judging opens | Oct 27, 2026 00:00 |
| Submissions close (hard) | **Oct 27, 2026 23:45** |
| Results | Nov 6, 2026 16:00 |

"Time zones do not extend the window." Ties go to the higher Impact score, then to the **earlier** submission, so submit early.

### Track 2, word for word
> **The Agent That Can Explain Why:** "Build agents that investigate complex questions across multiple data sources, connect findings, and produce evidence-backed answers or recommendations."

Every entry picks exactly one primary track. Cross-track relevance "is not scored twice".

### Prizes (§8)
- **Track 2:** $1,600 / $1,200 / $900.
- **Best use of NVIDIA Nemotron:** an NVIDIA DGX Spark (Founder's Edition, valued at $4,699). That is the whole text. It doesn't say which models count, whether you must call build.nvidia.com, or who judges it. **UNVERIFIED.** Ask hackathons@genai.works or on the Discord.
- **Best Cursor-built product:** $2,301 of API credits.
- **Wildcard "Bring Your Own Project":** $1,000 / $600 / $400. It is "scored on the new work rather than prior development".

### Judging (§7, out of 100)

| Criterion | Weight | What it means |
|---|---|---|
| Impact | 30 | fits the challenge statement; a meaningful real-world problem |
| Technical | 20 | implementation, reliability, architecture |
| Innovation | 15 | originality of the approach |
| Demo | 15 | how clearly the demo shows the value |
| Product & UX | 10 | intuitive, accessible |
| Sponsor tech | 10 | how well sponsor tech is used |

At least three judges review each entry.

### Hard requirements (§5) — these change the plan
- **"Every submission must integrate Zetaris and Meterless, and teams must use Cursor for development."** This applies to every track, not only Wildcard.
- NVIDIA tech: "wherever it contributes". It is optional for the cash tracks but needed for the Nemotron prize.
- **"Work committed before the window opens is not eligible, except for clearly declared pre-existing components."** The FAQ says: "declare anything pre-existing in your submission so judges can see what you built during the window."

> **Consequence for this repo:** everything here was committed on Oct 17, before the window opens. It is pre-existing work and must be declared as such. See `SUBMISSION.md` → "Pre-existing code: decide before Oct 22".

### What to submit (§6)
1. A **1–4 minute demo video**. It must show how Zetaris and Meterless are integrated. Our script is kept to 3 minutes.
2. A **slide deck**: problem and users, solution, agent architecture, stack, Zetaris and Meterless use, what was unique about the sponsor use, visuals, future work.
3. A **GitHub repo** with a README (setup, usage, dependencies). The rules don't say it must be public. The wave plan makes it public at submission anyway.
4. A **written explanation** of how Zetaris, Meterless, Cursor and NVIDIA were used.

The rules require no license and no live URL. You keep your IP, and sponsors get a promotional license to your demo (§9).

### Sponsor tech, as far as public sources go
- **Meterless (Nightshift).** A local-first "AI hotspot" that exposes **one OpenAI-compatible base URL and key** on your network ([meterless.ai](https://meterless.ai/)). Its model list includes Nemotron 3.5 Lightning and Nemotron 3 Super and Ultra.
  - The official "Power Day" workshop covers "running a product on NVIDIA Nemotron through Meterless" ([academy page](https://academy.genai.works/courses/open-agent-hackathon-2026/details)).
  - **Implication:** BLACKBOX's LLM backend is already OpenAI-compatible. Pointing `BLACKBOX_LLM_BASE_URL` at Meterless should cover both the required Meterless integration and the Nemotron prize in one move. **UNVERIFIED** until tested.
- **Zetaris ("AI Data Harness").** It gives agents federated, governed access to enterprise data where it lives, over Spark, Presto and Trino ([pulse2, secondary](https://pulse2.com/zetaris-launches-cloud-based-ai-data-harness-and-adds-steve-nouri-as-ai-strategy-advisor/)). No public API docs were found.
  - The integration path is in the Data Day recording on the academy page. **UNVERIFIED.**
  - **Natural fit:** serve the robot fleet's maintenance log, config changelog and object catalogue through Zetaris as the "multiple data sources" Track 2 asks for. BLACKBOX already treats these as separate sources (`records`, `objects_db`, `config` in the log).

## 2. Nemotron access

- **API key:** on any model page at build.nvidia.com, click *Get API Key*, then sign in to the NVIDIA Developer Program ([NIM quickstart](https://docs.api.nvidia.com/nim/docs/api-quickstart)).
- **Base URL:** `https://integrate.api.nvidia.com/v1`. It is OpenAI-compatible: `GET /v1/models` listed 81 models on Oct 17, and a chat call without a key returned 401 ([NVIDIA Nemotron page](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/llm-info/)).
- **Models live on Oct 17:**
  - `nvidia/nemotron-3.5-lightning-30b-a3b`: 30B/3B-active MoE, 1M context, "low-latency execution layer for always-on agents" ([docs](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b)). **BLACKBOX's default.**
  - `nvidia/nemotron-3-super-120b-a12b`: stronger agentic reasoning ([docs](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b)).
  - `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`: **takes images**, including base64 JPEG camera frames, and video ([docs](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-nano-omni-30b-a3b-reasoning)). The pick for reading frames.
  - **Retired from the catalog:** `llama-3.3-nemotron-super-49b-v1.5`, `nvidia-nemotron-nano-9b-v2` and `nemotron-nano-12b-v2-vl`. Don't build on them.
- **Reasoning:** switch it with `chat_template_kwargs: {"enable_thinking": true|false}`, not the old `/think` prompt string. Whether the hosted endpoint passes it through is **UNVERIFIED**. BLACKBOX's JSON parser ignores `<think>…</think>` either way.
- **Limits:** users report about 40 requests/min and 1,000 free credits ([forum](https://forums.developer.nvidia.com/t/request-for-nvidia-nim-api-rate-limit-increase-40-200-rpm/375340)). **UNVERIFIED.** One investigation costs 2–5 calls, so this is plenty for a demo.
- **Local on a 16 GB Mac:** only `nemotron-3-nano:4b` (text, 2.8 GB) fits in Ollama ([tags](https://ollama.com/library/nemotron-3-nano/tags)). No local Nemotron VLM fits today, so frames must go to the hosted API.

## 3. Prior art

### Academic: explaining or detecting robot failures

| Work | What it does | Link |
|---|---|---|
| **REFLECT** (Liu, Bahety, Song; CoRL 2023) | Hierarchical summary of multisensory observations, then an LLM is queried step by step for the failure explanation, which drives a replanner. Introduced the RoboFail dataset. | [arXiv 2306.15724](https://arxiv.org/abs/2306.15724) |
| **AHA** (Duan et al., NVIDIA/UW; ICLR 2025) | A VLM fine-tuned to detect and explain manipulation failures in free-form language. Trained on FailGen, which procedurally perturbs successful demos. | [arXiv 2410.00371](https://arxiv.org/abs/2410.00371) |
| **RoboFAC** (2025) | 9,440 failure trajectories with QA pairs, six failure types, and a VLM for failure analysis and correction. | [arXiv 2505.12224](https://arxiv.org/abs/2505.12224) |
| **Sentinel** (Agia et al.; CoRL) | Runtime monitor: statistical temporal consistency plus a VLM for task-progress failures. | [arXiv 2410.04640](https://arxiv.org/abs/2410.04640) |
| **Code-as-Monitor** (CVPR 2025) | A VLM writes **executable monitor code** for spatio-temporal constraints. These are runtime monitors, not post-hoc explanation. | [arXiv 2412.04455](https://arxiv.org/abs/2412.04455) |
| **I-FailSense** (ICRA 2026) | VLM with classification heads for semantic-misalignment failures. | [arXiv 2509.16072](https://arxiv.org/abs/2509.16072) |
| **FailSafe** (Oct 2025) | Generates failures paired with executable recovery actions. | [arXiv 2510.01642](https://arxiv.org/abs/2510.01642) |
| **KITE** (2026) | Turns long execution video into keyframe-indexed evidence tokens for VLM failure localisation and explanation. | [arXiv 2604.07034](https://arxiv.org/abs/2604.07034) |
| **ViFailback** (CVPR 2026) | About 58K VQA pairs over 5,202 real manipulation trajectories. | [arXiv 2512.02787](https://arxiv.org/abs/2512.02787) |
| **POPPER** (ICML 2025) | LLM agents design and **execute falsification experiments** with Type-I error control, applied to scientific datasets (not robots). | [arXiv 2502.09858](https://arxiv.org/abs/2502.09858) |

### Commercial: robot log tools that already have agents
- **Roboto Agents** (July 2026): root-cause analysis that claims to "test hypotheses against your real multimodal data". Method and evidence format are not public. **Closest overlap.** ([blog](https://www.roboto.ai/blog/root-cause-analysis/))
- **Foxglove Agentic Data Platform** (Aug 2026): "Every answer cites the topic, timestamp, or schema it came from." ([blog](https://foxglove.dev/blog/introducing-the-agentic-data-platform-for-physical-ai))
- **Alloy Robotics** ($8M seed, Aug 2026): "Each finding links to the underlying missions, timestamps, and signals." ([secondary](https://www.startuphub.ai/ai-news/startup-news/2026/alloy-robotics-raises-8m-to-debug-robot-fleets-with-ai.md))
- **Formant F3:** "Deep Research" agents over fleet data ([press release](https://www.businesswire.com/news/home/20250630008190/en/Formant-F3-Brings-Generative-AI-and-Agentic-Reasoning-to-Robot-Ops)).
- **Rerun:** open-source multimodal logging and viewing ([site](https://rerun.io/learn/what-is-rerun)).

### What this means for the pitch
- **Timestamp-linked answers are table stakes.** Foxglove and Alloy already ship them, so don't pitch "linked evidence" as new.
- **VLM-narrated explanations can't be checked:** REFLECT, AHA, RoboFAC, KITE and ViFailback all produce prose no one can audit.
- **The closest method is POPPER** (falsification), applied to science data, not robots. No paper was found that runs falsification-style executed checks against a recorded robot log with per-claim evidence spans.

## 4. BLACKBOX's differentiator

**"Every claim is a test that ran, and you can re-run it."**

1. **Falsification, not retrieval.** Each hypothesis is code over the log. It declares, before it runs, what result would refute it (`refute_if`). Refuted hypotheses stay on the sheet with the number that killed them.
   - On the slip run, "the arm accelerated too hard" is killed by a measured 0.5 m/s² against a 2.5 m/s² limit.
2. **Negative controls.** Every surviving hypothesis is re-run on a nominal, successful run. If it fires there too, it is demoted to *open*, because it doesn't single out this failure. `test_negative_control_demotes_unspecific_hypotheses` proves the demotion works.
3. **A citation gate.** A claim survives only if it cites evidence a check produced. A *cause* may cite only kept hypotheses; a *ruled out* claim may cite only killed ones. This is enforced in code (`validate_verdict`) for the LLM too.
4. **A replayable proof bundle.**
   - The bundle holds the log hash, each check's code version, and its results and evidence.
   - `python -m blackbox verify run/explain.json` re-runs everything and reports any drift. Tampering with one channel of the log is caught (`test_proof_bundle_reproduces_and_detects_tampering`).
5. **Multiple sources joined in one chain.** Telemetry, camera tracks, the goal, controller config, the config changelog, the maintenance log and the object catalogue are all used.
   - Example chain: slip → too little grip force for this object's catalogued weight → grip effort cut by config change PR #212 → worn pads ruled out by the maintenance log.
   - The LLM only proposes and words things. The verdict rests on executed checks.

**Honest limits:**
- All runs come from our simulator. The rules backend's checks were written against that same simulator, so its 120/120 score on seeded runs (`python -m blackbox eval`) shows the pipeline is consistent end to end, not that it generalizes.
- The real test is logs from a physical Thenar or SO-101 arm.
