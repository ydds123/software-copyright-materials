#!/usr/bin/env python3
"""Shared helpers for the software copyright materials skill."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "coverage",
    "target",
    "vendor",
    "软件著作权申请资料",
    "software-copyright-materials",
}

CODE_EXTS = {
    ".vue",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".svelte",
    ".astro",
    ".json",
    ".md",
}

KNOWN_CONFIG_FILES = {
    ".babelrc",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.yaml",
    ".eslintrc.yml",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yaml",
    ".prettierrc.yml",
    ".swcrc",
    "angular.json",
    "app.json",
    "astro.config.mjs",
    "astro.config.ts",
    "babel.config.js",
    "babel.config.json",
    "Cargo.lock",
    "Cargo.toml",
    "composer.json",
    "docker-compose.yaml",
    "docker-compose.yml",
    "eslint.config.cjs",
    "eslint.config.js",
    "eslint.config.mjs",
    "go.mod",
    "go.sum",
    "jsconfig.json",
    "lerna.json",
    "manifest.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "nuxt.config.js",
    "nuxt.config.ts",
    "nx.json",
    "package-lock.json",
    "package.json",
    "playwright.config.js",
    "playwright.config.ts",
    "postcss.config.cjs",
    "postcss.config.js",
    "prettier.config.cjs",
    "prettier.config.js",
    "prettier.config.mjs",
    "project.json",
    "pyproject.toml",
    "rollup.config.js",
    "rollup.config.mjs",
    "rollup.config.ts",
    "svelte.config.js",
    "stylelintrc.json",
    "tailwind.config.js",
    "tailwind.config.ts",
    "tsconfig.app.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "tslint.json",
    "turbo.json",
    "vite.config.js",
    "vite.config.mjs",
    "vite.config.ts",
    "vitest.config.js",
    "vitest.config.ts",
    "webpack.config.js",
    "webpack.config.ts",
    "workspace.json",
}

FRONTEND_EXTS = {
    ".vue",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".svelte",
    ".astro",
}

SUPPLEMENT_CODE_EXTS = {
    ".py",
    ".java",
    ".go",
    ".rs",
    ".cs",
    ".php",
    ".rb",
    ".kt",
    ".swift",
    ".sql",
    ".sh",
    ".json",
}

COPYRIGHT_CODE_EXTS = FRONTEND_EXTS | SUPPLEMENT_CODE_EXTS

LOCK_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "bun.lock",
}


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    name = path.name
    if name.startswith(".") and name not in {".env.example"}:
        return True
    if name in LOCK_FILES:
        return True
    if name.endswith(".map") or name.endswith(".min.js") or name.endswith(".min.css"):
        return True
    return False


def iter_project_files(project: Path, exts: set[str] | None = None) -> Iterable[Path]:
    project = project.resolve()
    for root, dirs, files in os.walk(project):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not is_excluded(root_path / d)]
        for filename in files:
            path = root_path / filename
            if is_excluded(path):
                continue
            if exts is not None and path.suffix.lower() not in exts:
                continue
            yield path


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_bytes()
    if limit is not None:
        data = data[:limit]
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def count_text_lines(path: Path, skip_blank: bool = True) -> int:
    try:
        text = read_text(path)
    except Exception:
        return 0
    if not text:
        return 0
    if skip_blank:
        return sum(1 for line in text.splitlines() if line.strip())
    return len(text.splitlines())


def is_known_config_file(path: Path) -> bool:
    """Return True for well-known config files that shouldn't count as source code."""
    return path.name in KNOWN_CONFIG_FILES


def looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except Exception:
        return True
    return b"\x00" in chunk


def normalize_title(value: str) -> str:
    value = re.sub(r"[-_]+", " ", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value or "待命名软件"


def safe_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value).strip()
    return value or "软件"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── Task-path auto-resolution ──

# OUTPUT_NAME is kept for backward compatibility (existing projects may still
# use the old nesting pattern) but new tasks place everything directly under
# the year-prefixed task directory.
OUTPUT_NAME = "软件著作权申请资料"
YEAR_WORKSPACE_PREFIX = "{}年软件著作权申请资料"
TASK_FILE = "任务登记.json"
DRAFT_DIR = "草稿"
FINAL_DIR = "正式资料"
SCREENSHOT_DIR = "截图"
ANALYSIS_DIR = "analysis"
GATE_FILE = "门禁状态.json"


def year_workspace_name(year: int | None = None) -> str:
    """Return the year-prefixed workspace folder name."""
    from datetime import datetime
    y = year if year else datetime.now().year
    return YEAR_WORKSPACE_PREFIX.format(y)


def proposed_task_path(project_root: Path, software_name: str, year: int | None = None) -> Path:
    """Compute the suggested task directory for a new soft copyright application.

    Returns ``<project_root>/<year>年软件著作权申请资料/<software_name>/``.
    Does NOT create anything on disk.
    """
    return project_root / year_workspace_name(year) / software_name


def existing_task_paths(project_root: Path) -> list[Path]:
    """Find existing task directories under year-prefixed workspaces in *project_root*."""
    tasks: list[Path] = []
    if not project_root.is_dir():
        return tasks
    for entry in sorted(project_root.iterdir()):
        if not entry.is_dir():
            continue
        if not entry.name.endswith("年软件著作权申请资料"):
            continue
        for child in sorted(entry.iterdir()):
            if child.is_dir() and (child / TASK_FILE).exists():
                tasks.append(child)
    return tasks


def resolve_task_dir(start: Path | str | None = None) -> Path:
    """Find the task directory by walking up from *start* (or cwd).

    A task directory is identified by the presence of ``任务登记.json``
    and ``门禁状态.json`` or the legacy ``软件著作权申请资料/`` subdirectory.
    Returns the task root directory itself.
    """
    here = Path(start).resolve() if start else Path.cwd()
    for ancestor in [here] + list(here.parents):
        # New-style: 门禁状态.json or 任务登记.json in the task dir itself
        if (ancestor / GATE_FILE).exists() or (ancestor / TASK_FILE).exists():
            # Verify it's a task dir by checking for expected subdirs
            if (ancestor / DRAFT_DIR).is_dir() or (ancestor / ANALYSIS_DIR).is_dir():
                return ancestor
        # Legacy: 软件著作权申请资料/ inside task root
        if (ancestor / OUTPUT_NAME).is_dir():
            return ancestor
        # Legacy: cwd IS the 软件著作权申请资料/ dir
        if ancestor.name == OUTPUT_NAME:
            return ancestor.parent
    return None


def resolve_workdir(task_dir: Path | str | None = None) -> Path:
    """Return the task workdir.

    For new-style tasks this is the task directory itself (all subdirs sit
    directly under it).  For legacy tasks with ``软件著作权申请资料/`` nesting,
    the inner directory is returned.
    """
    if task_dir is None:
        task_dir = resolve_task_dir()
    if task_dir is None:
        raise SystemExit(
            "找不到任务目录。请用 --task-dir 指定，或在任务目录下运行。\n"
            "示例: --task-dir \"E:/HSE/2026年软件著作权申请资料/化桉智能巡检数字化系统\""
        )
    td = Path(task_dir)
    # New-style: subdirs (草稿/, analysis/) are in the task dir itself
    if (td / DRAFT_DIR).is_dir() or (td / ANALYSIS_DIR).is_dir():
        return td
    # Legacy: subdirs are one level deeper inside 软件著作权申请资料/
    if (td / OUTPUT_NAME).is_dir():
        return td / OUTPUT_NAME
    # Legacy: cwd IS the old workdir
    if td.name == OUTPUT_NAME:
        return td
    # Not yet created — assume new-style
    return td


def resolve_draft_dir(task_dir: Path | str | None = None) -> Path:
    return ensure_dir(resolve_workdir(task_dir) / DRAFT_DIR)


def resolve_final_dir(task_dir: Path | str | None = None) -> Path:
    return ensure_dir(resolve_workdir(task_dir) / FINAL_DIR)


def resolve_screenshot_dir(task_dir: Path | str | None = None) -> Path:
    return ensure_dir(resolve_workdir(task_dir) / SCREENSHOT_DIR)


def resolve_analysis_dir(task_dir: Path | str | None = None) -> Path:
    return ensure_dir(resolve_workdir(task_dir) / ANALYSIS_DIR)


# ── User-confirmation guard ──

def confirm_params(inferred: dict[str, str], confirm: bool = False) -> None:
    """Print inferred parameters for user visibility.

    This function no longer blocks — confirmation is now managed exclusively
    by confirm_stage.py and gate_check.py.  The ``--confirm`` flag is kept
    in individual argparsers for backward compatibility but is ignored by
    this function.
    """
    lines = ["已预判以下参数：", ""]
    for label, value in inferred.items():
        lines.append(f"  {label}: {value}")
    print("\n".join(lines))
