"""Tech stack comparison between two projects."""

from typing import Any

from aetherfusion.scanner.project_analyzer import ProjectInfo


def compare_tech_stack(source: ProjectInfo, target: ProjectInfo) -> dict[str, Any]:
    """Compare technology stacks of two projects.

    Returns::

        {
            "source_stack": [...],
            "target_stack": [...],
            "common": [...],
            "unique_to_source": [...],
            "unique_to_target": [...],
        }
    """
    s_stack = set(source.tech_stack)
    t_stack = set(target.tech_stack)
    common = s_stack & t_stack
    return {
        "source_stack": sorted(s_stack),
        "target_stack": sorted(t_stack),
        "common": sorted(common),
        "unique_to_source": sorted(s_stack - t_stack),
        "unique_to_target": sorted(t_stack - s_stack),
    }