"""Import error extractor — extracts missing_import errors from repair-plan JSON.

Parses error evidence to identify the missing module name from common
error message patterns across TypeScript, JavaScript, and Python.
"""

import re
from typing import Any


def extract_missing_imports(
    repair_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter repair_items to those with error_type=missing_import
    and extract the missing module name.

    Each returned dict extends the original repair_item with:
        missing_module: str  — the extracted module name
        raw_error: str       — the original error text used for extraction

    Args:
        repair_items: List of repair_item dicts from repair-plan JSON.

    Returns:
        List of enriched repair_items (only missing_import type).
    """
    result: list[dict[str, Any]] = []
    for item in repair_items:
        if item.get("error_type") != "missing_import":
            continue
        evidence = item.get("evidence", "")
        module_name = _extract_module_name(evidence)
        enriched = dict(item)
        enriched["missing_module"] = module_name
        enriched["raw_error"] = evidence
        result.append(enriched)
    return result


def _extract_module_name(evidence: str) -> str:
    """Extract the missing module name from error text.

    Supports the following patterns (case-insensitive for keywords):
    - Cannot find module 'x' or "x"
    - Module not found: Can't resolve 'x' or "x"
    - TS2307: Cannot find module 'x' or "x"
    - ImportError: No module named x
    - ModuleNotFoundError: No module named 'x' or "x"
    - Error: Cannot find module 'x'

    Returns the module name as-is (including relative paths like './foo'),
    or "unknown_module" if no pattern matched.
    """
    if not evidence:
        return "unknown_module"

    # Pattern 1: 'Cannot find module' with quoted identifier
    # Handles both single and double quotes
    m = re.search(
        r"[Cc]annot\s+find\s+module\s+['\"]([^'\"]+)['\"]",
        evidence,
    )
    if m:
        return m.group(1)

    # Pattern 2: "Module not found: Can't resolve" with quoted identifier
    m = re.search(
        r"Module\s+not\s+found[:\s]+Can'?t\s+resolve\s+['\"]([^'\"]+)['\"]",
        evidence,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # Pattern 3: TS2307 with quoted identifier
    m = re.search(
        r"TS2307[:\s]+.*?Cannot\s+find\s+module\s+['\"]([^'\"]+)['\"]",
        evidence,
    )
    if m:
        return m.group(1)

    # Pattern 4: ImportError: No module named <name> (unquoted Python)
    m = re.search(
        r"ImportError[:\s]+No\s+module\s+named\s+['\"]?(\S+)['\"]?",
        evidence,
    )
    if m:
        return m.group(1).rstrip("'").rstrip('"')

    # Pattern 5: ModuleNotFoundError: No module named '<name>' or "<name>"
    m = re.search(
        r"ModuleNotFoundError[:\s]+No\s+module\s+named\s+['\"]([^'\"]+)['\"]",
        evidence,
    )
    if m:
        return m.group(1)

    # Pattern 6: ModuleNotFoundError unquoted (Python)
    m = re.search(
        r"ModuleNotFoundError[:\s]+No\s+module\s+named\s+['\"]?(\S+)['\"]?",
        evidence,
    )
    if m:
        return m.group(1).rstrip("'").rstrip('"')

    # Pattern 7: Generic "cannot resolve" (webpack)
    m = re.search(
        r"[Cc]annot\s+resolve\s+['\"]([^'\"]+)['\"]",
        evidence,
    )
    if m:
        return m.group(1)

    return "unknown_module"