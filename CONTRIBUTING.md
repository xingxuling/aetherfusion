# Contributing to AetherFusion

Thank you for considering contributing to AetherFusion.

## Development Setup

```bash
# Clone and install in editable mode
git clone https://github.com/taowind/aetherfusion.git
cd aetherfusion
pip install -e .
```

## Running Tests

```bash
# Full test suite
python -m pytest

# Smoke test (end-to-end pipeline)
python scripts/smoke_test.py
```

Target: 344 tests, 0 failures.

## Safety Boundaries

AetherFusion is designed for **safe, inspectable, reversible** codebase fusion. Contributions must respect these boundaries:

- **No network calls** — AetherFusion operates entirely on local filesystems
- **No automatic installation** — Never auto-install packages, dependencies, or tools
- **No automatic overwrites** — Apply mode only supports `add_file`; never modify or delete target files
- **No automatic fixes** — Diagnostic plans (repair-plan, import-fix-plan, dependency-plan, config-plan) are read-only reports; they must not execute changes
- **Dry-run by default** — All mutating operations require explicit user confirmation

## Pull Request Requirements

- New features must include corresponding tests in `tests/`
- All existing tests must pass (`python -m pytest`)
- Smoke test must pass (`python scripts/smoke_test.py`)
- Follow existing code style and structure conventions
- Update relevant documentation (README, QUICKSTART, RELEASE_NOTES) if applicable

## Code Style

- Pure Python standard library only — no external dependencies
- Type hints encouraged but not mandatory
- Follow existing module organization patterns

## Reporting Issues

- Bug reports: Open a GitHub Issue with clear reproduction steps
- Security issues: See [SECURITY.md](SECURITY.md) — do not post sensitive details publicly
