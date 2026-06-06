"""Directory structure comparison between two projects."""

from typing import Any

from aetherfusion.scanner.project_analyzer import ProjectInfo


def compare_structure(source: ProjectInfo, target: ProjectInfo) -> dict[str, Any]:
    """Compare top-level directory structures of two projects.

    Returns::

        {
            "source_dirs": [...],
            "target_dirs": [...],
            "common_dirs": [...],
            "unique_to_source": [...],
            "unique_to_target": [...],
        }
    """
    s_dirs = set(source.core_directories)
    t_dirs = set(target.core_directories)

    return {
        "source_dirs": sorted(s_dirs),
        "target_dirs": sorted(t_dirs),
        "common_dirs": sorted(s_dirs & t_dirs),
        "unique_to_source": sorted(s_dirs - t_dirs),
        "unique_to_target": sorted(t_dirs - s_dirs),
    }