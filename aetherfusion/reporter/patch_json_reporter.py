"""Patch JSON reporter — serializes the dry-run patch manifest to JSON."""

import json
from pathlib import Path
from typing import Any


def write_patch_json(json_path: Path, manifest: dict[str, Any]) -> None:
    """Serialize the patch manifest to a JSON file.

    Args:
        json_path: Output file path.
        manifest: The patch manifest dict from dry_run_patch_generator.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)