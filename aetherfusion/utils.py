"""Shared constants and utility functions for AetherFusion."""

import os
import json
from pathlib import Path
from typing import Any

IGNORE_DIRS: set[str] = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    "venv", ".venv", "env", ".env", ".tox",
    "target", ".next", ".nuxt", ".turbo",
    ".idea", ".vscode", ".vs",
    "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".codebuddy", ".cursor", ".workbuddy", ".marvis",
}

ENTRY_PATTERNS: list[str] = [
    "src/index.tsx", "src/index.ts", "src/index.jsx", "src/index.js",
    "src/main.tsx", "src/main.ts", "src/main.jsx", "src/main.js",
    "src/App.tsx", "src/App.ts", "src/App.jsx", "src/App.js",
    "pages/index.tsx", "pages/index.ts", "pages/index.jsx",
    "main.py", "app.py", "run.py", "manage.py",
    "src/main.py", "src/app.py", "src/__main__.py",
]

FUSIBLE_DIR_NAMES: set[str] = {
    "components", "lib", "utils", "services", "engines",
    "skills", "models", "training", "hooks", "stores",
    "pages", "layouts", "styles", "assets",
    "modules", "plugins", "middleware", "handlers",
    "helpers", "shared", "common",
}

CONFIG_FILES: dict[str, str] = {
    "package.json": "node",
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "Pipfile": "python",
    "tsconfig.json": "typescript",
    "jsconfig.json": "javascript",
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "vite.config.mjs": "vite",
    "vite.config.mts": "vite",
    "next.config.js": "nextjs",
    "next.config.ts": "nextjs",
    "next.config.mjs": "nextjs",
    "tailwind.config.js": "tailwind",
    "tailwind.config.ts": "tailwind",
    "webpack.config.js": "webpack",
    ".eslintrc.js": "eslint",
    ".eslintrc.json": "eslint",
    ".eslintrc.cjs": "eslint",
    "eslint.config.js": "eslint",
    "eslint.config.mjs": "eslint",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
}


def safe_read_json(path: Path) -> dict[str, Any] | None:
    """Safely read and parse a JSON file. Returns None on failure."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def safe_read_text(path: Path) -> str | None:
    """Safely read a text file. Returns None on failure."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError:
        return None


def normalize_path_for_report(path: str | Path) -> str:
    """Normalize Windows and host-native separators for stable reports."""
    return str(path).replace("\\", "/").replace(os.sep, "/")


def is_symlink(path: Path) -> bool:
    """Check if a path is a symbolic link (safe wrapper)."""
    try:
        return path.is_symlink()
    except OSError:
        return False
