# Agent Guidelines & Project Context

Welcome! This repository houses the **CS2 FACEIT Baiting Analyzer**, an evidence-first tactical analysis tool that analyzes CS2 player behavior on T-side Mirage from match demos (`.dem` / `.dem.zst`).

---

## Project Context & Architecture

- **Goal:** Help users review a selected player's T-side behavior in a FACEIT demo to judge whether recurring patterns indicate baiting.
- **Core Principle:** Evidence-first. Separate **observed facts** from **tactical interpretations**. Never state that a player is definitively baiting; provide confidence ratings and transparent, timestamped evidence.
- **Technology Stack:**
  - **Backend:** Python 3.12+ / FastAPI, SQLAlchemy 2.0 with SQLite (WAL mode, `busy_timeout = 5000`), Pydantic v2.
  - **Demo Parser & Data:** `demoparser2` (Rust-backed CS2 parser), `polars`, `numpy`, `zstandard`.
  - **Worker Queue:** Dedicated worker process pool with heartbeat tracking and startup recovery.
  - **PDF Engine:** Pure-Python ReportLab with embedded DejaVu Sans Unicode font.
  - **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide icons.

---

## Commands

### Backend Commands
- `pip install -r requirements.txt` or `uv sync` — install Python dependencies
- `pytest` or `uv run pytest` — run the entire test suite
- `pytest backend/tests/test_smoke.py` or `uv run pytest backend/tests/test_smoke.py` — run one specific test file
- `uvicorn backend.app.main:app --reload` — start the FastAPI development server

### Frontend Commands
- `npm install` — install frontend dependencies
- `npm run dev` — start Vite frontend development server
- `npm test` — run frontend test suite (Vitest)
- `npm run build` — build production frontend assets

---

## Rules

1. **One Task at a Time:** Tasks are GitHub issues ([Issues Tracker](https://github.com/AslanMurzalin/FronProject/issues)). Work on strictly one issue at a time in numerical/dependency order.
2. **Review Criteria Before & After:** Always read the acceptance criteria before starting work on an issue, and re-read every bullet point before closing it.
3. **No Unapproved Dependencies:** Dependencies are pinned in `pyproject.toml` / `requirements.txt`. Do not add any new library or package without explicit user confirmation.
4. **Zero-Retention Demo Storage:** Demo files (`.dem`, `.dem.zst`) must never be stored long-term. Temporary files in `var/scratch_demos/` must be unlinked in a `finally` block on both success and failure.
5. **Facts vs. Interpretations:** All tactical analysis logic, report schemas, and UI components must strictly separate objective factual events (e.g. death timestamps, distances, zone presence) from tactical interpretations.
6. **Commit Regularly:** Make focused, conventional commits referencing the issue number (e.g. `feat(parser): add round boundary filter (#14)`).

---

## Core Documents

All detailed specifications live in the `docs/` folder:

- [`docs/process.md`](file:///C:/Users/aslan/PycharmProjects/FronProject/docs/process.md) — How work is organized, task workflow, and testing discipline.
- [`docs/issue_flow.md`](file:///C:/Users/aslan/PycharmProjects/FronProject/docs/issue_flow.md) — Anatomy of an issue, standard sections (Goal, Acceptance Criteria, Done Means, Out of Scope, Constraints), and verification lifecycle.
- [`docs/plan.md`](file:///C:/Users/aslan/PycharmProjects/FronProject/docs/plan.md) — Product specification, MVP scope boundaries, and analysis guardrails.
- [`docs/architecture.md`](file:///C:/Users/aslan/PycharmProjects/FronProject/docs/architecture.md) — Technical architecture (v2.1), data models, heuristics, scoring formulas, and security limits.
- [`docs/tasks.md`](file:///C:/Users/aslan/PycharmProjects/FronProject/docs/tasks.md) — Complete 42-task development backlog mapped to GitHub issues #1 through #42.
