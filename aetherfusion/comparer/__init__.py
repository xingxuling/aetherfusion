"""Comparer module — compares two ProjectInfo objects."""

from aetherfusion.comparer.tech_stack import compare_tech_stack
from aetherfusion.comparer.dependencies import compare_dependencies
from aetherfusion.comparer.structure import compare_structure
from aetherfusion.comparer.fusion import analyze_fusion

__all__ = [
    "compare_tech_stack",
    "compare_dependencies",
    "compare_structure",
    "analyze_fusion",
]