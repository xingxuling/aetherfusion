# Changelog

All notable changes to AetherFusion.

## [1.0.1] — 2026-06-07

### Added
- QUICKSTART.md with step-by-step tutorial
- `examples/demo-source/` and `examples/demo-target/` demo projects
- `scripts/smoke_test.py` end-to-end pipeline test
- RELEASE_NOTES.md for all versions

### Fixed
- `test_empty_string_path_does_not_crash` now resilient to git-initialized working directories

## [1.0.0] — 2026-06-07

### Added
- `fusion-session` subcommand: end-to-end orchestration (scan → plan → patch → optional apply → optional verify → optional diagnostic plans)
- Session state tracking (`fusion-session.json`)
- Markdown session report (`fusion-session.md`, 13 sections)
- Artifact inventory (`artifact-index.json`)
- Audit log integration for session events
- Safe mode by default (no apply without `--apply-confirm`)

## [0.9.0] — 2026-06-06

### Added
- `config-plan` subcommand: configuration error diagnosis and remediation planning

## [0.8.0] — 2026-06-05

### Added
- `dependency-plan` subcommand: dependency update planning from repair/import-fix plans

## [0.7.0] — 2026-06-04

### Added
- `import-fix-plan` subcommand: import/path fix planning from repair plans

## [0.6.0] — 2026-06-03

### Added
- `repair-plan` subcommand: repair plan generation from verify results
- Error classification into 9 types with severity and confidence scoring

## [0.5.0] — 2026-06-02

### Added
- `verify` subcommand: whitelisted command verification for target projects

## [0.4.5] — 2026-06-01

### Added
- `rollback` subcommand: roll back files created by apply using rollback manifests
- Audit logging for rollback operations

## [0.4.0] — 2026-05-31

### Added
- `apply` subcommand: confirmed `add_file` application from patch manifests
- No modify/delete — apply only creates new files

## [0.3.0] — 2026-05-30

### Added
- `patch` subcommand: dry-run patch preview generation (no files modified)

## [0.2.0] — 2026-05-29

### Added
- `plan` subcommand: module-level fusion plan from JSON project maps

## [0.1.0] — 2026-05-28

### Added
- `scan` subcommand: two-project comparison and fusion report generation
- Fusion report in Markdown format
- Initial project structure
