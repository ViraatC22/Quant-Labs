# Quant Labs Completion Plan

**Recovery branch:** `automation/quant-labs-recovery`

**Plan date:** 2026-07-29

Statuses: `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`,
`DEFERRED_WITH_REASON`.

## Milestone 0 — Preservation and repository safety

### QL-001 — Preserve the pre-automation v3 work

- **Reason:** The working tree contained 17,000+ lines of intentional desk,
  graph, research, reporting, webhook, test, and poster work.
- **Files/modules:** 121 staged product files across `apps/web`, `services/api`,
  and `docs`.
- **Dependencies:** Secret and large-file scan; unrelated artifacts excluded.
- **Acceptance criteria:** Named backup branch exists; intentional product work
  is committed; `.env`, generated directories, and unrelated academic
  artifacts are absent from the commit.
- **Verification:** `git show --stat 2b23575`; `git status --short`.
- **Status:** `COMPLETED`
- **Commit:** `2b23575cc385efbf7812592d34da8e06faee8923`

### QL-002 — Add recovery audit and executable plan

- **Reason:** The repository had product roadmaps but no recovery-state audit.
- **Files/modules:** `docs/PROJECT_AUDIT.md`, `docs/COMPLETION_PLAN.md`.
- **Dependencies:** QL-001 and baseline quality-gate results.
- **Acceptance criteria:** Audit is evidence-based and identifies verified,
  deferred, externally dependent, and security-limited scope.
- **Verification:** Manual review; `git diff --check`.
- **Status:** `COMPLETED`
- **Commit:** `16ec02c`

## Milestone 1 — Reproducible quality gate and hygiene

### QL-101 — Add one-command local verification

- **Reason:** The README lists seven commands but there is no canonical gate,
  which makes local and automation results easy to diverge.
- **Files/modules:** `scripts/verify.sh`, `README.md`, root `package.json`.
- **Dependencies:** Existing API virtual environment and web dependencies.
- **Acceptance criteria:** One command runs API Ruff/Pyright/Pytest and web
  ESLint/TypeScript/Vitest/build. It also runs Compose configuration validation
  when Docker is installed and reports an explicit limitation otherwise. Any
  executed failing check returns nonzero.
- **Verification:** `npm run verify`.
- **Status:** `IN_PROGRESS`
- **Commit:** Pending.

### QL-102 — Keep unrelated artifacts out of repository state

- **Reason:** Three preserved academic artifact paths appear as untracked
  Quant Labs changes.
- **Files/modules:** `.gitignore`.
- **Dependencies:** Evidence that paths are unrelated; no deletion.
- **Acceptance criteria:** Files remain on disk, are ignored, and no broad rule
  hides legitimate product assets.
- **Verification:** `test -e` for all three paths; `git status --short`.
- **Status:** `IN_PROGRESS`
- **Commit:** Pending.

## Milestone 2 — Final verification and handoff

### QL-201 — Run canonical local verification

- **Reason:** Completion claims must be backed by one repeatable result.
- **Files/modules:** Entire API/web tree and Compose configuration.
- **Dependencies:** QL-101.
- **Acceptance criteria:** All local checks pass without weakening any gate.
- **Verification:** `npm run verify`.
- **Status:** `NOT_STARTED`
- **Commit:** Not applicable (verification result).

### QL-202 — Publish final project status

- **Reason:** The final coherent scope, deferred work, external checks, branch,
  remote, and commit must be explicit.
- **Files/modules:** `README.md`, `docs/FINAL_STATUS.md`,
  `docs/COMPLETION_PLAN.md`.
- **Dependencies:** QL-201.
- **Acceptance criteria:** Documentation matches the verified repository state.
- **Verification:** `git diff --check`; full diff review.
- **Status:** `NOT_STARTED`
- **Commit:** Pending.

### QL-203 — Push the tested recovery branch

- **Reason:** The verified work must be recoverable from the configured owner
  repository without altering `main`.
- **Files/modules:** Git remote state.
- **Dependencies:** QL-201 and QL-202.
- **Acceptance criteria:** `origin/automation/quant-labs-recovery` matches local
  HEAD and tracks `https://github.com/ViraatC22/Quant-Labs.git`.
- **Verification:** `git status -sb`; `git ls-remote origin`.
- **Status:** `NOT_STARTED`
- **Commit:** Not applicable.

## Deferred product milestones

### QL-D01 — Browser E2E and accessibility suite

- **Status:** `DEFERRED_WITH_REASON`
- **Reason:** Important future quality work, but the current repository provides
  no E2E harness or acceptance fixtures. It is not required to repair a failing
  local build, and adding a speculative suite would exceed this bounded
  recovery milestone.

### QL-D02 — Production authentication and hosting

- **Status:** `DEFERRED_WITH_REASON`
- **Reason:** No deployment target or multi-user product requirement is selected.
  The app remains explicitly local/single-user and safely ignores user
  impersonation headers outside local mode.

### QL-D03 — Async worker implementation

- **Status:** `DEFERRED_WITH_REASON`
- **Reason:** The worker is documented as a placeholder and no shipped flow
  depends on it. Implement it when ingestion/backtest latency creates a measured
  queued-work requirement.
