"""Session JSON reporter — writes fusion-session.json."""

import json
from pathlib import Path
from typing import Any


def write_session_json(path: Path, data: dict[str, Any]) -> None:
    """Write the fusion-session JSON to disk.

    Args:
        path: Output file path.
        data: Session data dict from SessionState.to_dict().

    Raises:
        OSError: If the file cannot be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
