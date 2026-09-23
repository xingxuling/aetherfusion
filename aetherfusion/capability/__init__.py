"""Capability-level fusion planning for AetherFusion.

This package is intentionally read-only in the v2 alpha slice. It turns a
source codebase into capability candidates, maps them onto TaoWind-style
canonical layers, chooses an integration strategy, and emits auditable plans.
"""

from .planner import CAPABILITY_FUSION_SCHEMA_VERSION, generate_capability_fusion_plan

__all__ = ["CAPABILITY_FUSION_SCHEMA_VERSION", "generate_capability_fusion_plan"]
