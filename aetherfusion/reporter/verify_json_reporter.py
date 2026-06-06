"""JSON reporter for verify results.

Writes the verify result dict to a JSON file with indent=2.
"""

import json
from pathlib import Path
from typing import Any


def write_verify_json(output_path: Path, result: dict[str, Any]) -> None:
    """Serialize the verify result dict to a JSON file.

    Creates parent directories as needed.

    Args:
        output_path: Destination file path.
        result: Verify result dict from run_verify.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a clean serializable copy
    serializable = dict(result)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2, ensure_ascii=False)