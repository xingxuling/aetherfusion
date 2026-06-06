"""Error classifier for verify results.

Classifies each failed/skipped/timeout/blocked verification result into
a well-known error type for repair plan generation.
"""

from typing import Any

# Error type constants
ERROR_TYPE_MISSING_IMPORT = "missing_import"
ERROR_TYPE_MISSING_DEPENDENCY = "missing_dependency"
ERROR_TYPE_TYPE_ERROR = "type_error"
ERROR_TYPE_SYNTAX_ERROR = "syntax_error"
ERROR_TYPE_TEST_FAILURE = "test_failure"
ERROR_TYPE_CONFIG_ERROR = "config_error"
ERROR_TYPE_COMMAND_NOT_FOUND = "command_not_found"
ERROR_TYPE_TIMEOUT = "timeout"
ERROR_TYPE_UNKNOWN_ERROR = "unknown_error"


def classify_error(result: dict[str, Any]) -> str:
    """Classify a single verify command result into an error type.

    Args:
        result: A single command result dict from safe_runner,
            containing command, status, exit_code, stdout_tail,
            stderr_tail, reason.

    Returns:
        One of the ERROR_TYPE_* constants.
    """
    status = result.get("status", "")
    command = result.get("command", "")
    stderr = result.get("stderr_tail", "").lower()
    stdout = result.get("stdout_tail", "").lower()
    reason = result.get("reason", "").lower()
    combined = f"{stderr} {stdout} {reason}"

    # Timeout
    if status == "timeout":
        return ERROR_TYPE_TIMEOUT

    # Command not found
    if "not recognized" in combined or "command not found" in combined or \
       "is not recognized as" in combined:
        return ERROR_TYPE_COMMAND_NOT_FOUND

    # Missing import / module
    if "modulenotfounderror" in combined or "cannot find module" in combined or \
       "import error" in combined or "importerror" in combined:
        return ERROR_TYPE_MISSING_IMPORT

    # Missing dependency (package)
    if "no module named" in combined or "package not found" in combined or \
       "could not find package" in combined or "could not resolve" in combined:
        return ERROR_TYPE_MISSING_DEPENDENCY

    # Type errors
    if "typeerror" in combined or "type '" in combined or \
       "is not assignable" in combined or "has no attribute" in combined:
        return ERROR_TYPE_TYPE_ERROR

    # Syntax errors
    if "syntaxerror" in combined or any(
        kw in combined for kw in ["unexpected token", "unexpected string",
                                   "unterminated string", "invalid syntax"]
    ):
        return ERROR_TYPE_SYNTAX_ERROR

    # Config errors
    if "enoent" in combined or "config" in combined or "configuration" in combined or \
       "tsconfig" in combined or "package.json" in combined or \
       "cannot find module" in combined:
        # Re-check: if it's definitely config-related
        if "enoent" in combined or "config" in combined or "tsconfig" in combined:
            return ERROR_TYPE_CONFIG_ERROR

    # Test failures
    if "assertionerror" in combined or "assert" in combined or \
       ("test" in command.lower() and ("failed" in combined or "error" in combined)):
        return ERROR_TYPE_TEST_FAILURE

    # Test failures (pytest-style output)
    if "failed" in combined and command.lower() in ("pytest", "python -m pytest"):
        return ERROR_TYPE_TEST_FAILURE

    # If status is failed/blocked but no specific pattern matched
    if status in ("failed", "blocked"):
        return ERROR_TYPE_UNKNOWN_ERROR

    return ERROR_TYPE_UNKNOWN_ERROR


def classify_all(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Classify all non-passed results into buckets by error type.

    Args:
        results: List of command result dicts.

    Returns:
        Dict mapping error_type -> list of result dicts.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        if r.get("status") == "passed":
            continue
        et = classify_error(r)
        buckets.setdefault(et, []).append(r)
    return buckets