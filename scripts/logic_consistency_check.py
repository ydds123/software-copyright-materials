#!/usr/bin/env python3
"""Logic consistency gate (1a.3).

Targets the exact defect classes from the correction notice:
  - 编号跳跃（6.8 之后直接 6.10；步骤编号从 4 开始）
  - 数量矛盾（说 6 种策略只列 4 条）
  - 枚举/维度取值重复（X 轴与 Z 轴取值相同）
  - 事实断言表驱动的一致性核对（来自材料证据计划）

Inputs:
  --manual  草稿/操作手册.md
  --plan    草稿/材料证据计划.json (fact_assertions, optional)

Exit codes: 0 pass / 1 consistency failure / 2 invalid input
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import read_json, read_text

SECTION_RE = re.compile(r"^#{2,4}\s*(\d+(?:\.\d+)*)\s+")
STEP_ROW_RE = re.compile(r"^\s*\|\s*(\d+)\s*\|")
COUNT_CLAIM_RE = re.compile(r"(\d+)\s*种")
LIST_CLAIM_RE = re.compile(r"(\d+)\s*条")


def check_section_numbering(lines: list[str]) -> list[str]:
    """Detect skipped section numbers and non-1 starts per level."""
    errors: list[str] = []
    level_seqs: dict[str, list[tuple[int, list[int]]]] = {}
    for lineno, line in enumerate(lines, start=1):
        m = SECTION_RE.match(line.strip())
        if not m:
            continue
        parts = [int(x) for x in m.group(1).split(".")]
        level = len(parts)
        parent = ".".join(str(x) for x in parts[:-1]) or "root"
        seq_list = level_seqs.setdefault(f"{level}:{parent}", [])
        seq_list.append((lineno, parts))
    for key, seqs in sorted(level_seqs.items()):
        if len(seqs) < 2:
            continue
        # top-level sequences must start at 1
        top = seqs[0][1]
        if top[-1] != 1:
            errors.append(
                f"章节编号未从 1 开始（{key}，首个编号 {'.'.join(map(str, top))}，行 {seqs[0][0]}）"
            )
        for (l1, a), (l2, b) in zip(seqs, seqs[1:]):
            if b[-1] != a[-1] + 1:
                errors.append(
                    f"章节编号跳跃：{'.'.join(map(str, a))}（行 {l1}）之后是 "
                    f"{'.'.join(map(str, b))}（行 {l2}）"
                )
    return errors


def check_step_numbering(lines: list[str]) -> list[str]:
    """Detect step tables whose first column does not start at 1 or skips."""
    errors: list[str] = []
    current_table: list[tuple[int, int]] = []
    table_start = 0
    for lineno, line in enumerate(lines, start=1):
        m = STEP_ROW_RE.match(line.strip())
        if m:
            if not current_table:
                table_start = lineno
            current_table.append((lineno, int(m.group(1))))
        else:
            if current_table:
                errors.extend(_check_step_seq(current_table, table_start))
            current_table = []
            table_start = 0
    if current_table:
        errors.extend(_check_step_seq(current_table, table_start))
    return errors


def _check_step_seq(seq: list[tuple[int, int]], table_start: int) -> list[str]:
    errors: list[str] = []
    values = [v for _, v in seq]
    if len(values) < 2:
        return errors
    if values[0] != 1:
        errors.append(f"操作步骤编号从 {values[0]} 开始（应 1 开始，表格起于行 {table_start}）")
    for (l1, a), (l2, b) in zip(seq, seq[1:]):
        if b != a + 1:
            errors.append(f"操作步骤编号跳跃：{a}（行 {l1}）之后是 {b}（行 {l2}）")
    return errors


def check_count_claims(text: str) -> list[str]:
    """Detect 'N 种' claims conflicting with 'M 条' listings in the same
    sentence/paragraph window."""
    errors: list[str] = []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paras:
        counts = [int(x) for x in COUNT_CLAIM_RE.findall(para)]
        lists = [int(x) for x in LIST_CLAIM_RE.findall(para)]
        for n in counts:
            for m in lists:
                if n != m and (n > 0 and m > 0):
                    errors.append(f"数量矛盾：段落中声称 {n} 种，但列出 {m} 条 → {para[:80]}")
    return errors


def check_fact_assertions(text: str, plan: dict[str, Any] | None) -> list[str]:
    """Verify fact_assertions of type count/enum against the document."""
    errors: list[str] = []
    if not plan:
        return errors
    for t in plan.get("fact_assertions") or []:
        if not isinstance(t, dict) or t.get("status") != "confirmed":
            continue
        subject = t.get("subject", "")
        value = t.get("value")
        ftype = t.get("type")
        if ftype == "count" and isinstance(value, int) and subject:
            # find subject mentions
            mentions = [m.start() for m in re.finditer(re.escape(subject), text)]
            if not mentions:
                errors.append(f"事实断言 {t.get('fact_id')}：文档中找不到主题 '{subject}'")
                continue
            for pos in mentions[:5]:
                window = text[pos : pos + 300]
                nums = [int(x) for x in re.findall(r"(\d+)", window)]
                if nums and abs(nums[0] - value) > 0 and value not in nums:
                    errors.append(
                        f"事实断言 {t.get('fact_id')}：'{subject}' 应出现 {value}，"
                        f"文档上下文数字为 {nums[:5]}"
                    )
    return errors


def check_enum_overlap(plan: dict[str, Any] | None) -> list[str]:
    """Detect identical value sets across distinct enum/range assertions
    (XYZ 轴取值相同类缺陷) — requires values as lists in the plan."""
    errors: list[str] = []
    if not plan:
        return errors
    seen: dict[str, str] = {}
    for t in plan.get("fact_assertions") or []:
        if not isinstance(t, dict):
            continue
        ftype = t.get("type")
        value = t.get("value")
        if ftype in ("enum", "range") and isinstance(value, list):
            key = "\u0000".join(sorted(str(v) for v in value))
            if key in seen:
                errors.append(
                    f"枚举取值重复：{t.get('fact_id')}({t.get('subject')}) 与 "
                    f"{seen[key]} 的取值集合完全相同"
                )
            else:
                seen[key] = t.get("fact_id")
    return errors


def run(manual_path: Path, plan: dict[str, Any] | None) -> dict[str, Any]:
    text = read_text(manual_path)
    lines = text.splitlines()
    errors: list[str] = []
    errors.extend(check_section_numbering(lines))
    errors.extend(check_step_numbering(lines))
    errors.extend(check_count_claims(text))
    errors.extend(check_fact_assertions(text, plan))
    errors.extend(check_enum_overlap(plan))
    # dedupe, keep order
    errors = list(dict.fromkeys(errors))
    return {
        "status": "pass" if not errors else "blocked",
        "errors": errors,
        "manual": str(manual_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", required=True, help="Path to 草稿/操作手册.md")
    parser.add_argument("--plan", help="Path to 材料证据计划.json (fact_assertions)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manual_path = Path(args.manual)
    if not manual_path.exists():
        print(f"LOGIC CONSISTENCY INVALID: 缺少 {manual_path}")
        sys.exit(2)

    plan = None
    if args.plan:
        plan_path = Path(args.plan)
        if plan_path.exists():
            try:
                plan = read_json(plan_path)
            except Exception:
                plan = None

    report = run(manual_path, plan)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"LOGIC CONSISTENCY {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
