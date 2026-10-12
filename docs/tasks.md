# CS2 FACEIT Baiting Analyzer — Development Tasks Backlog

**Version:** 3.0
**Target Specification:** `docs/plan.md` and `docs/architecture.md` (v2.1)
**Task Standard:** Each task is sized for a single working session and is independently actionable.

## 1. Project Scaffolding & Initial Smoke Test
Goal: Establish the root project layout, dependency management, virtual environment configuration, and automated test runner so any contributor or agent can clone and run a passing test suite immediately.
Acceptance criteria:
- **Repository & Directory Structure**: `backend/app/` with `__init__.py` and `backend/tests/` with `__init__.py` created.
- **Dependency Management**: `pyproject.toml` and `requirements.txt` define project metadata and pin core dependencies (`fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `demoparser2`, `polars`, `numpy`, `zstandard`, `argon2-cffi`, `slowapi`, `reportlab`, `pytest`, `httpx`). Python version pinned `>=3.12`.
- **Smoke Verification**: `backend/tests/test_smoke.py` asserts Python runtime compatibility, imports key packages, and validates test runner execution.
Done means:
- `pytest` or `uv run pytest` executes `backend/tests/test_smoke.py` and exits with code 0.
- All core packages import without missing native library errors.
Out of scope:
- Database tables (Issue #3), API routes (Issue #4), frontend scaffolding (Issue #32).
Constraints:
- Pinned dependencies only; root `.venv/` isolated; references `docs/architecture.md` Section 2.

## 2. Real-Demo Parser Spike & Event Inspection
Goal: Parse a real CS2 Mirage match demo with `demoparser2` and document the exact schema of extracted ticks, deaths, coordinates, utility events, bomb plants, and bot takeovers to ground all subsequent domain models and fixtures in observed reality.
Acceptance criteria:
- **Spike Execution**: Standalone test parses a real CS2 Mirage `.dem` file via `demoparser2.parse_ticks` and `demoparser2.parse_events`.
- **Captured Data**: Field names, types, nullability, and coordinates for player ticks, death causes (world/bomb/fall/teamkill), utility throws/detonations, bomb events, and bot takeovers.
- **Documentation**: Produce `docs/parser_spike.md` detailing event schemas, column types, and coordinate ranges on Mirage.
Done means:
- `docs/parser_spike.md` committed with complete schemas for player positions, deaths, utility, and round events.
- `backend/tests/test_parser_spike.py` parses demo events, asserts expected columns, and passes cleanly.
Out of scope:
- Domain models and dataclass adapters (Issue #10), round filtering (Issue #14), mock fixtures (Issue #11).
Constraints:
- Scratch demo files must be unlinked after parsing per Zero-Retention Demo Storage policy (`AGENTS.md` Rule 4); use `demoparser2` exclusively.

## 3. Database Engine & Relational Schema Setup
Goal: Initialize the SQLite database engine with Write-Ahead Logging (WAL) and implement SQLAlchemy 2.0 ORM models for Users, Sessions, Uploads, Jobs, and Reports with cascade deletion and heartbeat tracking.
Acceptance criteria:
- **Database Engine**: SQLite database at `var/app.db` with `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 5000;`, `PRAGMA synchronous = NORMAL;`, and `PRAGMA foreign_keys = ON;`.
- **Models (`app/db/models.py`)**: `User`, `Session`, `Upload`, `Job` (with `heartbeat_at`), and `Report` defined with SQLAlchemy 2.0 type annotations and indices.
- **Cascade Rules**: Deleting a User cascades to all owned Sessions, Uploads, Jobs, and Reports. Deleting a Job cascades to its produced Report.
Done means:
- Database initialization creates all 5 tables in `var/app.db` without errors.
- Unit tests verify foreign key enforcement, WAL pragma verification, and cascade deletes.
- Tests required: `backend/tests/test_database.py` covering table creation, WAL verification, and cascade deletes.
Out of scope:
- Auth API endpoints (Issue #4), upload file writing (Issue #7), worker queue (Issue #25).
Constraints:
- SQLAlchemy 2.0 `DeclarativeBase` with `Mapped` types; SQLite only (WAL mode); references `docs/architecture.md` Section 4.

## 4. Cookie-Based Session Authentication & Session Hygiene API
Goal: Provide user registration, secure password hashing with Argon2id, and httpOnly cookie-based session authentication with server-side revocation and CSRF Origin protection.
Acceptance criteria:
- **Password Security**: Argon2id hashing via `argon2-cffi`.
- **Endpoints**: `POST /api/auth/register` (creates user, validates email/password), `POST /api/auth/login` (verifies credentials, sets 7-day `httpOnly`, `SameSite=Lax`, configurable `Secure` cookie named `session_id`, stores SHA-256 hash in `SESSIONS`), `POST /api/auth/logout` (revokes session in DB, clears cookie), `GET /api/auth/me` (returns current user profile).
- **Session Hygiene**: Origin/Sec-Fetch-Site check on state-changing requests; `purge_expired_sessions(db)` helper.
Done means:
- Registration rejects duplicates; valid login sets `httpOnly` cookie and persists hashed token.
- Logout revokes session in DB so subsequent `/api/auth/me` calls fail with 401; expired sessions return 401.
- Tests required: `backend/tests/test_auth.py` covering register, invalid login, valid login cookie, `/me`, logout revocation, expired session rejection.
Out of scope:
- Email verification / password reset (out of scope per `docs/plan.md`), login rate limiting (Issue #6), account deletion (Issue #5).
Constraints:
- Cookie name `session_id`, `httpOnly=True`, `SameSite="lax"`; stateful `SESSIONS` table revocation; references `docs/architecture.md` Section 2 and 8.

## 5. Account Deletion & Resource Teardown API
Goal: Implement the `DELETE /api/account` endpoint to cancel any active background jobs for the user, unlink their demo scratch files from disk, and permanently delete all user records and history.
Acceptance criteria:
- **Endpoint**: `DELETE /api/account` requires valid authenticated session.
- **Teardown Sequence**: Cancels user's pending/processing jobs with failure message `"Job cancelled due to account deletion"`, unlinks demo files on disk (`scratch_path`, `decompressed_path`), deletes User record (cascading all sessions, uploads, jobs, reports), and clears auth cookie.
- **Idempotence & Safety**: Missing file unlinking handled gracefully without 500 errors; subsequent requests return 401.
Done means:
- Account deletion cancels in-progress jobs and deletes all user-owned files in `var/scratch_demos/`.
- Deleting the account completely removes user rows, sessions, jobs, and reports from the database.
- Old auth cookie is cleared and immediately invalidated.
- Tests required: `backend/tests/test_account_deletion.py` covering authenticated deletion, file unlinking, DB cascade, and post-deletion 401.
Out of scope:
- Deleting individual reports or clearing history without deleting account (Issue #29).
Constraints:
- Zero-retention guarantee: no demo files belonging to a deleted account linger on disk; references `docs/plan.md` Section 3.1, 3.9, `docs/architecture.md` Section 4, 8.

## 6. Reverse-Proxy Rate Limiting & User Quotas
### Goal
Integrate IP rate limiting, trusted reverse-proxy headers, active upload limits, and daily analysis quotas to protect backend resources from denial of service and compute abuse.

### Acceptance Criteria
- **Reverse-Proxy Header Validation**: Configure `slowapi` rate limiting middleware with trusted reverse-proxy CIDR/IP list (`forwarded_allow_ips = ["127.0.0.1"]` in `app/core/config.py`); extract client IP correctly from `X-Forwarded-For`.
- **IP Rate Limit**: Enforce an IP rate limit of at most 5 upload requests per minute per client IP on `POST /api/uploads`; exceeding requests are rejected with HTTP 429 (`RATE_LIMIT_EXCEEDED`).
- **Concurrent Upload Limit**: Enforce business rule allowing at most 1 active upload (`status in ['pending', 'processing']` or unanalyzed upload within 1-hour TTL) per authenticated user; exceeding requests are rejected with HTTP 429 (`CONCURRENT_UPLOAD_LIMIT`).
- **Daily Analysis Quota**: Enforce business rule allowing at most 10 completed analyses per user per rolling 24-hour window (tracked via `JOBS` where `user_id = :uid`, `completed_at >= NOW() - 24h`, and `status = 'completed'`); exceeding requests are rejected with HTTP 429 (`DAILY_QUOTA_EXCEEDED`).
- **Quota Helper**: Provide reusable dependency/helper `check_user_quotas(user_id: str, db: Session)` in `app/api/deps.py` returning specific error details.

### Done Means
- `pytest backend/tests/test_quotas.py` passes covering:
  - Client IP rate limit triggered after 5 rapid requests on `/api/uploads`.
  - Proper client IP extraction behind trusted `X-Forwarded-For` header.
  - Second concurrent upload rejected with HTTP 429 while first is active.
  - 11th analysis attempt rejected with HTTP 429 when 10 completed in 24 hours.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Paid tier quota expansions or dynamic quota overrides via admin UI (deferred to future backlog).
- Captcha challenges on rate limit breach (out of scope for MVP).

### Constraints
- File placement: `backend/app/core/config.py`, `backend/app/api/deps.py`, `backend/app/api/uploads.py`.
- Dependencies: `slowapi` (pinned in requirements). No new dependencies without approval.
- References: `docs/architecture.md` §7.3, `docs/plan.md` §7.

## 7. Ephemeral Scratch Disk & Storage Quota Manager
### Goal
Implement storage helpers for scratch directories with strict host disk and folder quota guards to guarantee system stability and prevent disk exhaustion.

### Acceptance Criteria
- **Scratch Directory Isolation**: All temporary match files are written strictly to isolated subdirectories under `var/scratch_demos/{upload_id}/`.
- **Path Traversal Protection**: Helpers `get_scratch_dir(upload_id)` and `get_scratch_filepath(upload_id, filename)` validate that resolved canonical paths never escape `var/scratch_demos/`.
- **Host Disk Free Space Guard**: Before creating directories or accepting file writes, check host free disk space via `shutil.disk_usage`; reject writes with `InsufficientStorageError` (HTTP 507) if free disk space is under 5.0 GB (`5 * 1024 * 1024 * 1024` bytes).
- **Directory Quota Guard**: Verify that total cumulative usage of `var/scratch_demos/` does not exceed 10.0 GB (`10 * 1024 * 1024 * 1024` bytes); reject writes with HTTP 507 if limit breached.
- **Orphan Sweeper**: Implement `cleanup_expired_scratch_dirs(max_age_seconds=3600)` to delete scratch directories older than 1 hour based on directory modification time.

### Done Means
- `pytest backend/tests/test_storage_manager.py` passes covering:
  - Path traversal attempts with `../` raise validation errors.
  - Mock disk usage < 5 GB raises `InsufficientStorageError` (HTTP 507).
  - Mock folder size > 10 GB raises `InsufficientStorageError` (HTTP 507).
  - Scratch directories older than 3600 seconds are safely unlinked by cleanup utility.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Cloud object storage (S3 / GCS) integrations (MVP uses local scratch disk exclusively per `docs/architecture.md` §1).
- Per-user disk byte accounting tables.

### Constraints
- File placement: `backend/app/services/storage_service.py`.
- Scratch directory: `var/scratch_demos/`.
- References: `docs/architecture.md` §7.2, `docs/plan.md` §3.9.

## 8. Demo Upload Streaming, Byte-Counting & Decompression Caps
### Goal
Build `POST /api/uploads` to stream demo archives with active chunk-by-chunk byte counting, a 350 MB upload limit, a 1.2 GB decompression cap, and auto-generated match names.

### Acceptance Criteria
- **Supported Formats**: Accept `.dem` and `.dem.zst` multipart file uploads; reject any other file extension immediately with HTTP 400 (`UNSUPPORTED_FILE_TYPE`).
- **Streaming Byte Counting**: Stream file upload chunks (64 KB) directly to disk; if cumulative incoming bytes exceed 350 MB (`350 * 1024 * 1024`), abort stream, unlink partial file, and return HTTP 413 (`UPLOAD_TOO_LARGE`). Full files must never be loaded into RAM at once.
- **Streaming Decompression Cap**: For `.dem.zst` files, decompress via `zstandard.ZstdDecompressor` streaming API; abort decompression immediately and unlink files if uncompressed bytes exceed 1.2 GB (`1.2 * 1024 * 1024 * 1024`), returning HTTP 413 (`DECOMPRESSION_LIMIT_EXCEEDED`).
- **Match Name Handling**: Accept optional form field `match_name` (1-100 characters); if empty or omitted, generate default placeholder `Mirage YYYY-MM-DD HH:MM`.
- **Database Record**: Create `Upload` record in database with `original_filename`, `scratch_path`, `decompressed_path`, `file_size_bytes`, `expires_at = NOW() + 1h`, `user_id`.

### Done Means
- `pytest backend/tests/test_upload_streaming.py` passes covering:
  - Successful upload of `.dem` file under 350 MB.
  - Successful upload and decompression of `.dem.zst` file.
  - Aborting stream exceeding 350 MB mid-transfer with partial file unlinked.
  - Aborting decompression bomb exceeding 1.2 GB uncompressed limit with files unlinked.
  - Fallback default match name generation when omitted.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Offloaded roster extraction (handled in Issue #9).
- Upload dropzone frontend component (handled in Issue #34).

### Constraints
- File placement: `backend/app/api/uploads.py`, `backend/app/services/upload_service.py`.
- Zero-Retention: scratch files must be unlinked in `finally` blocks on error (`AGENTS.md` Rule 4).
- References: `docs/architecture.md` §7.2, §8, `docs/plan.md` §3.2.

## 9. Offloaded Roster Extraction & Roster Caching
### Goal
Extract player SteamIDs and nicknames in an executor thread with an `asyncio.Semaphore(1)` guard, validate that map is `de_mirage`, and cache the roster on the `Upload` model.

### Acceptance Criteria
- **Concurrency Guard**: Wrap roster parsing in `asyncio.Semaphore(1)` to prevent CPU/memory starvation in the API process.
- **Non-blocking Execution**: Execute synchronous parsing in a worker thread via `asyncio.to_thread` or thread pool executor so the FastAPI event loop remains responsive.
- **Map Validation**: Parse demo header using `demoparser2.DemoParser(path).parse_header()`; verify `map_name == "de_mirage"`; if different, unlink demo files and return HTTP 400 (`INVALID_MAP`, detail: "Only de_mirage demos are supported in MVP").
- **Player Roster Extraction**: Extract participant SteamIDs and nicknames using `DemoParser.parse_player_info()`; filter out spectators, HLTV bots, and invalid IDs; ensure non-empty nicknames.
- **Roster Caching**: Serialize extracted players as JSON `[{"steam_id": "...", "name": "..."}]` and persist to `Upload.cached_roster` and `Upload.map_name = "de_mirage"`.
- **API Response**: `POST /api/uploads` returns HTTP 201 with `{ "upload_id": "...", "match_name": "...", "map_name": "de_mirage", "expires_at": "...", "players": [...] }`.

### Done Means
- `pytest backend/tests/test_roster_extraction.py` passes covering:
  - Correct extraction of 10 human players with SteamIDs and nicknames from Mirage demo.
  - Rejection of non-Mirage demos (e.g. `de_inferno`, `de_dust2`) with HTTP 400 and file unlinking.
  - Roster JSON correctly cached on `Upload` row in database.
  - Semaphore permits only 1 concurrent extraction without blocking other API routes.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Full tick trajectory extraction (Issue #16).
- Player selection modal UI (Issue #35).

### Constraints
- File placement: `backend/app/services/upload_service.py`, `backend/app/api/uploads.py`.
- Parser: `demoparser2.DemoParser` only.
- References: `docs/architecture.md` §7.2, §8, `docs/plan.md` §3.2, §3.3.

## 10. Internal Match Domain Model & Parser Adapter
### Goal
Define strongly typed match dataclasses and build an adapter converting raw `demoparser2` outputs into internal entities to isolate tactical analysis from parser library internals.

### Acceptance Criteria
- **Domain Dataclasses (`app/services/analysis/models.py`)**:
  - `ParsedMatch`: `match_name`, `map_name`, `rounds: List[ParsedRound]`, `players: Dict[str, str]`.
  - `ParsedRound`: `round_num`, `start_tick`, `freeze_end_tick`, `end_tick`, `winner_team`, `t_players: List[str]`, `ct_players: List[str]`, `bomb_planted: bool`, `plant_tick: Optional[int]`, `plant_site: Optional[str]`, `deaths: List[ParsedDeath]`, `utility: List[ParsedUtility]`.
  - `ParsedDeath`: `tick`, `round_num`, `victim_steam_id`, `victim_name`, `victim_pos: Tuple[float, float, float]`, `killer_steam_id`, `killer_name`, `killer_pos: Tuple[float, float, float]`, `assister_steam_id: Optional[str]`, `weapon: str`, `is_headshot: bool`, `is_tradeable: bool` (False for world/bomb/fall/teamkill).
  - `ParsedUtility`: `tick`, `round_num`, `thrower_steam_id`, `grenade_type: str`, `throw_pos: Tuple[float, float, float]`, `detonate_pos: Tuple[float, float, float]`, `detonate_tick: int`.
  - `PlayerTick`: `tick`, `second_in_round: float`, `steam_id: str`, `team: str`, `pos: Tuple[float, float, float]`, `is_alive: bool`, `health: int`.
- **Parser Adapter (`app/services/analysis/adapter.py`)**:
  - Function `adapt_demo_events(raw_events: dict, raw_ticks: dict) -> ParsedMatch`.
  - Normalizes coordinate tuples, sanitizes player strings, converts timestamps, and sets `is_tradeable = False` for deaths where killer is None, world, or teammate.

### Done Means
- `pytest backend/tests/test_parser_adapter.py` passes covering:
  - Correct conversion of raw dictionary event structures into `ParsedMatch`.
  - Flagging `is_tradeable = False` for suicide, fall damage, bomb explosion, and teamkill.
  - Coordinate normalization and schema validation without validation errors.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Round filtering for warmups/halftimes (handled in Issue #14).
- Mock fixture creation (handled in Issue #11).

### Constraints
- File placement: `backend/app/services/analysis/models.py`, `backend/app/services/analysis/adapter.py`.
- Pure Python dataclasses / Pydantic models; no ORM coupling.
- References: `docs/architecture.md` §3, §5, `docs/plan.md` §3.4.

## 11. Golden Mock Demo Fixtures for Unit Testing
### Goal
Generate lightweight JSON mock event fixtures based on the parser spike to support deterministic unit tests without requiring large binary `.dem` files in repository.

### Acceptance Criteria
- **Fixture Files (`backend/tests/fixtures/`)**:
  - `match_mirage_standard.json`: full 24-round match covering standard defaults, A executes, B executes, lurks, and saves.
  - `match_trades.json`: isolated rounds covering successful trade (<3s, <800u), team trade (teammate kills killer), missed trade (>3s), out-of-range (>800u), and non-player death exclusions.
  - `match_executes.json`: rounds covering utility + approach route, utility + site clustering, and utility-free rush (negative case).
  - `match_disconnects.json`: rounds with player disconnects, bot takeovers, overtime rounds, and warmup rounds.
- **Fixture Loader (`backend/tests/fixtures/loader.py`)**:
  - Helper `load_fixture_match(fixture_filename: str) -> ParsedMatch` that deserializes JSON into `ParsedMatch` domain models.
- **Fixture Integrity**: All fixtures strictly conform to `ParsedMatch` schema and contain realistic Mirage coordinates and timestamps.

### Done Means
- `pytest backend/tests/test_fixtures.py` passes covering:
  - Loading each of the 4 golden mock fixtures without schema or deserialization errors.
  - Asserting expected round counts, player SteamIDs, and event counts for each fixture.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Running tactical evaluator logic against fixtures (Issues #18–#23).
- Storing binary `.dem` files in Git (strictly prohibited).

### Constraints
- File placement: `backend/tests/fixtures/*.json`, `backend/tests/fixtures/loader.py`, `backend/tests/test_fixtures.py`.
- JSON format only. No binary assets committed.
- References: `docs/architecture.md` §3, §5, `docs/plan.md` §3.4.

## 12. Mirage Tactical Map Spike & Zone Boundary Fallback
### Goal
Conduct a spike on `de_mirage.nav` parsing versus a 2D polygonal fallback to resolve 3D coordinates into zones, documenting findings in `docs/nav_mesh_spike.md`.

### Acceptance Criteria
- **Spike Investigation**: Compare native `.nav` binary file parsing vs 2D polygon bounding lookup (`shapely`) for Mirage coordinates.
- **Landmark Coordinate Tests**: Verify resolution of 10+ key Mirage landmark coordinates (T Spawn, A Ramp, Palace, A Site, Connector, Window, Catwalk, B Site, B Apartments, Underpass).
- **Benchmark**: Measure lookup performance (target: > 10,000 coordinate lookups per second in Python).
- **Spike Documentation**: Commit `docs/nav_mesh_spike.md` detailing:
  - Nav mesh availability, parsing complexity, and license findings.
  - 2D polygon bounding fallback coordinates and polygon definitions.
  - Final architectural recommendation for Issue #13.

### Done Means
- `docs/nav_mesh_spike.md` committed with complete coordinate ranges and benchmark results.
- `pytest backend/tests/test_zone_spike.py` passes resolving known Mirage landmark coordinates.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Full 15-zone topological adjacency graph (handled in Issue #13).
- Trajectory path generation (handled in Issue #16).

### Constraints
- File placement: `docs/nav_mesh_spike.md`, `backend/tests/test_zone_spike.py`.
- References: `docs/architecture.md` §5.1, `docs/plan.md` §3.5, §9.

## 13. Mirage 15-Zone Tactical Graph & Spatial Lookup Service
### Goal
Implement the 15 connected tactical zones of Mirage and their walkable adjacency graph to provide spatial coordinate resolution and topological routing queries.

### Acceptance Criteria
- **15 Tactical Zones (`app/services/analysis/zone_graph.py`)**:
  - Exact nodes: `T Spawn`, `Top Mid / T Roof`, `Lower Mid`, `Underpass`, `Catwalk / Short`, `Connector`, `Window (Sniper's Nest)`, `Ladder Room`, `A Ramp`, `Palace`, `A Site`, `CT Spawn`, `B Site`, `B Apartments`, `Market / Kitchen`.
  - Do NOT merge A-side and B-side; Market/Kitchen is strictly isolated from A-side.
- **Topological Adjacency Edges**: Define valid walkable connections between adjacent zones (e.g. `T Spawn` connects to `Top Mid / T Roof`, `A Ramp`, `B Apartments`; `Connector` connects to `Top Mid / T Roof`, `Underpass`, `A Site`, `Window`).
- **Spatial Coordinate Lookup**: `get_zone(x: float, y: float, z: float) -> str` resolving 3D coordinates to zone name; returns `"Unknown"` if coordinates are out of bounds.
- **Graph Methods**:
  - `get_adjacent_zones(zone_name: str) -> List[str]`.
  - `is_adjacent(zone_a: str, zone_b: str) -> bool`.
  - `get_shortest_path(start_zone: str, target_zone: str) -> List[str]`.

### Done Means
- `pytest backend/tests/test_zone_graph.py` passes covering:
  - All 15 zones exist in graph.
  - `get_zone` correctly resolves 20+ test coordinates to expected zones.
  - Out of bounds coordinates return `"Unknown"`.
  - Adjacency checks succeed for valid corridors and return False for disconnected zones (e.g. `Palace` and `B Site`).
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Player tick timeline sampling (Issue #16).
- CT rotator departure detection (Issue #17).

### Constraints
- File placement: `backend/app/services/analysis/zone_graph.py`.
- Graph representation: pure Python dictionary / adjacency set or NetworkX if approved.
- References: `docs/architecture.md` §5.1, `docs/plan.md` §3.5.

## 14. Round Boundary & Match State Filtering
### Goal
Filter demo events to extract official regulation and overtime T-side rounds while discarding warmups, resets, and pauses.

### Acceptance Criteria
- **Event Filtering Logic (`app/services/analysis/round_filter.py`)**:
  - Inspect `round_start`, `round_freeze_end`, `round_end`, `round_officially_ended` events and `is_warmup_period` flags.
  - Discard all warmup rounds (`is_warmup_period == True`), knife rounds, and halftime reset sequences.
- **T-Side Round Isolation**:
  - Isolate rounds where the selected player is assigned to the Terrorist (`T`) team.
  - Cover both regulation halves (first half and second half after side-switch) and **all overtime rounds**.
- **Round Metadata Extraction**:
  - For each valid round, record `round_num`, `start_tick`, `freeze_end_tick`, `end_tick`, `duration_seconds`.
  - Extract bomb plant event if planted: `plant_tick`, `plant_site` (`A` or `B`).

### Done Means
- `pytest backend/tests/test_round_filter.py` passes covering:
  - Filtering out warmup rounds and match restarts.
  - Correct capture of regulation T-side rounds across side swap.
  - Correct capture of overtime T-side rounds.
  - Accurate extraction of `freeze_end_tick` and plant status.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Disconnected player and bot takeover detection (handled in Issue #15).
- Player trajectory mapping (handled in Issue #16).

### Constraints
- File placement: `backend/app/services/analysis/round_filter.py`.
- References: `docs/architecture.md` §5.2, `docs/plan.md` §3.4.

## 15. Player Disconnect & Bot Takeover Filtering
### Goal
Identify T-side rounds where the selected player was disconnected or replaced by a bot, record them as skipped rounds, and fail the job if zero analyzable T rounds remain.

### Acceptance Criteria
- **Presence & Bot Verification (`app/services/analysis/disconnect_filter.py`)**:
  - For each extracted T-side round, check player tick presence and bot takeover events (`bot_takeover`).
  - If selected player has 0 ticks, is disconnected, or replaced by a bot for >50% of the active round, tag round as skipped.
- **Skipped Rounds Recording**:
  - Append skipped round to list: `[{"round_num": int, "reason": "player_disconnected" | "bot_takeover"}]`.
  - Exclude skipped rounds from all subsequent tactical evaluators.
- **Fatal Error Guard**:
  - If all T-side rounds are skipped ($N_{	ext{analyzed}} == 0$), raise `NoAnalyzableRoundsError` (which marks job `failed` with detail: `"Zero analyzable T-side rounds found in match."`).
  - If at least 1 analyzable round remains, processing proceeds normally.

### Done Means
- `pytest backend/tests/test_disconnect_filter.py` passes covering:
  - Round with player disconnect tagged as skipped with reason.
  - Round with bot takeover tagged as skipped with reason.
  - Raising `NoAnalyzableRoundsError` when 100% of T rounds are disconnected.
  - Passing through valid rounds when player is present.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Tactical evaluators (Issues #18–#21).
- Frontend skipped rounds warning banner (Issue #37).

### Constraints
- File placement: `backend/app/services/analysis/disconnect_filter.py`.
- Custom exception: `NoAnalyzableRoundsError`.
- References: `docs/architecture.md` §5.2 Rule 5, `docs/plan.md` §3.4.

## 16. T-Side Player Spatial Trajectory Reconstruction
### Goal
Reconstruct tick-by-tick coordinate timelines and zone transitions for the selected player in each T-side round sampled at 1-second intervals.

### Acceptance Criteria
- **Downsampling (`app/services/analysis/timeline.py`)**:
  - Sample player ticks at 1.0-second intervals (`second_in_round`) starting from `freeze_end_tick` until player death or round end.
- **Zone Assignment**:
  - Map each sampled 3D coordinate `(x, y, z)` to its tactical zone using the 15-zone graph from Issue #13.
- **Discrete Zone Transitions**:
  - Detect and chronologically log zone transition events `(timestamp_s, from_zone, to_zone)` (e.g. `14.0s: T Spawn -> Top Mid / T Roof`).
- **Data Structure**:
  - Return `PlayerTrajectory` containing `round_num`, `points: List[TrajectoryPoint]`, and `transitions: List[ZoneTransition]`.

### Done Means
- `pytest backend/tests/test_player_trajectories.py` passes covering:
  - 1-second temporal downsampling from freeze end to death.
  - Accurate mapping of coordinates to zones along route.
  - Chronological recording of discrete zone transition events.
  - Stopping trajectory points at tick of death.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- CT defender rotation tracking (handled in Issue #17).
- Execution participation evaluation (handled in Issue #19).

### Constraints
- File placement: `backend/app/services/analysis/timeline.py`.
- References: `docs/architecture.md` §3, §5, `docs/plan.md` §3.4.

## 17. CT Defender Anchor & Rotator Detection Engine
### Goal
Identify CT initial anchor sites during early round time and detect when defenders vacate their sites to rotate toward the active contested bombsite.

### Acceptance Criteria
- **Initial Anchor Classification**:
  - During the first 25 seconds of each round (post-freeze), analyze all 5 CT player positions.
  - Classify each CT's starting anchor site: `A` (A Site, Palace, Ramp, Connector), `Mid` (Window, Connector, Catwalk, Ladder Room), or `B` (B Site, B Apps, Market).
- **Rotator Detection**:
  - Track CT player departures from their initial anchor site toward the active T-pressured site.
  - Tag CT with `is_rotator = True` alongside `rotation_start_tick` and `rotation_timestamp` upon departure.
- **CT Timeline Structure**:
  - `CTTimelineManager` producing `Dict[str, CTPlayerTimeline]` tracking initial anchor, rotation status, and zone transitions for all 5 CTs.

### Done Means
- `pytest backend/tests/test_rotator_detection.py` passes covering:
  - Accurate initial anchor assignment (A, Mid, B) for all 5 CTs in first 25s.
  - Tagging `is_rotator = True` when B anchor rotates to A Site through CT Spawn or Market.
  - Static defenders maintaining `is_rotator = False`.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Lurk kill crediting (handled in Issue #20).
- Execution utility detection (handled in Issue #19).

### Constraints
- File placement: `backend/app/services/analysis/timeline.py`.
- References: `docs/architecture.md` §5.2 Rule 3, `docs/plan.md` §3.4.

## 18. Trade Opportunity Evaluator
### Goal
Implement trade opportunity detection based on the 800-unit, 3.0-second candidate window, filtering non-player deaths and properly crediting teammate trades.

### Acceptance Criteria
- **Candidate Trigger (`app/services/analysis/trade_detector.py`)**:
  - Teammate dies within 800 Euclidean units and selected player is alive at teammate's death tick.
- **Non-Player Death Exclusions**:
  - Teammate deaths from fall damage, bomb explosions, world damage, or friendly fire (team kills) are strictly excluded from triggering trade opportunities.
- **Outcome Classification**:
  - `TRADED_BY_PLAYER`: selected player kills the killer within 3.0 seconds.
  - `TRADED_BY_TEAM`: another teammate kills the killer within 3.0 seconds (credited as a team trade; NOT counted as a missed trade for selected player).
  - `MISSED_TRADE`: neither selected player nor any teammate kills the killer within 3.0 seconds.
- **Confidence Tagging**:
  - Without line-of-sight raycasting, every trade opportunity carries confidence `low` or `medium` and notes missing LOS evidence.
- **Data Structure**:
  - Return `TradeEvaluation` containing total opportunities, missed trades, traded by player, traded by teammate, and list of `TradeOpportunity` objects.

### Done Means
- `pytest backend/tests/test_trade_detector.py` passes covering:
  - Teammate death within 800u and traded within 3s credited to player.
  - Teammate death traded by another teammate credited without penalty.
  - Teammate death untraded after 3.0s flagged as `MISSED_TRADE`.
  - Deaths from bomb, fall damage, and teamkill excluded from trade opportunities.
  - Teammate death > 800u does not trigger opportunity.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Dynamic weight renormalization and score bounding (Issues #22, #23).
- Line-of-sight raycasting (explicitly out of scope for MVP).

### Constraints
- File placement: `backend/app/services/analysis/trade_detector.py`.
- Metric parameters: distance threshold = 800 units, time threshold = 3.0 seconds.
- References: `docs/architecture.md` §5.2 Rule 1, `docs/plan.md` §3.4.

## 19. Site Execution Detection Engine
### Goal
Detect offensive site executions requiring utility deployment plus at least one independent spatial signal, evaluating player participation and excluding utility-free rushes.

### Acceptance Criteria
- **Architecture 2.1 Rule (`app/services/analysis/execution_detector.py`)**:
  - $\text{Execution} = \text{Utility Condition} \land (\text{Approach Vector} \lor \text{Site Clustering})$.
- **Utility Condition (Required)**:
  - $\ge 2$ smokes or flashes deployed toward a site (A Site or B Site) within a 6-second window.
- **Spatial Signal (At least one)**:
  - *Approach Vector*: $\ge 3$ Ts moving along approach edges into the site zone within 5 seconds.
  - *Site Clustering*: $\ge 3$ Ts present in the site zone or its entry bottleneck (Ramp/Palace for A, Apps for B) concurrently.
- **Utility-Free Rush Exclusion**:
  - Fast site rushes without qualifying utility are classified as fast defaults/rushes, NOT executions.
- **Player Participation**:
  - Selected player is evaluated during the execute window: flagged `participated = True` if present in the site zone or on the execution approach route; `participated = False` if absent.

### Done Means
- `pytest backend/tests/test_execution_detector.py` passes covering:
  - Site execution recognized when utility + site clustering occur.
  - Site execution recognized when utility + approach vector occur.
  - Utility-free rush rejected from execution classification.
  - Execution rejected if spatial signals are absent despite utility.
  - Player participation flag correctly set based on player zone presence during execute window.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Excluding lurk rounds from execution denominator (handled in Issue #22).
- First-contact location heuristics (deferred to Phase 2 backlog).

### Constraints
- File placement: `backend/app/services/analysis/execution_detector.py`.
- References: `docs/architecture.md` §5.2 Rule 2, `docs/plan.md` §3.4.

## 20. Lurk Output Evaluator (Mitigating Factor)
### Goal
Measure the impact of isolated play by tracking kills against confirmed rotating CT defenders as a mitigating factor that reduces suspicion without penalizing non-lurkers.

### Acceptance Criteria
- **Isolated Round Detection (`app/services/analysis/lurk_analyzer.py`)**:
  - Classify round as an isolated/lurk round if selected player operates in an isolated map zone while $\ge 3$ teammates are clustered elsewhere for $\ge 15$ seconds of the round.
- **Rotator Kill Evaluation**:
  - Match kills secured by selected player against CTs tagged as confirmed rotators (`is_rotator == True` from Issue #17).
  - Award rotator kills toward lurk output. Kills against static anchors are recorded as normal kills, not rotator mitigation.
- **Zero Penalty for Non-Lurkers**:
  - If player has 0 isolated rounds, lurk mitigation output $M_{\text{lurk}} = 0.0$ (neutral; 0 penalty points). Lurking is strictly a mitigating term.
- **Data Structure**:
  - Return `LurkAnalysisResult` containing isolated rounds count, rotator kills count, and detailed lurk kill events.

### Done Means
- `pytest backend/tests/test_lurk_analyzer.py` passes covering:
  - Correct classification of isolated rounds based on team separation.
  - Crediting kills on confirmed rotators during isolated play.
  - Ignoring kills on static site anchors for lurk mitigation credit.
  - Asserting that 0 isolated rounds results in 0 penalty points.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Normalizing lurk metric into primary score formula (handled in Issue #22, #23).
- Space creation and rotation delay modeling (deferred to Phase 2 backlog).

### Constraints
- File placement: `backend/app/services/analysis/lurk_analyzer.py`.
- References: `docs/architecture.md` §5.2 Rule 3, §6.1, `docs/plan.md` §3.4.

## 21. Contextual Death-Order & Survival Evaluator
### Goal
Evaluate player death timing while recognizing entry fragging and strictly excluding post-plants and save situations from late-survival penalties.

### Acceptance Criteria
- **Entry Fragging Recognition (`app/services/analysis/death_order.py`)**:
  - Dying first within the first 30 seconds of the round inside an entry zone (A Ramp, Palace, A Site, B Apps, B Site) is classified as an entry attempt (`is_entry_attempt = True`).
  - Entry frag deaths are strictly exempt from death-order penalties.
- **Late Survival Flagging**:
  - Late survival is flagged ONLY if:
    1. Selected player is the last alive or dies last, AND
    2. The team had zero trades in the round.
- **Exclusion 1: Post-Plant Situations**:
  - If the bomb was planted by Ts, late survival represents legitimate objective defense and is NEVER flagged.
- **Exclusion 2: Save Situations**:
  - If $\ge 3$ teammates are dead and round is statistically unwinnable, saving equipment is legitimate play and is NEVER flagged.

### Done Means
- `pytest backend/tests/test_death_order.py` passes covering:
  - First death in entry zone in first 30s tagged as entry frag without penalty.
  - Late survival flagged in lost round with zero trades.
  - Late survival excluded when bomb is planted (post-plant).
  - Late survival excluded when $\ge 3$ teammates dead and player saves.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Sub-signal bounding and scoring aggregation (handled in Issue #22, #23).
- Economy and loadout dollar value tracking (deferred to future backlog).

### Constraints
- File placement: `backend/app/services/analysis/death_order.py`.
- References: `docs/architecture.md` §5.2 Rule 4, `docs/plan.md` §3.4.

## 22. Sub-Signal Sample Size Thresholds & Bounding
### Goal
Apply minimum sample thresholds per sub-signal, exclude lurk rounds from the execution denominator, and bound all active sub-signals to $[0.0, 1.0]$.

### Acceptance Criteria
- **Metric Normalization & Bounds (`app/services/analysis/sub_signals.py`)**:
  - $S_{\text{trade}} = \frac{\text{Missed Trades}}{\text{Total Trade Opportunities}}$, bounded to $[0.0, 1.0]$.
  - $S_{\text{exec}} = 1.0 - \frac{\text{Participated Executions}}{\max(1, \text{Executions in Non-Lurk Rounds})}$, bounded to $[0.0, 1.0]$.
  - $S_{\text{death}} = \min\left(1.0, \frac{\text{Flagged Late Rounds}}{N_{\text{analyzed\_rounds}}}\right)$, bounded to $[0.0, 1.0]$.
  - $M_{\text{lurk}} = \min\left(1.0, \frac{\text{Kills on Rotators}}{\max(1, \text{Isolated Rounds})}\right)$, bounded to $[0.0, 1.0]$.
- **Lurk Exclusion from Execution Denominator**:
  - Rounds where the player played as an isolated lurker are excluded from the execution denominator to prevent double-penalizing lurkers.
- **Minimum Sample Thresholds**:
  - $S_{\text{trade}} = \text{no\_data}$ (`null`) if $\text{Total Trade Opportunities} < 3$.
  - $S_{\text{exec}} = \text{no\_data}$ (`null`) if $\text{Executions in Non-Lurk Rounds} < 3$.
  - $M_{\text{lurk}} = \text{no\_data}$ (`null`) if $\text{Isolated Rounds} < 2$.
  - $S_{\text{death}} = \text{no\_data}$ (`null`) if $N_{\text{analyzed\_rounds}} < 6$.

### Done Means
- `pytest backend/tests/test_sub_signals.py` passes covering:
  - Sub-signals with samples below thresholds return `no_data` (`None`).
  - Lurk rounds excluded from execution denominator.
  - All calculated sub-signals strictly bounded in $[0.0, 1.0]$.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Dynamic weight renormalization across remaining active signals (handled in Issue #23).
- UI presentation of sub-signals (handled in Issue #37).

### Constraints
- File placement: `backend/app/services/analysis/sub_signals.py`.
- References: `docs/architecture.md` §6.1, §6.2, `docs/plan.md` §3.6.

## 23. Weight Renormalization & Low-Evidence Guardrail
### Goal
Dynamically renormalize active weights, calculate the 1–100 score with lurk mitigation, and apply low-evidence guardrails when sample depth is insufficient.

### Acceptance Criteria
- **Dynamic Weight Renormalization (`app/services/analysis/scoring.py`)**:
  - Base weights: $w_{\text{trade}} = 0.45, w_{\text{exec}} = 0.35, w_{\text{death}} = 0.20$.
  - When any sub-signal is `no_data`, renormalize remaining active weights: $w_i' = \frac{w_i}{\sum_{j \in \text{active}} w_j}$ so active weights sum to 1.0.
- **Score Calculation with Lurk Mitigation**:
  - $B_{\text{raw}} = 100 \times \sum_{i \in \text{active}} w_i' S_i - 15 \times M_{\text{lurk}}$.
  - Clamped score: $B = \text{clamp}(1, 100, \text{round}(B_{\text{raw}}))$.
- **Low-Evidence Guardrail**:
  - If $N_{\text{analyzed\_rounds}} < 6$ OR fewer than 2 *informative* sub-signals are active ($S_{\text{trade}}, S_{\text{exec}}, M_{\text{lurk}}$):
    - Cap final score below 25 ($B = \min(B, 24)$).
    - Set `confidence = "low"`.
    - Set `insufficient_evidence = True`.
- **Config Snapshot**:
  - Serialize snapshot `{ "weights": {...}, "thresholds": {...}, "weights_version": "1.0.0" }` to include in report.

### Done Means
- `pytest backend/tests/test_scoring.py` passes covering:
  - Weight renormalization when $S_{\text{exec}}$ has no data.
  - Lurk mitigation reducing raw score up to 15 points.
  - Score clamping between 1 and 100.
  - Low-evidence guardrail capping score < 25 and forcing confidence "low" when < 2 informative signals active.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Report row persistence in database (handled in Issue #27).
- PDF rendering of score hero (handled in Issue #31).

### Constraints
- File placement: `backend/app/services/analysis/scoring.py`, `backend/app/core/weights.py`.
- References: `docs/architecture.md` §6.2, §6.3, `docs/plan.md` §3.6.

## 24. Fact vs. Interpretation Evidence Timeline Formatter
### Goal
Structure round-by-round tactical findings into an evidence timeline separating observed facts from interpretations with confidence labels and missing evidence notes.

### Acceptance Criteria
- **Timeline Item Schema (`app/services/analysis/evidence.py`)**:
  - Each item contains:
    - `round_num: int`
    - `tick: int`
    - `timestamp_s: float`
    - `zone: str`
    - `category: str` (`trade`, `execution`, `lurk`, `death`)
    - `factual_description: str` (objective facts only, e.g. "Teammate died 650 units away; player did not eliminate killer within 3.0s")
    - `tactical_interpretation: str` (inferred meaning, e.g. "Missed trade opportunity on A site approach")
    - `confidence: str` (`low`, `medium`, `high`)
    - `missing_evidence: Optional[str]` (e.g. "Line of sight unverified; obstructed vision possible")
- **Fact vs. Interpretation Separation**:
  - Factual descriptions must strictly exclude subjective intent or judgment words.
  - Tactical interpretations explicitly contain heuristic analysis.
- **Chronological Sorting**:
  - Timeline items are sorted chronologically by round number and timestamp.

### Done Means
- `pytest backend/tests/test_evidence_formatter.py` passes covering:
  - Generation of timeline items adhering to schema.
  - Strict separation of factual text from tactical interpretations.
  - Accurate tagging of confidence and missing evidence notes.
  - Chronological ordering across all rounds.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Interactive frontend timeline component (handled in Issue #38).
- PDF table rendering (handled in Issue #31).

### Constraints
- File placement: `backend/app/services/analysis/evidence.py`.
- Rule: `AGENTS.md` Rule 5 (Facts vs. Interpretations).
- References: `docs/architecture.md` §1, §4, `docs/plan.md` §1, §3.6.

## 25. Worker Job Claiming & Heartbeat Monitor
### Goal
Implement atomic job claiming via SQL `UPDATE ... RETURNING` and a 10-second heartbeat updater in the worker process to prevent race conditions and detect stalled workers.

### Acceptance Criteria
- **Atomic Job Claiming (`app/services/job_service.py`)**:
  - Worker claims next available job atomically using `UPDATE jobs SET status='processing', heartbeat_at=CURRENT_TIMESTAMP WHERE id = (SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1) RETURNING *`.
  - Guarantees zero duplicate job claims across concurrent worker processes.
- **Worker Process Concurrency**:
  - Dedicated worker pool process concurrency strictly capped at 1–2 simultaneous jobs.
- **Heartbeat Loop**:
  - While processing a job, background task executes every 10 seconds updating `JOBS.heartbeat_at = datetime.utcnow()`.
- **Failure Handling**:
  - If unhandled exception occurs, worker catches error, updates `status = 'failed'`, records `error_message` and `failing_stage`.

### Done Means
- `pytest backend/tests/test_worker_claiming.py` passes covering:
  - Atomic claiming prevents race condition when two workers claim simultaneously.
  - Worker updates `heartbeat_at` periodically during execution.
  - Unhandled exception sets status to failed with error message.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Leader startup recovery of stalled jobs (handled in Issue #26).
- Pipeline orchestrator logic (handled in Issue #27).

### Constraints
- File placement: `backend/app/services/job_service.py`, `backend/app/worker.py`.
- Concurrency limit: 1–2 jobs. Heartbeat frequency: 10 seconds.
- References: `docs/architecture.md` §7.1, `docs/plan.md` §3.7.

## 26. Worker Leader Startup Recovery & Orphan Sweeper
### Goal
Implement startup recovery to mark stale interrupted jobs as failed and sweep orphan scratch directories on worker boot.

### Acceptance Criteria
- **Leader-Only Execution (`app/services/job_service.py`)**:
  - Recovery logic runs solely in the worker leader process on startup (never executed by FastAPI web processes).
- **Stale Job Recovery**:
  - Query `JOBS` where `status = 'processing'` and (`heartbeat_at IS NULL` or `heartbeat_at < NOW() - 60s`).
  - Mark matching jobs as `status = 'failed'` with `error_message = 'Worker interrupted by server restart'`.
  - Active jobs with recent heartbeats (< 60s) remain untouched.
- **Orphan Directory Sweeper**:
  - Scan `var/scratch_demos/` and delete directories older than 1 hour based on modification time.

### Done Means
- `pytest backend/tests/test_worker_recovery.py` passes covering:
  - Stale processing jobs with heartbeat > 60s marked as failed on startup.
  - Processing jobs with fresh heartbeat (< 60s) left untouched.
  - Orphan directories in scratch folder older than 1 hour unlinked.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Job submission and SSE status streaming (handled in Issue #28).
- User-triggered job cancellation (handled in Issue #29).

### Constraints
- File placement: `backend/app/worker_leader.py` or startup hook in `app/services/job_service.py`.
- Stale heartbeat threshold: 60 seconds. Orphan TTL: 1 hour.
- References: `docs/architecture.md` §7.1, `docs/plan.md` §3.9.

## 27. Pipeline Orchestrator & Zero-Retention Cleanup
### Goal
Wire the 4 pipeline stages together, manage stage transitions, save reports, and ensure demo deletion in a `finally` block on both success and failure.

### Acceptance Criteria
- **4 Pipeline Stages (`app/services/orchestrator.py`)**:
  - Stage 1: *Parsing demo* (`demoparser2` extraction & adapter).
  - Stage 2: *Building player timelines* (trajectories & CT rotators).
  - Stage 3: *Analyzing rounds* (trades, executions, lurks, death order).
  - Stage 4: *Generating report* (scoring, evidence timeline, report persistence).
- **Stage State Transitions**:
  - Update `JOB.stage` as each stage starts. If an error occurs, save `JOB.failing_stage`.
- **Report Persistence**:
  - On successful completion, insert `Report` record with `baiting_score`, `confidence`, `insufficient_evidence`, `sub_signals`, `evidence_timeline`, `skipped_rounds`, `config_snapshot`, and version stamps.
- **Zero-Retention Guarantee**:
  - In a `finally` block on both success and failure, unlink `.dem` and `.dem.zst` files from disk, and set `Upload.scratch_path = NULL` and `Upload.decompressed_path = NULL` in database.

### Done Means
- `pytest backend/tests/test_orchestrator.py` passes covering:
  - Successful end-to-end execution of all 4 stages creating a `Report` record.
  - Recording `failing_stage` and error message upon exception.
  - Unlinking demo files on disk on successful completion.
  - Guaranteed unlinking of demo files on disk on pipeline failure.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Live status SSE streaming (handled in Issue #28).
- PDF report generation (handled in Issue #31).

### Constraints
- File placement: `backend/app/services/orchestrator.py`.
- Rule: `AGENTS.md` Rule 4 (Zero-Retention Demo Storage).
- References: `docs/architecture.md` §1, §7.2, `docs/plan.md` §3.9.

## 28. Job Dispatch & Live Status Tracking API
### Goal
Implement `/api/jobs` for job dispatch and provide live progress tracking via polling and native Server-Sent Events (SSE).

### Acceptance Criteria
- **Job Dispatch (`POST /api/jobs`)**:
  - Accepts `{ "upload_id": "...", "steam_id": "..." }`.
  - Validates upload ownership and that upload has not expired (< 1h TTL).
  - Verifies selected `steam_id` exists in cached roster of the upload.
  - Creates `Job` record with `status = 'pending'`, returns HTTP 202 with `{ "job_id": "...", "status": "pending", "stage": "Parsing demo" }`.
- **Status Polling (`GET /api/jobs/{id}`)**:
  - Returns job status, active stage, `error_message`, `failing_stage`, and `report_id` (if completed).
  - Rejects unauthorized users with HTTP 403/404.
- **SSE Stream (`GET /api/jobs/{id}/stream`)**:
  - Native `text/event-stream` endpoint authenticated via session cookie.
  - Emits stage transition events (`parsing`, `timelines`, `analyzing`, `generating`) and closes connection on completion or failure.

### Done Means
- `pytest backend/tests/test_jobs_api.py` passes covering:
  - Submitting job returns HTTP 202 with job metadata.
  - Rejecting job dispatch for expired or non-owned upload.
  - Status polling returning current stage and status.
  - SSE endpoint streaming stage transitions and terminating cleanly.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Frontend stepper UI component (handled in Issue #36).
- History listing API (handled in Issue #29).

### Constraints
- File placement: `backend/app/api/jobs.py`.
- Auth: httpOnly session cookie.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.7.

## 29. Unified History & Job Deletion API
### Goal
Build `GET /api/history` returning completed reports and failed jobs, alongside endpoints to delete individual runs or clear all history.

### Acceptance Criteria
- **Unified History List (`GET /api/history`)**:
  - Queries user's jobs joined with reports.
  - Returns unified list including completed reports (with scores, match name, player nickname, date, `report_id`) and failed jobs (with `failing_stage`, `error_message`, `retryable: true`).
- **Single Job Deletion (`DELETE /api/history/{job_id}`)**:
  - Validates authenticated ownership.
  - If job is active (`pending`/`processing`), cancels job; unlinks any lingering scratch files; deletes job row cascading to report row; returns HTTP 204.
- **Clear Entire History (`DELETE /api/history`)**:
  - Deletes all completed and failed jobs and associated reports for authenticated user; returns HTTP 204.

### Done Means
- `pytest backend/tests/test_history_api.py` passes covering:
  - `GET /api/history` returns both completed and failed analyses with retryable metadata.
  - Deleting single job removes job and cascading report.
  - Deleting active job cancels processing and cleans up scratch files.
  - `DELETE /api/history` clears all user records without affecting other users.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Frontend history page view (handled in Issue #39).
- Report JSON export (handled in Issue #30).

### Constraints
- File placement: `backend/app/api/history.py`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.8.

## 30. Report Retrieval & JSON Export API
### Goal
Implement `GET /api/reports/{id}` and `GET /api/reports/{id}/export/json` with mandatory safeguard statements, sub-signals, and version stamps.

### Acceptance Criteria
- **Report Retrieval (`GET /api/reports/{id}`)**:
  - Returns full report JSON for authenticated owner: `baiting_score`, `confidence`, `insufficient_evidence`, `sub_signals`, `evidence_timeline`, `skipped_rounds`, `app_version`, `weights_version`, `map_version`.
  - Access control: returns HTTP 404/403 for non-owners.
- **Downloadable JSON Export (`GET /api/reports/{id}/export/json`)**:
  - Serves downloadable JSON attachment with header `Content-Disposition: attachment; filename="report_mirage_{player}_{date}.json"`.
- **Mandatory Safeguard Statement**:
  - Both endpoints include mandatory disclaimer: `"Heuristic indicator, not definitive proof of player intent."`

### Done Means
- `pytest backend/tests/test_reports_api.py` passes covering:
  - Report retrieval returns complete payload with all sub-signals and timeline items.
  - Export endpoint returns downloadable JSON attachment header.
  - Safeguard statement present in all JSON outputs.
  - Non-owner requests rejected with 403/404.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- ReportLab PDF export (handled in Issue #31).
- Frontend report score hero (handled in Issue #37).

### Constraints
- File placement: `backend/app/api/reports.py`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.6, §3.8.

## 31. ReportLab PDF Export Service with Unicode Font Support
### Goal
Generate styled, standalone PDF reports using ReportLab with embedded Unicode fonts and mandatory disclaimers.

### Acceptance Criteria
- **PDF Generation Endpoint (`GET /api/reports/{id}/export/pdf`)**:
  - Generates and streams PDF document (`application/pdf`) with `Content-Disposition: attachment; filename="report_mirage_{player}_{date}.pdf"`.
- **Pure-Python ReportLab**:
  - Use ReportLab flowables exclusively (no WeasyPrint, no Playwright, no headless browser).
- **Unicode Font Embedding**:
  - Register TTF font (e.g. DejaVu Sans) to support Cyrillic, Chinese, and special characters in player nicknames without crash or missing glyphs.
- **Visual Report Layout**:
  - Render match header, 1–100 score hero, confidence badge, sub-signals breakdown, skipped rounds table, evidence timeline summary, and mandatory safeguard disclaimer banner.

### Done Means
- `pytest backend/tests/test_pdf_export.py` passes covering:
  - PDF generation creates valid binary starting with `%PDF`.
  - Cyrillic and unicode player nicknames render without font exceptions.
  - Download headers specify attachment with sanitized filename.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Client-side download trigger buttons (handled in Issue #40).
- Interactive chart web components (handled in Issue #37).

### Constraints
- File placement: `backend/app/services/pdf_service.py`, `backend/app/api/reports.py`.
- Engine: ReportLab only.
- References: `docs/architecture.md` §2, §8, `docs/plan.md` §3.8.

## 32. Frontend Project Scaffolding & Design System
### Goal
Initialize the React 19 + TypeScript + Vite frontend with Tailwind CSS, Lucide icons, and shared layout components.

### Acceptance Criteria
- **Client Project Setup (`frontend/`)**:
  - Initialize Vite + React 19 + TypeScript in `frontend/`.
  - Configure Tailwind CSS with dark-mode tactical defaults (zinc/slate surfaces, amber/emerald/red status accents).
  - Configure TypeScript path aliases (`@/` mapping to `frontend/src/`).
- **Shared Layout Components**:
  - `Header`: app logo, navigation links, user profile badge, daily quota indicator ("Quota: 3/10").
  - `Footer`: version stamps and heuristic disclaimer.
  - `Layout`: responsive container wrapping all page routes.

### Done Means
- `npm run build` in `frontend/` succeeds without TypeScript or Vite errors.
- `npm test` runs `frontend/src/__tests__/Layout.test.tsx` verifying component rendering and responsive layout.
- Lint passes: `npm run lint`.

### Out of Scope
- Authentication context provider (handled in Issue #33).
- Upload dropzone component (handled in Issue #34).

### Constraints
- Tech stack: React 19, TypeScript, Vite, Tailwind CSS, Lucide React.
- File placement: `frontend/src/components/layout/`, `frontend/src/App.tsx`.
- References: `docs/architecture.md` §2, §3.

## 33. Frontend Authentication Context & Session Pages
### Goal
Build the AuthContext provider and user interfaces for login, registration, and account deletion backed by httpOnly session cookies.

### Acceptance Criteria
- **AuthContext Provider (`frontend/src/context/AuthContext.tsx`)**:
  - Manages `user`, `isAuthenticated`, `isLoading`.
  - Exposes `login(email, password)`, `register(email, password)`, `logout()`, `deleteAccount()`.
  - All API requests include `credentials: "include"` for httpOnly cookie handling.
- **Session Pages**:
  - `LoginPage.tsx`: email and password inputs with client-side validation and error alerts.
  - `RegisterPage.tsx`: email, password, and confirm password inputs with strength validation.
  - `AccountSettingsPage.tsx`: account details with Account Deletion confirmation modal requiring user to type "DELETE" before issuing `DELETE /api/account`.
- **Route Guard**:
  - Protect authenticated routes, redirecting unauthenticated users to `/login`.

### Done Means
- Vitest test `frontend/src/__tests__/Auth.test.tsx` passes covering:
  - Form validation on login and registration pages.
  - AuthContext state updates upon login and logout.
  - Account deletion modal requiring typed confirmation before dispatching delete request.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Upload dropzone and roster modal (Issues #34, #35).
- Password reset and email verification (explicitly out of scope per `docs/plan.md` §3.1).

### Constraints
- File placement: `frontend/src/context/AuthContext.tsx`, `frontend/src/pages/`.
- Auth: httpOnly session cookies (`credentials: "include"`).
- References: `docs/architecture.md` §8, `docs/plan.md` §3.1.

## 34. Frontend Demo Upload Dropzone Component
### Goal
Create a drag-and-drop file upload component with client-side 350 MB checks, progress feedback, and match name input.

### Acceptance Criteria
- **Drag & Drop Dropzone (`frontend/src/components/upload/UploadDropzone.tsx`)**:
  - Accepts `.dem` and `.dem.zst` files via drag-and-drop or file picker.
  - Rejects unsupported extensions client-side with clear error feedback.
- **Client-Side Size Guard**:
  - Rejects files larger than 350 MB before upload initiates, showing error: "Demo file exceeds 350 MB limit."
- **Match Name Field**:
  - Optional text input for custom match name with auto-generated default placeholder.
- **Upload Progress Bar**:
  - Visual progress bar showing upload progress percentage.
- **Post-Upload Handshake**:
  - On HTTP 201 response, passes upload token and cached roster to the Player Roster Modal.

### Done Means
- Vitest test `frontend/src/__tests__/UploadDropzone.test.tsx` passes covering:
  - Selecting valid `.dem` or `.dem.zst` initiates upload.
  - File > 350 MB triggers immediate validation error without network request.
  - Progress bar displays upload percentage.
  - Successful upload invokes roster selection callback.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Player roster selection modal (handled in Issue #35).
- Job status stepper (handled in Issue #36).

### Constraints
- File placement: `frontend/src/components/upload/UploadDropzone.tsx`.
- Size cap: 350 MB client check.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.2.

## 35. Frontend Player Roster Selection Modal
### Goal
Build an interactive modal displaying the demo's player roster for single-click player selection by SteamID.

### Acceptance Criteria
- **Roster Modal Display (`frontend/src/components/upload/RosterModal.tsx`)**:
  - Renders list of match participants (`steam_id`, `name`) returned from upload endpoint.
- **Live Search Filter**:
  - Search input allowing instant filtering by player nickname or SteamID.
- **Job Dispatch**:
  - Clicking a player triggers `POST /api/jobs` with `{ upload_id, steam_id }`.
  - Disables player selection and displays loading indicator while job is dispatched.
- **Navigation**:
  - On HTTP 202 response, redirects user to `/jobs/{job_id}` status view.

### Done Means
- Vitest test `frontend/src/__tests__/RosterModal.test.tsx` passes covering:
  - Modal renders all players in cached roster.
  - Search filter updates visible player list.
  - Selecting player calls API with correct SteamID.
  - Navigates to job status page upon HTTP 202.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Real-time job status tracking view (handled in Issue #36).
- Tactical report view (handled in Issue #37).

### Constraints
- File placement: `frontend/src/components/upload/RosterModal.tsx`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.3.

## 36. Frontend Live Job Status & Stage Stepper View
### Goal
Build the real-time job progress page displaying the 4 named stages and handling failure states with clear error prompts.

### Acceptance Criteria
- **4-Stage Visual Stepper (`frontend/src/pages/JobStatusPage.tsx`)**:
  - Displays sequential stages: *Parsing demo* $\rightarrow$ *Building player timelines* $\rightarrow$ *Analyzing rounds* $\rightarrow$ *Generating report*.
  - Highlights currently active stage with pulsing indicator; completed stages marked with checkmarks.
- **Real-Time Stage Updates**:
  - Connects to `GET /api/jobs/{id}/stream` via native `EventSource`.
  - Falls back to 2-second polling of `GET /api/jobs/{id}` if SSE connection fails.
- **Failure State Presentation**:
  - If job fails, displays error banner highlighting `failing_stage`, `error_message`, and a "Retry by Re-uploading" button.
- **Completion Navigation**:
  - Upon job completion, automatically navigates user to `/reports/{report_id}`.

### Done Means
- Vitest test `frontend/src/__tests__/JobStatus.test.tsx` passes covering:
  - Stepper reflects active stage from incoming SSE events.
  - Failure displays failing stage and retry prompt.
  - Completion event triggers navigation to report page.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Report overview score hero (handled in Issue #37).
- Unified history list (handled in Issue #39).

### Constraints
- File placement: `frontend/src/pages/JobStatusPage.tsx`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.7.

## 37. Frontend Tactical Report Score Hero & Warning Banner
### Goal
Build the report overview view featuring the 1–100 baiting score hero, confidence badge, sub-signal metric cards, and low-evidence warning banner.

### Acceptance Criteria
- **Score Hero Component (`frontend/src/components/report/ScoreHero.tsx`)**:
  - Displays prominent 1–100 baiting score with color grading (emerald $\le 30$, amber 31–60, rose $> 60$).
  - Renders Confidence Badge (`Low`, `Medium`, `High`) with explanatory tooltip.
- **Low-Evidence Warning Banner**:
  - Conditionally renders prominent warning banner if `insufficient_evidence == true` stating: "Insufficient evidence to evaluate player patterns ($N_T < 6$ or lack of trade/execute opportunities)."
- **Sub-Signal Metric Cards (`frontend/src/components/report/SubSignalCards.tsx`)**:
  - Metric cards for Missed Trades ($S_{\text{trade}}$), Execution Absence ($S_{\text{exec}}$), Late Survival ($S_{\text{death}}$), and Lurk Mitigation ($M_{\text{lurk}}$).
  - Displays normalized score or "Insufficient Sample" badge if metric had no data.
- **Header Metadata**:
  - Shows match name, player nickname, analyzed rounds count, and skipped rounds count.

### Done Means
- Vitest test `frontend/src/__tests__/ScoreHero.test.tsx` passes covering:
  - Score hero renders with correct color class based on score value.
  - Confidence badge renders expected label.
  - Low-evidence banner renders when `insufficient_evidence: true` and is hidden when false.
  - Sub-signal cards display values or "Insufficient Sample".
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Interactive evidence timeline component (handled in Issue #38).
- PDF and JSON export actions (handled in Issue #40).

### Constraints
- File placement: `frontend/src/components/report/ScoreHero.tsx`, `frontend/src/components/report/SubSignalCards.tsx`.
- References: `docs/architecture.md` §6, `docs/plan.md` §3.6.

## 38. Interactive Chronological Evidence Timeline Component
### Goal
Develop an interactive evidence timeline with round filtering, category tags, and distinct styling separating observed facts from tactical interpretations.

### Acceptance Criteria
- **Fact vs. Interpretation Typography (`frontend/src/components/report/EvidenceTimeline.tsx`)**:
  - Factual descriptions styled in bold, neutral typography labeled "Fact".
  - Tactical interpretations styled in distinct italicized accent typography labeled "Interpretation".
- **Category Filter Tabs**:
  - Filter timeline items by category: All, Trades, Executions, Lurk Output, Death Order.
- **Round Selector**:
  - Quick dropdown / button list to isolate specific round numbers.
- **Uncertainty & Missing Evidence**:
  - Confidence badge per item (`Low`, `Medium`, `High`).
  - Expandable / visible notes detailing missing evidence (e.g. "Line of sight unverified").

### Done Means
- Vitest test `frontend/src/__tests__/EvidenceTimeline.test.tsx` passes covering:
  - Typographic distinction between facts and interpretations.
  - Category filtering showing only selected event types.
  - Round selector filtering items to specific round.
  - Missing evidence note toggle/display.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Report export triggers (handled in Issue #40).
- History page view (handled in Issue #39).

### Constraints
- File placement: `frontend/src/components/report/EvidenceTimeline.tsx`.
- Rule: `AGENTS.md` Rule 5 (Facts vs. Interpretations).
- References: `docs/plan.md` §1, §3.6.

## 39. Frontend Unified History View & Retry Flow
### Goal
Implement the history page displaying past analyses and failed jobs with delete actions and one-click retry triggers.

### Acceptance Criteria
- **Unified History Table (`frontend/src/pages/HistoryPage.tsx`)**:
  - Queries `GET /api/history` and renders completed analyses (score, player nickname, match name, date) and failed runs (failing stage, error reason, retry button).
- **One-Click Retry Flow**:
  - Clicking "Retry" on a failed run prompts demo re-upload with match name pre-filled.
- **Deletion Actions**:
  - Individual delete button calling `DELETE /api/history/{job_id}` removing the item from view.
  - "Clear All History" button with confirmation modal calling `DELETE /api/history`.
- **Navigation**:
  - Clicking a completed row opens `/reports/{report_id}`.

### Done Means
- Vitest test `frontend/src/__tests__/HistoryPage.test.tsx` passes covering:
  - Table renders completed and failed jobs.
  - Retry button navigates to upload flow.
  - Single item delete calls API and removes row from DOM.
  - Clear all history triggers confirmation modal and purges list.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- PDF and JSON download triggers (handled in Issue #40).
- Export history to CSV (deferred to future backlog).

### Constraints
- File placement: `frontend/src/pages/HistoryPage.tsx`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.8.

## 40. Client-Side PDF & JSON Report Export Actions
### Goal
Add download triggers on the report page to export analyses as styled PDF and JSON files with loading states and error handling.

### Acceptance Criteria
- **Export Buttons (`frontend/src/components/report/ExportActions.tsx`)**:
  - "Export PDF" and "Export JSON" buttons on the report view.
- **Download Handling**:
  - Fetch from `/api/reports/{id}/export/pdf` and `/api/reports/{id}/export/json` using authenticated credentials.
  - Triggers browser blob download with sanitized filename from `Content-Disposition`.
- **Loading & Error Feedback**:
  - Displays spinner and disables buttons during download generation.
  - Shows toast alert if download request fails.

### Done Means
- Vitest test `frontend/src/__tests__/ReportExports.test.tsx` passes covering:
  - PDF export button initiates fetch and triggers download.
  - JSON export button initiates fetch and triggers download.
  - Loading state disables buttons during fetch.
  - Error state displays toast alert.
- `npm run build` and `npm run lint` pass cleanly.

### Out of Scope
- Backend ReportLab PDF engine (handled in Issue #31).
- Backend JSON export endpoint (handled in Issue #30).

### Constraints
- File placement: `frontend/src/components/report/ExportActions.tsx`.
- References: `docs/architecture.md` §8, `docs/plan.md` §3.8.

## 41. Real-Demo Validation Dataset & Weight Calibration
### Goal
Assemble 10–20 hand-reviewed Mirage demos and calibrate heuristic weights and sample size thresholds, bumping `weights_version`.

### Acceptance Criteria
- **Validation Dataset & Runner (`backend/tests/test_calibration.py`)**:
  - Assemble metadata / test cases for 10–20 reviewed FACEIT Mirage demos representing diverse playstyles:
    - Obvious baiting patterns (passive non-trading, delayed late survivals).
    - Aggressive entry fraggers (first deaths on site entries).
    - Dedicated effective lurkers (kills on rotating defenders).
    - Standard balanced team players.
- **Score Calibration**:
  - Verify entry fraggers score $\le 30$.
  - Verify effective lurkers receive lurk mitigation and do not suffer execution absence penalty.
  - Verify passive non-trading players score elevated baiting indicators ($> 60$).
- **Weight Calibration & Version Bump**:
  - Tune base weights and sample thresholds in `app/core/weights.py` if anomalies are found; bump `weights_version` (e.g. to `"1.1.0"`).

### Done Means
- `pytest backend/tests/test_calibration.py` passes asserting:
  - Validation demos score within expected heuristic bands.
  - `weights_version` in `app/core/weights.py` is calibrated and committed.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Automated machine-learning weight optimization (deferred to Phase 3).
- Support for maps other than Mirage (Phase 2 backlog).

### Constraints
- File placement: `backend/app/core/weights.py`, `backend/tests/test_calibration.py`.
- References: `docs/architecture.md` §6, `docs/plan.md` §9.

## 42. Documentation Synchronization & Specification Alignment
### Goal
Finalize and sync `docs/plan.md` with all architectural decisions, trade rules, and operational thresholds, resolving open items.

### Acceptance Criteria
- **Specification Audit & Alignment**:
  - Update `docs/plan.md` §9 (Open Items) to mark all open items as resolved with explicit cross-references to `docs/architecture.md`:
    - Validation set: resolved by Issue #41.
    - Initial weights: resolved by `app/core/weights.py`.
    - Too little evidence threshold: resolved ($N_T < 6$ or $<2$ informative signals).
    - Execution rule: resolved (Utility + Route/Cluster).
    - Trade operationalization: resolved (800u / 3.0s window).
    - Decompressed size cap: resolved (1.2 GB cap).
    - Temp-file TTL: resolved (1 hour TTL).
- **Cross-Reference & Link Integrity**:
  - Verify all markdown links across `AGENTS.md`, `docs/plan.md`, `docs/architecture.md`, `docs/tasks.md`, `docs/process.md`, `docs/issue_flow.md` resolve to existing files and valid anchors.
- **Automated Doc Test**:
  - Automated verification test `backend/tests/test_doc_integrity.py` checks link resolution and schema alignment.

### Done Means
- `pytest backend/tests/test_doc_integrity.py` passes asserting all documentation links and references resolve without broken paths.
- All open items in `docs/plan.md` §9 marked resolved.
- Full test suite passes: `uv run pytest`.
- Lint passes: `ruff check backend/`.

### Out of Scope
- Adding future backlog features (Phase 2 / Phase 3) to MVP scope.

### Constraints
- Documentation updates and doc verification test only.
- References: `docs/plan.md`, `docs/architecture.md`, `docs/tasks.md`.
