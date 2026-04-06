# Git Workflow

## Rules

1. **Never commit directly to `main`.** All work happens on a feature branch.
2. **Always pull before starting work.** Keeps your branch from diverging unnecessarily.
3. **One feature per branch.** Branch name must match the feature being built.
4. **Clear, descriptive commit messages.** State what changed and why, not just what.
5. **Open a Pull Request for every branch.** No direct merges — PR required even for solo work.
6. **All tests must pass before opening a PR.** Run `pytest tests/ -q` locally first.

---

## Exact Command Flow

```bash
# 1. Start from an up-to-date main
git pull origin main

# 2. Create a feature branch (name must describe the feature)
git checkout -b feature/<feature-name>
# Examples:
#   feature/player-hub-ui
#   feature/adp-explorer
#   feature/roster-flags-service
#   feature/combo-service

# 3. Make your changes
# (write code, run tests, verify nothing is broken)

# 4. Stage changes
git add .
# Prefer staging specific files when possible:
#   git add backend/services/roster_flags.py tests/services/test_roster_flags.py

# 5. Commit with a clear message
git commit -m "<type>: <short description>

<optional longer explanation if needed>"
# Types: feat | fix | refactor | test | docs | chore
# Examples:
#   feat: add roster_flags service with all 5 flag types
#   fix: correct ghost_player threshold from 7 to 10 days
#   test: add smoke tests for /api/adp endpoints

# 6. Push the branch
git push origin feature/<feature-name>

# 7. Open a Pull Request on GitHub
#    Title: matches commit message style
#    Body: what changed, why, how to test it
#    Link any related issues
```

---

## Branch Naming Conventions

| Work type | Pattern | Example |
|---|---|---|
| New feature | `feature/<name>` | `feature/adp-explorer` |
| Bug fix | `fix/<name>` | `fix/lineup-setter-flex` |
| Refactor | `refactor/<name>` | `refactor/bpcor-service` |
| Tests only | `test/<name>` | `test/etl-coverage` |
| Docs | `docs/<name>` | `docs/api-reference` |

---

## Commit Message Format

```
<type>(<scope>): <short summary>

<body — optional, explains the why>
```

**Note:** Do NOT add `Co-Authored-By` trailers to commits. This repo is private and Vercel Hobby plan blocks deployments from commits it cannot associate with a single GitHub user.

**Types:** `feat` `fix` `refactor` `test` `docs` `chore`  
**Scope:** the module or area affected, e.g. `bpcor`, `adp-router`, `nightly-etl`

---

## Pull Request Checklist

Before opening a PR:

- [ ] `pytest tests/ -q` passes with 0 failures
- [ ] No hardcoded secrets, credentials, or local paths
- [ ] New functionality has at least one test
- [ ] Branch is up to date with `main` (`git pull origin main` + rebase if needed)
- [ ] PR description explains what changed and how to verify it
