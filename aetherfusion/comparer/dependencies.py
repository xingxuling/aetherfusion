"""Dependency comparison between two projects."""

from typing import Any

from aetherfusion.scanner.project_analyzer import ProjectInfo


def compare_dependencies(source: ProjectInfo, target: ProjectInfo) -> dict[str, Any]:
    """Compare dependencies of two projects.

    Returns::

        {
            "common": {name: {"source_version": ..., "target_version": ..., "conflict": bool}},
            "unique_to_source": {name: info},
            "unique_to_target": {name: info},
            "version_conflicts": [{name, source_ver, target_ver}],
        }
    """
    s_deps = source.dependencies
    t_deps = target.dependencies
    s_names = set(s_deps)
    t_names = set(t_deps)

    common_names = s_names & t_names
    common: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, str]] = []

    for name in sorted(common_names):
        s_ver = s_deps[name]["version"]
        t_ver = t_deps[name]["version"]
        is_conflict = (s_ver != t_ver) and bool(s_ver) and bool(t_ver)
        common[name] = {
            "source_version": s_ver,
            "target_version": t_ver,
            "conflict": is_conflict,
        }
        if is_conflict:
            conflicts.append({
                "name": name,
                "source_version": s_ver,
                "target_version": t_ver,
            })

    return {
        "common": common,
        "unique_to_source": {n: s_deps[n] for n in sorted(s_names - t_names)},
        "unique_to_target": {n: t_deps[n] for n in sorted(t_names - s_names)},
        "version_conflicts": conflicts,
    }