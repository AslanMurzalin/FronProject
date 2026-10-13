# CS2 FACEIT Baiting Analyzer — Development Tasks Backlog

**Version:** 4.0 (Iterative Roadmap: Core Analyzer -> MVP Backend -> Hardening -> Frontend)
**Target Specification:** `docs/plan.md` and `docs/architecture.md` (v2.1)
**Task Standard:** Each task is sized for a single working session and is independently actionable. The Product Manager (`docs/team/pm.md`) grooms each issue into full acceptance criteria prior to implementation.

---

## Completed Tasks (1–6)

### 1. Project Scaffolding & Initial Smoke Test [CLOSED]
Goal: Establish the root project layout, dependency management, virtual environment configuration, and automated test runner so any contributor or agent can clone and run a passing test suite immediately.
Acceptance criteria:
- Repository & Directory Structure: `backend/app/` with `__init__.py` and `backend/tests/` with `__init__.py` created.
- Dependency Management: `pyproject.toml` and `requirements.txt` define project metadata and pin core dependencies.
- Smoke Verification: `backend/tests/test_smoke.py` asserts Python runtime compatibility, imports key packages, and validates test runner execution.
Done means: Full test suite passes; committed and verified.

### 2. Real-Demo Parser Spike & Event Inspection [CLOSED]
Goal: Parse a real CS2 Mirage match demo with `demoparser2` and document the exact schema of extracted ticks, deaths, coordinates, utility events, bomb plants, and bot takeovers.
Done means: `docs/parser_spike.md` and `backend/tests/test_parser_spike.py` committed and verified.

### 3. Database Engine & Relational Schema Setup [CLOSED]
Goal: Initialize the SQLite database engine with Write-Ahead Logging (WAL) and implement SQLAlchemy 2.0 ORM models for Users, Sessions, Uploads, Jobs, and Reports with cascade deletion and heartbeat tracking.
Done means: Database models, WAL pragmas, and cascade delete tests pass.

### 4. Cookie-Based Session Authentication & Session Hygiene API [CLOSED]
Goal: Provide user registration, secure password hashing with Argon2id, and httpOnly cookie-based session authentication with server-side revocation and CSRF Origin protection.
Done means: Register, login, /me, logout, session purge implemented and tested.

### 5. Account Deletion & Resource Teardown API [CLOSED]
Goal: Implement the `DELETE /api/account` endpoint to cancel any active background jobs for the user, unlink their demo scratch files from disk, and permanently delete all user records and history.
Done means: `DELETE /api/account` full teardown implemented and tested.

### 6. Reverse-Proxy Rate Limiting & User Quotas [CLOSED]
Goal: Integrate IP rate limiting, trusted reverse-proxy headers, active upload limits, and daily analysis quotas to protect backend resources from denial of service and compute abuse.
Done means: SlowAPI rate limiting, trusted `X-Forwarded-For` extraction, concurrent upload limits, and daily quotas implemented and tested.

---

## Phase 1: Core Tactical Analysis Engine (Demo Analyzer Service)

### 7. Golden Mock Demo Fixtures & Domain Models
Goal: Define clean domain models (`Round`, `PlayerTick`, `PlayerDeath`, `UtilityEvent`, `BombEvent`, `PlayerState`) and synthetic mock fixture generators reproducing realistic Mirage rounds for fast, isolated unit testing of all downstream evaluators.
Done means: `backend/app/domain/models.py` and `backend/tests/fixtures/mock_data.py` created with comprehensive unit tests in `backend/tests/test_domain_models.py`.

### 8. Mirage 15-Zone Tactical Graph & Spatial Lookup
Goal: Implement the Mirage 15-zone spatial coordinate classifier and tactical connectivity graph (T Spawn, Top Mid, Underpass, Connector, Window, A Site, B Site, etc.) with Euclidean and path distance lookup helpers.
Done means: `backend/app/analytics/mirage_graph.py` maps coordinates to zones, computes zone distances, and passes all zone mapping tests in `backend/tests/test_mirage_graph.py`.

### 9. Round Boundary & Match State Filtering
Goal: Extract valid competitive rounds using freeze-time end and round end markers, filtering out warmup, knife rounds, overtime anomalies, disconnected players, and bot takeovers.
Done means: `backend/app/analytics/round_filter.py` correctly filters invalid rounds and bot events, tested in `backend/tests/test_round_filter.py`.

### 10. T-Side Player Spatial Trajectory & Site Execution Detection
Goal: Reconstruct player spatial movement trajectories during T-side rounds and detect site execution windows based on utility detonated and bomb site entry timestamps.
Done means: `backend/app/analytics/execution_detector.py` identifies execution windows and entry paths, tested in `backend/tests/test_execution_detector.py`.

### 11. CT Defender Anchor & Rotator Detection Engine
Goal: Identify CT site anchor players vs rotators based on freeze-time positions, detecting whether an anchor holds their assigned site or rotates prematurely/late during an enemy attack.
Done means: `backend/app/analytics/ct_roles.py` classifies anchor/rotator roles and rotation delays, tested in `backend/tests/test_ct_roles.py`.

### 12. Trade Opportunity Evaluator
Goal: Detect combat engagements where a teammate died within 1000 units, evaluating whether the target player re-engaged within a 3-second window or baited without trading.
Done means: `backend/app/analytics/trade_evaluator.py` accurately flags traded vs un-traded deaths with penalty scores, tested in `backend/tests/test_trade_evaluator.py`.

### 13. Lurk Output Evaluator (Mitigating Factor)
Goal: Evaluate player impact when positioned away from the main team (space creation, flank frags, bomb site cutoffs) to prevent mislabeling productive lurkers as baiters.
Done means: `backend/app/analytics/lurk_evaluator.py` computes lurk impact scores and applies baiting mitigation, tested in `backend/tests/test_lurk_evaluator.py`.

### 14. Contextual Death-Order & Survival Evaluator
Goal: Evaluate player death timing across rounds, penalizing habitual last-alive survival without round-win impact while rewarding impactful opening and mid-round participation.
Done means: `backend/app/analytics/death_order_evaluator.py` scores survival and death sequence patterns, tested in `backend/tests/test_death_order_evaluator.py`.

### 15. Sub-Signal Sample Size Thresholds & Bounding
Goal: Normalize all sub-signals to bounded 0-100 scales and enforce minimum sample size thresholds (e.g. at least 3 trade opportunities) required for signal validity.
Done means: `backend/app/analytics/signal_bounds.py` bounds signals and computes sample size validity flags, tested in `backend/tests/test_signal_bounds.py`.

### 16. Weight Renormalization & Low-Evidence Guardrail
Goal: Dynamically reallocate signal weights when certain sub-signals lack sufficient sample size, setting an insufficient evidence flag if too few competitive rounds qualify.
Done means: `backend/app/analytics/weight_renormalizer.py` dynamically normalizes weights and triggers low-evidence guardrails, tested in `backend/tests/test_weight_renormalizer.py`.

### 17. Fact vs. Interpretation Evidence Timeline Formatter
Goal: Format analysis findings into an evidence timeline that strictly separates objective facts (timestamps, coordinates, weapon, distances) from tactical interpretations.
Done means: `backend/app/analytics/timeline_formatter.py` formats round events into verified fact vs interpretation structures, tested in `backend/tests/test_timeline_formatter.py`.

### 18. Unified Demo Analysis Engine (Facade Service)
Goal: Assemble all evaluators and spatial models into a unified demo analysis service that accepts a demo file and target Steam ID, producing the complete factual timeline and tactical baiting score report.
Done means: `backend/app/services/analyzer_service.py` executes full analysis pipeline and produces validated report schemas, tested in `backend/tests/test_analyzer_service.py`.

---

## Phase 2: MVP Backend API (Simple, Task-Focused, SQLite-Backed)

### 19. Ephemeral Scratch Storage & File Handling
Goal: Implement simple temporary demo storage under `var/scratch_demos/` with path safety validation, host disk space guards, and zero-retention cleanup helpers.
Done means: `backend/app/services/storage_service.py` manages temporary demo files with path traversal checks, tested in `backend/tests/test_storage_service.py`.

### 20. Demo Upload Endpoint & Decompression Handler
Goal: Implement `POST /api/uploads` accepting raw `.dem` and compressed `.dem.zst` files, decompressing if needed and enforcing file size caps (350MB compressed, 1.2GB uncompressed).
Done means: Demo upload endpoint successfully streams and decompresses demo files, tested in `backend/tests/test_upload_service.py`.

### 21. Offloaded Roster Extraction & Roster Caching
Goal: Fast-extract the 10-player match roster (nicknames, Steam IDs, team sides) from the uploaded demo header and cache it in the database to allow player selection before full analysis.
Done means: `GET /api/uploads/{id}/roster` returns extracted roster and caches results in `Upload.cached_roster`, tested in `backend/tests/test_roster_service.py`.

### 22. Analysis Job Dispatch & SQLite Background Worker
Goal: Implement `POST /api/jobs` dispatching analysis tasks to a pragmatic SQLite-backed background worker that calls the Unified Demo Analysis Engine.
Done means: Background worker picks up pending jobs, updates stages/heartbeats, executes analysis, and records report, tested in `backend/tests/test_worker_dispatch.py`.

### 23. Job Status & Report Retrieval JSON API
Goal: Provide `GET /api/jobs/{id}` for polling analysis progress and `GET /api/reports/{id}` returning the full tactical baiting score report and evidence timeline in JSON format.
Done means: Status polling and report retrieval endpoints implemented and tested in `backend/tests/test_reports_api.py`.

---

## Phase 3: Backend Polishing & Hardening

### 24. Unified History & Job Deletion API
Goal: Implement `GET /api/history` returning past completed and in-progress analyses for the authenticated user, and `DELETE /api/jobs/{id}` for removing individual records and associated reports.
Done means: User match history and job deletion endpoints implemented and tested in `backend/tests/test_history_api.py`.

### 25. Worker Leader Startup Recovery & Orphan Sweeper
Goal: Automatically recover orphaned or interrupted jobs on backend startup and sweep expired scratch demo directories older than 1 hour.
Done means: Startup recovery resets dead jobs and unlinks orphaned scratch folders, tested in `backend/tests/test_orphan_sweeper.py`.

### 26. ReportLab PDF Export Service with Unicode Font Support
Goal: Implement a PDF report generator formatting the tactical summary, score gauge, sub-signals, and round timeline with Unicode player nickname support.
Done means: `backend/app/services/pdf_service.py` generates valid PDF documents from report data, tested in `backend/tests/test_pdf_service.py`.

### 27. PDF & JSON Report Export Endpoints
Goal: Expose `GET /api/reports/{id}/export/pdf` and `GET /api/reports/{id}/export/json` for downloading formatted tactical analysis reports.
Done means: File download export endpoints return valid PDF and JSON attachments, tested in `backend/tests/test_export_api.py`.

### 28. Real-Demo Validation Dataset & Weight Calibration
Goal: Validate the complete analysis pipeline against a benchmark dataset of real CS2 Mirage Faceit demos and calibrate heuristic weights.
Done means: Benchmark test runs across real demo files verifying score plausibility and zero crashes, tested in `backend/tests/test_calibration.py`.

---

## Phase 4: Frontend Development

### 29. Frontend Project Scaffolding & Design System
Goal: Set up Vite + React + TypeScript with Tailwind CSS, base layout, and common UI design tokens.
Done means: `npm run dev` and `npm run build` succeed; base navigation layout renders.

### 30. Frontend Authentication Context & Session Pages
Goal: Build Login and Register pages with React context managing auth state and protected routes.
Done means: User can sign in, register, sign out, and stay logged in across page refreshes.

### 31. Frontend Demo Upload Dropzone Component
Goal: Create a drag-and-drop file upload component supporting `.dem` and `.dem.zst` with upload progress and client-side validation.
Done means: Upload component accepts valid files, shows progress bar, and handles upload errors.

### 32. Frontend Player Roster Selection Modal
Goal: Build a modal displaying extracted player rosters divided by team (T / CT) allowing the user to select the target player to analyze.
Done means: User can pick target player from modal roster list and initiate analysis job.

### 33. Frontend Live Job Status & Stage Stepper View
Goal: Build a real-time progress view polling job status and displaying an animated stage stepper (Uploading -> Extracting Roster -> Parsing -> Scoring -> Complete).
Done means: Progress view smoothly transitions through stages until report completion.

### 34. Frontend Tactical Report Score Hero & Warning Banner
Goal: Display the overall Baiting Score (0-100) hero gauge with confidence indicator and low-evidence warning banner.
Done means: Report page renders overall score gauge, verdict summary, and confidence warnings.

### 35. Frontend Chronological Evidence Timeline Component
Goal: Build an interactive round-by-round timeline clearly displaying factual events and tactical tags.
Done means: Interactive timeline lets user filter rounds and view detailed event cards.

### 36. Frontend Sub-Signal Breakdown Cards
Goal: Render metric cards displaying individual scores for Trade Opportunity, Lurk Output, Survival Impact, and Site Execution.
Done means: Sub-signal cards display scores, weights, and explanatory tooltips.

### 37. Frontend Unified History View & Match Retry Flow
Goal: Implement the user history page listing past analyzed matches with status badges, date, player, and quick links to view or delete.
Done means: History page lists user jobs, supports deletion, and links to existing reports.

### 38. Frontend Report Export Actions & Download Triggers
Goal: Add buttons and handlers for triggering PDF and JSON report downloads from the report view.
Done means: Clicking export buttons downloads valid PDF and JSON files in browser.

### 39. Frontend Error Boundaries & Edge-Case Polish
Goal: Add error boundaries, empty states, network failure banners, and responsive mobile/desktop adjustments.
Done means: App gracefully handles API downtimes, 404s, and empty states.

### 40. End-to-End User Flow Integration & Smoke Tests
Goal: Write frontend integration tests verifying the full user flow from login through demo upload, player selection, and report viewing.
Done means: `npm test` passes all component and integration tests.

### 41. Documentation Synchronization & Specification Alignment
Goal: Update `docs/plan.md`, `docs/architecture.md`, and `README.md` to match the finalized iterative architecture.
Done means: Documentation fully reflects delivered system and APIs.

### 42. Production Build & Final Release Verification
Goal: Configure production build assets, verify production server launch with static asset serving, and confirm release readiness.
Done means: Production server serves optimized frontend and passing API endpoints cleanly.
