"""Import fix planner — classifies missing imports and generates fix candidates.

v0.7 is read-only — it analyses import errors from repair-plan JSON,
indexes the target project, and produces a fix plan.

No files are modified, no dependencies installed, no imports auto-fixed.
"""

import json
from pathlib import Path
from typing import Any

from aetherfusion.importfix.import_error_extractor import extract_missing_imports
from aetherfusion.importfix.target_indexer import index_target

IMPORT_FIX_PLAN_VERSION = "0.7.0"

# --- Classification constants ---

CLASS_RELATIVE = "missing_local_file"
CLASS_WRONG_PATH = "wrong_relative_path"
CLASS_ALIAS = "missing_alias_config"
CLASS_INDEX_EXPORT = "missing_index_export"
CLASS_SOURCE_ONLY = "source_only_dependency"
CLASS_PACKAGE = "package_missing"
CLASS_UNKNOWN = "unresolved_unknown"

# --- Classification descriptions ---

_CLASS_DESCRIPTIONS: dict[str, str] = {
    CLASS_RELATIVE: "Relative import path points to a file not found in target.",
    CLASS_WRONG_PATH: "Target has a file with the same name but at a different relative path.",
    CLASS_ALIAS: "Import uses a path alias (@/ ~/) not configured in target's build tool.",
    CLASS_INDEX_EXPORT: "Target has a matching directory but no index file (index.ts/__init__.py).",
    CLASS_SOURCE_ONLY: "Module exists in source (patch/apply records) and is missing in target.",
    CLASS_PACKAGE: "Import refers to an npm package or PyPI package not installed in target.",
    CLASS_UNKNOWN: "Could not determine the nature of this missing import.",
}

# --- Cause text ---

_CAUSE_TEXT: dict[str, str] = {
    CLASS_RELATIVE: "Source file references a relative import that does not exist at the expected path in target.",
    CLASS_WRONG_PATH: "A file with the same name exists in the target project but at a different directory level.",
    CLASS_ALIAS: "Import uses an alias (e.g. '@/utils/foo') that is not configured in target's tsconfig paths or vite/webpack resolve.alias.",
    CLASS_INDEX_EXPORT: "Target has a matching directory but lacks a barrel/index re-export file.",
    CLASS_SOURCE_ONLY: "The imported module only exists in the source project and was not applied to target.",
    CLASS_PACKAGE: "The import refers to an external package not installed in target's dependencies.",
    CLASS_UNKNOWN: "Unable to determine the cause from available error evidence.",
}

# --- Suggested actions ---

_ACTION_TEXT: dict[str, str] = {
    CLASS_RELATIVE: "Copy the missing file from source to the correct target path, or update the import statement to point to the correct location.",
    CLASS_WRONG_PATH: "Update the import statement to use the correct relative path to the existing target file.",
    CLASS_ALIAS: "Add the path alias to target's tsconfig.json paths or vite.config resolve.alias, or replace with a relative import.",
    CLASS_INDEX_EXPORT: "Create an index/barrel file in the target directory that re-exports the required modules.",
    CLASS_SOURCE_ONLY: "Run 'aetherfusion apply' to copy the source file to target, or add the module to a new patch manifest.",
    CLASS_PACKAGE: "Review and manually add the package to target's package.json / requirements.txt. v0.7 does not install dependencies.",
    CLASS_UNKNOWN: "Manually inspect the source file's import statements and verify target project structure.",
}

# --- Automation eligibility ---

_AUTOMATION_MAP: dict[str, str] = {
    CLASS_RELATIVE: "safe_auto_candidate",
    CLASS_WRONG_PATH: "plan_only",
    CLASS_ALIAS: "manual_only",
    CLASS_INDEX_EXPORT: "safe_auto_candidate",
    CLASS_SOURCE_ONLY: "plan_only",
    CLASS_PACKAGE: "manual_only",
    CLASS_UNKNOWN: "manual_only",
}

# --- Risk levels ---

_RISK_MAP: dict[str, str] = {
    CLASS_RELATIVE: "low",
    CLASS_WRONG_PATH: "medium",
    CLASS_ALIAS: "medium",
    CLASS_INDEX_EXPORT: "low",
    CLASS_SOURCE_ONLY: "low",
    CLASS_PACKAGE: "medium",
    CLASS_UNKNOWN: "high",
}

# --- Confidence mappings ---

_CONFIDENCE_MAP: dict[str, int] = {
    CLASS_RELATIVE: 90,
    CLASS_WRONG_PATH: 80,
    CLASS_ALIAS: 85,
    CLASS_INDEX_EXPORT: 75,
    CLASS_SOURCE_ONLY: 85,
    CLASS_PACKAGE: 70,
    CLASS_UNKNOWN: 10,
}


def _load_patch_manifest(patch_path: Path | None) -> dict[str, Any] | None:
    """Load optional patch manifest JSON."""
    if patch_path is None:
        return None
    pp = Path(patch_path)
    if not pp.is_file():
        return None
    try:
        with open(pp, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _load_apply_result(apply_path: Path | None) -> dict[str, Any] | None:
    """Load optional apply result JSON."""
    if apply_path is None:
        return None
    ap = Path(apply_path)
    if not ap.is_file():
        return None
    try:
        with open(ap, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _build_source_file_set(
    patch: dict[str, Any] | None,
    apply_result: dict[str, Any] | None,
) -> set[str]:
    """Build a set of source file relative paths from patch/apply manifests.

    Returns a set of relative paths (using / separators) of source files.
    """
    source_files: set[str] = set()

    if patch:
        for op in patch.get("operations", []):
            if isinstance(op, dict) and op.get("type") in ("add_file",):
                sp = op.get("source_path", "")
                if sp:
                    source_files.add(Path(sp).as_posix())

    if apply_result:
        for op in apply_result.get("operations_applied", []):
            if isinstance(op, dict):
                sp = op.get("source_path", "")
                if sp:
                    source_files.add(Path(sp).as_posix())

    return source_files


def _classify_import(
    missing_module: str,
    index: dict[str, Any],
    source_files: set[str],
) -> tuple[str, list[str]]:
    """Classify a missing import and return (category, related_files).

    Args:
        missing_module: The module name extracted from error (e.g. './utils/foo').
        index: Target file index from target_indexer.
        source_files: Set of source file paths known from patch/apply.

    Returns:
        (classification_constant, list_of_related_file_paths)
    """
    related: list[str] = []

    # --- Rule 1: ./ or ../ prefix → relative import ---
    if missing_module.startswith("./") or missing_module.startswith("../"):
        # Check if a file with matching stem exists at a different path
        stem = Path(missing_module).stem
        by_stem = index.get("by_stem", {})
        if stem in by_stem:
            related = [e["relative_path"] for e in by_stem[stem]]
            return CLASS_WRONG_PATH, related

        # Check if the referenced path is a directory that exists in target
        relative_part = missing_module
        if relative_part.startswith("./"):
            relative_part = relative_part[2:]
        elif relative_part.startswith("../"):
            # For ../ resolution, strip leading ../ and look for matching dir suffix
            relative_part = relative_part.lstrip("./")

        by_dir = index.get("by_dir", {})
        if relative_part in by_dir:
            # Directory exists — check for index file
            has_index = any(
                e["stem"] == "index" or e["stem"] == "__init__"
                for e in by_dir[relative_part]
            )
            if not has_index:
                return CLASS_INDEX_EXPORT, [relative_part]

        return CLASS_RELATIVE, related

    # --- Rule 2: @/ or ~ prefix → alias config ---
    if missing_module.startswith("@/") or missing_module.startswith("~"):
        return CLASS_ALIAS, related

    # --- Rule 3: Check if it looks like a local file reference ---
    # e.g. "utils/foo" or "components/Button" (no package-like pattern)
    is_local_pattern = "/" in missing_module or missing_module[0].isupper()

    if is_local_pattern:
        # Check if the module stem exists in target
        stem = Path(missing_module).stem
        by_name = index.get("by_name", {})
        by_stem = index.get("by_stem", {})

        # Try exact filename
        for ext in [".ts", ".tsx", ".js", ".jsx", ".py"]:
            fname = f"{stem}{ext}"
            if fname in by_name:
                related = [e["relative_path"] for e in by_name[fname]]
                return CLASS_WRONG_PATH, related

        # Check if a directory with that name exists but no index
        by_dir = index.get("by_dir", {})
        dir_name = missing_module.split("/")[-1]
        matching_dirs = [d for d in by_dir if d.endswith(dir_name) or d == dir_name]
        if matching_dirs:
            # Check if any matching dir has an index file
            has_index = False
            for d in matching_dirs:
                for idx_name in ["index.ts", "index.tsx", "index.js", "index.jsx", "__init__.py"]:
                    fname = f"{d}/{idx_name}" if d != "." else idx_name
                    if any(e["relative_path"] == fname for e in index.get("indexed_files", [])):
                        has_index = True
                        break
            if not has_index:
                return CLASS_INDEX_EXPORT, matching_dirs
            else:
                # Has index but still not resolved — maybe wrong path
                if stem in by_stem:
                    related = [e["relative_path"] for e in by_stem[stem]]
                    return CLASS_WRONG_PATH, related

        # Check source files from patch/apply
        for sf in source_files:
            sf_stem = Path(sf).stem
            if sf_stem == stem:
                related.append(sf)
        if related:
            return CLASS_SOURCE_ONLY, related

        return CLASS_RELATIVE, related

    # --- Rule 4: Looks like a package name (no path separators, not local) ---
    # Check if it might be in source files
    stem = missing_module
    for sf in source_files:
        sf_stem = Path(sf).stem
        if sf_stem == stem:
            related.append(sf)
    if related:
        return CLASS_SOURCE_ONLY, related

    return CLASS_PACKAGE, related


def _build_blocked_actions() -> list[str]:
    """Return the standard v0.7 blocked actions list."""
    return [
        "Do NOT modify source or target project files.",
        "Do NOT auto-fix import statements.",
        "Do NOT auto-create files or directories.",
        "Do NOT auto-modify config files (tsconfig.json / vite.config / package.json).",
        "Do NOT auto-install dependencies (npm install / pip install).",
        "Do NOT execute build / test / lint / typecheck commands.",
        "Do NOT call the network or download packages.",
        "Do NOT auto-apply any file changes.",
        "This is a read-only import fix plan. All actions require human review.",
    ]


def generate_import_fix_plan(
    repair_path: Path,
    target_path: Path,
    patch_path: Path | None = None,
    apply_path: Path | None = None,
    source_repair_file_override: str = "",
) -> dict[str, Any]:
    """Generate an import fix plan from a repair-plan JSON.

    Args:
        repair_path: Path to the v0.6 repair-plan JSON.
        target_path: Path to the target project root.
        patch_path: Optional path to v0.3 patch manifest JSON.
        apply_path: Optional path to v0.4 apply result JSON.
        source_repair_file_override: Override for the source_repair_file field.

    Returns:
        Import fix plan dict.

    Raises:
        FileNotFoundError: If repair_path or target_path does not exist.
        NotADirectoryError: If target_path is not a directory.
        json.JSONDecodeError: If repair JSON is invalid.
        ValueError: If required fields are missing.
    """
    repair_path = Path(repair_path)
    if not repair_path.is_file():
        raise FileNotFoundError(f"Repair plan file not found: {repair_path}")

    target_path = Path(target_path).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_path}")

    # Load repair plan
    with open(repair_path, "r", encoding="utf-8") as fh:
        repair_data = json.load(fh)

    if not isinstance(repair_data, dict):
        raise ValueError("Repair plan must be a JSON object")

    # Load optional inputs
    patch_data = _load_patch_manifest(patch_path)
    apply_data = _load_apply_result(apply_path)
    source_files = _build_source_file_set(patch_data, apply_data)

    # Extract missing_import errors
    repair_items = repair_data.get("repair_items", [])
    if not isinstance(repair_items, list):
        repair_items = []
    missing_imports = extract_missing_imports(repair_items)

    # Index target
    index = index_target(target_path)

    # Generate fix candidates
    fix_candidates: list[dict[str, Any]] = []
    for mi in missing_imports:
        module_name = mi.get("missing_module", "unknown_module")
        classification, related = _classify_import(module_name, index, source_files)

        candidate = {
            "missing_module": module_name,
            "originating_command": mi.get("command", "?"),
            "suspected_import_kind": classification,
            "likely_cause": _CAUSE_TEXT.get(classification, _CAUSE_TEXT[CLASS_UNKNOWN]),
            "confidence": _CONFIDENCE_MAP.get(classification, 10),
            "suggested_action": _ACTION_TEXT.get(classification, _ACTION_TEXT[CLASS_UNKNOWN]),
            "automation_eligibility": _AUTOMATION_MAP.get(classification, "manual_only"),
            "risk_level": _RISK_MAP.get(classification, "high"),
            "evidence": mi.get("evidence", ""),
            "raw_error": mi.get("raw_error", ""),
            "related_files": related,
        }
        fix_candidates.append(candidate)

    # Summary
    total_imports = len(fix_candidates)
    by_kind: dict[str, int] = {}
    by_automation: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for fc in fix_candidates:
        k = fc["suspected_import_kind"]
        a = fc["automation_eligibility"]
        r = fc["risk_level"]
        by_kind[k] = by_kind.get(k, 0) + 1
        by_automation[a] = by_automation.get(a, 0) + 1
        by_risk[r] = by_risk.get(r, 0) + 1

    return {
        "import_fix_plan_version": IMPORT_FIX_PLAN_VERSION,
        "source_repair_file": source_repair_file_override or str(repair_path.resolve()),
        "target_path": str(target_path),
        "summary": {
            "total_extracted_import_errors": len(missing_imports),
            "total_fix_candidates": total_imports,
            "by_suspected_kind": by_kind,
            "by_automation_eligibility": by_automation,
            "by_risk_level": by_risk,
        },
        "extracted_import_errors": [
            {
                "missing_module": mi.get("missing_module", "unknown_module"),
                "command": mi.get("command", "?"),
                "evidence": mi.get("evidence", "")[:300],
            }
            for mi in missing_imports
        ],
        "fix_candidates": fix_candidates,
        "blocked_actions": _build_blocked_actions(),
        "next_recommended_command": (
            "python -m aetherfusion plan --map maps/map.json --module <name> && "
            "python -m aetherfusion patch --plan plans/plan.json --dry-run && "
            "python -m aetherfusion apply --patch patches/patch.json --confirm"
        ),
    }