# Coding Execution Rules

## Before Starting Any Work

1. **Run `/bestball`** — load the full app spec into context and verify the 5 key rules before writing a single line of code. Do not proceed without this step.
2. **Read `docs/project_context.md`** — confirm repo location, stack, and data sources.
3. **Read `docs/workflow.md`** — create the correct branch before touching any files.
4. **Match the branch name to the feature exactly.** If the feature is "roster flags service", the branch is `feature/roster-flags-service`.

---

## Code Quality Standards

### Modularity
- Each service, ETL module, and router lives in its own file.
- No file does more than one job. If it does, split it.
- Business logic stays in `services/`. Routers only call services — no raw SQL in routers.
- ETL steps stay in `etl/`. The nightly orchestrator (`scripts/nightly_etl.py`) only calls ETL functions — no inline data logic.

### Completeness
- **Return complete scripts, not partial snippets.** Every file delivered must be runnable as-is.
- If modifying an existing file, include all existing content with changes applied — do not return only the changed section.
- If a function references a helper that doesn't exist yet, create the helper in the same session.

### Production quality
- No `TODO` comments left in delivered code.
- No placeholder logic (e.g., `return []`, `pass`, `# implement later`) in non-stub functions.
- No hardcoded file paths that differ between dev and prod — use constants or config.
- No `print()` statements in production code — use `logging`.
- Handle the empty/no-data case explicitly. Every function that queries the DB or reads Parquet must handle the case where no rows are returned.

### Comments
- Comment non-obvious logic only. Self-explanatory code does not need comments.
- Every module must have a top-level docstring explaining its purpose and what it does.
- Every public function must have a one-line docstring if its purpose isn't immediately obvious from the name.

---

## Testing Requirements

- Every new service function gets at least one test covering the happy path.
- Every edge case mentioned in `docs/app-spec.md` gets its own test.
- Tests use in-memory SQLite — never a real `bestball.db`.
- Test file naming: `tests/<layer>/test_<module>.py` — e.g., `tests/services/test_roster_flags.py`.
- Run `pytest tests/ -q` before marking any task complete. Zero failures required.

---

## Spec Compliance

- **`docs/app-spec.md` is the source of truth.** When in doubt about business logic, scoring rules, flag thresholds, or data definitions, read the spec — do not invent behavior.
- Key rules to hold in memory at all times:
  - Scoring: hitters `1B×3 + 2B×6 + 3B×8 + HR×10 + RBI×2 + R×2 + SB×4 + BB×3 + HBP×3`
  - Scoring: pitchers `IP×3 + K×3 + W×5 + QS×5 + ER×(-3)`, QS = ≥6 IP and ≤3 ER
  - Lineup: top 3P + 3IF + 3OF starters, FLEX = highest remaining IF/OF (never P)
  - Replacement level: per-roster, per-week — not a global constant
  - BPCOR: `max(0, contributed_score − replacement_score)` per player per week
  - All roster flag thresholds are in `backend/constants.py` — never hardcode them

---

## Task Completion Checklist

Before marking any task done:

- [ ] `/bestball` was run at session start
- [ ] Correct feature branch created and checked out
- [ ] Code is complete (no stubs, no TODOs)
- [ ] All referenced helpers/imports exist
- [ ] Tests written and passing (`pytest tests/ -q`)
- [ ] Branch pushed to GitHub
- [ ] PR opened with description
