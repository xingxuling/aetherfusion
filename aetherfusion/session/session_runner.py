"""Session runner — orchestrates fusion-session pipeline.

Chains scan → plan → patch → optional apply → optional verify →
optional diagnostic plans (repair/import-fix/dependency/config)
into a single auditable fusion session.

v1.0 is an orchestration layer; it does not add new repair capabilities.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from aetherfusion import __version__
from aetherfusion.scanner.project_analyzer import ProjectAnalyzer
from aetherfusion.reporter.markdown_reporter import generate_report
from aetherfusion.reporter.json_reporter import generate_json_map, write_json_map
from aetherfusion.planner.fusion_planner import generate_fusion_plan
from aetherfusion.reporter.plan_markdown_reporter import generate_plan_report
from aetherfusion.reporter.plan_json_reporter import write_plan_json
from aetherfusion.patcher.dry_run_patch_generator import generate_dry_run_patch
from aetherfusion.reporter.patch_markdown_reporter import generate_patch_report
from aetherfusion.reporter.patch_json_reporter import write_patch_json
from aetherfusion.applier.safe_apply import apply_patch
from aetherfusion.reporter.apply_markdown_reporter import generate_apply_report
from aetherfusion.reporter.apply_json_reporter import write_apply_json
from aetherfusion.verifier.verify_runner import run_verify
from aetherfusion.reporter.verify_json_reporter import write_verify_json
from aetherfusion.reporter.verify_markdown_reporter import generate_verify_report
from aetherfusion.repair.repair_planner import generate_repair_plan
from aetherfusion.reporter.repair_json_reporter import write_repair_json
from aetherfusion.reporter.repair_markdown_reporter import generate_repair_report
from aetherfusion.importfix.import_fix_planner import generate_import_fix_plan
from aetherfusion.reporter.import_fix_json_reporter import write_import_fix_json
from aetherfusion.reporter.import_fix_markdown_reporter import generate_import_fix_report
from aetherfusion.dependency.dependency_planner import generate_dependency_plan
from aetherfusion.reporter.dependency_json_reporter import write_dependency_json
from aetherfusion.reporter.dependency_markdown_reporter import generate_dependency_report
from aetherfusion.reporter.session_json_reporter import write_session_json
from aetherfusion.reporter.session_markdown_reporter import generate_session_report
from aetherfusion.session.session_state import SessionState, ModuleResult
from aetherfusion.session.artifact_index import build_artifact_index, write_artifact_index
from aetherfusion.audit.audit_logger import log_audit_event, make_fusion_session_event


def run_fusion_session(
    source_path: str,
    target_path: str,
    modules: list[str],
    reports_dir: str,
    mode: str = "safe",
    apply_confirm: bool = False,
    verify: bool = False,
    audit_path: str = "",
) -> dict[str, Any]:
    """Run a full fusion-session pipeline.

    Performs scan → plan → patch → optional apply → optional verify →
    optional diagnostic plans. Generates session summary artifacts.

    Args:
        source_path: Path to the source project.
        target_path: Path to the target project.
        modules: List of module names to process.
        reports_dir: Directory for all generated reports.
        mode: Session mode (default "safe").
        apply_confirm: Whether to apply patches after dry-run.
        verify: Whether to run verification after apply.
        audit_path: Path for audit log (default: reports_dir/aetherfusion-audit.jsonl).

    Returns:
        Session result dict with session-level summary.

    Raises:
        FileNotFoundError: If source or target is not a directory.
        ValueError: If modules list is empty.
    """
    source = Path(source_path).resolve()
    target = Path(target_path).resolve()

    # --- Validate inputs ---
    if not source.is_dir():
        raise FileNotFoundError(f"Source path is not a directory: {source}")
    if not target.is_dir():
        raise FileNotFoundError(f"Target path is not a directory: {target}")
    if not modules:
        raise ValueError("modules list cannot be empty")

    # --- Prepare reports directory ---
    rdir = Path(reports_dir).resolve()
    rdir.mkdir(parents=True, exist_ok=True)

    # --- Create session state ---
    session_id = str(uuid.uuid4())
    state = SessionState(
        session_id=session_id,
        source_path=str(source),
        target_path=str(target),
        modules=modules,
        mode=mode,
        options={
            "apply_confirm": apply_confirm,
            "verify": verify,
            "audit": audit_path,
        },
    )

    # Default audit path
    audit_file = Path(audit_path) if audit_path else rdir / "aetherfusion-audit.jsonl"

    # ==================================================================
    # A. SCAN  —  fusion-report.md + fusion-map.json
    # ==================================================================
    scan_report_path = rdir / "fusion-report.md"
    scan_map_path = rdir / "fusion-map.json"

    try:
        source_info = ProjectAnalyzer(source).analyze()
        target_info = ProjectAnalyzer(target).analyze()

        report = generate_report(source_info, target_info)
        scan_report_path.write_text(report, encoding="utf-8")
        state.scan_report_path = str(scan_report_path)

        data = generate_json_map(source_info, target_info)
        write_json_map(scan_map_path, data)
        state.scan_map_path = str(scan_map_path)
    except Exception as e:
        raise RuntimeError(f"Scan failed: {e}") from e

    # ==================================================================
    # B. PLAN → PATCH → optional APPLY  (per module)
    # ==================================================================
    for module_name in modules:
        mr = ModuleResult(module_name=module_name)
        state.module_results[module_name] = mr

        plan_md_path = rdir / f"fusion-plan-{module_name}.md"
        plan_json_path = rdir / f"fusion-plan-{module_name}.json"

        patch_md_path = rdir / f"fusion-patch-{module_name}.md"
        patch_json_path = rdir / f"fusion-patch-{module_name}.json"

        # --- Plan ---
        try:
            plan = generate_fusion_plan(scan_map_path, module_name)
            mr.plan = plan
            mr.status = "planned"
            plan_md_path.write_text(generate_plan_report(plan), encoding="utf-8")
            write_plan_json(plan_json_path, plan)
            mr.plan_json_path = str(plan_json_path)
            mr.plan_md_path = str(plan_md_path)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            mr.status = "failed"
            mr.error = f"Plan failed: {e}"
            continue

        # --- Patch (dry-run) ---
        try:
            manifest = generate_dry_run_patch(plan_json_path)
            mr.patch = manifest
            mr.status = "patched"
            patch_md_path.write_text(generate_patch_report(manifest), encoding="utf-8")
            write_patch_json(patch_json_path, manifest)
            mr.patch_json_path = str(patch_json_path)
            mr.patch_md_path = str(patch_md_path)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            mr.status = "failed"
            mr.error = f"Patch failed: {e}"
            continue

        # --- Apply (if --apply-confirm) ---
        if apply_confirm:
            apply_md_path = rdir / f"apply-result-{module_name}.md"
            apply_json_path = rdir / f"apply-result-{module_name}.json"
            backup_path = rdir / f"apply-backup-{module_name}.json"

            try:
                result = apply_patch(patch_json_path, backup_path)
                mr.apply = result
                mr.status = "applied"
                apply_md_path.write_text(generate_apply_report(result), encoding="utf-8")
                write_apply_json(apply_json_path, result)
                mr.apply_json_path = str(apply_json_path)
                mr.apply_md_path = str(apply_md_path)

                if result.get("rollback_manifest_path"):
                    mr.rollback_manifest_path = result["rollback_manifest_path"]
                    state.rollback_manifests.append(result["rollback_manifest_path"])
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
                mr.status = "failed"
                mr.error = f"Apply failed: {e}"
        else:
            # Record skipped_by_user_choice
            mr.status = "patched"  # keep as patched; apply was skipped intentionally

    # ==================================================================
    # C. VERIFY  (optional)
    # ==================================================================
    if verify:
        verify_json_path = rdir / "verify-result.json"
        verify_md_path = rdir / "verify-result.md"

        try:
            vresult = run_verify(target)
            state.verify_result = vresult
            state.verify_json_path = str(verify_json_path)
            state.verify_md_path = str(verify_md_path)

            write_verify_json(verify_json_path, vresult)
            verify_md_path.write_text(generate_verify_report(vresult), encoding="utf-8")

            summary = vresult.get("summary", {})
            if summary.get("failed", 0) > 0:
                state.verify_passed = False

                # --- Diagnostic plans ---
                repair_json = rdir / "repair-plan.json"
                repair_md = rdir / "repair-plan.md"

                try:
                    rplan = generate_repair_plan(str(verify_json_path))
                    write_repair_json(repair_json, rplan)
                    repair_md.write_text(generate_repair_report(rplan), encoding="utf-8")
                    state.repair_plan_json_path = str(repair_json)
                    state.repair_plan_md_path = str(repair_md)
                    state.diagnostic_plans_generated.append("repair-plan")
                except Exception as e:
                    state.errors.append(f"Repair plan generation failed: {e}")

                # -- import-fix-plan
                import_fix_json = rdir / "import-fix-plan.json"
                import_fix_md = rdir / "import-fix-plan.md"
                try:
                    iplan = generate_import_fix_plan(repair_json, target, None, None)
                    write_import_fix_json(import_fix_json, iplan)
                    import_fix_md.write_text(generate_import_fix_report(iplan), encoding="utf-8")
                    state.import_fix_plan_json_path = str(import_fix_json)
                    state.import_fix_plan_md_path = str(import_fix_md)
                    state.diagnostic_plans_generated.append("import-fix-plan")
                except Exception as e:
                    state.errors.append(f"Import-fix plan generation failed: {e}")

                # -- dependency-plan
                dep_json = rdir / "dependency-plan.json"
                dep_md = rdir / "dependency-plan.md"
                try:
                    dplan = generate_dependency_plan(repair_json, target, source)
                    write_dependency_json(dep_json, dplan)
                    dep_md.write_text(generate_dependency_report(dplan), encoding="utf-8")
                    state.dependency_plan_json_path = str(dep_json)
                    state.dependency_plan_md_path = str(dep_md)
                    state.diagnostic_plans_generated.append("dependency-plan")
                except Exception as e:
                    state.errors.append(f"Dependency plan generation failed: {e}")

                # -- config-plan (optional — may not exist)
                try:
                    from aetherfusion.configplan.config_planner import generate_config_plan
                    from aetherfusion.reporter.config_json_reporter import write_config_json
                    from aetherfusion.reporter.config_markdown_reporter import generate_config_report

                    cfg_json = rdir / "config-plan.json"
                    cfg_md = rdir / "config-plan.md"
                    cplan = generate_config_plan(
                        repair_file=repair_json,
                        import_fix_file=import_fix_json if state.import_fix_plan_json_path else None,
                        dependency_file=dep_json,
                        target_path=target,
                        source_path=source,
                    )
                    write_config_json(cfg_json, cplan)
                    cfg_md.write_text(generate_config_report(cplan), encoding="utf-8")
                    state.config_plan_json_path = str(cfg_json)
                    state.config_plan_md_path = str(cfg_md)
                    state.diagnostic_plans_generated.append("config-plan")
                except ImportError:
                    state.errors.append("Config-plan module not available (v0.9 required)")
                except Exception as e:
                    state.errors.append(f"Config plan generation failed: {e}")
            else:
                state.verify_passed = True
        except Exception as e:
            state.errors.append(f"Verify failed: {e}")

    # ==================================================================
    # D. GENERATE FINAL ARTIFACTS
    # ==================================================================
    session_json_path = rdir / "fusion-session.json"
    session_md_path = rdir / "fusion-session.md"
    artifact_index_path = rdir / "artifact-index.json"

    # -- artifact-index.json
    artifacts = state.get_artifact_paths()
    art_data = build_artifact_index(
        session_id, str(source), str(target), modules, artifacts, rdir
    )
    try:
        write_artifact_index(artifact_index_path, art_data)
        state.artifact_index_path = str(artifact_index_path)
    except OSError as e:
        state.errors.append(f"Artifact index write failed: {e}")

    # -- fusion-session.json
    session_data = state.to_dict()
    # Include errors in session data
    session_data["errors"] = state.errors
    try:
        write_session_json(session_json_path, session_data)
        state.session_json_path = str(session_json_path)
    except OSError as e:
        state.errors.append(f"Session JSON write failed: {e}")

    # -- fusion-session.md
    try:
        md_report = generate_session_report(state)
        session_md_path.write_text(md_report, encoding="utf-8")
        state.session_md_path = str(session_md_path)
    except OSError as e:
        state.errors.append(f"Session Markdown write failed: {e}")

    # -- Audit
    try:
        audit_event = make_fusion_session_event(
            session_id=session_id,
            source_path=str(source),
            target_path=str(target),
            modules=modules,
            summary={
                "total_modules": len(modules),
                "failed_modules": state.failed_modules,
                "succeeded_modules": state.succeeded_modules,
                "verify_passed": state.verify_passed,
                "diagnostic_plans": state.diagnostic_plans_generated,
            },
            session_json_path=str(session_json_path),
        )
        log_audit_event(audit_file, audit_event)
    except Exception as e:
        state.errors.append(f"Audit write failed: {e}")

    # Build blocked_operations
    state.blocked_operations = [
        "No automatic apply without --apply-confirm",
        "No automatic verify without --verify",
        "No automatic dependency installation",
        "No automatic config modification",
        "No automatic import fixes",
        "No network calls",
        "No target file overwrites",
        "Apply only allows add_file operations",
    ]

    return state.to_dict()
