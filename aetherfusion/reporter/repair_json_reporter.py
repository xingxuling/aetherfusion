"""JSON reporter for repair plans.

Writes the repair plan dict to a JSON file with indent=2.
"""

import json
from pathlib import Path
from typing import Any


def write_repair_json(output_path: Path, plan: dict[str, Any]) -> None:
    """Serialize the repair plan dict to a JSON file.

    Creates parent directories as needed.

    Args:
        output_path: Destination file path.
        plan: Repair plan dict from generate_repair_plan.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(plan)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2, ensure_ascii=False)