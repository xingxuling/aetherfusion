"""Extract dependency-related errors from repair-plan and import-fix-plan JSONs."""

import re
from typing import Any

# Patterns for extracting package/module names from error messages.
# Ordered from most specific to most generic.
_PACKAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Cannot find module '([^']+)'"), "node"),
    (re.compile(r"Cannot find module \"([^\"]+)\""), "node"),
    (re.compile(r"Module not found: Can't resolve '([^']+)'"), "node"),
    (re.compile(r"Module not found: Can't resolve \"([^\"]+)\""), "node"),
    (re.compile(r"Could not resolve dependency:\s*(\S+)"), "node"),
    (re.compile(r"ModuleNotFoundError: No module named '([^']+)'"), "python"),
    (re.compile(r'ModuleNotFoundError: No module named "([^"]+)"'), "python"),
    (re.compile(r"ImportError: No module named ([^\s]+(?:\[[\w,\s]+\])?)"), "python"),
    (re.compile(r"Could not find a declaration file for module '([^']+)'"), "node"),
    (re.compile(r"Cannot resolve '([^']+)'"), "node"),
    (re.compile(r"Failed to resolve import \"([^\"]+)\""), "node"),
    (re.compile(r"Package not found:\s*(\S+)"), "generic"),
    (re.compile(r"Missing package:\s*(\S+)"), "generic"),
    (re.compile(r"Could not import (\S+)"), "generic"),
]

# Path-like prefixes that indicate local file imports, not packages.
_PATH_LIKE_PREFIXES = ("./", "../", "@/", "~")


def _is_path_like(name: str) -> bool:
    """Check if a module name looks like a relative/alias path."""
    return any(name.startswith(p) for p in _PATH_LIKE_PREFIXES)


def _extract_package_name(evidence: str) -> str:
    """Extract a package name from an error string.

    Returns the raw module name or an empty string if nothing matched.
    """
    for pattern, _eco in _PACKAGE_PATTERNS:
        m = pattern.search(evidence)
        if m:
            name = m.group(1).strip()
            if name and not _is_path_like(name):
                return name
    return ""


def _guess_ecosystem(package_name: str, evidence: str) -> str:
    """Guess the package ecosystem from the error text and package name."""
    # Check evidence for explicit ecosystem markers
    evidence_lower = evidence.lower()
    if "modulenotfounderror" in evidence_lower or "importerror" in evidence_lower:
        return "python"
    if "cannot find module" in evidence_lower or "can't resolve" in evidence_lower:
        return "node"
    if "ts2307" in evidence_lower:
        return "node"
    # Heuristic: scoped packages are npm
    if package_name.startswith("@"):
        return "node"
    # Heuristic: dot-separated like flask.ext are Python
    if "." in package_name and not package_name.startswith("@"):
        return "python"
    return "unknown"


def extract_dependency_errors(
    repair_plan: dict[str, Any],
    import_fix_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract dependency-related errors from a repair plan and optional import-fix plan.

    Scans:
    1. repair_items with error_type='missing_dependency'
    2. fix_candidates with suspected_import_kind='package_missing' (from import-fix-plan)

    Args:
        repair_plan: The v0.6 repair-plan JSON dict.
        import_fix_plan: Optional v0.7 import-fix-plan JSON dict.

    Returns:
        List of enriched dependency error dicts, each containing:
        - package_name: The extracted package/module name
        - ecosystem: 'node' / 'python' / 'unknown'
        - originating_command: The command that produced this error
        - severity: low / medium / high
        - evidence: The original error text
        - source: 'repair_plan' or 'import_fix_plan'
    """
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()  # Deduplicate by package_name

    # 1. Extract from repair plan: error_type=missing_dependency
    for item in repair_plan.get("repair_items", []):
        if not isinstance(item, dict):
            continue
        if item.get("error_type") != "missing_dependency":
            continue
        evidence = item.get("evidence", "")
        package_name = _extract_package_name(evidence)
        if not package_name:
            # Also try stderr_tail / stdout_tail
            for field in ("stderr_tail", "stdout_tail"):
                tail = item.get(field, "")
                if tail:
                    package_name = _extract_package_name(tail)
                    evidence = tail if package_name else evidence
                    break

        if package_name and package_name not in seen:
            seen.add(package_name)
            errors.append({
                "package_name": package_name,
                "ecosystem": _guess_ecosystem(package_name, evidence),
                "originating_command": item.get("command", ""),
                "severity": item.get("severity", "medium"),
                "evidence": evidence,
                "source": "repair_plan",
                "confidence": item.get("confidence", 70),
            })

    # 2. Extract from import-fix plan: fix_candidates with package_missing
    if import_fix_plan:
        for cand in import_fix_plan.get("fix_candidates", []):
            if not isinstance(cand, dict):
                continue
            if cand.get("suspected_import_kind") != "package_missing":
                continue
            missing_mod = cand.get("missing_module", "")
            if not missing_mod:
                continue
            if _is_path_like(missing_mod):
                continue
            if missing_mod in seen:
                continue
            seen.add(missing_mod)
            errors.append({
                "package_name": missing_mod,
                "ecosystem": _guess_ecosystem(missing_mod, cand.get("evidence", "")),
                "originating_command": cand.get("originating_command", ""),
                "severity": cand.get("risk_level", "medium"),
                "evidence": cand.get("evidence", ""),
                "source": "import_fix_plan",
                "confidence": cand.get("confidence", 70),
            })

    return errors
