# AetherFusion Quickstart (v1.0.1)

## Installation

```powershell
# Windows PowerShell — install in editable mode
cd C:\path\to\aetherfusion
pip install -e .
```

No external dependencies required (stdlib only). Works with Python 3.9+ (3.11+ recommended).

## Verify Installation

```powershell
python -m aetherfusion --help
python -m aetherfusion --version
# Output: aetherfusion 1.0.1
```

## Quick Smoke Test

```powershell
python scripts/smoke_test.py
```

Uses the demo projects in `examples/` to run a full scan → plan → dry-run patch → fusion-session pipeline. Outputs `smoke test passed` or `smoke test failed` with non-zero exit on failure.

## Basic Usage — Scan Two Projects

```powershell
python -m aetherfusion scan `
  --source .\examples\demo-source `
  --target .\examples\demo-target `
  --out .\reports\scan-report.md `
  --json .\reports\scan-map.json
```

Generates:
- `reports/scan-report.md` — 9-section Markdown comparison
- `reports/scan-map.json` — machine-readable JSON with fusion plan candidates

## Dry-Run Patch Preview

```powershell
# Step 1: Plan a specific module
python -m aetherfusion plan `
  --map .\reports\scan-map.json `
  --module utils `
  --out .\reports\plan-utils.md `
  --json .\reports\plan-utils.json

# Step 2: Generate dry-run patch (no files modified)
python -m aetherfusion patch `
  --plan .\reports\plan-utils.json `
  --out .\reports\patch-utils.md `
  --json .\reports\patch-utils.json `
  --diff .\reports\patch-utils.diff `
  --dry-run
```

## Apply with Confirmation

```powershell
# Apply only add_file operations (never overwrites)
python -m aetherfusion apply `
  --patch .\reports\patch-utils.json `
  --confirm `
  --out .\reports\apply-utils.md `
  --json .\reports\apply-utils.json `
  --backup .\reports\apply-backup-utils.json
```

Rollback if needed:

```powershell
python -m aetherfusion rollback `
  --manifest .\reports\apply-backup-utils.json `
  --confirm `
  --out .\reports\rollback-utils.md
```

## Verify Target Project

```powershell
# Auto-detect commands (npm build, tsc, pytest, etc.)
python -m aetherfusion verify `
  --target .\examples\demo-target `
  --out .\reports\verify-report.md `
  --json .\reports\verify-result.json
```

## Fusion Session — End-to-End Pipeline

```powershell
# Safe mode: scan + plan + dry-run patch only (no apply, no verify)
python -m aetherfusion fusion-session `
  --source .\examples\demo-source `
  --target .\examples\demo-target `
  --modules utils `
  --reports .\reports\session-safe

# With apply and verify
python -m aetherfusion fusion-session `
  --source .\examples\demo-source `
  --target .\examples\demo-target `
  --modules utils `
  --reports .\reports\session-full `
  --apply-confirm `
  --verify
```

## Reading Report Files

### Scan Report (`scan-report.md`)
Nine sections covering project overview, tech stack, dependencies, directory trees, structure comparison, fusible modules, conflict risks, and recommendations.

### Fusion Map (`scan-map.json`)
Machine-readable JSON with `fusion_plan_candidates` — each candidate has value_score, portability_score, conflict_score, priority_score, risk_level, and recommended_action.

### Fusion Plan (`plan-*.json`)
Five-stage step-by-step plan with score summary, ordered steps, human decision categories, and blocked action list.

### Patch Preview (`patch-*.json`)
Dry-run manifest with per-file operations: `add_file`, `conflict_same_name`, `skip_unsafe`, `review_import_dependency`. Includes summary counts and safety classifications.

### Apply Result (`apply-*.json`)
Confirmed apply result: files_applied, files_skipped, files_blocked, files_failed, directories_created. Includes rollback_manifest_path for safe rollback.

### Verify Result (`verify-result.json`)
Per-command results: command, status (passed/failed/skipped/timeout/blocked), exit code, duration, stdout and stderr tails.

### Fusion Session Report (`fusion-session.md`)
Thirteen-section session summary: Session Summary, Source/Target, Modules Processed, Scan Result, Per-Module Plan/Patch/Apply Summary, Verify Result, Diagnostic Plans Generated, Blocked Operations, Rollback Information, Artifact Index, Next Recommended Action.

### Fusion Session JSON (`fusion-session.json`)
Full session state serialization including session_id, module_results, verify_summary, diagnostic_plans, blocked_operations, rollback_manifests, artifacts, and next_recommended_action.

### Artifact Index (`artifact-index.json`)
Inventory of all generated artifacts: session_id, created_at, source, target, modules, and paths to scan_reports, plan_reports, patch_reports, apply_results, verify_result, diagnostic plans, and audit_log.

## Diagnostic Plans

When verify finds failures, the session auto-generates:

| Plan | File | Purpose |
|------|------|---------|
| Repair Plan | `repair-plan.json` | Classifies errors into 9 types with severity/confidence |
| Import Fix Plan | `import-fix-plan.json` | Analyses missing_import errors with 7 classifications |
| Dependency Plan | `dependency-plan.json` | Analyses missing_dependency errors with 6 rules |
| Config Plan | `config-plan.json` | Analyses config mismatch errors |

All plans are read-only — they never modify files, install dependencies, or make network calls.