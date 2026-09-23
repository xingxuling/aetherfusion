"""Static capability extraction from a local software project."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from .catalog import CAPABILITY_SIGNATURES, CANONICAL_LAYER_LABELS, CapabilitySignature
from .license_gate import assess_license


IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "coverage", ".next", ".nuxt",
    "__pycache__", ".venv", "venv", "target", ".idea", ".vscode",
}
TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rs",
    ".go", ".java", ".kt", ".kts", ".swift", ".c", ".cc", ".cpp", ".h",
    ".hpp", ".md", ".rst", ".txt", ".json", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".gradle", ".xml", ".sh", ".ps1", ".bat",
}
DEPENDENCY_FILES = ("package.json", "pyproject.toml", "requirements.txt", "Cargo.toml")


@dataclass(frozen=True)
class CapabilityCandidate:
    capability_id: str
    display_name: str
    score: int
    canonical_layer: str
    canonical_layer_zh: str
    role: str
    default_strategy: str
    evidence: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["evidence"] = list(self.evidence)
        return data


@dataclass(frozen=True)
class ProjectCapabilityProfile:
    root: str
    name: str
    files_scanned: int
    bytes_scanned: int
    languages: tuple[str, ...]
    dependency_tokens: tuple[str, ...]
    license: dict
    capabilities: tuple[CapabilityCandidate, ...]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "name": self.name,
            "files_scanned": self.files_scanned,
            "bytes_scanned": self.bytes_scanned,
            "languages": list(self.languages),
            "dependency_tokens": list(self.dependency_tokens),
            "license": self.license,
            "capabilities": [c.to_dict() for c in self.capabilities],
        }


def _iter_text_files(root: Path, max_files: int = 1800) -> Iterable[Path]:
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= max_files:
            return
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts[:-1]
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in DEPENDENCY_FILES:
            continue
        try:
            if path.stat().st_size > 384_000:
                continue
        except OSError:
            continue
        count += 1
        yield path


def _dependency_tokens(root: Path) -> set[str]:
    tokens: set[str] = set()
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                value = data.get(section, {})
                if isinstance(value, dict):
                    tokens.update(str(k).lower() for k in value)
        except (OSError, json.JSONDecodeError):
            pass
    for name in ("requirements.txt", "pyproject.toml", "Cargo.toml"):
        path = root / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for raw in text.replace("=", " ").replace('"', " ").replace("'", " ").split():
                token = raw.strip("[](),{}<>:;~! ")
                if token and len(token) <= 80:
                    tokens.add(token)
    return tokens


def _language_from_suffix(suffix: str) -> str | None:
    return {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript", ".rs": "rust",
        ".go": "go", ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
        ".swift": "swift", ".c": "c", ".cc": "cpp", ".cpp": "cpp",
    }.get(suffix.lower())


def _match_signature(
    signature: CapabilitySignature,
    files: list[tuple[Path, str]],
    deps: set[str],
    root: Path,
) -> CapabilityCandidate | None:
    score = 0
    evidence: list[str] = []
    dep_hits = sorted({d for d in deps for term in signature.dependency_terms if term in d})
    if dep_hits:
        score += min(25, 10 + 5 * len(dep_hits))
        evidence.append("dependencies: " + ", ".join(dep_hits[:6]))

    path_hit_count = 0
    content_hit_count = 0
    for path, text in files:
        rel = str(path.relative_to(root)).replace("\\", "/").lower()
        local_path_hits = [term for term in signature.path_terms if term in rel]
        local_content_hits = [term for term in signature.content_terms if term in text]
        if local_path_hits:
            path_hit_count += len(local_path_hits)
            if len(evidence) < 12:
                evidence.append(f"path:{rel} -> {', '.join(local_path_hits[:3])}")
        if local_content_hits:
            content_hit_count += len(local_content_hits)
            if len(evidence) < 12:
                evidence.append(f"content:{rel} -> {', '.join(local_content_hits[:3])}")

    score += min(35, path_hit_count * 5)
    score += min(50, content_hit_count * 4)
    score = min(100, score)
    if score < 18:
        return None
    return CapabilityCandidate(
        capability_id=signature.capability_id,
        display_name=signature.display_name,
        score=score,
        canonical_layer=signature.canonical_layer,
        canonical_layer_zh=CANONICAL_LAYER_LABELS.get(signature.canonical_layer, signature.canonical_layer),
        role=signature.role,
        default_strategy=signature.default_strategy,
        evidence=tuple(evidence),
        rationale=signature.rationale,
    )


def analyze_project_capabilities(project_root: str | Path) -> ProjectCapabilityProfile:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root}")

    files: list[tuple[Path, str]] = []
    languages: set[str] = set()
    bytes_scanned = 0
    for path in _iter_text_files(root):
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lowered = raw.lower()
        files.append((path, lowered))
        bytes_scanned += len(raw.encode("utf-8", errors="ignore"))
        lang = _language_from_suffix(path.suffix)
        if lang:
            languages.add(lang)

    deps = _dependency_tokens(root)
    capabilities = [
        candidate
        for signature in CAPABILITY_SIGNATURES
        if (candidate := _match_signature(signature, files, deps, root)) is not None
    ]
    capabilities.sort(key=lambda c: (-c.score, c.capability_id))
    license_assessment = assess_license(root).to_dict()
    return ProjectCapabilityProfile(
        root=str(root),
        name=root.name,
        files_scanned=len(files),
        bytes_scanned=bytes_scanned,
        languages=tuple(sorted(languages)),
        dependency_tokens=tuple(sorted(deps)[:200]),
        license=license_assessment,
        capabilities=tuple(capabilities),
    )
