"""Session state tracker — manages mutable state for fusion-session runs.

Tracks module results, verify outcomes, diagnostic plans, and
rolled-back operations across the session lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModuleResult:
    """Per-module result within a session."""

    module_name: str
    plan: dict[str, Any] | None = None
    plan_json_path: str | None = None
    plan_md_path: str | None = None
    patch: dict[str, Any] | None = None
    patch_json_path: str | None = None
    patch_md_path: str | None = None
    apply: dict[str, Any] | None = None
    apply_json_path: str | None = None
    apply_md_path: str | None = None
    rollback_manifest_path: str | None = None
    status: str = "pending"  # pending / planned / patched / applied / failed
    error: str | None = None


@dataclass
class SessionState:
    """Mutable state for a single fusion-session run.

    Tracks the session-level metadata and per-module results
    as the pipeline progresses through scan → plan → patch →
    apply → verify → diagnostic plans.
    """

    session_id: str
    source_path: str
    target_path: str
    modules: list[str]
    mode: str = "safe"
    options: dict[str, bool] = field(default_factory=dict)

    # Scan artifacts
    scan_report_path: str | None = None
    scan_map_path: str | None = None

    # Per-module results
    module_results: dict[str, ModuleResult] = field(default_factory=dict)

    # Verify
    verify_result: dict[str, Any] | None = None
    verify_json_path: str | None = None
    verify_md_path: str | None = None
    verify_passed: bool | None = None

    # Diagnostic plans (generated when verify fails)
    repair_plan_json_path: str | None = None
    repair_plan_md_path: str | None = None
    import_fix_plan_json_path: str | None = None
    import_fix_plan_md_path: str | None = None
    dependency_plan_json_path: str | None = None
    dependency_plan_md_path: str | None = None
    config_plan_json_path: str | None = None
    config_plan_md_path: str | None = None
    diagnostic_plans_generated: list[str] = field(default_factory=list)

    # Blocked operations
    blocked_operations: list[str] = field(default_factory=list)

    # Rollback manifests
    rollback_manifests: list[str] = field(default_factory=list)

    # Session artifacts
    session_json_path: str | None = None
    session_md_path: str | None = None
    artifact_index_path: str | None = None

    # Error collection
    errors: list[str] = field(default_factory=list)

    @property
    def failed_modules(self) -> list[str]:
        return [m for m, r in self.module_results.items() if r.status == "failed"]

    @property
    def succeeded_modules(self) -> list[str]:
        return [m for m, r in self.module_results.items() if r.status != "failed"]

    def get_artifact_paths(self) -> dict[str, Any]:
        """Collect all artifact paths for artifact-index.json."""
        plan_reports: list[str] = []
        patch_reports: list[str] = []
        apply_results: list[str] = []

        for mr in self.module_results.values():
            if mr.plan_json_path:
                plan_reports.append(mr.plan_json_path)
            if mr.patch_json_path:
                patch_reports.append(mr.patch_json_path)
            if mr.apply_json_path:
                apply_results.append(mr.apply_json_path)

        return {
            "scan_report": self.scan_report_path,
            "scan_map": self.scan_map_path,
            "plan_reports": plan_reports,
            "patch_reports": patch_reports,
            "apply_results": apply_results,
            "rollback_manifests": self.rollback_manifests,
            "verify_result": self.verify_json_path,
            "repair_plan": self.repair_plan_json_path,
            "import_fix_plan": self.import_fix_plan_json_path,
            "dependency_plan": self.dependency_plan_json_path,
            "config_plan": self.config_plan_json_path,
            "audit_log": None,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state to dict (for fusion-session.json)."""
        module_results_serialized: dict[str, Any] = {}
        for name, mr in self.module_results.items():
            module_results_serialized[name] = {
                "module_name": mr.module_name,
                "status": mr.status,
                "error": mr.error,
                "plan_json_path": mr.plan_json_path,
                "patch_json_path": mr.patch_json_path,
                "apply_json_path": mr.apply_json_path,
                "rollback_manifest_path": mr.rollback_manifest_path,
            }

        verify_summary = None
        if self.verify_result:
            verify_summary = {
                "passed": self.verify_passed,
                "summary": self.verify_result.get("summary"),
                "json_path": self.verify_json_path,
            }

        return {
            "session_version": "1.0.1",
            "session_id": self.session_id,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "modules": self.modules,
            "mode": self.mode,
            "options": self.options,
            "module_results": module_results_serialized,
            "verify_summary": verify_summary,
            "diagnostic_plans": {
                "generated": self.diagnostic_plans_generated,
                "repair_plan": self.repair_plan_json_path,
                "import_fix_plan": self.import_fix_plan_json_path,
                "dependency_plan": self.dependency_plan_json_path,
                "config_plan": self.config_plan_json_path,
            },
            "blocked_operations": self.blocked_operations,
            "rollback_manifests": self.rollback_manifests,
            "artifacts": self.get_artifact_paths(),
            "next_recommended_action": self._build_next_action(),
        }

    def _build_next_action(self) -> str:
        """Generate next recommended action based on session state."""
        if self.failed_modules:
            return f"Review failed modules: {', '.join(self.failed_modules)}"
        if self.verify_result and not self.verify_passed:
            plans = ", ".join(self.diagnostic_plans_generated)
            return f"Review diagnostic plans: {plans}"
        if self.options.get("apply_confirm") and self.module_results:
            return "All modules applied. Run verify to validate."
        if self.module_results:
            return "Review patch previews. Re-run with --apply-confirm to apply."
        return "Review scan report to plan modules."
