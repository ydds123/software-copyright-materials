#!/usr/bin/env python3
"""human-writing adapter for technical documents (1b).

Runs the human-writing check_prose.py in *technical-document restricted
mode*: strip non-prose regions (headings, tables, code blocks, machine
fields, image references, legal fields) before checking, then remap the
human-writing failures into soft-copyright-relevant warnings.

Guarantees:
  - never mutates the document
  - reports the human-writing skill version used
  - outputs "模型化文风风险" only — never an "AI detection" verdict

Exit codes: 0 = no hard style failures / 1 = hard style failures found
(warnings only do not fail) / 2 = invalid input or missing dependency
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import read_text

# human-writing skill location: env var override, then the shared
# cross-harness skills directory (~/.agents/skills).
HUMAN_WRITING_SKILL = (
    Path(os.environ["HUMAN_WRITING_SKILL_DIR"])
    if os.environ.get("HUMAN_WRITING_SKILL_DIR")
    else Path.home() / ".agents" / "skills" / "human-writing"
)
CHECKER = HUMAN_WRITING_SKILL / "scripts" / "check_prose.py"

# Regions stripped before checking (technical-document restricted mode)
STRIP_PATTERNS = [
    (re.compile(r"^#{1,6}\s+.*$", re.M), "heading"),                    # headings
    (re.compile(r"^\|.*\|$", re.M), "table-row"),                       # tables
    (re.compile(r"```.*?```", re.S), "code-block"),                     # code
    (re.compile(r"!\[[^\]]*\]\([^)]+\)", re.S), "image-ref"),           # images
    (re.compile(r"【截图预留：[^】]*】", re.S), "screenshot-placeholder"),  # placeholders
    (re.compile(r"^[-*]\s+\[[ xX]\]\s+.*$", re.M), "checklist"),        # checklists
    (re.compile(r"[A-Za-z0-9_./:-]{6,}"), None),                        # machine fields
]


def strip_non_prose(text: str) -> str:
    """Return only narrative prose for style checking."""
    out = text
    for pattern, _label in STRIP_PATTERNS:
        out = pattern.sub("", out)
    # drop empty lines left behind
    return "\n".join(line for line in out.splitlines() if line.strip())


def read_skill_version() -> str:
    version_file = HUMAN_WRITING_SKILL / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def run_checker(prose_path: Path) -> tuple[int, str, str]:
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(prose_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def run(manual_path: Path, workdir: Path | None = None) -> dict[str, Any]:
    if not manual_path.exists():
        return {"status": "invalid", "errors": [f"缺少 {manual_path}"]}
    if not CHECKER.exists():
        return {
            "status": "dependency-missing",
            "errors": [],
            "warnings": [
                f"human-writing 检查器不存在: {CHECKER}\n"
                "文风检查未执行（不静默放行，由人工决定）。\n"
                "安装方式（二选一）：\n"
                "  1. python3 <skill>/scripts/install_dependencies.py --install\n"
                "  2. git clone https://github.com/KKKKhazix/human-writing "
                "~/.agents/skills/human-writing\n"
                "或设置环境变量 HUMAN_WRITING_SKILL_DIR 指向已安装位置。"
            ],
            "human_writing_version": "missing",
        }

    text = read_text(manual_path)
    prose = strip_non_prose(text)
    stripped_chars = len(text) - len(prose)
    tmp = workdir or manual_path.parent
    prose_path = tmp / ".prose-only-check.tmp.md"
    prose_path.write_text(prose, encoding="utf-8")

    code, stdout, stderr = run_checker(prose_path)
    try:
        prose_path.unlink()
    except OSError:
        pass

    report = {
        "status": "pass" if code == 0 else ("hard-failures" if code == 1 else "invalid"),
        "human_writing_version": read_skill_version(),
        "checker_exit": code,
        "stripped_chars": stripped_chars,
        "prose_chars": len(prose),
        "checker_output": (stdout + stderr).strip()[:3000],
        "errors": [],
        "warnings": [],
    }
    if code == 1:
        report["errors"].append(
            "叙述正文存在文风硬失败（见 checker_output）。请人工修订后重跑；"
            "注意：本项只报告模型化文风风险，不构成 AI 判定。"
        )
    elif code == 2:
        report["errors"].append(f"human-writing 检查器输入无效: {stderr.strip()[:300]}")
    if stripped_chars > 0:
        report["warnings"].append(
            f"已屏蔽 {stripped_chars} 字符非叙述内容（标题/表格/代码/图注/机器字段），仅检查叙述正文"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", required=True, help="Path to 操作手册.md")
    parser.add_argument("--workdir", help="Task workdir (for temp file placement)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run(Path(args.manual), Path(args.workdir) if args.workdir else None)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"HUMAN-WRITING STYLE CHECK {report['status'].upper()} "
              f"(human-writing v{report['human_writing_version']})")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
    if report["status"] == "invalid" or report["status"] == "dependency-missing":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
