#!/usr/bin/env python3
"""Validate the material evidence plan (1a.1 gate layer).

Hard rules (exit 1 on failure):
  R1 计划文件必须存在且 schema_version == 3
  R2 每个核心功能 (importance=core) 必须至少映射一项 selected 且非 D 级
     的代码证据（核心功能代码证据映射完整率 100%）
  R3 A/B 级证据总数必须 > 0（完全没有高价值证据则阻断）
  R4 署名三分法：framework 类别文件若被选中且 resolution=replace → 阻断
      （情况一禁止改署名）
  R5 选中文件必须存在且 sha256 与计划记录一致（防止计划外改动）

Warnings (exit 0):
  W1 D 级选中占比过高（> 50%）
  W2 存在 ai_tool 署名文件被选中且未填写 resolution
  W3 存在未确认来源 (source_kind=unknown) 的选中文件

Exit codes: 0 pass / 1 quality failure / 2 invalid input
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from common import read_json, resolve_draft_dir, write_json

PLAN_FILE_NAME = "材料证据计划.json"
REVIEW_REPORT_FILE = "独创性代表性审查报告.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_root_path(plan: dict[str, Any], root_id: str) -> Path | None:
    for root in plan.get("input_roots") or []:
        if root.get("root_id") == root_id:
            return Path(root["path"])
    return None


def check_plan(plan_path: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return (errors, warnings, report)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_path.exists():
        return [f"缺少 {plan_path}"], [], {}

    plan = read_json(plan_path)
    if plan.get("schema_version") != 3:
        return [f"schema_version 必须为 3，当前 {plan.get('schema_version')}"], [], {}

    features = plan.get("features") or []
    evidence = plan.get("code_evidence") or []
    ev_by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    selected = [e for e in evidence if isinstance(e, dict) and e.get("selected")]

    # R2: core features must map to a selected, non-D evidence
    core_features = [f for f in features if isinstance(f, dict) and f.get("importance") == "core"]
    if not core_features:
        warnings.append("W-002: 没有 importance=core 的功能；所有功能均为 supporting，跳过核心映射检查")
    for f in core_features:
        mapped = f.get("code_evidence") or []
        valid = []
        for ev_id in mapped:
            ev = ev_by_id.get(ev_id)
            if not ev:
                continue
            if ev.get("selected") and ev.get("grade") not in ("D", ""):
                valid.append(ev_id)
        if not valid:
            errors.append(
                f"R2: 核心功能 '{f.get('name', f.get('feature_id'))}' ({f.get('feature_id')}) "
                f"没有 selected 且非 D 级的代码证据"
            )

    # R3: at least one A/B evidence overall
    ab_count = sum(1 for e in selected if e.get("grade") in ("A", "B"))
    if ab_count == 0:
        errors.append("R3: 选中代码证据中没有任何 A/B 级文件")

    # R4: framework authorship must never be replace'd
    for e in selected:
        auth = e.get("author_declaration") or {}
        if auth.get("resolution") == "replace":
            for cat in auth.get("categories") or []:
                if cat.get("category") == "framework":
                    errors.append(
                        f"R4: 文件 {e.get('root_id')}/{e.get('path')} 命中框架署名 "
                        f"({cat.get('author')})，禁止 resolution=replace（情况一）。"
                        f"请移出材料或人工核实权属。"
                    )

    # R5: selected files exist and hash matches
    for e in selected:
        root = resolve_root_path(plan, e.get("root_id", "primary"))
        if root is None:
            errors.append(f"R5: 文件 {e.get('path')} 的输入根 {e.get('root_id')} 不存在")
            continue
        fpath = root / e.get("path", "")
        if not fpath.exists():
            errors.append(f"R5: 选中文件不存在: {e.get('path')}")
            continue
        if sha256_of(fpath) != e.get("sha256"):
            errors.append(f"R5: 文件哈希与计划不一致（文件已被修改）: {e.get('path')}")

    # W1: D ratio among selected
    if selected:
        d_count = sum(1 for e in selected if e.get("grade") == "D")
        ratio = d_count / len(selected)
        if ratio > 0.5:
            warnings.append(f"W-001: D 级选中占比 {ratio:.0%}，超过 50% 建议上限")

    # W2: ai_tool authorship selected without resolution
    for e in selected:
        auth = e.get("author_declaration") or {}
        has_ai = any(c.get("category") == "ai_tool" for c in auth.get("categories") or [])
        if has_ai and not auth.get("resolution"):
            warnings.append(f"W-002: AI 工具署名文件被选中但未填写 resolution: {e.get('path')}")

    # W3: unknown source_kind among selected
    unknown = [e.get("path") for e in selected if e.get("source_kind") in ("unknown", "")]
    if unknown:
        warnings.append(f"W-003: {len(unknown)} 个选中文件 source_kind 未确认（unknown）")

    report = {
        "schema_version": 3,
        "status": "pass" if not errors else "blocked",
        "core_feature_count": len(core_features),
        "selected_evidence_count": len(selected),
        "ab_evidence_count": ab_count,
        "errors": errors,
        "warnings": warnings,
        "plan_sha256": sha256_of(plan_path),
    }
    # Persist the review report (single source of truth, plan §5.1)
    try:
        write_json(plan_path.parent / REVIEW_REPORT_FILE, report)
    except Exception:
        pass
    return errors, warnings, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", help="Path to 材料证据计划.json; auto-derived if omitted")
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    args = parser.parse_args()

    plan_path = Path(args.plan) if args.plan else None
    if plan_path is None:
        draft = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)
        plan_path = draft / PLAN_FILE_NAME
    else:
        plan_path = plan_path

    if not plan_path.exists():
        if args.json:
            print(json.dumps({"status": "invalid", "errors": [f"缺少 {plan_path}"]}, ensure_ascii=False))
        else:
            print(f"EVIDENCE PLAN INVALID: 缺少 {plan_path}")
        sys.exit(2)

    try:
        errors, warnings, report = check_plan(plan_path)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "invalid", "errors": [str(exc)]}, ensure_ascii=False))
        else:
            print(f"EVIDENCE PLAN INVALID: {exc}")
        sys.exit(2)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"EVIDENCE PLAN {'PASS' if report['status'] == 'pass' else 'BLOCKED'}")
        print(f"核心功能: {report['core_feature_count']} | 选中证据: {report['selected_evidence_count']} | A/B 证据: {report['ab_evidence_count']}")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  WARNING: {w}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
