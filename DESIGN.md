---
name: BLACKBOX
description: A flight recorder for robot runs, drawn as a chart-recorder strip that an examiner marks up in red.
colors:
  examiner-red: "#c3301b"
  red-on-film: "#e2492f"
  red-wash: "rgba(195, 48, 27, .085)"
  red-line: "rgba(195, 48, 27, .55)"
  commanded-blue: "#2c66a8"
  camera-violet: "#6a4f9e"
  paper: "#f4ede2"
  paper-2: "#efe6d8"
  paper-3: "#e8dccb"
  sheet: "#fbf8f2"
  grid: "rgba(219, 112, 92, .17)"
  grid-major: "rgba(205, 88, 68, .36)"
  rule: "#d9c7b0"
  rule-2: "#c7b195"
  ink: "#1c2333"
  ink-2: "#485065"
  ink-3: "#5f6476"
  pencil: "#8a8478"
  film-black: "#1d1d1d"
  cited-white: "#ffffff"
  red-on-ink: "#f2a493"
typography:
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(25px, 2.3vw, 31px)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-.005em"
  wordmark:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: ".2em"
  readout:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-.02em"
    fontFeature: "\"tnum\""
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
  caption:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  section-label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: ".14em"
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: ".1em"
  stamp:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: ".14em"
  data:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\""
  data-sm:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1
    fontFeature: "\"tnum\""
rounded:
  hairline: "2px"
  sm: "3px"
  dot: "50%"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  xl: "22px"
  section: "30px"
  label-gutter: "92px"
  label-gutter-phone: "66px"
components:
  button-transport:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "34px"
  button-transport-hover:
    backgroundColor: "{colors.paper-2}"
  button-transport-icon:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    size: "34px"
  button-failure-moment:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.examiner-red}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "34px"
  button-failure-moment-hover:
    backgroundColor: "{colors.red-wash}"
  chip-evidence:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    typography: "{typography.data-sm}"
    rounded: "{rounded.hairline}"
    padding: "0 4px"
    height: "18px"
  chip-evidence-active:
    backgroundColor: "{colors.examiner-red}"
    textColor: "#ffffff"
  stamp-holds:
    backgroundColor: "transparent"
    textColor: "{colors.examiner-red}"
    typography: "{typography.stamp}"
    rounded: "{rounded.sm}"
    padding: "5px 7px 4px"
  stamp-refuted:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    typography: "{typography.stamp}"
    rounded: "{rounded.sm}"
    padding: "5px 7px 4px"
  stamp-open:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
    typography: "{typography.stamp}"
    rounded: "{rounded.sm}"
    padding: "5px 7px 4px"
  reel-tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "9px 13px 8px"
  reel-tab-hover:
    backgroundColor: "{colors.paper-2}"
  reel-tab-active:
    backgroundColor: "{colors.paper}"
  evidence-slip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.data}"
    rounded: "{rounded.hairline}"
    padding: "10px 12px 11px"
  evidence-slip-active:
    backgroundColor: "#ffffff"
  badge-simulated:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.hairline}"
    padding: "3px 6px 2px"
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "8px 10px"
---

# Design System: BLACKBOX

## Overview

**Creative North Star: "The Examiner's Chart Strip"**

A run is a length of salmon-gridded chart paper fed out of a recorder, and the agent is the examiner who marks it up. The paper carries the measurements in pen; the examiner carries the verdict in red. Everything on the surface is either a trace of what the robot did or a mark someone made about it, and the two never blur: instrument ink is navy, blue and violet; judgment is red; refuted ideas are struck through, not erased.

The world is warm, dense and literal. Density is a feature here, the way it is on a strip-chart or a flight-data printout: twelve lanes of signal stacked on a shared time axis, labelled in condensed instrument capitals, with every number in a monospaced readout. The grid is not texture; it is the real time axis (fine lines every 0.2 s, heavy lines every second), so the paper itself is a ruler. Depth is almost absent. Paper lies flat; only physical objects resting on it (the camera viewfinder, a document slip pulled forward, a tooltip) lift with a soft shadow.

The world explicitly refuses the dark, multi-panel log dashboard with a chat sidebar. It also refuses any marker that is not data: no kickers above headings, no ornamental badges, no gradients for mood. The one rubber-stamp texture is earned, because stamping HOLDS or REFUTED on a hypothesis is the examiner's actual act.

**Key Characteristics:**
- Warm chart-paper ground with a red-salmon grid that measures time.
- A pen code: solid navy = measured, dashed blue = commanded, violet = seen by the camera.
- Examiner red reserved for findings, failures, limits and refutations.
- Condensed instrument capitals for labels; monospaced tabular figures for every measured value.
- Rubber stamps with rough ink edges and individual tilt as the verdict on each hypothesis.
- Cancel, never delete: refuted claims stay on the page, struck through.

## Colors

A paper-and-ink palette: warm cream neutrals, a three-pen data code, and one examiner red that means "this is where it went wrong."

### Primary
- **Examiner Red** (examiner-red): the examiner's pen. The failure box on the strip and its label, evidence brackets when a claim is active, HOLDS stamps, active evidence chips, the Failure-moment button, bad-event ticks on the stage lane, and rejected/fallback steps in the examiner's log. 4.8:1 on paper, so it may carry small bold text.
- **Red Wash** (red-wash): the translucent fill inside the failure box, behind a Fix claim (as a left-to-right fade), the Failure-moment button's hover, and the brief flash on a hypothesis when its evidence is cited.
- **Red Line** (red-line): the strike-through on refuted hypotheses and ruled-out claims, and the dashed carry-limit line on the acceleration lane. Red at half strength, so the cancelled statement stays legible underneath.
- **Red on Film** (red-on-film): the brighter red used only where the mark sits on the dark camera image: the hit frame on the film ticker, the rough ring around a tracked object in the viewfinder, and the red window in the logo's waveform. Examiner Red goes muddy on near-black; this is its dark-ground counterpart, not a second accent.

### Secondary
- **Commanded Blue** (commanded-blue): the dashed pen for what the controller asked for (joint and gripper commands). Always dashed (4 3), always beneath the measured trace.
- **Camera Violet** (camera-violet): the pen for object heights seen by the camera tracker, drawn on the Height lane.

### Neutral
- **Chart Paper** (paper): the page ground and the lane interiors. The approved world: warm, never white.
- **Worn Paper** (paper-2): hover ground for tabs and buttons, inline code wells, alternating stage bands, scrollbar track.
- **Stage Band** (paper-3): the darker alternating stage band on the events lane.
- **Clean Sheet** (sheet): the examiner's report column, the top bar, the time ruler and resting buttons; a fresher sheet laid over the chart paper.
- **Grid Fine** (grid): minor time lines (every 0.2 s) and the four horizontal quarter lines in each lane.
- **Grid Second** (grid-major): major time lines at every whole second.
- **Paper Rule** (rule): soft dividers between claims, between reel tabs, and inside the top bar.
- **Paper Rule Dark** (rule-2): structural paper divisions: the top-bar baseline, column split, lane separators, slip borders, the hypothesis-tree spine and dashed hypothesis separators.
- **Navy Ink** (ink): primary text, the measured-signal pen, instrument borders around the strip and buttons, the playhead, the active reel underline and the tooltip ground.
- **Ink Faded** (ink-2): secondary text, refuted stamps, struck-through statements, the simulated badge.
- **Ink Faint** (ink-3): tertiary text: units, ruler figures, captions, test descriptions, section labels. The lightest tone allowed for text (5.1:1 on paper).
- **Pencil** (pencil): the dashed border of an Open (inconclusive) stamp. A line tone only (3.2:1 on paper); never a text color.
- **Film Black** (film-black): the ground behind camera imagery (film ticker, viewfinder).

### Named Rules
**The Examiner's Red Rule.** Red marks a finding, never a resting state. It appears only on the failure box, active evidence brackets, HOLDS stamps, active chips, refutation strikes, limit lines, bad events and the Failure-moment button. Resting chips are ink-outlined; hover and the focus ring may borrow red because they preview the finding.

**The Pen Code Rule.** Solid navy is measured, dashed blue is commanded, violet is what the camera saw. A pen color is a data claim; never reuse one for decoration or swap their meanings between lanes.

**The Warm Ground Rule.** No surface is pure white at rest. White is reserved for a document slip that has been pulled forward as cited evidence.

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow, sans-serif)
**Body Font:** Barlow (with system-ui, sans-serif)
**Label/Mono Font:** JetBrains Mono (with ui-monospace, monospace)

**Character:** Barlow Condensed reads like the stencilled legends on an instrument panel; Barlow is its plain-spoken sibling for prose; JetBrains Mono is the readout. The three come from one engineering register, so the page reads as a single printed instrument rather than an app with a font stack.

### Hierarchy
- **Headline** (600, clamp 25–31px, 1.1, -0.005em, Barlow Condensed): the verdict at the top of the examiner's report, and the run title beside the viewfinder at the same tier (clamp 24–32px, 1.08). Balanced/pretty wrapping. On phones a 21px version of the verdict repeats under the run title.
- **Wordmark** (700, 19px, 0.2em tracking, Barlow Condensed, uppercase): BLACKBOX in the top bar only.
- **Readout** (500, 22px, -0.02em, JetBrains Mono, tabular): the run clock; its "/ total s" suffix drops to 13.5px Ink Faint.
- **Body** (400, 15px, 1.5, Barlow): claims and hypothesis statements (statements at weight 500, 1.35).
- **Body Small** (400, 13.5px, 1.45): run facts, tally, test results, ruled-out items, button labels (500).
- **Caption** (400, 12px): test descriptions, legend, control-run notes, proof line, tooltip text.
- **Section Label** (600, 13.5px, 0.14em, uppercase, Barlow Condensed, Ink Faint): the report's own section headings ("Hypotheses, as tested", "Examiner's log"). They are the heading, not a line above one.
- **Label** (600, 12px, 0.1em, uppercase, Barlow Condensed): lane names, claim kinds (Outcome, Finding, Cause, Ruled out, Fix), slip headers, reel names (13.5px, 0.08em).
- **Stamp** (700, 12px, 0.14em, uppercase, Barlow Condensed): HOLDS / REFUTED / OPEN.
- **Data** (400, 12px, 1.5, JetBrains Mono): document slips, log lines, run ids.
- **Data Small** (500, 12px, JetBrains Mono; live lane values 12.5px): chips, live lane values, ruler figures, bracket tags, units. 12px is the floor for any text on the page.

### Named Rules
**The Readout Rule.** Every measured number, timestamp, id and count is set in JetBrains Mono with tabular figures, even mid-sentence in prose. Words are Barlow; values are mono.

**The Instrument Capitals Rule.** Uppercase is only for Barlow Condensed instrument labels, with tracking between 0.08em and 0.2em. Never uppercase Barlow or the mono.

## Layout

Two columns on desktop: the recording deck on the left (fluid) and the examiner's report on the right (380–470px), split by a Paper Rule Dark line. Above 1100px the report is sticky under the 52px top bar and scrolls on its own, so the verdict stays beside the strip while you scrub. Between 760 and 1100px the report drops below the deck; under 760px the page is a single column with 16px side gutters, the wordmark and examiner credit hide, lane labels shorten, and claims stack their kind label above the text.

The strip is the spine. Every row of the strip (camera ticker, time ruler, each signal lane) shares one label gutter (92px desktop, 66px phone) so all traces start on the same x and time aligns vertically through the whole stack. Horizontal position is time and nothing else; length is duration. Lanes are 41px (48px for Height), 38/44px on phones.

Spacing is a tight instrument rhythm: 6–8px inside controls, 12px between related rows, 18–22px column padding, 30px between major blocks (head to strip, claims to hypothesis tree). The top bar is a single bordered row of cells (brand, reel tabs, examiner), each divided by a rule, with the reel row scrolling horizontally and fading at its edge when more runs exist.

**The Shared Axis Rule.** Anything placed on the strip is positioned by its timestamp against the shared gutter. A mark that is not at a real time does not go on the strip.

## Elevation & Depth

The system is flat paper. Depth comes from paper tone (Chart Paper under Clean Sheet), 1px rules and ink borders, not shadows. Three physical objects lift, each with a soft, warm, negative-spread shadow that reads as an object resting on paper, not as a UI layer.

### Shadow Vocabulary
- **Mounted viewfinder** (`box-shadow: 0 1px 0 rgba(255,255,255,.6), 0 6px 16px -8px rgba(40,30,20,.45)`): the camera frame, as a print pinned to the sheet.
- **Pulled slip** (`box-shadow: 0 0 0 1px var(--red), 0 6px 14px -8px rgba(40,30,20,.35)`): a document slip when it is the cited evidence.
- **Tooltip** (`box-shadow: 0 8px 20px -8px rgba(0,0,0,.5)`): the evidence tooltip floating over the page.

### Named Rules
**The Flat Paper Rule.** Surfaces lie flat. A shadow means a physical object resting on the paper (a mounted photo, a slip pulled forward, a note held over the page) and appears on nothing else.

## Shapes

Corners are nearly square: 2px for paper things (slips, chips, the failure box, the simulated badge, code wells) and 3px for things you press or stamp (buttons, stamps, brackets, tooltip, focus ring). The only circles are the reel status dots (filled navy for a failed run, an outlined ring for a nominal one) and the viewfinder's tracking ring.

Line style carries meaning. A 1px navy border means an instrument (strip frame, lane edges, buttons). A Paper Rule line means a division of the page. A dashed line means unproven or not-in-time: commanded traces, document-only evidence chips, the pencilled spans kept hypotheses rest on, the separators between hypotheses, and the Open stamp. Stamps are the one rotated form: HOLDS at -4°, REFUTED at +3°, OPEN at -2°, each masked with the stamp-ink texture at its own offset so no two impressions match.

**The Dashed Means Unproven Rule.** Solid is measured or decided; dashed is intended, inferred, pencilled or still open.

## Components

### Buttons
Tactile, square, outlined in ink, like the keys on a recorder's transport.
- **Shape:** gently squared (3px), 34px tall; icon-only buttons are 34px squares.
- **Transport (default):** Clean Sheet ground, 1px Navy Ink border, Navy Ink label at 13.5px/500 with a 16px stroked icon and 7px gap.
- **Hover / Active:** ground shifts to Worn Paper; on press the button drops 1px. Transitions 0.15s on the house ease.
- **Failure moment:** the same button with Examiner Red border and label; hover fills with Red Wash. It is the only red control, because it jumps to the finding.
- **Text link (phone verdict):** "Read the examiner's report" in Examiner Red, 14px/500, underlined at 3px offset.

### Chips
- **Style:** inline evidence references (E1, E15) after a claim: transparent ground, 1px Ink Faint outline, Ink Faded mono 12px, 20px tall, 2px corners.
- **State:** hover or active fills Examiner Red with white text (keyboard focus takes the house 2px red focus ring); active chips stay red everywhere that evidence id appears. Document-only evidence (no timestamp) uses a dashed outline.

### Cards / Containers
- **Evidence slip:** the paper documents cited as evidence (workcell notes, scene map). Clean Sheet ground, 1px Paper Rule Dark border, 2px corners, 10/12px padding, a condensed Ink Faint header with the evidence id at right, body in 12px mono. When cited it turns white with a red double edge and the Pulled slip shadow.
- **Report sheet:** the right column itself on Clean Sheet, no card, no border beyond the column rule.
- **Claims list:** a two-column ledger (74px kind label, text) divided by Paper Rule lines; a Fix claim carries a Red Wash fade from the left.

### Navigation
- **Reel tabs:** one tab per recorded run across the top bar. Each is a cell divided by a rule: status dot + condensed uppercase run name (13.5px, 600) above the mono run id in Ink Faint. Hover takes Worn Paper; the current run drops to Chart Paper (as if the bar opens onto the page) with a 3px Navy Ink underline. Horizontal scroll with a 56px fade mask when the row overflows.

### Signature: The Chart Strip
The recording itself. A film ticker of camera frames on Film Black, a mono time ruler, then stacked signal lanes on Chart Paper with the time grid. Each lane has a condensed label and a live mono value in the gutter. Measured traces are 1.35px navy (motors 0.9px at 55%), commanded traces dashed blue, camera tracks 1.5px violet, tracking error drawn as a translucent red band between commanded and measured, limits as a dashed Red Line. The navy playhead with a small triangular head spans the ruler and every lane; the strip is a keyboard slider (arrow keys scrub, space plays).

### Signature: Examiner's Marks
- **Failure box:** a 2px Examiner Red frame with Red Wash fill spanning the failure interval through every lane, labelled in red condensed capitals with its timestamp on a paper chip; when the interval is too thin, the label hangs beside the box. Enters with a 0.6s scale-settle.
- **Evidence bracket:** when a claim is cited, a 2px red bracket wraps the exact lane and time span, tagged with the evidence id on a red mono tab; the matching camera frame gets a red hit frame on the ticker and a rough red ring in the viewfinder. Enters at 0.7s, scaling in from 1.25× width.
- **Pencil marks:** every span a held hypothesis rests on is outlined faintly on the strip in a dashed Ink Faded line at 55%, so the evidence is visible before anything is clicked.

### Signature: Verdict Stamps
Rubber stamps beside each hypothesis: Stamp type in a 2px border of the text color, 3px corners, masked by the stamp-ink texture (`web/stamp-ink.svg`, 80×32px tile) at a per-hypothesis offset. HOLDS is Examiner Red with a doubled inner edge; REFUTED is Ink Faded and its statement is struck through in Red Line; OPEN has a dashed Pencil border. They land in sequence (0.42s, 55ms apart) from 1.7× scale and -12°.

### Simulated Badge
A small condensed SIMULATED tag (12px, 600, 0.14em) with a 1px Paper Rule Dark outline in the run facts. Every synthetic run carries it.

## Do's and Don'ts

### Do:
- **Do** keep the page ground Chart Paper and the report column Clean Sheet; the warm paper is the approved world.
- **Do** reserve Examiner Red for findings: failure box, active brackets, HOLDS stamps, active chips, refutation strikes, limit lines, bad events, the Failure-moment button.
- **Do** outline resting chips in ink and let them fill red only when hovered or active.
- **Do** draw the chart grid only inside the strip lanes, at real time intervals (0.2 s fine, 1 s heavy).
- **Do** set every measured value, id and timestamp in JetBrains Mono with tabular figures.
- **Do** keep refuted hypotheses on the page, struck through in Red Line and stamped REFUTED.
- **Do** position every strip mark by its timestamp against the shared label gutter (92px, 66px on phones).
- **Do** use Red on Film, not Examiner Red, for any mark drawn over camera imagery.
- **Do** honor reduced motion: stamps, brackets, the failure box and flashes all collapse to instant.

### Don't:
- **Don't** build a dark, multi-panel log dashboard with a chat sidebar; this world is paper.
- **Don't** put an eyebrow or kicker line above the verdict, the run title or any heading.
- **Don't** use Examiner Red for resting states, decoration, brand accents or generic emphasis.
- **Don't** reuse a pen color (navy, dashed blue, violet) for anything that is not that kind of data.
- **Don't** set text in Pencil; the lightest text tone is Ink Faint.
- **Don't** add shadows to flat paper surfaces, cards or lanes; only the viewfinder, a pulled slip and the tooltip lift.
- **Don't** delete or hide a refuted hypothesis to tidy the report.
- **Don't** round corners past 3px or introduce pill shapes outside the reel status dots.

## Failure jump and evidence links (interaction contract)

- **Failure moment** (button, `F` key, or `#run=<id>&jump=1`) sweeps the playhead to the failure's start. It brackets every strip lane the symptom's evidence lives on and turns those lane labels red. It also outlines the ticker frame, rings the tracked object on the camera when there is one, and lights the verdict's Finding with a red wash and a red kind label.
- **An evidence chip** does the reverse. It moves the strip, the frame and any cited document to the evidence, and lights every verdict line that cites it.
- Lit lines use a red wash (`rgba(195, 48, 27, .11)`), never a colored side border. The Fix line rests on Paper 2 so it never reads as lit.

