"""Import fix plan generation (v0.7).

Extracts missing_import errors from repair-plan JSON, indexes the
target project, and generates a detailed import/path fix plan.

v0.7 is read-only — no files are modified, no dependencies installed,
no imports auto-fixed, no configs changed.
"""

from aetherfusion.importfix.import_fix_planner import generate_import_fix_plan

__all__ = ["generate_import_fix_plan"]