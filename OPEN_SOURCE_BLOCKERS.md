# Open Source Blockers Report

Generated: 2026-06-07

## Summary

| Risk | File | Status |
|------|------|--------|
| MEDIUM | MIGRATION_REPORT.md | RESOLVED — path redacted |
| LOW | audit.log | RESOLVED — removed, added to .gitignore |

## Findings

### 1. MIGRATION_REPORT.md — User-specific absolute path

- **File**: `MIGRATION_REPORT.md`
- **Lines**: 11, 13
- **Risk Type**: Internal directory structure disclosure
- **Content**: Contains `C:\Users\User\AppData\Roaming\Tencent\Marvis\User\...` — reveals internal Marvis agent workspace path
- **Resolution**: Redacted internal paths to `<internal-source-path>`. File retained as it documents the migration provenance.

### 2. audit.log — Test artifact with temp paths

- **File**: `audit.log`
- **Lines**: 1-3
- **Risk Type**: Test environment path leakage
- **Content**: Contains pytest temporary directory paths (`C:\Users\User\AppData\Local\Temp\pytest-of-User\...`)
- **Resolution**: File deleted and `audit.log` added to `.gitignore`.

## False Positives (Not Sensitive)

The following terms appeared in source code matches but are **AetherFusion feature/subcommand names** or **output artifact template names**, not actual file paths to real fusion reports:

- `repair-plan` — CLI subcommand name
- `import-fix-plan` — CLI subcommand name
- `dependency-plan` — CLI subcommand name
- `config-plan` — feature reference
- `fusion-report.md` — documentation reference to tool output format
- `fusion-map.json` — documentation reference to tool output format
- `apply-result` / `apply-backup` / `verify-result` — documentation references to tool artifacts

These are integral to the tool's API and documentation. No action needed.
