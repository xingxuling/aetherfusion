"""Artifact index builder for fusion-session.

Generates artifact-index.json tracking all files produced during a session.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_artifact_index(
    session_id: str,
    source_path: str,
    target_path: str,
    modules: list[str],
    artifacts: dict[str, Any],
    reports_dir: Path,
) -> dict[str, Any]:
    """Build the artifact-index.json structure.

    Args:
        session_id: Unique session identifier.
        source_path: Source project path.
        target_path: Target project path.
        modules: List of module names processed.
        artifacts: Dict of artifact path categories from SessionState.
        reports_dir: Root directory for the session reports.

    Returns:
        Struct dict for artifact-index.json.
    """
    # Filter out None values and ensure paths are relative or absolute strings
    def _clean(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, list):
            return [str(v) for v in val if v is not None]
        return str(val)

    cleaned = {k: _clean(v) for k, v in artifacts.items()}

    return {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "target": str(target_path),
        "modules": modules,
        "artifacts": cleaned,
    }


def write_artifact_index(path: Path, data: dict[str, Any]) -> None:
    """Write artifact-index.json to disk.

    Args:
        path: Output file path.
        data: Artifact index dict from build_artifact_index.

    Raises:
        OSError: If the file cannot be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
