---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: b43d9e79e7d49311cb99af87a8f606d0_0d49767a611811f19f62525400d9a7a1
    ReservedCode1: eQ2maYGFnuSaTyRiJFfAy+Ivrt9z0GR/hZN6EEEaAacmx+aQUWzSquyPMH1DOhAn79J4QmfpsqEmCfNNLHO7o5fGijAEHevp6ghJsiaT1nxnDBLDyxoqQCB5jiXxK2WBynIROIwdyoKyTEGlKR0zhAxGtA06jfWWP0i6FIj78J4jN0MJ7N9lXb7a0WM=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: b43d9e79e7d49311cb99af87a8f606d0_0d49767a611811f19f62525400d9a7a1
    ReservedCode2: eQ2maYGFnuSaTyRiJFfAy+Ivrt9z0GR/hZN6EEEaAacmx+aQUWzSquyPMH1DOhAn79J4QmfpsqEmCfNNLHO7o5fGijAEHevp6ghJsiaT1nxnDBLDyxoqQCB5jiXxK2WBynIROIwdyoKyTEGlKR0zhAxGtA06jfWWP0i6FIj78J4jN0MJ7N9lXb7a0WM=
---













# AetherFusion v1.0.1

Local Code Project Fusion Tool — End-to-End Session Orchestration

Scans two local projects and runs a complete fusion session: scan → plan → patch → optional apply → optional verify → optional diagnostic plans. v1.0 is an **orchestration layer** that chains existing subcommands into a single auditable, reusable session. It does not add new repair capabilities.

**Safe by default** — no apply without `--apply-confirm`, no verify without `--verify`, no automatic dependency installation, no automatic config modification, no automatic import fixes, no target file overwrites, apply only allows `add_file` operations.

## What's New in v1.0.0

- **`fusion-session` subcommand**: chains scan → plan → patch → optional apply → optional verify → optional diagnostic plans into one auditable, reusable session
- **Session orchestration**: v1.0 is an orchestration layer — no new repair/fix capabilities, uses existing v0.1–v0.8 subcommands
- **Per-module step tracking**: each module gets plan → patch → apply status with full artifact paths
- **Diagnostic plan auto-generation**: when verify fails, automatically generates repair-plan / import-fix-plan / dependency-plan / config-plan
- **Session artifacts**: `fusion-session.json` (full session state), `fusion-session.md` (13-section Markdown report), `artifact-index.json` (artifact inventory)
- **Audit integration**: session start/completion events appended to JSONL audit log
- **Default safe mode**: no apply without `--apply-confirm`, no verify without `--verify` flag
- **Individual module failure isolation**: failed modules recorded in session report without losing overall session output
- **Session state tracking**: `session_id` (UUID), `source_path`, `target_path`, `modules`, `mode`, per-module results, verify summary, diagnostic plans, blocked operations, rollback manifests
- New modules: `session/session_runner.py`, `session/session_state.py`, `session/artifact_index.py`, `reporter/session_json_reporter.py`, `reporter/session_markdown_reporter.py`
- **24 new tests** (344 total)

## Quickstart

See **[QUICKSTART.md](./QUICKSTART.md)** for a step-by-step guide covering:

- Installation via `pip install -e .`
- Smoke test with `python scripts/smoke_test.py`
- Windows PowerShell examples for all subcommands
- How to read each report file format

## What's New in v1.0.1

**Stabilization release** — no new core fusion capabilities. Focused on formalization, usability, examples, and quick validation.

- **[RELEASE_NOTES.md](./RELEASE_NOTES.md)**: documents v0.1 → v1.0 capability evolution, fusion-session core value, safety boundary summary
- **[QUICKSTART.md](./QUICKSTART.md)**: how to run `--help`, dry-run example, apply-confirm example, verify example, report file reference
- **[examples/](./examples/)**: demo TypeScript projects for smoke testing — `demo-source` (has utils module) and `demo-target` (missing utils module)
- **[scripts/smoke_test.py](./scripts/smoke_test.py)**: automated scan → plan → patch --dry-run → fusion-session pipeline on demo projects
- **Installation**: recommended `pip install -e .` for development; Windows PowerShell examples added
- **Version**: `1.0.1`; all 344 tests pass

Install and verify:

```powershell
# Windows PowerShell
cd path\to\aetherfusion
pip install -e .
python -m aetherfusion --version
python scripts/smoke_test.py
```

## What's New in v0.8.0

- **`dependency-plan` subcommand**: analyses missing_dependency errors from repair-plan / import-fix-plan and generates a structured dependency update plan
- **Dependency error extraction**: 14 regex patterns covering Node.js (Cannot find module / Can't resolve) and Python (ModuleNotFoundError / ImportError) error formats
- **Dependency file parsing**: read-only parsing of package.json (dependencies / devDependencies / optionalDependencies / peerDependencies), requirements.txt, pyproject.toml (dependencies / poetry), lock files (presence-only)
- **6-classification rules**: add_to_target / review_version_conflict / likely_not_dependency_issue / manual_research / builtin_or_stdlib_skipped / redirect_to_import_fix
- **Comprehensive builtin/stdlib lists**: 40 Node.js builtins (fs, path, crypto, etc.) and 60+ Python stdlib modules (os, sys, json, etc.) automatically excluded
- **Source vs target analysis**: compares dependency manifests from both projects, detects mismatches, version conflicts, and missing packages
- **JSON / Markdown / audit output**: 8-section Markdown report, structured JSON plan, audit event appended
- New modules: `dependency/dependency_error_extractor.py`, `dependency/dependency_file_parser.py`, `dependency/dependency_planner.py`, `reporter/dependency_json_reporter.py`, `reporter/dependency_markdown_reporter.py`

## What's New in v0.7.0 (previous)

- **`import-fix-plan` subcommand**: analyses missing_import errors from a v0.6 repair-plan JSON and generates a targeted import/path fix plan
- **Import error extraction**: supports TS2307, webpack Module not found, Python ModuleNotFoundError/ImportError patterns
- **7 import classifications**: missing_local_file / wrong_relative_path / missing_alias_config / missing_index_export / source_only_dependency / package_missing / unresolved_unknown
- **Target file indexer**: builds a read-only index of the target project for import resolution analysis (ignores node_modules/.git/dist/build/__pycache__, skips binary and >1MB files)
- **Optional source context**: accepts `--patch` and `--apply` inputs to detect source_only_dependency scenarios
- **Each fix candidate scored**: confidence (0-100), risk_level (low/medium/high), automation_eligibility (manual_only/plan_only/safe_auto_candidate)
- **JSON / Markdown / audit output**: import fix plan JSON with full classification, Markdown report with 7 sections, audit event appended
- New modules: `importfix/import_error_extractor.py`, `importfix/target_indexer.py`, `importfix/import_fix_planner.py`, `reporter/import_fix_json_reporter.py`, `reporter/import_fix_markdown_reporter.py`

## What's New in v0.6.0 (previous)

- **`repair-plan` subcommand**: analyses verify result failures and generates a classified repair plan
- **Error classification**: 9 error types — missing_import, missing_dependency, type_error, syntax_error, test_failure, config_error, command_not_found, timeout, unknown_error
- **Each repair item scored**: severity (low/medium/high), confidence (0-100), automation_eligibility (manual_only/plan_only/safe_auto_candidate)
- **Actionable suggestions**: missing_import → check import paths, missing_dependency → generate dependency-plan, type_error → human review, etc.
- **JSON / Markdown / audit output**: repair plan JSON with full error classification, Markdown report with 7 sections, audit event appended
- **35 new tests** (231 total)
- New modules: `repair/error_classifier.py`, `repair/repair_planner.py`, `reporter/repair_json_reporter.py`, `reporter/repair_markdown_reporter.py`

## What's New in v0.5.0 (previous)

- **`verify` subcommand**: runs safe whitelisted validation commands (npm run build, npx tsc --noEmit, pytest, etc.) against the target project
- **Auto-detection**: detects package.json, tsconfig.json, pytest.ini, pyproject.toml, and tests/ directory to suggest appropriate verification commands
- **Safe execution**: 120-second timeout per command, single command failure doesn't stop verification, all commands restricted to target cwd
- **Whitelist only**: blocks rm/del, curl/wget, git push, install commands, shell splicing
- **JSON / Markdown / audit output**: verify results include per-command status (passed/failed/skipped/timeout/blocked), exit code, duration, stdout/stderr tails
- **Audit integration**: verify events appended to the existing JSONL audit log
- **41 new tests** (196 total)
- New modules: `verifier/command_detector.py`, `verifier/safe_runner.py`, `verifier/verify_runner.py`, `reporter/verify_json_reporter.py`, `reporter/verify_markdown_reporter.py`

## What's New in v0.4.5 (previous)

## What's New in v0.3.0 (previous)

- **`patch` subcommand**: dry-run patch preview from a fusion plan JSON
- **File classification**: `add_file` / `conflict_same_name` / `skip_unsafe` / `review_import_dependency`
- **Safety guardrails**: path traversal detection, binary file detection, 1 MB size limit
- **Unified diff output**: add_file-only diff generation (no overwrite diffs)
- **`--dry-run` required**: patch command refuses to run without explicit `--dry-run` flag

## What's New in v0.2.0 (previous)

- **`plan` subcommand**: generates detailed module-level fusion plans from a JSON project map
- **`fusion_planner.py`**: scoring-aware plan generation with ordered steps, human decisions, and blocked actions
- **Step-by-step plans**: 5-stage plan (inspect → copy → imports → config → dry-run preview)
- **Required human decisions**: 4 decision categories (file conflicts, dependencies, routes, structure)
- **`score_breakdown`**: each fusion candidate now includes value/portability/conflict reasoning

## What's New in v0.1.5 (previous)

- `--json` output: machine-readable project map for agent consumption
- `fusion_plan_candidates`: scored module candidates with priority/risk/action
- Git status inspection: clean / dirty / not_git_repo (read-only)

## Supported Project Types

- Node.js / React / Vite / TypeScript / JavaScript
- Python (pip / pyproject.toml)

## What It Scans

| Category | Details |
|----------|---------|
| Config files | `package.json`, `requirements.txt`, `pyproject.toml`, `tsconfig.json`, `vite.config.*`, `next.config.*`, `tailwind.config.*`, `webpack.config.js`, `Dockerfile`, `docker-compose.yml`, and more |
| Entry files | `src/index.tsx`, `src/main.py`, `src/App.tsx`, etc. |
| Core directories | All top-level dirs (ignoring `node_modules`, `.git`, `dist`, `build`, `__pycache__`, `venv`, etc.) |
| Dependencies | From `package.json` (dependencies + devDependencies) and `requirements.txt` / `pyproject.toml` |
| Scripts | From `package.json` scripts and `pyproject.toml` `[project.scripts]` |
| Directory tree | Up to 4 levels deep, 30 files per dir max (with truncation markers) |
| Git status | Branch, clean/dirty, changed files count (read-only) |

## What the Reports Include

**Markdown report (`--out`):**
1. Project Overview
2. Scan Summary
3. Tech Stack Comparison
4. Dependency Analysis
5. Directory Trees
6. Structure Comparison
7. Fusible Modules
8. Conflict Risks
9. Recommendations

**JSON map (`--json`):**
1. Report metadata (tool, version, schema_version, timestamp)
2. Source & target project summaries (incl. git_status/branch)
3. Tech stack comparison (shared, unique)
4. Dependencies (common, unique, version conflicts)
5. Directory structure comparison
6. Fusible modules list
7. Conflict risks (version, name, script, entry)
8. **Fusion plan candidates** — scored module candidates for downstream agent
9. Recommendations
10. Git status (both projects)

## Fusion Plan Candidates

Each candidate in the JSON map includes:

| Field | Type | Description |
|-------|------|-------------|
| `module_name` | string | Module identifier (e.g. "components", "utils") |
| `module_type` | string | Inferred module type |
| `source_paths` | list | Absolute paths in source project |
| `target_paths` | list | Absolute paths in target project |
| `value_score` | 0-100 | How valuable this module is to bring over |
| `portability_score` | 0-100 | How easy it is to migrate |
| `conflict_score` | 0-100 | Estimated conflict severity |
| `priority_score` | float | Composite: value * portability / conflict |
| `risk_level` | low/medium/high | Overall risk classification |
| `reason` | string | Human-readable justification |
| `recommended_action` | string | proceed_to_fuse / copy_to_target / manual_review / review_and_replan |

## Requirements

- Python 3.9+ (Python 3.11+ recommended for full `pyproject.toml` parsing via `tomllib`)
- No external dependencies (stdlib only for scanning)
- `pytest` (for running tests only)

## Installation

```bash
# Clone or copy the aetherfusion directory into your project

# Recommended: editable install (pip install -e .)
pip install -e .

# Or run directly without install
python -m aetherfusion scan --help
```

Quick smoke test on Windows:

```powershell
cd path\to\aetherfusion
pip install -e .
python scripts/smoke_test.py
```

## Usage

### CLI — Plan (Module-Level Fusion Plan)

> **v0.2:** Planning only — no files are modified.

```bash
# Generate a fusion plan for the 'components' module
python -m aetherfusion plan \
  --map ./reports/aetherfusion-map.json \
  --module components \
  --out ./reports/fusion-plan-components.md \
  --json ./reports/fusion-plan-components.json
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--map` | yes | — | Path to the JSON project map from `aetherfusion scan --json` |
| `--module` | yes | — | Module name (must be in fusion_plan_candidates, e.g. components, utils, services) |
| `--out` | no* | none | Output path for the Markdown fusion plan |
| `--json` | no* | none | Output path for the JSON fusion plan |

*\* At least one of `--out` or `--json` must be provided.*

The plan includes:
- **Score summary**: value / portability / conflict / priority
- **5 ordered steps**: inspect same-named files → copy non-conflicting → review imports → check config → dry-run preview
- **4 human decision categories**: same-named files (overwrite/namespace/skip/manual_merge), dependency updates, route integration, directory structure preservation
- **5 blocked actions**: no modify, no overwrite, no dependency changes, no build/test, no network
- **Next recommended command**: for re-running the plan

If the module does not exist in `fusion_plan_candidates`, the command exits with a non-zero code and lists available modules.

### CLI — Patch (Dry-Run Preview)

> **v0.3:** Dry-run only — no source or target files are modified. `--dry-run` is mandatory.

```bash
# Generate a dry-run patch preview for the 'components' module
python -m aetherfusion patch \
  --plan ./reports/fusion-plan-components.json \
  --out ./reports/fusion-patch-components.md \
  --json ./reports/fusion-patch-components.json \
  --diff ./reports/fusion-patch-components.diff \
  --dry-run
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--plan` | yes | — | Path to the v0.2 fusion plan JSON from `aetherfusion plan --json` |
| `--dry-run` | **yes** | `False` | Required — patch only operates in dry-run mode (v0.3) |
| `--out` | no* | none | Output path for the Markdown patch preview |
| `--json` | no* | none | Output path for the JSON patch manifest |
| `--diff` | no* | none | Output path for the unified diff file (add_file operations only) |

*\* At least one of `--out`, `--json`, or `--diff` must be provided.*

**Patch manifest JSON** contains:
- `patch_version`, `mode` (always `dry_run`)
- `module_name`, `source_module_path`, `target_match_path`
- `summary`: `files_to_add`, `files_conflicted`, `files_skipped`
- `operations`: list of `add_file` / `conflict_same_name` / `skip_unsafe`
- `blocked_actions`: 5 safety constraints (no modify, no overwrite, no dependency changes, no build/test, no network)
- `required_human_decisions`: conflict resolution and import review
- `next_recommended_command`

**Markdown patch preview** includes: Summary, Safe Additions, Conflicts, Import Notes, Skipped Files, Blocked Actions, Required Decisions, Next Command.

**Diff output**: unified diff format (only for `add_file` operations — never generates overwrite diffs).

**Safety guarantees**:
- `--dry-run` is mandatory; the command refuses to run without it
- Path traversal detection (paths with `..` are rejected)
- Binary files are skipped (detected via null-byte scan)
- Files larger than 1 MB are marked `skip_unsafe`
- `node_modules`, `.git`, `dist`, `build`, `__pycache__` are excluded
- No source or target files are modified

### CLI — Apply (Confirmed File Addition)

> **v0.4:** Applied with explicit `--confirm`. Only `add_file` operations are applied — no overwrites, no dependency changes, no build/test.

```bash
# Safely apply non-conflicting new files to the target project
python -m aetherfusion apply \
  --patch ./reports/fusion-patch-components.json \
  --confirm \
  --backup ./reports/apply-backup-components.json \
  --json ./reports/apply-result-components.json \
  --out ./reports/apply-result-components.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--patch` | yes | — | Path to the v0.3 patch manifest JSON from `aetherfusion patch --json` |
| `--confirm` | **yes** | `False` | Required — explicitly authorize file copying |
| `--out` | no* | none | Output path for the Markdown apply report |
| `--json` | no* | none | Output path for the JSON apply result |
| `--backup` | no | none | Output path for the rollback manifest (JSON) |

*\* At least one of `--out` or `--json` must be provided.*

**What gets applied:**
- Only `type: add_file` operations where the target file does **not** already exist
- Source files that pass safety checks (non-binary, under 1 MB, no path traversal)

**What gets blocked:**
- `conflict_same_name` — not supported (requires human merge decision)
- `skip_unsafe` — binary files, oversized files, path traversal attempts
- `review_import_dependency` — dependency resolution deferred to v0.5+
- Target file already exists — never overwrites
- Unknown operation types

**Apply result JSON** contains:
- `apply_version`, `mode` (always `confirmed_apply`)
- `module_name`, `source_module_path`, `target_match_path`
- `summary`: `files_applied`, `files_skipped`, `files_blocked`, `files_failed`, `directories_created`
- `operations_applied`, `operations_skipped`, `operations_blocked`, `operations_failed`
- `rollback_manifest_path`
- `next_recommended_command`

**Rollback manifest** (`--backup`) contains:
- `created_files`: list of absolute paths of newly created files
- `skipped_files`, `blocked_files`
- `rollback_actions`: "These files were copied into the target project."
- `rollback_command_hint`: command to delete the created files

### Manual Rollback → Replaced by `rollback` in v0.4.5

Use the `rollback` subcommand (see below) instead of manual deletion.

### CLI — Rollback (Undo Apply)

> **v0.4.5:** Deletes files created by `apply` using a rollback manifest. `--confirm` is mandatory.

```bash
# Roll back files created by the last apply operation
python -m aetherfusion rollback \
  --manifest ./reports/apply-backup-components.json \
  --confirm \
  --json ./reports/rollback-result-components.json \
  --out ./reports/rollback-result-components.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--manifest` | yes | — | Path to the v0.4 rollback manifest JSON (from `apply --backup`) |
| `--confirm` | **yes** | `False` | Required — explicitly authorize file deletion |
| `--out` | no* | none | Output path for the Markdown rollback report |
| `--json` | no* | none | Output path for the JSON rollback result |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to the audit log JSONL file |

*\* At least one of `--out` or `--json` must be provided.*

**What gets deleted:**
- Only files listed in the manifest's `created_files` (i.e., files that `apply` created)
- Files that still exist on disk

**What gets blocked:**
- Path traversal attempts (`..` in paths)
- Protected config files (package.json, requirements.txt, pyproject.toml, tsconfig.json, vite.config.*, etc.)
- Files outside the target project

**What gets recorded without error:**
- Files already missing (`already_missing`)
- Failed deletions (`failed` — does not stop processing other files)

**Rollback result JSON** contains:
- `rollback_version`, `mode` (always `confirmed_rollback`)
- `manifest_file`, `module_name`, `target_match_path`
- `summary`: `files_deleted`, `files_already_missing`, `files_blocked`, `files_failed`
- Per-file detail lists: `files_deleted`, `files_already_missing`, `files_blocked`, `files_failed`
- `next_recommended_command`

### Audit Logging

> **v0.4.5:** Every `apply` and `rollback` operation appends a JSONL audit event.

The audit log defaults to `reports/aetherfusion-audit.jsonl` and can be customized with `--audit`.

```bash
# Apply with custom audit path
python -m aetherfusion apply \
  --patch ./reports/fusion-patch-components.json \
  --confirm \
  --audit ./logs/audit.jsonl \
  --out ./reports/apply-result.md

# Rollback with custom audit path
python -m aetherfusion rollback \
  --manifest ./reports/apply-backup-components.json \
  --confirm \
  --audit ./logs/audit.jsonl \
  --out ./reports/rollback-result.md
```

**Audit event schema:**

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `"apply"` or `"rollback"` | Operation type |
| `version` | string | AetherFusion version at time of operation |
| `timestamp` | ISO 8601 | UTC timestamp of the event |
| `input_file` | string | Path to the patch manifest or rollback manifest |
| `summary` | object | Operation summary (files_applied, files_deleted, etc.) |
| `result_json_path` | string | Path to the result JSON (if saved) |
| `backup_or_manifest_path` | string | Path to the backup/rollback manifest |

If audit log writing fails (e.g., disk full, permission denied), a warning is printed but the main operation continues normally.

### CLI — Verify (Run Validation)

> **v0.5.0:** Run safe whitelisted validation commands against the target project. Read-only — never installs, never modifies files.

```bash
# Auto-detect commands from project config
python -m aetherfusion verify \
  --target ./project-a \
  --json ./reports/verify-result.json \
  --out ./reports/verify-result.md

# Specify explicit commands (comma-separated)
python -m aetherfusion verify \
  --target ./project-a \
  --commands "npm run build,npx tsc --noEmit,pytest" \
  --json ./reports/verify-result.json \
  --out ./reports/verify-result.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--target` | yes | — | Path to the target project root |
| `--out` | no* | none | Output path for the Markdown verify report |
| `--json` | no* | none | Output path for the JSON verify result |
| `--commands` | no | auto-detect | Comma-separated list of commands to run |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to the audit log JSONL file |

*\* At least one of `--out` or `--json` must be provided.*

**Auto-detection:**
- `package.json` with `scripts.build` → `npm run build`
- `package.json` with `scripts.test` → `npm test`
- `package.json` with `scripts.lint` → `npm run lint`
- `package.json` with `scripts.typecheck` → `npm run typecheck`
- `tsconfig.json` → `npx tsc --noEmit`
- `pytest.ini` / `pyproject.toml [tool.pytest]` / `setup.cfg [tool:pytest]` → `pytest`
- `tests/` with Python test files → `pytest`

**Allowed commands (whitelist only):**
`npm run build`, `npm test`, `npm run test`, `npm run lint`, `npm run typecheck`, `npx tsc --noEmit`, `pytest`, `python -m pytest`

**Blocked commands:**
`rm`, `del`, `curl`, `wget`, `git push`, `npm install`, `pip install`, shell splicing (`;`, `&&`, `|`)

**Per-command result fields:** `command`, `status` (passed/failed/skipped/timeout/blocked), `exit_code`, `duration_ms`, `stdout_tail`, `stderr_tail`, `reason`

**Timeout:** 120 seconds per command. Single command failure does not stop remaining commands. Audit event appended on completion.

### CLI — Repair Plan (Error Analysis)

> **v0.6.0:** Analyse verify result JSON and generate a classified repair plan. Read-only — never fixes errors, never installs dependencies, never modifies files.

```bash
# Generate repair plan from verify result
python -m aetherfusion repair-plan \
  --verify ./reports/verify-result.json \
  --json ./reports/repair-plan.json \
  --out ./reports/repair-plan.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--verify` | yes | — | Path to the v0.5 verify result JSON |
| `--out` | no* | none | Output path for the Markdown repair plan |
| `--json` | no* | none | Output path for the repair plan JSON |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to the audit log JSONL file |

*\* At least one of `--out` or `--json` must be provided.*

**Error classification (9 types):**
`missing_import` / `missing_dependency` / `type_error` / `syntax_error` / `test_failure` / `config_error` / `command_not_found` / `timeout` / `unknown_error`

**Each repair item includes:** `error_type`, `command`, `severity` (low/medium/high), `confidence` (0-100), `suspected_files`, `evidence`, `recommended_action`, `automation_eligibility`, `risk_level`, `reason`

**Blocked actions:** No source/target modification, no auto-fix imports, no dependency install, no config changes, no build/test/lint/typecheck, no network calls.

### CLI — Import Fix Plan

> **v0.7.0:** Analyse missing_import errors from a repair-plan JSON and generate a targeted import/path fix plan. Read-only — never fixes imports, never modifies files, never installs dependencies.

```bash
# Basic usage (required inputs only)
python -m aetherfusion import-fix-plan \
  --repair ./reports/repair-plan.json \
  --target ./project-a \
  --json ./reports/import-fix-plan.json \
  --out ./reports/import-fix-plan.md

# With optional source context (--patch and --apply)
python -m aetherfusion import-fix-plan \
  --repair ./reports/repair-plan.json \
  --target ./project-a \
  --patch ./reports/fusion-patch-components.json \
  --apply ./reports/apply-result-components.json \
  --json ./reports/import-fix-plan.json \
  --out ./reports/import-fix-plan.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--repair` | yes | — | Path to the v0.6 repair plan JSON |
| `--target` | yes | — | Path to the target project root |
| `--out` | no* | none | Output path for the Markdown import fix plan |
| `--json` | no* | none | Output path for the JSON import fix plan |
| `--patch` | no | none | Optional v0.3 patch manifest (for source_only_dependency detection) |
| `--apply` | no | none | Optional v0.4 apply result (for source_only_dependency detection) |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to the audit log JSONL file |

*\* At least one of `--out` or `--json` must be provided.*

**Import error extraction** — parses these patterns from `repair_items` with `error_type=missing_import`:
- `TS2307: Cannot find module 'x'`
- `Module not found: Can't resolve 'x'`
- `Cannot find module 'x'`
- `ImportError: No module named x`
- `ModuleNotFoundError: No module named 'x'`

**Import classification (7 types):**

| Kind | Trigger |
|------|---------|
| `missing_local_file` | `./` or `../` path — local relative import |
| `wrong_relative_path` | A file with the same stem exists in target but at a different path |
| `missing_alias_config` | `@/` or `~` prefixed — likely path alias (tsconfig paths / vite resolve.alias) |
| `missing_index_export` | Directory exists in target but has no `index` file |
| `source_only_dependency` | The source file was seen in `--patch` or `--apply` — likely not yet copied |
| `package_missing` | No local file match and no relative/alias prefix — likely a package |
| `unresolved_unknown` | Fallback when no pattern matches |

**Each fix candidate includes:** `missing_module`, `originating_command`, `suspected_import_kind`, `likely_cause`, `confidence` (0-100), `suggested_action`, `automation_eligibility` (manual_only/plan_only/safe_auto_candidate), `risk_level` (low/medium/high), `evidence`, `related_files`

**Import fix plan JSON** contains: `import_fix_plan_version`, `source_repair_file`, `target_path`, `summary`, `extracted_import_errors`, `fix_candidates`, `blocked_actions`, `next_recommended_command`

**Markdown import fix plan** (7 sections): Summary / Extracted Import Errors / Fix Candidates (with classification table) / Automation Eligibility / Related Files / Blocked Actions / Next Recommended Command

**Blocked actions:** No source/target modification, no auto-fix imports, no file creation, no tsconfig/vite config/package.json modification, no dependency installation, no verification commands, no network calls.

**Error handling:**
- Repair file not found / invalid JSON → exit 1
- Target not found / not a directory → exit 1
- No `missing_import` errors → empty plan, exit 0 (success)
- Unresolvable import → classified as `unresolved_unknown`, no crash

### CLI — Dependency Plan

> **v0.8.0:** Analyse missing_dependency errors from a repair-plan or import-fix-plan JSON and generate a dependency update plan. Read-only — never installs packages, never modifies dependency files.

```bash
# Basic usage (required inputs)
python -m aetherfusion dependency-plan \
  --repair ./reports/repair-plan.json \
  --target ./project-a \
  --source ./project-b \
  --json ./reports/dependency-plan.json \
  --out ./reports/dependency-plan.md

# With optional --import-fix
python -m aetherfusion dependency-plan \
  --repair ./reports/repair-plan.json \
  --import-fix ./reports/import-fix-plan.json \
  --target ./project-a \
  --source ./project-b \
  --json ./reports/dependency-plan.json \
  --out ./reports/dependency-plan.md
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--repair` | yes | — | Path to the v0.6 repair plan JSON |
| `--target` | yes | — | Path to the target project root |
| `--source` | yes | — | Path to the source project root |
| `--out` | no* | none | Output path for the Markdown dependency plan |
| `--json` | no* | none | Output path for the JSON dependency plan |
| `--import-fix` | no | none | Optional v0.7 import-fix-plan JSON (extracts package_missing) |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to the audit log JSONL file |

*\* At least one of `--out` or `--json` must be provided.*

**Dependency error extraction** — from `repair_items` with `error_type=missing_dependency` and `fix_candidates` with `package_missing`:
- Node: `Cannot find module 'x'` / `Module not found: Can't resolve 'x'` / `Could not resolve dependency: x`
- Python: `ModuleNotFoundError: No module named 'x'` / `ImportError: No module named x`
- Generic: `Package not found: x` / `Missing package: x`

**Dependency file parsing** (read-only):
- `package.json` — dependencies, devDependencies, optionalDependencies, peerDependencies
- `requirements.txt` — Python package list with version extraction
- `pyproject.toml` — project.dependencies and poetry dependencies
- `setup.py` — presence detection only (not parsed)
- Lock files — `package-lock.json`, `poetry.lock`, `pnpm-lock.yaml`, `yarn.lock` — presence only

**Dependency classification (6 rules):**

| Rule | Trigger | Action |
|------|---------|--------|
| `add_to_target` | Source has the package, target does not | Add to target dependency plan |
| `review_version_conflict` | Both projects have it, versions differ | Human review required |
| `likely_not_dependency_issue` | Target already has the package | Check import paths or config |
| `manual_research` | Neither project has it in dependencies | Research transitive/vendored dependency |
| `builtin_or_stdlib_skipped` | Node.js builtin or Python stdlib | Skip — import error is config issue |
| `redirect_to_import_fix` | `./` `../` `@/` `~` prefix | Redirect to import-fix-plan |

**Each dependency candidate includes:** `package_name`, `ecosystem` (node/python/unknown), `found_in_source`, `found_in_target`, `source_version`, `target_version`, `version_conflict`, `likely_cause`, `recommended_action`, `automation_eligibility` (manual_only/plan_only), `risk_level` (low/medium/high), `evidence`

**Dependency plan JSON** contains: `dependency_plan_version`, `source_repair_file`, `source_import_fix_file`, `target_path`, `source_path`, `summary`, `extracted_dependency_errors`, `dependency_candidates`, `dependency_files_detected`, `blocked_actions`, `next_recommended_command`

**Markdown dependency plan** (8 sections): Summary / Extracted Dependency Errors / Dependency Files Detected / Dependency Candidates / Version Conflicts / Builtin / Stdlib Skipped / Automation Eligibility / Blocked Actions / Next Recommended Command

**Blocked actions:** No source/target modification, no auto-modification of package.json / requirements.txt / pyproject.toml / lock files, no npm install / pip install / poetry install, no build/test/lint/typecheck, no network calls, no installer execution.

**Error handling:**
- Repair file not found / invalid JSON → exit 1
- Import-fix file invalid JSON → exit 1
- Target / source not found / not a directory → exit 1
- No `missing_dependency` or `package_missing` errors → empty plan, exit 0 (success)
- Unresolvable package → classified as `manual_research`, no crash

### CLI — Fusion Session (Orchestration)

> **v1.0:** End-to-end session orchestration. Chains scan → plan → patch → optional apply → optional verify → optional diagnostic plans. Default safe mode: no apply, no verify.

```bash
# Safe mode: scan + plan + dry-run patch only (no apply, no verify)
python -m aetherfusion fusion-session \
  --source ./project-b \
  --target ./project-a \
  --modules utils,lib \
  --reports ./aether-fusion-reports \
  --mode safe

# With apply and verify
python -m aetherfusion fusion-session \
  --source ./project-b \
  --target ./project-a \
  --modules utils,lib \
  --reports ./aether-fusion-reports \
  --mode safe \
  --apply-confirm \
  --verify \
  --audit ./logs/audit.jsonl

# Windows PowerShell
python -m aetherfusion fusion-session `
  --source .\examples\demo-source `
  --target .\examples\demo-target `
  --modules utils `
  --reports .\reports\session-demo `
  --mode safe
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--source` | yes | — | Path to the source project |
| `--target` | yes | — | Path to the target project |
| `--modules` | yes | — | Comma-separated list of module names (e.g. utils,lib) |
| `--reports` | yes | — | Directory for all generated session reports and artifacts |
| `--mode` | no | `safe` | Session mode |
| `--apply-confirm` | no | `False` | Apply patches after dry-run (default: skipped) |
| `--verify` | no | `False` | Run verification after apply (default: skipped) |
| `--audit` | no | `reports/aetherfusion-audit.jsonl` | Path to audit log JSONL file |

**Session flow:**
1. **Scan**: generate `fusion-report.md` + `fusion-map.json`
2. **Per-module**: plan → patch (dry-run) → optional apply
3. **Verify** (if `--verify`): run verification; on failure, auto-generate repair-plan / import-fix-plan / dependency-plan / config-plan
4. **Final artifacts**: `fusion-session.json` + `fusion-session.md` + `artifact-index.json` + audit event

**Session report (`fusion-session.md`)** includes 13 sections:
Session Summary / Source Target / Modules Processed / Scan Result / Per-Module Plan Patch Apply Summary / Verify Result / Diagnostic Plans Generated / Blocked Operations / Rollback Information / Artifact Index / Next Recommended Action

**`artifact-index.json`**: `session_id`, `created_at`, `source`, `target`, `modules`, `artifacts` (scan_report, scan_map, plan_reports, patch_reports, apply_results, rollback_manifests, verify_result, repair_plan, import_fix_plan, dependency_plan, config_plan, audit_log)

**`fusion-session.json`**: `session_version`, `session_id`, `source_path`, `target_path`, `modules`, `mode`, `options`, `steps`, `module_results`, `verify_summary`, `diagnostic_plans`, `blocked_operations`, `rollback_manifests`, `artifacts`, `next_recommended_action`

**Safety boundaries:**
- Default safe mode: no apply without `--apply-confirm`
- No verify without `--verify`
- No automatic dependency installation
- No automatic config modification
- No automatic import fixes
- No target file overwrites
- Apply only allows `add_file` operations

**Error handling:**
- Source / target not found → exit 1
- Modules empty → exit 1
- Reports directory → auto-created if missing
- Single module plan/patch failure → recorded as failed, other modules continue (scan failure exits immediately)
- Verify failure → generates diagnostic plans, session report still produced
- Artifact write failure → recorded in errors array, session report still produced
- Audit write failure → warning logged, main workflow continues

### CLI — Scan (Report Generation)

```bash
python -m aetherfusion scan \
  --source ./project-b \
  --target ./project-a \
  --out ./reports/aetherfusion-report.md
```

Windows PowerShell:

```powershell
python -m aetherfusion scan `
  --source .\project-b `
  --target .\project-a `
  --out .\reports\aetherfusion-report.md
```

### CLI — JSON Map Only

```bash
python -m aetherfusion scan \
  --source ./project-b \
  --target ./project-a \
  --json ./reports/aetherfusion-map.json
```

### CLI — Both Outputs

```bash
python -m aetherfusion scan \
  --source ./project-b \
  --target ./project-a \
  --out ./reports/aetherfusion-report.md \
  --json ./reports/aetherfusion-map.json
```

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--source` | yes | — | Path to source project (project-b), the one being merged **from** |
| `--target` | yes | — | Path to target project (project-a), the one being merged **into** |
| `--out` | no* | none | Output path for the Markdown report |
| `--json` | no* | none | Output path for the JSON map |

*\* At least one of `--out` or `--json` must be provided.*

### Programmatic API

```python
from aetherfusion.scanner.project_analyzer import ProjectAnalyzer
from aetherfusion.reporter.markdown_reporter import generate_report
from aetherfusion.reporter.json_reporter import generate_json_map

source = ProjectAnalyzer("./project-b").analyze()
target = ProjectAnalyzer("./project-a").analyze()

# Markdown
report = generate_report(source, target)

# JSON (dict, ready for json.dumps)
data = generate_json_map(source, target)
```

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
aetherfusion/
├── __init__.py              # Package init, version
├── __main__.py              # python -m entry point
├── cli.py                   # Argument parsing & CLI logic
├── utils.py                 # Constants, safe I/O helpers
├── git_checker.py           # Read-only Git status inspection
├── scanner/
│   ├── __init__.py
│   ├── config_parser.py     # Parse package.json, requirements.txt, pyproject.toml, tsconfig.json
│   ├── tree_builder.py      # Build directory tree with exclusions
│   └── project_analyzer.py  # Orchestrate full project scan
├── comparer/
│   ├── __init__.py
│   ├── tech_stack.py        # Compare inferred tech stacks
│   ├── dependencies.py      # Compare dependencies & version conflicts
│   ├── structure.py         # Compare directory structures
│   └── fusion.py            # Identify fusible modules, conflicts & plan candidates
├── planner/
│   ├── __init__.py
│   └── fusion_planner.py    # Generate module-level fusion plans from JSON maps
├── patcher/
│   ├── __init__.py
│   └── dry_run_patch_generator.py # Classify source files for fusion (add/conflict/skip)
├── applier/
│   ├── __init__.py
│   └── safe_apply.py             # Apply add_file operations safely with rollback
├── rollback/
│   ├── __init__.py
│   └── safe_rollback.py          # Undo apply by deleting created_files from manifest
├── session/
│   ├── __init__.py               # Session module init
│   ├── session_state.py          # Session state tracking (session_id, modules, mode)
│   ├── session_runner.py         # End-to-end session orchestration (scan→plan→patch→apply→verify→diagnostics)
│   └── artifact_index.py         # Artifact inventory tracking
├── audit/
│   ├── __init__.py
│   └── audit_logger.py           # JSONL audit logging for apply/rollback/verify events
├── verifier/
│   ├── __init__.py
│   ├── command_detector.py       # Auto-detect verification commands from project config
│   ├── safe_runner.py            # Whitelist-enforcing command runner with timeout
│   └── verify_runner.py          # Orchestrate full verify flow
├── repair/
│   ├── __init__.py
│   ├── error_classifier.py       # Classify verify failures into 9 error types
│   └── repair_planner.py         # Generate structured repair items with severity/confidence
├── importfix/
│   ├── __init__.py
│   ├── import_error_extractor.py  # Extract missing_import errors from repair plan JSON
│   ├── target_indexer.py          # Build read-only file index of target project
│   └── import_fix_planner.py      # Classify and plan import/path fix candidates
├── dependency/
│   ├── __init__.py
│   ├── dependency_error_extractor.py  # Extract missing_dependency errors from plans
│   ├── dependency_file_parser.py      # Parse dependency manifest files
│   └── dependency_planner.py          # Generate dependency update candidates
└── reporter/
    ├── __init__.py
    ├── markdown_reporter.py         # Generate the Markdown scan report
    ├── json_reporter.py             # Generate the JSON project map
    ├── plan_markdown_reporter.py    # Generate the Markdown fusion plan
    ├── plan_json_reporter.py        # Generate the JSON fusion plan
    ├── patch_markdown_reporter.py   # Generate the Markdown patch preview
    ├── patch_json_reporter.py       # Generate the JSON patch manifest
    ├── diff_reporter.py             # Generate unified diff for add_file operations
    ├── apply_markdown_reporter.py   # Generate the Markdown apply report
    ├── apply_json_reporter.py       # Generate the JSON apply result
    ├── rollback_markdown_reporter.py # Generate the Markdown rollback report
    ├── rollback_json_reporter.py    # Generate the JSON rollback result
    ├── verify_markdown_reporter.py  # Generate the Markdown verify report
    ├── verify_json_reporter.py      # Generate the JSON verify result
    ├── repair_markdown_reporter.py  # Generate the Markdown repair plan
    ├── repair_json_reporter.py      # Generate the JSON repair plan
    ├── import_fix_markdown_reporter.py  # Generate the Markdown import fix plan
    ├── import_fix_json_reporter.py      # Generate the JSON import fix plan
    ├── dependency_markdown_reporter.py  # Generate the Markdown dependency plan
    └── dependency_json_reporter.py      # Generate the JSON dependency plan
    ├── session_markdown_reporter.py     # Generate the Markdown session report
    └── session_json_reporter.py         # Generate the JSON session report
tests/
├── __init__.py
├── test_scanner.py          # Tests for scanner module
├── test_comparer.py         # Tests for comparer + fusion plan candidates
├── test_reporter.py         # Tests for Markdown reporter
├── test_json_reporter.py    # Tests for JSON reporter
├── test_planner.py          # Tests for planner + plan reporters
├── test_patcher.py          # Tests for patcher + patch reporters + CLI
├── test_apply.py            # Tests for apply + apply reporters + CLI
├── test_rollback_audit.py   # Tests for rollback + audit + CLI
├── test_verify.py           # Tests for verify + verify reporters + CLI
├── test_repair.py           # Tests for repair-plan + repair reporters + CLI
├── test_import_fix.py        # Tests for import-fix-plan + import fix reporters + CLI
├── test_dependency.py       # Tests for dependency-plan + dependency reporters + CLI
└── test_fusion_session.py   # Tests for fusion-session + session reporters + CLI
└── test_git_checker.py      # Tests for git status checker
scripts/
└── smoke_test.py            # Automated scan → plan → patch → fusion-session smoke test
examples/
├── demo-source/             # TypeScript project with src/utils/ module
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts
│       └── utils/
│           ├── index.ts
│           ├── math.ts
│           └── strings.ts
└── demo-target/             # TypeScript project without utils module
    ├── package.json
    ├── tsconfig.json
    └── src/
        └── index.ts
RELEASE_NOTES.md             # v0.1 → v1.0 capability evolution
QUICKSTART.md                # Step-by-step usage guide
```

## Safety

- **No network requests** — all scanning is local
- **No file modifications** — read-only analysis
- **Git read-only** — only inspects `.git` directory, never runs `git commit`, `git push`, or any modifying command
- **Apply is safe** — only copies non-conflicting `add_file` operations, never overwrites
- **Rollback is safe** — only deletes files recorded in the rollback manifest's `created_files`; path traversal blocked; config files protected
- **Verify is safe** — only runs whitelisted commands; blocks rm/del/curl/wget/install; never installs dependencies, never modifies files
- **Repair-plan is safe** — only analyses verify result errors, never fixes code, never installs, never modifies
- **Import-fix-plan is safe** — only analyses missing_import errors, never fixes imports, never modifies files, never installs dependencies
- **Dependency-plan is safe** — only analyses missing_dependency errors, never modifies package.json/requirements.txt/pyproject.toml, never installs packages
- **Config-plan is safe** — only analyses config errors, never modifies tsconfig.json/vite.config.*/package.json, never creates config files
- **Fusion-session is safe** — orchestration only; default safe mode (no apply, no verify); no automatic dependency/import/config changes; apply only allows add_file; all operations use existing safe subcommands
- **Audit trail** — every `apply`, `rollback`, `verify`, `repair-plan`, `import-fix-plan`, `dependency-plan`, `config-plan`, and `fusion-session` appends a JSONL event; audit write failures never break the main workflow
- **Path safety** — all paths are resolved and validated before access
- **Graceful error handling** — unreadable files are skipped, not crashed on
- **Ignores** — `node_modules`, `.git`, `dist`, `build`, `__pycache__`, `venv`, `.venv`, `.next`, `.nuxt`, `target`, `.idea`, `.vscode`, `coverage`, and various cache directories are excluded from scanning

## License

MIT
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
