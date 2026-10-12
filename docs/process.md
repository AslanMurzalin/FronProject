# Development Process & Workflow

This document sets the ground rules for how engineering work is organized, executed, and validated in this repository.

## Core Rules

- **Tasks are GitHub issues, one at a time.** Never implement multiple issues in a single batch. Keep each pull request or commit series scoped strictly to one issue number.
- **Read the acceptance criteria before starting and before closing.** The issue specification is the contract. Check every bullet point before writing code and re-verify every bullet before declaring an issue done.
- **Commit regularly.** Make small, focused commits with clear conventional commit messages (e.g. `feat:`, `fix:`, `test:`, `docs:`, `refactor:`). Never bundle unrelated refactors into a task commit.

## Issue Execution Workflow

1. **Pick the next sequential issue** from [github.com/AslanMurzalin/FronProject/issues](https://github.com/AslanMurzalin/FronProject/issues) or `docs/tasks.md`.
2. **Review prerequisites**: Check if the issue depends on previously merged tables, predicates, or fixtures.
3. **Follow `docs/issue_flow.md`**: Pay strict attention to the *Constraints*, *Out of Scope*, and *Done Means* sections.
4. **Implement tests first or alongside code**: Every behavior specified in *Done Means* must have an automated test in `backend/tests/` (or `frontend/src/__tests__/`).
5. **Execute tests and verify clean state**:
   ```bash
   # Run full test suite
   pytest

   # Run specific test file
   pytest backend/tests/test_<name>.py
   ```
6. **Zero-retention verification**: Any test or service dealing with demos must confirm temporary files are unlinked.
7. **Audit against acceptance criteria**: Review the issue checklist. Ensure no scope creep occurred and no acceptance criterion was missed.
8. **Commit and push**: Reference the issue number in the commit message (e.g. `test: add trade detection tests (#18)`).
