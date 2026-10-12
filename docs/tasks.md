# CS2 FACEIT Baiting Analyzer — Development Tasks Backlog

**Version:** 3.0
**Target Specification:** `docs/plan.md` and `docs/architecture.md` (v2.1)
**Task Standard:** Each task is sized for a single working session and is independently actionable.

## 1. Project Scaffolding & Initial Smoke Test
Goal: Set up the root project structure, Python virtual environment, dependencies configuration, and a passing smoke test.
Description: This task establishes the backend directory layout (`backend/app`), pins core dependencies in `requirements.txt` / `pyproject.toml` (FastAPI, SQLAlchemy, demoparser2, polars, pydantic, pytest), and configures pytest. It confirms the virtual environment is working properly on the host system.
Done when:
- Project directories (`backend/app`, `backend/tests`) and dependency files are created.
- Virtualenv runs `pytest` successfully on a minimal smoke test asserting environment and library imports.
- Tests required: `backend/tests/test_smoke.py` asserting Python version, imports, and test runner execution.

## 2. Real-Demo Parser Spike & Event Inspection
Goal: Parse a real CS2 Mirage demo with `demoparser2` and document the exact event schemas and fields available.
Description: This task conducts an early spike on a real CS2 `.dem` file to identify the precise tick events, player coordinates, death records with damage/killer causes, grenade throws, bomb plants, and bot takeovers returned by `demoparser2`. The findings will be documented in `docs/parser_spike.md` to guide the data model and test fixtures.
Done when:
- A test script parses a real demo and logs raw outputs for player ticks, death events, and utility events.
- `docs/parser_spike.md` is produced detailing event names, column types, coordinate formats, and bot takeover representations.
- Tests required: `backend/tests/test_parser_spike.py` verifying raw extraction of ticks, deaths, and grenade events on a sample demo file.

## 3. Database Engine & Relational Schema Setup
Goal: Configure SQLite with Write-Ahead Logging (WAL) and create SQLAlchemy 2.0 ORM models for all system entities.
Description: This task configures the SQLite engine with WAL mode, `PRAGMA busy_timeout = 5000;`, and declarative models in `app/db/`. You will define the ORM schemas for `Users`, `Sessions`, `Uploads`, `Jobs`, and `Reports` including UUID primary keys, foreign keys, cascade deletes, and heartbeat timestamps.
Done when:
- SQLite connection event listeners apply WAL mode, busy timeout, and foreign keys.
- ORM models (`User`, `Session`, `Upload`, `Job`, `Report`) are defined with type annotations and indices.
- Tests required: `backend/tests/test_database.py` verifying tables create cleanly, WAL pragma is active, and cascade deletions work.

## 4. Cookie-Based Session Authentication & Session Hygiene API
Goal: Implement user registration, Argon2id password hashing, httpOnly session cookies, and session invalidation.
Description: This task builds `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me`. Session tokens are stored in the `SESSIONS` table with a configurable `SECURE_COOKIE` flag (disabled in local dev), an Origin header check on state-changing routes, and a query to purge expired sessions.
Done when:
- Registration, login, logout, and current user endpoints return correct schemas and manage `SESSIONS` rows.
- Auth cookies are set with `httpOnly`, `SameSite=Lax`, and configurable `Secure` flag; logout deletes the session row.
- Tests required: `backend/tests/test_auth.py` testing registration, invalid login, valid login session persistence, logout revocation, and Origin check validation.

## 5. Account Deletion & Resource Teardown API
Goal: Implement the `/api/account` endpoint to cancel active jobs, remove user scratch files, and delete all user records.
Description: This task implements `DELETE /api/account` to remove the authenticated user and all associated sessions, uploads, jobs, and reports. It identifies any running jobs for that user, triggers their cancellation flag, and unlinks all demo scratch files owned by the user.
Done when:
- `DELETE /api/account` revokes the user's session, flags active jobs as cancelled, and removes user records.
- Associated scratch files on disk for the user's uploads are deleted immediately upon account deletion.
- Tests required: `backend/tests/test_account_deletion.py` verifying full database cascade and file removal on disk.

## 6. Reverse-Proxy Rate Limiting & User Quotas
Goal: Integrate IP rate limiting, trusted reverse-proxy headers, active upload limits, and daily analysis quotas.
Description: This task configures `slowapi` to enforce an IP rate limit of 5 uploads per minute, reading client IPs via trusted proxy headers (`forwarded_allow_ips`). It also enforces business rules limiting each user to at most 1 active upload concurrently and a daily quota of 10 completed analyses.
Done when:
- Rate limiter middleware handles `X-Forwarded-For` with trusted proxy validation.
- Endpoints reject requests exceeding 5/min per IP, 1 concurrent upload per user, or 10 analyses per user per day with HTTP 429.
- Tests required: `backend/tests/test_quotas.py` testing IP rate limiting, concurrent upload rejection, and daily quota exhaustion.

## 7. Ephemeral Scratch Disk & Storage Quota Manager
Goal: Implement storage helpers for scratch directories with strict host disk and folder quota guards.
Description: This task builds a storage manager managing files in `var/scratch_demos/`. It verifies that host free disk space is at least 5 GB and total scratch folder usage does not exceed 10 GB before accepting new files, rejecting writes with HTTP 507, and provides a utility to delete abandoned files older than 1 hour.
Done when:
- Storage helper provides safe file path generators, quota checks, and cleanup routines.
- Operations fail gracefully with `InsufficientStorageError` when disk free space or directory quota thresholds are breached.
- Tests required: `backend/tests/test_storage_manager.py` verifying path isolation, mock disk full rejections, and TTL cleanup.

## 8. Demo Upload Streaming, Byte-Counting & Decompression Caps
Goal: Build `/api/uploads` to stream demo archives with active byte counting and a 1.2 GB decompression limit.
Description: This task implements multipart file streaming for `.dem` and `.dem.zst` files, counting bytes chunk-by-chunk and aborting with HTTP 413 if the stream exceeds 350 MB. For `.dem.zst` files, it performs streaming decompression with `zstandard`, enforcing a strict 1.2 GB cap on uncompressed bytes and auto-generating a default match name if blank.
Done when:
- Upload endpoint accepts valid archives up to 350 MB and aborts oversized streams chunk-by-chunk without loading full files into memory.
- Decompression aborts immediately if decompressed data exceeds 1.2 GB; default match name is generated from metadata.
- Tests required: `backend/tests/test_upload_streaming.py` testing normal uploads, chunked 350 MB cutoff, and decompression bomb cutoff.

## 9. Offloaded Roster Extraction & Roster Caching
Goal: Extract player SteamIDs and nicknames in an executor thread with an `asyncio.Semaphore(1)` guard and cache the roster.
Description: This task implements match participant extraction from the uploaded demo using `demoparser2` wrapped in `asyncio.to_thread` to prevent event-loop blocking. The extraction is protected by a semaphore of size 1, validates that the map is `de_mirage`, and caches the roster JSON on the `Upload` model.
Done when:
- Uploaded demos are checked for `map == "de_mirage"`, rejecting non-Mirage demos with HTTP 400 (`INVALID_MAP`).
- Extracted players (SteamID and nickname) are saved to `Upload.cached_roster` without blocking other HTTP endpoints.
- Tests required: `backend/tests/test_roster_extraction.py` testing Mirage roster extraction, non-Mirage rejection, and non-blocking executor execution.

## 10. Internal Match Domain Model & Parser Adapter
Goal: Define strongly typed match dataclasses and build an adapter converting raw `demoparser2` outputs into internal entities.
Description: This task creates dataclasses for `ParsedMatch`, `ParsedRound`, `ParsedDeath`, `ParsedUtility`, and `PlayerTick` in `app/services/analysis/models.py`. An adapter parses raw `demoparser2` event dictionaries into these structured models, normalizing coordinates, weapons, death causes, and bomb plant states.
Done when:
- Internal match dataclasses are fully specified with strict typing.
- Adapter function successfully transforms raw demoparser dictionary outputs into validated domain objects.
- Tests required: `backend/tests/test_parser_adapter.py` asserting proper mapping and normalization of sample ticks, kills, and bomb plants.

## 11. Golden Mock Demo Fixtures for Unit Testing
Goal: Generate lightweight JSON mock event fixtures based on the parser spike to support deterministic unit tests.
Description: This task constructs realistic JSON fixture files in `backend/tests/fixtures/` representing parsed match data. These fixtures will cover trade situations, site executions, lurk kills, disconnects, warmup periods, and overtime rounds, allowing all subsequent tactical evaluators to be tested without binary demo files.
Done when:
- Fixture files (`match_mirage_standard.json`, `match_trades.json`, `match_executes.json`, `match_disconnects.json`) are created.
- A fixture loader utility loads and deserializes fixtures into the internal `ParsedMatch` domain model.
- Tests required: `backend/tests/test_fixtures.py` verifying that all mock fixtures load into domain objects without schema errors.

## 12. Mirage Tactical Map Spike & Zone Boundary Fallback
Goal: Conduct a spike on `de_mirage.nav` parsing versus a 2D polygonal fallback to resolve 3D coordinates into zones.
Description: This task investigates parsing nav-mesh polygons from `de_mirage.nav`. If the binary structure presents high maintenance or library overhead, it implements the fallback using `shapely` 2D polygon bounding regions representing the 15 tactical zones of Mirage, documenting the chosen approach.
Done when:
- Spike report in `docs/nav_mesh_spike.md` evaluates `.nav` parsing feasibility versus 2D bounding polygons.
- Coordinate resolver correctly determines the tactical zone for landmark Mirage positions (e.g., A Ramp, Window, B Apartments).
- Tests required: `backend/tests/test_zone_spike.py` verifying coordinate-to-zone resolution for known Mirage landmarks.

## 13. Mirage 15-Zone Tactical Graph & Spatial Lookup Service
Goal: Implement the 15 connected tactical zones of Mirage and their walkable adjacency graph.
Description: This task establishes the 15 connected tactical zones (T Spawn, Mid, Lower Mid, Underpass, Catwalk/Short, Connector, Window, Ladder Room, A Ramp, Palace, A Site, CT Spawn, B Site, B Apartments, Market) as discrete graph nodes with valid walkable edges. It exposes a lookup method to resolve any `(x, y, z)` coordinate tuple to its zone and retrieve adjacent zones.
Done when:
- Zone graph is constructed with 15 nodes and verified topological adjacency edges.
- `get_zone(x, y, z)` resolves player positions accurately, returning `"Unknown"` for out-of-bounds coordinates.
- Tests required: `backend/tests/test_zone_graph.py` testing spatial lookups and graph edge connectivity between adjacent zones.

## 14. Round Boundary & Match State Filtering
Goal: Filter demo events to extract official regulation and overtime T-side rounds while discarding warmups, resets, and pauses.
Description: This task writes the round boundary filter in `app/services/analysis/round_filter.py`. It uses game event state flags (`round_start`, `round_freeze_end`, `round_end`, `is_warmup_period == False`) to discard warmup rounds, halftime resets, and technical pauses, capturing only official match rounds.
Done when:
- Warmup rounds and match restarts are eliminated from the round sequence.
- Overtime rounds and side-swap halves are correctly extracted and indexed.
- Tests required: `backend/tests/test_round_filter.py` testing filtering against mock matches containing warmup rounds and overtime.

## 15. Player Disconnect & Bot Takeover Filtering
Goal: Identify T-side rounds where the selected player was disconnected or replaced by a bot and record them as skipped rounds.
Description: This task inspects player presence flags, team assignments, and bot takeover events across all T-side rounds. Any round where the selected player was absent or controlled by a bot is tagged as skipped with a descriptive reason, and the job fails if zero analyzable T rounds remain.
Done when:
- Rounds with player disconnects or bot takeovers are flagged and recorded with reasons in `skipped_rounds`.
- Pipeline raises `NoAnalyzableRoundsError` if all T rounds were disconnected.
- Tests required: `backend/tests/test_disconnect_filter.py` testing skip classification and zero-round error conditions.

## 16. T-Side Player Spatial Trajectory Reconstruction
Goal: Reconstruct tick-by-tick coordinate timelines and zone transitions for the selected player in each T-side round.
Description: This task builds chronological position trajectories for the selected player across each analyzed round. It samples coordinates at 1-second intervals, maps them to tactical zones, and records discrete zone transition events.
Done when:
- Player trajectory contains sequential timestamps, coordinates, and zone IDs for all analyzed rounds.
- Zone transition events (e.g. T Spawn -> T Roof -> A Ramp) are chronologically logged.
- Tests required: `backend/tests/test_player_trajectories.py` testing trajectory creation and transition detection from mock ticks.

## 17. CT Defender Anchor & Rotator Detection Engine
Goal: Identify CT initial anchor sites during early round time and detect when defenders vacate their sites to rotate.
Description: This task tracks all 5 CT players during the first 25 seconds of each round to determine their starting anchor sites (A, Mid, or B). It monitors departures from these anchor zones toward the active contested site to flag specific CT players as active rotators.
Done when:
- Initial CT anchor positions are resolved during the freeze/early phase.
- Departure events toward opposite sites tag players with `is_rotator = True` alongside rotation timestamps.
- Tests required: `backend/tests/test_rotator_detection.py` testing anchor assignment and rotator detection on rotation event fixtures.

## 18. Trade Opportunity Evaluator
Goal: Implement trade opportunity detection based on the 800-unit, 3.0-second window with teammate trade handling.
Description: This task detects when a teammate dies within 800 units and 3.0 seconds of the alive selected player, filtering out non-player deaths (fall, bomb, teamkill). It classifies the outcome as traded by selected player, traded by teammate, or missed trade.
Done when:
- Teammate deaths trigger trade candidate windows based on 800 Euclidean units and 3.0 seconds.
- Deaths from fall damage, bomb explosions, and world damage are excluded; teammate trades are credited without penalty.
- Tests required: `backend/tests/test_trade_detector.py` testing trade detection, non-player death exclusions, and team-trade outcomes.

## 19. Site Execution Detection Engine
Goal: Detect offensive site executions requiring utility deployment plus at least one independent spatial signal.
Description: This task detects site executions when $\ge 2$ smokes/flashes land at a bomb site within 6 seconds alongside either $\ge 3$ Ts on approach routes or $\ge 3$ Ts clustered in the site entry zone. It evaluates whether the selected player participated in the execute, excluding utility-free rushes.
Done when:
- Executes are recognized only when utility criteria plus at least one spatial signal are met.
- Player participation is evaluated based on the player being present on the execute route or site during the window.
- Tests required: `backend/tests/test_execution_detector.py` testing execute detection, utility-free rush exclusion, and participation flags.

## 20. Lurk Output Evaluator (Mitigating Factor)
Goal: Measure the impact of isolated play by tracking kills against confirmed rotating CT defenders as a mitigating term.
Description: This task detects rounds where the player operated in an isolated zone away from the main team concentration. It calculates lurk effectiveness based on kills secured against confirmed CT rotators, designed as a mitigating factor that reduces suspicion rather than penalizing non-lurkers.
Done when:
- Isolated rounds outside team clusters are identified.
- Kills on confirmed rotators are credited; rounds with 0 isolated play return a neutral outcome rather than a penalty.
- Tests required: `backend/tests/test_lurk_analyzer.py` testing isolated round detection, rotator kill crediting, and non-lurker neutrality.

## 21. Contextual Death-Order & Survival Evaluator
Goal: Evaluate player death timing while recognizing entry fragging and excluding post-plants and save situations.
Description: This task analyzes death order in team context, classifying deaths in the first 30 seconds inside entry zones as entry frag attempts. Late survival is only flagged if unassisted in lost rounds, strictly excluding rounds where the bomb was planted or the player was saving equipment.
Done when:
- First deaths in entry areas are tagged as entry frags without penalty.
- Late survival flags only occur in lost rounds with zero trades, excluding post-plants and save situations.
- Tests required: `backend/tests/test_death_order.py` testing entry frag tagging, post-plant exclusions, and save situation exclusions.

## 22. Sub-Signal Sample Size Thresholds & Bounding
Goal: Apply minimum sample thresholds per sub-signal, exclude lurk rounds from execution denominator, and bound metrics.
Description: This task enforces minimum sample sizes ($\ge 3$ trade opportunities, $\ge 3$ team executions, $\ge 2$ isolated rounds; below which the signal is marked `no_data`). It excludes lurk rounds from the execution denominator to prevent double-penalizing lurkers and bounds all active sub-signals to $[0.0, 1.0]$.
Done when:
- Sub-signals with samples below minimum thresholds return `no_data` (`null`).
- Lurk rounds are excluded from the execution denominator; all active metrics are bounded between 0.0 and 1.0.
- Tests required: `backend/tests/test_sub_signals.py` testing threshold cutoffs, lurker execution exclusion, and bounding.

## 23. Weight Renormalization & Low-Evidence Guardrail
Goal: Dynamically renormalize active weights, calculate the 1–100 score, and apply low-evidence guardrails.
Description: This task renormalizes weights across active sub-signals ($\sum w_i' = 1.0$) and calculates the clamped 1–100 score. If analyzed rounds $N_T < 6$ or fewer than 2 informative sub-signals are active (excluding $S_{\text{death}}$), it caps the score under 25 and sets `insufficient_evidence = True`.
Done when:
- Dropped sub-signals trigger dynamic weight renormalization among remaining active metrics.
- Low-evidence guardrail caps score $< 25$, sets confidence to `"low"`, and activates the warning flag when thresholds are breached.
- Tests required: `backend/tests/test_scoring.py` testing renormalization math, low-evidence triggers, and config snapshot assembly.

## 24. Fact vs. Interpretation Evidence Timeline Formatter
Goal: Structure round-by-round tactical findings into an evidence timeline separating observed facts from interpretations.
Description: This task formats chronological timeline items with round number, tick timestamp, zone, factual event description, and tactical interpretation. Each item includes a confidence tag (`low`, `medium`, `high`) and documents missing evidence such as unverified line of sight.
Done when:
- Timeline items strictly separate factual observation text from tactical interpretation text.
- Every evidence entry includes confidence labels, timestamps, zone names, and missing evidence notes.
- Tests required: `backend/tests/test_evidence_formatter.py` asserting schema compliance and separation of facts from interpretations.

## 25. Worker Job Claiming & Heartbeat Monitor
Goal: Implement atomic job claiming via SQL `UPDATE ... RETURNING` and a 10-second heartbeat updater in the worker process.
Description: This task implements the worker queue loop that atomically claims pending jobs from the database using `UPDATE jobs SET status='processing', heartbeat_at=... WHERE id = (...) RETURNING *`. The worker updates `heartbeat_at` every 10 seconds while running to indicate active health.
Done when:
- Worker claims pending jobs atomically without race conditions between worker processes.
- Worker updates `heartbeat_at` on the active job row periodically during task execution.
- Tests required: `backend/tests/test_worker_claiming.py` testing atomic claiming, concurrency limits, and heartbeat timestamps.

## 26. Worker Leader Startup Recovery & Orphan Sweeper
Goal: Implement startup recovery to mark stale interrupted jobs as failed and sweep orphan scratch directories.
Description: This task adds startup logic executed solely by the worker leader process. It queries for jobs left in `processing` with heartbeats older than 60 seconds, marks them as failed with an explanatory message, and sweeps `var/scratch_demos/` for directories older than 1 hour.
Done when:
- Stale jobs with expired heartbeats are marked as failed on worker startup without affecting active jobs.
- Orphan scratch directories older than 1 hour are cleaned up from disk by the worker leader.
- Tests required: `backend/tests/test_worker_recovery.py` testing stale job recovery and orphan file sweeping.

## 27. Pipeline Orchestrator & Zero-Retention Cleanup
Goal: Wire the 4 pipeline stages together, manage stage transitions, save reports, and ensure demo deletion.
Description: This task builds the orchestrator service that executes the 4 stages, updates `stage` in the DB, checks cancellation flags between stages, saves the `Report` row, and unlinks both `.zst` and `.dem` files in a `finally` block on completion or error.
Done when:
- Orchestrator steps through the 4 stages, recording `failing_stage` and error messages upon exceptions.
- Both compressed and decompressed demo files are unlinked in a `finally` block, and paths are set to NULL in `Uploads`.
- Tests required: `backend/tests/test_orchestrator.py` testing successful end-to-end runs, failure stage capture, and file deletion verification.

## 28. Job Dispatch & Live Status Tracking API
Goal: Implement `/api/jobs` for job dispatch and provide live progress tracking via polling and Server-Sent Events.
Description: This task creates the endpoint to submit analysis jobs after validating upload ownership and 1-hour TTL. It provides a status polling endpoint and a native Server-Sent Events stream (`/api/jobs/{id}/stream`) emitting the 4 named progress stages to authenticated users.
Done when:
- `POST /api/jobs` validates upload ownership and queues the job, returning HTTP 202 with job metadata.
- Polling and SSE endpoints emit active stage updates and stream completion/failure events using cookie authentication.
- Tests required: `backend/tests/test_jobs_api.py` testing job creation, ownership validation, status polling, and SSE streaming.

## 29. Unified History & Job Deletion API
Goal: Build `/api/history` returning completed reports and failed jobs, alongside an endpoint to delete individual runs.
Description: This task implements `GET /api/history` by joining `Jobs` and `Reports` to display both successful analyses and failed runs with failure stage and retry prompts. It also implements `DELETE /api/history/{job_id}` to cancel running jobs, unlink files, and remove records.
Done when:
- `GET /api/history` returns completed reports and failed jobs with retryable metadata.
- `DELETE /api/history/{job_id}` cancels processing if active, deletes scratch files, and removes job and report rows.
- Tests required: `backend/tests/test_history_api.py` testing listing completed/failed jobs, deletion cascade, and active job cancellation.

## 30. Report Retrieval & JSON Export API
Goal: Implement `/api/reports/{id}` and `/api/reports/{id}/export/json` with mandatory safeguard statements.
Description: This task builds endpoints to retrieve full report JSON payloads and download structured JSON export files. Both endpoints include heuristic disclaimers, confidence labels, skipped round lists, and version metadata (`app_version`, `weights_version`, `map_version`).
Done when:
- `GET /api/reports/{id}` returns complete report data, sub-signals, timeline items, and version information.
- `/export/json` serves downloadable JSON with required disclaimers and matching structure.
- Tests required: `backend/tests/test_reports_api.py` asserting schema compliance, disclaimer presence, and export formatting.

## 31. ReportLab PDF Export Service with Unicode Font Support
Goal: Generate styled, standalone PDF reports using ReportLab with embedded Unicode fonts and mandatory disclaimers.
Description: This task builds `/api/reports/{id}/export/pdf` using ReportLab. It registers an open-source Unicode TTF font (DejaVu Sans) to support international player nicknames and renders the match header, 1–100 score, sub-signals, skipped rounds, and evidence timeline alongside required disclaimers.
Done when:
- ReportLab generator embeds DejaVu Sans and handles Cyrillic and special characters in player nicknames without crashing.
- Exported PDF cleanly displays the score hero, sub-signals, timeline, and mandatory disclaimer banners.
- Tests required: `backend/tests/test_pdf_export.py` verifying PDF generation, Unicode font rendering, and output file validity.

## 32. Frontend Project Scaffolding & Design System
Goal: Initialize the React 19 + TypeScript + Vite frontend with Tailwind CSS and Lucide icons.
Description: This task sets up the client application structure, configures Vite and TypeScript path aliases, and installs Tailwind CSS with dark-mode tactical defaults. It creates shared layout components including the navigation header, user profile badge, and daily quota indicator.
Done when:
- Vite project compiles cleanly with TypeScript, Tailwind CSS, and Lucide React.
- Base layout components (Header, Navigation, Quota badge) render with responsive styling.
- Tests required: `frontend/src/__tests__/Layout.test.tsx` verifying component rendering and responsive layout.

## 33. Frontend Authentication Context & Session Pages
Goal: Build the AuthContext provider and user interfaces for login, registration, and account deletion.
Description: This task implements client-side authentication state backed by httpOnly session cookies. It creates responsive pages for user login, account registration, and account settings with confirmation modals for account deletion.
Done when:
- AuthContext provides login, register, logout, and user profile state to all routes.
- Login, registration, and account deletion pages render and submit credentials properly.
- Tests required: `frontend/src/__tests__/Auth.test.tsx` verifying login submission, session storage, and route protection.

## 34. Frontend Demo Upload Dropzone Component
Goal: Create a drag-and-drop file upload component with client-side 350 MB checks, progress feedback, and match name input.
Description: This task develops the upload interface with progress bar indicators and client-side validation rejecting files over 350 MB or invalid extensions. Upon successful upload, it stores the returned upload token and triggers the player roster modal.
Done when:
- Upload dropzone handles drag-and-drop, validates file size and extension client-side, and displays upload progress.
- Successful upload triggers the player selection step with cached match metadata.
- Tests required: `frontend/src/__tests__/UploadDropzone.test.tsx` testing file validation, progress state, and upload submission.

## 35. Frontend Player Roster Selection Modal
Goal: Build an interactive modal displaying the demo's player roster for single-click player selection by SteamID.
Description: This task creates a modal that renders the cached player roster returned from the upload endpoint. The user can search or select one player by SteamID, which submits the job creation request and navigates to the job status view.
Done when:
- Modal displays player nicknames and SteamIDs with a search filter.
- Selecting a player calls `/api/jobs` and smoothly navigates the user to the status monitor.
- Tests required: `frontend/src/__tests__/RosterModal.test.tsx` verifying player list rendering, filtering, and job submission.

## 36. Frontend Live Job Status & Stage Stepper View
Goal: Build the real-time job progress page displaying the 4 named stages and handling failure states.
Description: This task develops a visual stepper component that connects to the job status SSE stream or polling endpoint. It displays active stages (*Parsing demo* $\rightarrow$ *Building player timelines* $\rightarrow$ *Analyzing rounds* $\rightarrow$ *Generating report*), displays clear error messages on failure, and redirects to the report on success.
Done when:
- Stepper component reflects the 4 named stages in real time via SSE or polling.
- Failure states display the failing stage and error message with a retry prompt; completion navigates to the report.
- Tests required: `frontend/src/__tests__/JobStatus.test.tsx` testing stepper transitions, error handling, and redirection.

## 37. Frontend Tactical Report Score Hero & Warning Banner
Goal: Build the report overview view featuring the 1–100 baiting score, confidence badge, and low-evidence warning.
Description: This task creates the main report header component displaying the calculated score, confidence badge (`low`, `medium`, `high`), and sub-signal breakdown cards. It conditionally renders a prominent alert banner when the report has insufficient evidence.
Done when:
- Score hero renders with color-coded confidence badges and sub-signal metric cards.
- Low-evidence warning banner renders prominently when `insufficient_evidence == true`.
- Tests required: `frontend/src/__tests__/ScoreHero.test.tsx` verifying score formatting, confidence styling, and warning banner display.

## 38. Interactive Chronological Evidence Timeline Component
Goal: Develop an interactive evidence timeline with round filtering, category tags, and fact/interpretation styling.
Description: This task builds the round-by-round evidence timeline component. It features category filters (trades, executes, lurks), round selectors, clear typographic separation of observed facts from interpretations, and expandable notes on missing evidence.
Done when:
- Timeline items render with bold facts, italic interpretations, and expandable missing-evidence tags.
- Filters allow filtering by specific round numbers and tactical event categories.
- Tests required: `frontend/src/__tests__/EvidenceTimeline.test.tsx` testing filter interactions and fact/interpretation rendering.

## 39. Frontend Unified History View & Retry Flow
Goal: Implement the history page displaying past analyses and failed jobs with delete and retry capabilities.
Description: This task creates the history dashboard that queries `GET /api/history`. It renders completed analyses with scores and report links, shows failed runs with their failing stage and error reason, provides a one-click retry prompt, and allows single or bulk record deletion.
Done when:
- History table displays both completed reports and failed analyses with app version and match metadata.
- Failed runs offer a clear retry prompt; delete buttons call `DELETE /api/history/{id}` and update the UI.
- Tests required: `frontend/src/__tests__/HistoryPage.test.tsx` testing history list rendering, delete actions, and retry links.

## 40. Client-Side PDF & JSON Report Export Actions
Goal: Add download triggers on the report page to export analyses as styled PDF and JSON files.
Description: This task implements export action buttons that trigger downloads from `/api/reports/{id}/export/pdf` and `/api/reports/{id}/export/json`. It manages downloading states, handles download failures gracefully, and formats file download names appropriately.
Done when:
- Export buttons initiate PDF and JSON downloads with loading indicators.
- Downloaded files have sanitized, descriptive filenames (e.g. `report_mirage_player_date.pdf`).
- Tests required: `frontend/src/__tests__/ReportExports.test.tsx` verifying export trigger buttons and download states.

## 41. Real-Demo Validation Dataset & Weight Calibration
Goal: Assemble 10–20 hand-reviewed Mirage demos and calibrate heuristic weights and sample size thresholds.
Description: This task runs the analysis pipeline against a validation set of 10–20 real FACEIT Mirage demos with human-reviewed playstyles. It verifies that known baiting patterns, entry fraggers, and standard lurkers receive expected score ranges, tuning the weights in `core/weights.py`.
Done when:
- 10–20 demos are evaluated and scored against human tactical review baselines.
- Scoring weights and sample thresholds in `app/core/weights.py` are calibrated and committed with a bumped `weights_version`.
- Tests required: `backend/tests/test_calibration.py` asserting that validation demos score within expected heuristic bands.

## 42. Documentation Synchronization & Specification Alignment
Goal: Finalize and sync `docs/plan.md` with all architectural decisions, trade rules, and operational thresholds.
Description: This task updates `docs/plan.md` to reflect all finalized decisions, including the independent execution rule, teammate trade logic, sample thresholds, decompression caps, and quota limits, ensuring documentation integrity across the codebase.
Done when:
- `docs/plan.md` is updated and verified against `docs/architecture.md` and `docs/tasks.md`.
- All open items in `docs/plan.md` §9 are marked as resolved with cross-references to architecture specifications.
- Tests required: Lint check / verification script asserting all documentation links and file cross-references resolve.
