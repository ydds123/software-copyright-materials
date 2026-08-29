#!/usr/bin/env python3
"""Fact lock check (1b) — detect protected-fact drift after style revision.

Compares a document against its pre-revision snapshot (or against an
explicit protected_facts list from the evidence plan) and hard-blocks on
any change to locked facts:

  software name / version / module / menu / button / role / state /
  numbers / dates / step numbers / figure numbers / paths / URLs /
  screenshot references

Deterministic comparison only; semantic drift goes to human review.

Exit codes: 0 = no locked-fact changes / 1 = drift found / 2 = invalid
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import read_json, read_text

LOCKED_PATTERNS = [
    re.compile(r"(?:软件名称|版本号)\s*[：:]\s*(.+)"),
    re.compile(r"图\s*\d+(?:[-—]\d+)?\s*[^\n]*"),
    re.compile(r"第\s*\d+\s*页"),
    re.compile(r"【截图预留：[^】]*】"),
    re.compile(r"!\[[^\]]*\]\([^)]+\)"),
    re.compile(r"\b(?:https?://|/)[^\s|>]+"),
    re.compile(r"`[^`]+`"),
]

NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?(?:%|年|月|日|时|分|秒|人|条|种|个|次|页)?")


def extract_locked_facts(text: str) -> list[str]:
    """Deterministic extraction of lockable fact tokens."""
    facts: list[str] = []
    for pattern in LOCKED_PATTERNS:
        facts.extend(m.group(0).strip() for m in pattern.finditer(text))
    # numbers with units (strong signals)
    facts.extend(m.group(0) for m in NUMBER_TOKEN_RE.finditer(text))
    return facts


def extract_plan_facts(plan: dict[str, Any] | None) -> list[str]:
    """Locked facts declared in the material evidence plan."""
    facts: list[str] = []
    if not plan:
        return facts
    scope = plan.get("software_scope") or {}
    for key in ("name", "version"):
        value = str(scope.get(key) or "").strip()
        if value:
            facts.append(f"{key}:{value}")
    for f in plan.get("features") or []:
        if isinstance(f, dict):
            name = str(f.get("name") or "").strip()
            if name:
                facts.append(f"feature:{name}")
    for t in plan.get("fact_assertions") or []:
        if isinstance(t, dict) and t.get("status") == "confirmed":
            facts.append(
                f"fact:{t.get('subject')}={t.get('value')}"
            )
    return facts


def run(
    current_path: Path,
    snapshot_path: Path | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not current_path.exists():
        return {"status": "invalid", "errors": [f"缺少 {current_path}"]}

    current = read_text(current_path)
    if snapshot_path and snapshot_path.exists():
        before = read_text(snapshot_path)
        # deterministic comparison of extracted facts
        before_facts = set(extract_locked_facts(before))
        after_facts = set(extract_locked_facts(current))
        removed = sorted(before_facts - after_facts)
        added = sorted(after_facts - before_facts)
        plan_facts = set(extract_plan_facts(plan))
        # plan-declared facts must exist verbatim in the current doc
        missing_plan_facts = sorted(f for f in plan_facts if f.split(":", 1)[-1] not in current and f not in current)
        errors: list[str] = []
        if removed:
            errors.append(f"锁定事实消失（{len(removed)} 处）：{'; '.join(removed[:10])}")
        if added:
            errors.append(f"新增事实令牌（{len(added)} 处，疑似改写引入）：{'; '.join(added[:10])}")
        if missing_plan_facts:
            errors.append(f"计划锁定事实在文档中缺失（{len(missing_plan_facts)} 处）：{'; '.join(missing_plan_facts[:10])}")
        # raw diff stat for human review
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(), current.splitlines(), lineterm="", n=1
            )
        )
        return {
            "status": "pass" if not errors else "drift",
            "errors": errors,
            "removed_count": len(removed),
            "added_count": len(added),
            "diff_hunk_count": sum(1 for l in diff_lines if l.startswith("@@")),
            "diff_preview": "\n".join(diff_lines[:60]),
        }
    return {"status": "invalid", "errors": ["缺少快照文件，无法做事实回归比较"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", required=True, help="当前文档")
    parser.add_argument("--snapshot", help="改写前快照")
    parser.add_argument("--plan", help="材料证据计划.json（提取计划锁定事实）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = None
    if args.plan and Path(args.plan).exists():
        try:
            plan = read_json(Path(args.plan))
        except Exception:
            plan = None

    report = run(
        Path(args.manual),
        Path(args.snapshot) if args.snapshot else None,
        plan,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"FACT LOCK {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
