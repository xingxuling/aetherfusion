# AetherFusion Release Notes

## v1.0.1 (2026-06-06) — Stabilization

### Scope
Stabilization release — no new core fusion capabilities. Focused on formalization,
usability, examples, quick validation, and release polish.

### Changes

- **RELEASE_NOTES.md**: New — documents v0.1 → v1.0 capability evolution, fusion-session
  core value, safety boundary summary.
- **QUICKSTART.md**: New — how to run `--help`, dry-run example, apply-confirm example,
  verify example, and how to read report files.
- **examples/**: New demo projects for smoke testing and onboarding:
  - `examples/demo-source/` — TypeScript project with `src/utils/` module (3 source files,
    package.json, tsconfig.json).
  - `examples/demo-target/` — TypeScript project without utils module (package.json,
    tsconfig.json).
- **scripts/smoke_test.py**: New — automated smoke test that runs scan → plan →
  patch --dry-run → fusion-session on the demo projects, exits non-zero on failure.
- **README.md**: Updated with v1.0.1 Quickstart link, `pip install -e .` recommendation,
  Windows PowerShell examples.
- **Version**: `__init__.py` bumped to `1.0.1`; all test assertions updated.

### Test Coverage
344 tests pass (no regression).

---

## v1.0.0 (2026-06-06) — Session Orchestration

### What It Is
v1.0 adds the `fusion-session` subcommand, an **orchestration layer** that chains
existing subcommands (scan → plan → patch → optional apply → optional verify →
optional diagnostic plans) into a single auditable, reusable session.

### Core Value

| Layer | Capability | Version |
|-------|-----------|---------|
| Scan | Project analysis, JSON map, fusion candidates | v0.1 |
| Plan | Module-level fusion planning, score analysis | v0.2 |
| Patch | Dry-run patch preview, unified diff | v0.3 |
| Apply | Safe add_file only, rollback manifest | v0.4 |
| Rollback | Undo apply, audit logging | v0.4.5 |
| Verify | Whitelisted command validation | v0.5 |
| Repair Plan | Error classification, actionable suggestions | v0.6 |
| Import Fix Plan | Import/path resolution analysis | v0.7 |
| Dependency Plan | Dependency update analysis | v0.8 |
| Config Plan | Config error analysis | v0.9 |
| **Fusion Session** | **End-to-end orchestration** | **v1.0** |

### Safety Boundaries
- **Default safe mode**: No apply without `--apply-confirm`
- **No verify without `--verify` flag**
- **No automatic dependency installation**
- **No automatic config modification**
- **No automatic import fixes**
- **No target file overwrites**
- **Apply only allows `add_file` operations**
- **No network requests** — entirely local

### fusion-session Flow
```
A. scan → fusion-report.md + fusion-map.json
B. Per module: plan → patch --dry-run → [optional apply]
C. [optional verify] → on failure: repair-plan + import-fix-plan + dependency-plan + config-plan
D. Final artifacts: fusion-session.json + fusion-session.md + artifact-index.json + audit event
```

### New Modules
- `aetherfusion/session/session_runner.py` — pipeline orchestrator
- `aetherfusion/session/session_state.py` — mutable session state tracker
- `aetherfusion/session/artifact_index.py` — artifact inventory
- `aetherfusion/reporter/session_json_reporter.py` — JSON session report
- `aetherfusion/reporter/session_markdown_reporter.py` — 13-section Markdown report

### Error Handling
- Source/target not found → exit 1
- Modules empty → exit 1
- Reports directory → auto-created
- Single module failure → recorded, other modules continue
- Verify failure → diagnostic plans generated, session still reports
- Artifact write failure → recorded in errors, session still reports
- Audit write failure → warning, workflow continues

### Test Coverage
24 new tests (344 total).

---

## v0.1–v0.9 Capability Evolution

### v0.1 — Project Scanning
- `scan` subcommand: source vs target project analysis
- Markdown report (9 sections) + JSON map
- Fusion plan candidates with scored modules
- Directory tree, dependency analysis, tech stack detection
- Git status inspection (read-only)

### v0.2 — Module Planning
- `plan` subcommand: detailed module-level fusion plan
- Score-aware plan generation (value/portability/conflict)
- 5-stage plan: inspect → copy → imports → config → dry-run preview
- Required human decisions (4 categories)

### v0.3 — Dry-Run Patch
- `patch` subcommand: dry-run preview only
- File classification: add_file / conflict / skip / review
- Path traversal detection, binary/size safety guards
- Unified diff output (add_file only)

### v0.4 — Safe Apply
- `apply` subcommand: confirmed add_file only
- Never overwrites target files
- Rollback manifest generation
- JSONL audit logging

### v0.4.5 — Rollback & Audit
- `rollback` subcommand: undo apply operations
- Path traversal protection for delete
- Protected config file exclusion
- Audit events for apply and rollback

### v0.5 — Verification
- `verify` subcommand: whitelisted command execution
- Auto-detection of project commands
- 120s timeout per command, blocking of dangerous commands
- Verify result JSON + Markdown

### v0.6 — Repair Planning
- `repair-plan` subcommand: error classification
- 9 error types: missing_import, missing_dependency, type_error, syntax_error,
  test_failure, config_error, command_not_found, timeout, unknown_error
- Severity/confidence scoring, automation eligibility

### v0.7 — Import Fix Planning
- `import-fix-plan` subcommand: import/path resolution analysis
- 7 import classifications: missing_local_file, wrong_relative_path,
  missing_alias_config, missing_index_export, source_only_dependency,
  package_missing, unresolved_unknown
- Target file indexer, source context support

### v0.8 — Dependency Planning
- `dependency-plan` subcommand: dependency analysis
- 14 regex patterns for Node.js and Python error extraction
- 6 classification rules: add_to_target through redirect_to_import_fix
- Builtin/stdlib exclusion (40 Node.js, 60+ Python)

### v0.9 — Config Planning
- `config-plan` subcommand: config error analysis
- tsconfig.json / vite.config.* / package.json configuration diff analysis