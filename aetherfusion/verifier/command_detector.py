"""Command detector — inspects a target project and suggests whitelist-safe
verify commands based on detected configuration files.

Returns a list of command strings that are safe to run via
the safe_runner.

Detection logic:
- package.json -> scripts: build / test / lint / typecheck
- tsconfig.json -> npx tsc --noEmit
- pytest.ini / pyproject.toml (with [tool.pytest]) / tests/ -> pytest

If no commands are detected, returns an empty list and sets
no_commands_detected = True.
"""

from pathlib import Path
from typing import Any

# Config file paths that signal a Python test project
PYTHON_TEST_SIGNALS: list[str] = [
    "pytest.ini",
    "pyproject.toml",          # checked for [tool.pytest] inside
    "tox.ini",
    "setup.cfg",               # checked for [tool:pytest] inside
]

# Script keys we look for inside package.json scripts block
NPM_SCRIPT_KEYS: list[str] = ["build", "test", "lint", "typecheck"]


def detect_commands(target_path: Path) -> tuple[list[str], list[str], bool]:
    """Detect safe verification commands for a project.

    Args:
        target_path: Root directory of the target project.

    Returns:
        Tuple of (commands, detected_stack, no_commands_detected).
        - commands: list of shell command strings to run
        - detected_stack: list of technology tags (e.g. ["node", "typescript", "python"])
        - no_commands_detected: True when zero commands were found
    """
    commands: list[str] = []
    detected: list[str] = []

    # -- package.json / Node -------------------------------------------------
    pkg_json = target_path / "package.json"
    if pkg_json.is_file():
        try:
            import json
            with open(pkg_json, "r", encoding="utf-8-sig") as fh:
                pkg: dict[str, Any] = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pkg = {}
        scripts: dict[str, Any] = pkg.get("scripts", {})
        if isinstance(scripts, dict):
            for key in NPM_SCRIPT_KEYS:
                if key in scripts:
                    cmd = f"npm run {key}"
                    if cmd not in commands:
                        commands.append(cmd)
                    if key == "build" or key == "test":
                        if "node" not in detected:
                            detected.append("node")
                        if key == "test":
                            if "npm-test" not in detected:
                                detected.append("npm-test")

    # -- tsconfig.json -> TypeScript -----------------------------------------
    ts_config = target_path / "tsconfig.json"
    if ts_config.is_file():
        detected.append("typescript")
        cmd = "npx tsc --noEmit"
        if cmd not in commands:
            commands.append(cmd)

    # -- Python test signals -------------------------------------------------
    test_dir = target_path / "tests"
    has_python_tests = False

    for signal_file in PYTHON_TEST_SIGNALS:
        sp = target_path / signal_file
        if not sp.is_file():
            continue

        # For pyproject.toml, check for [tool.pytest] section
        if signal_file == "pyproject.toml":
            try:
                content = sp.read_text(encoding="utf-8-sig")
            except OSError:
                continue
            if "[tool.pytest]" not in content and "[tool.pytest.ini_options]" not in content:
                continue

        # For setup.cfg, check for [tool:pytest]
        if signal_file == "setup.cfg":
            try:
                content = sp.read_text(encoding="utf-8-sig")
            except OSError:
                continue
            if "[tool:pytest]" not in content:
                continue

        has_python_tests = True
        break

    # Also check if tests/ directory exists with test files
    if not has_python_tests and test_dir.is_dir():
        try:
            for item in test_dir.rglob("test_*.py"):
                has_python_tests = True
                break
            if not has_python_tests:
                for item in test_dir.rglob("*_test.py"):
                    has_python_tests = True
                    break
        except OSError:
            pass

    if has_python_tests:
        if "python" not in detected:
            detected.append("python")
        cmd = "pytest"
        if cmd not in commands:
            commands.append(cmd)

    no_commands = (len(commands) == 0)
    return commands, detected, no_commands