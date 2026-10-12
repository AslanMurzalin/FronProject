# CS2 FACEIT Baiting Analyzer — Project Scope

**Document type:** MVP product specification
**Status:** Scope defined (v0.2); open items listed in §9
**App version:** To be assigned
**Primary goal:** Help users review a selected CS2 player's T-side behavior in a FACEIT demo and judge whether recurring behavior may indicate baiting.

> Items marked **(proposed)** are my suggested defaults that have not been explicitly confirmed. Everything else was decided in the scope discussion.

## 1. Product Overview

The application analyzes a user-uploaded CS2 demo and produces an evidence-based tactical report for **one selected player**.

The report should help users distinguish potentially selfish behavior from legitimate roles and situations, such as entry fragging, lurking, or playing for team objectives. It must present concrete evidence and explain uncertainty rather than claiming it can determine a player's intent with certainty.

### Core principles

- Evidence first: provide round references, timestamps, observed events, and explanations.
- Separate **observed facts** from **interpretations**.
- Treat the baiting score as a heuristic indicator, not an objective measurement of intent.
- Do not label a player a baiter based on K/D, ADR, death count, or death order alone.
- Identify uncertainty and explain when important evidence is missing.
- Keep the MVP focused on T-side analysis on Mirage.

## 2. MVP User Flow

1. The user creates an account or signs in.
2. The user uploads a CS2 demo file and optionally types a match name.
3. The app validates that the demo is supported and contains usable data for the MVP.
4. The app shows the player roster from the demo; the user selects one player (identified by SteamID).
5. The app analyzes the demo and provides processing status.
6. The demo file is deleted when the job ends (success or failure).
7. The user opens the resulting report.
8. The report presents a preliminary baiting score, tactical summaries, and timestamped evidence.
9. The report is saved to the user's history.
10. The user can view, export, or delete reports from history.

To analyze a different player, a newer demo version, or to retry a failed analysis, the user uploads the demo again.

## 3. MVP Features

### 3.1 Accounts and authentication

- Accounts are required.
- Authentication uses email and password.
- Each user has their own private report history.
- **Account deletion is included** and removes the account and all its reports.
- Steam login is not included.
- **Known limitations (accepted for MVP):** no email verification and no password reset. A forgotten password means the history is inaccessible.

### 3.2 Demo upload and compatibility

- Users manually upload demo files; entering a FACEIT match URL is not an MVP input method.
- **Accepted formats:** raw `.dem` and `.dem.zst`.
- **Size limit:** demos up to **350 MB** are supported; larger files are rejected with a clear message. A cap on decompressed size is also enforced to guard against decompression bombs (exact value open, see §9).
- **Match name:** the user may type a name at upload; if left empty, a default is generated automatically from map, date, and final score (for example "Mirage 2026-10-12, 13-9").
- Validate compatibility before expensive analysis.
- The MVP supports CS2 demos that the selected parser can read.
- The MVP supports **Mirage only**.
- Reject unsupported demos early and explain why, where possible.
- Confirm that usable player and round data are available before analysis begins.

### 3.3 Player selection

- Analyze one selected player per report.
- After validation, the app lists the players found in the demo; selection is by SteamID.
- Comparing players side by side or analyzing multiple players in one report is out of scope for the MVP.

### 3.4 Tactical analysis

Analyze **all T-side rounds**, considering each round independently before aggregating findings across the match.

- **Scope of rounds:** all rounds where the selected player is on T side, including both halves after side swaps and **overtime**.
- **Skipped rounds:** rounds in which the selected player disconnects or is replaced by a bot are **skipped** and noted in the report.
- The report header shows how many T rounds were analyzed out of the total and how many were skipped, with reasons.

The analysis should identify and evaluate, where evidence allows:

- Round phases and situations: defaults, executions, lurks, and other situations.
- Player movement and transitions between map zones.
- Participation in team executions.
- Lurk activity and its apparent effectiveness.
- Potential trading opportunities and possible missed trades.
- Death order in context.
- Recurring behavioral patterns across rounds.

These categories may describe different phases within the same round and are not necessarily mutually exclusive.

#### Execution detection

Infer likely executions from a combination of three signals:

1. **Utility timing** — smokes and flashes thrown near a site.
2. **Zone-graph route** — movement toward a site along the zone graph.
3. **Group position clustering** — three or more players in the same zone.

Do not rely on one signal alone. **(Architecture 2.1 required to change it)** Label a phase "execution" only when **utility timing** agrees with at least one spatial signal (**zone-graph route** or **group position clustering**); otherwise label it "unknown / low confidence". Known limitation: utility-free site rushes are classified as fast defaults/rushes, not executions. First-contact location is not used in v1.

#### Lurk effectiveness

For the MVP, focus on kills, with particular attention to kills against rotating defenders. This is an initial, limited measure — not a complete measure of lurk value.

#### Trading

Use teammate death proximity and a short timing window to identify **potential** trade opportunities:

- **Rule:** a teammate dies within **3 seconds** and within about **800 units** of the selected player.
- **(proposed operationalization)** An opportunity exists if the selected player is alive and within ~800 units at the teammate's death. It counts as a **missed** opportunity if the player does not kill the teammate's killer within 3 seconds afterward.
- Without line-of-sight modeling, every trade finding carries a low or medium confidence label.

A missed opportunity is evidence to review, not automatic proof of baiting.

#### Death order and team participation

Interpret death order alongside role, positioning, timing, team movement, and opportunities to contribute. Dying first may be legitimate entry fragging; surviving longer is not automatically suspicious.

### 3.5 Map representation

- Use a **zone graph** for Mirage.
- Zones are nodes; walkable connections are edges.
- **Zones are derived from the map's navigation mesh**, with nav mesh areas grouped into named tactical zones at a moderate level of detail — not tiny, overly granular areas.
- A one-time manual labeling pass maps nav areas to named zones. A validation script must confirm that every nav area is assigned to exactly one zone.
- Reconstruct movement routes through the graph.
- Initial zone concepts include T spawn, mid, lower mid, catwalk/short, connector, A site, palace, ramp, CT, window, market/kitchen, B site, B apartments, underpass, and ladder room.
- The zone data stores a **map version**, which is recorded in each report. Final zone boundaries and connections must be verified against the actual map data.
- Before shipping, confirm that the nav file can be obtained from the current game files and that Valve's terms allow the intended use.

A predefined library of tactical routes is not required for the MVP.

### 3.6 Report contents and scoring

The report includes:

- A preliminary baiting score from **1 to 100**.
- Category summaries linked to a chronological evidence timeline.
- Concrete examples with round number and timestamp.
- An explanation of why each event may be relevant.
- Lurk effectiveness, execution participation, trading evidence, death order, and recurring patterns.
- Confidence labels: **low, medium, or high**.
- Notes about missing evidence and uncertainty.
- A clear distinction between observed facts and inferred interpretations.
- Rounds analyzed / skipped (see §3.4).
- Versions used: **app version, scoring-weights version, and map version**.

#### Score design

The score is produced from **weighted sub-signals** combined into 1–100:

| Sub-signal | Expected direction |
|---|---|
| Missed trade opportunities | More misses raise the score |
| Death order / timing in context | Context-dependent; interpreted alongside role and team movement |
| Execution participation | Low participation raises the score |
| Lurk output (kills vs rotators) | Strong lurk output lowers the score |

- Weights live in a single configuration file and carry a version that is saved with every report.
- Initial weights are heuristic guesses until validated against reviewed demos (see §9).
- **(proposed)** Sub-signals are normalized per round so the score does not scale with match length (important because overtime rounds are included).
- Each sub-signal's contribution is shown in the report so the score is explainable and linked to supporting evidence.
- The score must not be presented as proof of intent or as a definitive verdict.

#### Insufficient evidence

When there is too little evidence (few T rounds analyzed, few trade opportunities, many skipped rounds), the report shows a **low score** and **explicitly states that there is too little evidence**. **(proposed)** The report also shows a prominent banner, forces a low confidence label, and lists which sub-signals lacked data, so a low number is not read as "clean player." The threshold for "too little evidence" is open (see §9).

### 3.7 Processing status and failures

- Demo analysis runs as a background job.
- After upload, the user receives a job identifier and can see the processing status.
- Show named stages:
  1. Parsing demo
  2. Building player timelines
  3. Analyzing rounds
  4. Generating report
- Do not display a fabricated percentage if reliable progress cannot be calculated.
- On failure, show a clear error, preserve a record of the failed analysis in history (error, failing stage, app version), and let the user **retry by re-uploading** the demo.

### 3.8 Report history, export, and privacy

The report history list shows:

- Match name
- Player nickname
- Analysis date
- Baiting score
- App version

Users can:

- Open saved reports.
- **Export a report as PDF or JSON.**
- Delete an individual report.
- Clear their entire report history.
- Delete their account (removes all reports).

**Privacy:** reports are **private to their owner**; there are no share links in the MVP. Every export carries the same safeguards as the report itself: "heuristic, not proof" statement, confidence labels, app / weights / map versions, and the skipped-rounds note.

### 3.9 Data retention

- **Demo files are not stored.** They exist only temporarily while the job runs and are deleted when processing ends, whether it succeeds or fails.
- Only the report and its version information are saved.
- Reports remain in history until the user deletes them or deletes their account.
- Abandoned uploads and jobs interrupted by a server shutdown are cleaned up by a short-TTL cleanup job (exact TTL open, see §9).

## 4. Explicitly Out of Scope for the MVP

- CT-side tactical analysis.
- FACEIT match URL import.
- Steam login.
- Email verification and password reset.
- Report sharing links.
- Storing demo files or parsed match data for later reanalysis.
- Comparing two players side by side.
- Analyzing multiple selected players in a single report.
- Maps other than Mirage.
- Automatic claims that a player is definitively baiting.
- A predefined tactical-route library.
- Advanced line-of-sight and weapon-state modeling for trade opportunities.
- A complete multi-factor model of lurk impact.
- Desktop application development unless later evidence shows it is needed.

## 5. Future Backlog

These ideas are deliberately retained for later phases and are **not MVP requirements**.

### Phase 2 — Deeper tactical impact

- Measure space creation and information gathering.
- Evaluate rotation disruption and lurk timing.
- Combine kills with round outcome and other tactical-impact metrics.
- Improve trade-opportunity detection using visibility, line of sight, weapon state, and additional context.
- Improve execution and phase classification (including first-contact location).
- Consider support for additional maps.

### Phase 3 — Advanced analysis and validation

- Infer likely player roles from repeated behavior.
- Recognize more adaptive tactical patterns.
- Calibrate confidence, weights, and heuristics using reviewed demos.
- Improve report quality based on user feedback and validated examples.

### Additional future considerations

- Analyze multiple players from one demo.
- Compare players side by side.
- Steam authentication, email verification, password reset.
- Retain compact parsed match data to make reanalysis easier without retaining the original demo.
- Report sharing.
- Consider a desktop app only if practical testing shows local processing would provide a meaningful benefit.

Keep the backlog visible and distinguish features that are **not implemented**, **experimental**, or **validated**. A heuristic should not silently become a firm rule without testing.

## 6. Product and Analysis Guardrails

- Never treat a high or low K/D, ADR, death count, or death order as sufficient proof of baiting.
- A potential missed trade is not proof of baiting.
- Lack of utility usage or not being first into a site is not proof by itself.
- Account for role, position, timing, team movement, and the opportunity available.
- Preserve useful uncertain events when relevant, but label their confidence and explain what is missing.
- Prefer transparent evidence over unsupported certainty.
- Make the report useful for a human reviewer who will make the final judgment.

## 7. Implementation Notes — Non-Binding

- `demoparser2` is a candidate for extracting CS2 demo data.
- The pipeline can be organized into upload validation, parsing, player timelines, round analysis, evidence generation, and report storage.
- Delete the original demo when processing finishes, including when processing fails.
- Enforce size limits on both the compressed upload and the decompressed result.
- Include cleanup for abandoned uploads or jobs after unexpected server shutdowns.
- Keep scoring weights, trade thresholds, and execution thresholds in versioned configuration, not hard-coded.
- Choose queueing, storage, and infrastructure based on implementation needs rather than treating a specific technology as a scope requirement.

## 8. MVP Acceptance Checklist

- [ ] Users can register and sign in with email and password.
- [ ] Users can delete their account, which removes all their reports.
- [ ] Users can upload a supported CS2 Mirage demo (`.dem` or `.dem.zst`, up to 350 MB).
- [ ] Oversized or unsupported demos are rejected with a useful explanation.
- [ ] Users can type a match name at upload; a default is generated if left empty.
- [ ] Users can pick one player by SteamID from the demo's roster.
- [ ] Analysis covers all T-side rounds, including overtime.
- [ ] Rounds with a disconnect or bot takeover are skipped and noted in the report.
- [ ] The report includes a preliminary 1–100 score built from the four weighted sub-signals, with each sub-signal's contribution visible.
- [ ] The report includes timestamped, round-specific evidence.
- [ ] Category summaries link to the chronological evidence timeline.
- [ ] Facts, interpretations, confidence, and missing evidence are distinguished.
- [ ] With too little evidence, the report shows a low score and explicitly says so.
- [ ] Processing status and failures are visible; failed analyses are kept in history and can be retried by re-uploading.
- [ ] Demo files are deleted when processing ends (success or failure) and are never stored long-term.
- [ ] Reports are saved to the correct user's history and are private to that user.
- [ ] History displays match name, player nickname, analysis date, score, and app version.
- [ ] Users can export a report (PDF/JSON) with the safeguards included.
- [ ] Users can delete one report or clear their history.
- [ ] Each report records the app version, scoring-weights version, and map version.

## 9. Open Items

| Item | Notes |
|---|---|
| Validation set | Assemble 10–20 hand-reviewed Mirage demos to sanity-check scores, thresholds, and weights before release |
| Initial weights | Values for the four sub-signals; start as guesses, tune against the validation set |
| "Too little evidence" threshold | Minimum analyzed T rounds / trade opportunities below which the banner is shown |
| Execution rule | **(Architecture 2.1 required to change it)** Utility timing plus at least one spatial signal (route or clustering). Known limitation: utility-free rushes are not executions. |
| Trade operationalization | Confirm the proposed "alive within ~800 units, no kill of the killer within 3 s" definition |
| Per-round normalization | Confirm the proposed normalization of sub-signals |
| Decompressed size cap | Exact value for the `.dem.zst` limit |
| Temp-file TTL | How long abandoned uploads live before cleanup |
| Nav mesh availability and licensing | Verify the file is obtainable and usable before building the zone graph |
| Nav-to-zone mapping | One-time manual labeling pass plus completeness check |

## 10. Decision Log (this discussion)

| Topic | Decision |
|---|---|
| Demo retention | Do not store demos; keep only the report and version info |
| Score design | Weighted sub-signals combined into 1–100 |
| Sub-signals | Missed trades, death order/timing, execution participation, lurk output |
| Execution detection | Utility timing, zone-graph route, group clustering (no first-contact) |
| Trade opportunity | Teammate dies within 3 s and ~800 units |
| Match name | User-typed, auto-generated default |
| Thin evidence | Low score plus explicit "too little evidence" statement |
| Accounts | Account deletion in; email verification and password reset out |
| Upload formats | `.dem`, `.dem.zst` |
| Size limit | 350 MB, larger rejected |
| Zone graph | Derived from the nav mesh |
| Disconnect / bot | Skip those rounds and note it |
| Round coverage | All T rounds including overtime |
| Sharing | Private; PDF/JSON export included |

**Scope rule:** If a feature is not listed as an MVP requirement, treat it as out of scope unless the product scope is deliberately updated.
