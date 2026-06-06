"""AetherFusion dependency-plan module — v0.8.0 read-only dependency analysis.

Provides the `dependency-plan` subcommand: analyses missing_dependency
and package_missing errors from repair-plan / import-fix-plan, parses
dependency manifest files, and generates a structured dependency update
plan without modifying any project files.
"""

from aetherfusion.dependency.dependency_planner import generate_dependency_plan

__all__ = ["generate_dependency_plan"]
