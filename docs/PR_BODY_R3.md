# PR: ci — add CI/CodeQL/release workflows and sync docs (R3)

> Branch: `arena/01a02949-eovpn-pro` → `master`

## Summary

Implements the action plan from the third-round senior audit
([`docs/REVIEW_SENIOR_2026-08-R3.md`](../REVIEW_SENIOR_2026-08-R3.md)). The
audit found the codebase itself needed **no code changes** (Ruff / mypy / 81
unit tests all green); the single critical gap was the **absence of CI/CD
automation** while `README.md`, `SECURITY.md`, `PACKAGING.md` and `CHANGELOG.md`
already promised it.

## Added — three GitHub Actions workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| [`ci.yml`](../../.github/workflows/ci.yml) | push to `master` + PRs | Ruff lint+format, mypy, **81 offline unit tests** on Python 3.10/3.11/3.12 + coverage, metadata consistency, `pip-audit --strict`, a full Meson build with desktop/AppStream validation, and `.deb` / `.rpm` / `.arch` smoke builds |
| [`codeql.yml`](../../.github/workflows/codeql.yml) | push, PRs, weekly | `security-extended` CodeQL for Python **and** the compiled C bindings (a real `meson compile` drives the C compiler so CodeQL traces it) |
| [`release.yml`](../../.github/workflows/release.yml) | tag `v*.*.*` | version-parity check, builds all 5 formats in parallel, build-provenance attestations for `.deb` + AppImage, `SHA256SUMS`, publishes the GitHub Release |

## Changed (Minimal Diff — no source code touched)

- `README.md`, `CHANGELOG.md`, `PACKAGING.md`: corrected the offline test count
  **56 → 81** everywhere (English + Persian); the CI/Release badges and tables
  are now backed by real files.
- `PACKAGING.md`: closed an unclosed code fence in §6 so §7 renders as prose
  instead of a code block.

## Bugs caught & fixed during internal QA review

- **`appstream-util` is being removed from Debian/Ubuntu** (appstream-glib
  `0.8.3-3`, 2026-03) → switched to the maintained `appstreamcli`.
- **`pip install -r requirements-dev.txt` would fail on CI** — PyGObject can't
  pip-build without GObject dev headers, and the offline tests don't need `gi`
  → each job installs only the tools it uses.
- **GitHub Actions gotcha:** job-level `permissions:` replace the top-level
  set, which drops `contents: read` needed by `actions/checkout` → restated it
  on the `deb`, `appimage` and CodeQL `analyze` jobs.
- Corrected the `tag_name` ternary for the `workflow_dispatch` trigger.

## Verification

- `ruff check` ✅ · `ruff format --check` ✅ · `mypy` ✅ (26 files)
- **81/81 unit tests** ✅ · `scripts/check_project_meta.py` ✅
- All three workflow YAML files validated.
- Opening this PR runs `ci.yml` + `codeql.yml` on the PR itself, validating the
  workflows end-to-end.

## Notes

- No business logic, Python source, or C bindings were modified — CI/CD + docs
  only. Kill-switch / DNS-leak protection remain tracked in
  `docs/SECURITY-ROADMAP.md` for 1.6.0 (out of scope).

Closes the P0 gap from the R3 audit.

*یا علی مدد* 💚
