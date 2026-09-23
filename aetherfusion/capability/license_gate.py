"""Conservative, heuristic license gate for capability fusion plans.

This is a planning aid, not legal advice. It never authorizes copying by
itself; it records a machine-readable gate that downstream users can review.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path


LICENSE_NAMES = (
    "LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt",
)


@dataclass(frozen=True)
class LicenseAssessment:
    detected: str
    category: str
    gate: str
    source_file: str | None
    evidence: str
    notice_required: bool
    legal_review_required: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _classify(text: str) -> tuple[str, str, str, bool, bool, str]:
    normalized = " ".join(text.lower().split())
    if "apache license" in normalized and "version 2.0" in normalized:
        return ("Apache-2.0", "permissive", "allowed_with_notice", True, False,
                "Apache License 2.0 markers detected.")
    if "mit license" in normalized or "permission is hereby granted, free of charge" in normalized:
        return ("MIT", "permissive", "allowed_with_notice", True, False,
                "MIT-style permission grant detected.")
    if "redistribution and use in source and binary forms" in normalized:
        return ("BSD-like", "permissive", "allowed_with_notice", True, False,
                "BSD-style redistribution clause detected.")
    if "mozilla public license" in normalized and "2.0" in normalized:
        return ("MPL-2.0", "weak-copyleft", "review_required", True, True,
                "Mozilla Public License 2.0 markers detected.")
    if "gnu affero general public license" in normalized:
        return ("AGPL", "strong-copyleft", "boundary_required", True, True,
                "AGPL markers detected; copying/integration boundaries require review.")
    if "gnu general public license" in normalized:
        return ("GPL", "strong-copyleft", "boundary_required", True, True,
                "GPL markers detected; copying/integration boundaries require review.")
    return ("UNKNOWN", "unknown", "review_required", False, True,
            "No supported license fingerprint matched.")


def assess_license(project_root: str | Path) -> LicenseAssessment:
    root = Path(project_root).resolve()
    for name in LICENSE_NAMES:
        candidate = root / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")[:120_000]
            except OSError:
                continue
            detected, category, gate, notice, review, evidence = _classify(text)
            return LicenseAssessment(
                detected=detected,
                category=category,
                gate=gate,
                source_file=str(candidate),
                evidence=evidence,
                notice_required=notice,
                legal_review_required=review,
            )
    return LicenseAssessment(
        detected="UNKNOWN",
        category="unknown",
        gate="review_required",
        source_file=None,
        evidence="No license file was found at the project root.",
        notice_required=False,
        legal_review_required=True,
    )
