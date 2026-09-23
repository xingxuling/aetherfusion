"""Standalone capability-fusion CLI for the AetherFusion v2 alpha slice."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .planner import generate_capability_fusion_plan
from .reporter import write_json, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aetherfusion-capability",
        description=(
            "AetherFusion v2 alpha — inspect and plan capability-level fusion "
            "between local codebases."
        ),
    )
    parser.add_argument("--source", required=True, help="Local source project to inspect.")
    parser.add_argument("--target", required=True, help="Local target project to compare against.")
    parser.add_argument(
        "--project-url",
        default=None,
        help="Optional provenance URL for the source project.",
    )
    parser.add_argument("--out", default=None, help="Markdown plan path.")
    parser.add_argument("--json", dest="json_out", default=None, help="JSON plan path.")
    parser.add_argument(
        "--strict-license",
        action="store_true",
        help="Return exit code 2 when source licensing needs manual review.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.out and not args.json_out:
        parser.error("provide --out and/or --json")

    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    if not source.is_dir():
        parser.error(f"source is not a directory: {source}")
    if not target.is_dir():
        parser.error(f"target is not a directory: {target}")

    try:
        plan = generate_capability_fusion_plan(
            source,
            target,
            project_url=args.project_url,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.out:
        path = write_markdown(args.out, plan)
        print(f"Markdown plan: {path}")
    if args.json_out:
        path = write_json(args.json_out, plan)
        print(f"JSON plan: {path}")

    summary = plan["summary"]
    print(
        "Capability fusion: "
        f"{summary['recognized_source_capabilities']} source capabilities, "
        f"{summary['gaps']} gaps, {summary['overlaps']} overlaps."
    )
    print(f"License gate: {plan['source']['license']['gate']}")

    if args.strict_license and plan["source"]["license"].get("legal_review_required"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
