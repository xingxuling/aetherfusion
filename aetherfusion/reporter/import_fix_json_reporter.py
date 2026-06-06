"""JSON reporter for import fix plans.

Writes the import fix plan dict to a JSON file with indent=2.
"""

import json
from pathlib import Path
from typing import Any


def write_import_fix_json(output_path: Path, plan: dict[str, Any]) -> None:
    """Serialize the import fix plan dict to a JSON file.

    Creates parent directories as needed.

    Args:
        output_path: Destination file path.
        plan: Import fix plan dict from generate_import_fix_plan.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(plan)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2, ensure_ascii=False)