#!/usr/bin/env python3
"""Shared constants and helpers for evidence planning (1a.1).

Ownership label libraries and code-grade signals derived from the
real correction feedback (补正报告) and dry-run findings.
"""

from __future__ import annotations
SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "shared helpers for propose_evidence_plan/evidence_plan_check; no CLI surface"

import re
from pathlib import Path
from typing import Any

# ── Ownership label libraries ──────────────────────────────────────────
# Category semantics (署名三分法 v0.5.1):
#   framework  -> 情况一：第三方/框架生成代码，禁止 replace，建议 exclude
#   ai_tool    -> 默认情况三：归属不明，移出材料；用户声明自研后可按情况二
#   team_member-> 用户声明后正常采信（不在此库，由计划 team_members 提供）

FRAMEWORK_AUTHORS = [
    "lion",  # Lion Li（RuoYi 等框架默认署名）
    "ruoyi",
    "若依",
]

AI_TOOL_AUTHORS = [
    "claude",
    "cursor",
    "copilot",
    "codex",
    "gemini",
    "chatgpt",
    "gpt",
]

AUTHOR_TAG_RE = re.compile(r"@author\s+([^\s*\n]+)")


def classify_author(author: str) -> str | None:
    """Return 'framework' | 'ai_tool' | None for a raw @author value.

    A raw tag like ``Lion`` (extracted token) is matched against library
    entries; the check is bidirectional (token starts library entry or
    library entry starts token) because ``@author Lion Li`` extracts only
    the first token.
    """
    value = author.strip().lower()
    if not value:
        return None
    for entry in FRAMEWORK_AUTHORS:
        if value.startswith(entry) or entry.startswith(value):
            return "framework"
    for entry in AI_TOOL_AUTHORS:
        if value.startswith(entry) or entry.startswith(value):
            return "ai_tool"
    return None


# ── Grade signal heuristics (first version, signal-based) ──────────────
# These are hints for human review, NOT automatic grading. Hard rules live
# in evidence_plan_check.py.

CRUD_METHODS = {"list", "export", "getinfo", "add", "edit", "remove"}

HIGH_VALUE_MARKERS = [
    "handler",
    "factory",
    "strategy",
    "@scheduled",
    "cron",
    "statemachine",
    "state machine",
    "责任链",
    "状态机",
]

BOILERPLATE_MARKERS = [
    "controller",
    "pure_api_wrapper",
    "pure_pojo",
    "crud_six_piece",
]


def scan_author_tags(text: str) -> list[str]:
    return [m.group(1).strip() for m in AUTHOR_TAG_RE.finditer(text)]


def crud_method_hits(text: str) -> list[str]:
    """Detect the standard generated CRUD six-piece endpoint set."""
    names: set[str] = set()
    for m in re.finditer(r"public\s+[\w<>\[\],\s]+\s+(\w+)\s*\(", text):
        names.add(m.group(1).lower())
    return sorted(CRUD_METHODS & names)


def is_crud_six_piece(text: str) -> bool:
    hits = crud_method_hits(text)
    mappings = len(re.findall(r"@(?:Get|Post|Put|Delete)Mapping", text))
    return len(hits) >= 5 and mappings >= 5


def is_pure_pojo(java_text: str) -> bool:
    """Java file that only declares fields (no methods beyond accessors)."""
    if "class " not in java_text and "public class" not in java_text:
        return False
    methods = [
        m.group(1)
        for m in re.finditer(r"\b(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\(", java_text)
    ]
    return len(methods) == 0


def is_pure_api_wrapper(ts_text: str) -> bool:
    """TypeScript file where every export is a request() call wrapper."""
    exports = re.findall(r"export\s+(?:async\s+)?function\s+\w+", ts_text)
    if not exports:
        return False
    request_calls = len(re.findall(r"\brequest\s*\(", ts_text))
    return request_calls >= len(exports) and "request" in ts_text


def high_value_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for marker in HIGH_VALUE_MARKERS:
        if marker in lowered:
            hits.append(marker)
    # dynamic SQL
    if re.search(r"<if\s|</if>|<foreach", text, re.IGNORECASE):
        hits.append("dynamic_sql")
    return sorted(set(hits))


def suggest_grade(path: Path, text: str) -> tuple[str, list[str]]:
    """Return (grade_hint, signals) for one source file.

    Grades: A/B/C/D as defined in the plan; this is a hint only.
    """
    signals: list[str] = []
    name = path.name.lower()
    suffix = path.suffix.lower()

    if name.endswith("controller.java") or name.endswith("controller.ts"):
        signals.append("controller")
        if is_crud_six_piece(text):
            signals.append("crud_six_piece")
    if suffix in {".java"} and is_pure_pojo(text):
        signals.append("pure_pojo")
    if suffix in {".ts", ".js"} and is_pure_api_wrapper(text):
        signals.append("pure_api_wrapper")
    hv = high_value_hits(text)
    signals.extend(hv)

    has_boilerplate = any(
        s in signals for s in ("crud_six_piece", "pure_api_wrapper", "pure_pojo")
    )
    if hv and not has_boilerplate:
        grade = "A"
    elif has_boilerplate and hv:
        # Mixed file: generated CRUD plus real business endpoints.
        # Per the correction report these are C-grade (worth keeping for
        # their custom endpoints) — human review decides final grade.
        grade = "C"
    elif has_boilerplate:
        grade = "D"
    elif signals.count("controller"):
        grade = "C"
    else:
        grade = "B"
    return grade, signals


def file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def aggregate_roots_digest(roots: list[dict[str, str]]) -> str:
    """Aggregate hash over (root_id, relpath, file_sha256) of all code files."""
    import hashlib
    from common import COPYRIGHT_CODE_EXTS, iter_project_files, is_known_config_file

    h = hashlib.sha256()
    for root in roots:
        root_path = Path(root["path"])
        if not root_path.exists():
            continue
        rows: list[str] = []
        try:
            files = [
                p
                for p in iter_project_files(root_path, COPYRIGHT_CODE_EXTS)
                if not is_known_config_file(p)
            ]
        except Exception:
            files = []
        for p in files:
            try:
                rel = p.resolve().relative_to(root_path.resolve()).as_posix()
                rows.append(f"{root['root_id']}|{rel}|{file_sha256(p)}")
            except Exception:
                continue
        rows.sort()
        h.update(("\n".join(rows) + "\n").encode("utf-8"))
    return h.hexdigest()
