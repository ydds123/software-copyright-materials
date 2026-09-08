#!/usr/bin/env python3
"""Document plan proposer (v1.6): pick a document type per task.

Rules (manual_authoring_spec v1.5):
  - Algorithm-heavy evidence (strategy/chain/algorithm/engine/solver paths,
    or >=3 A-grade files with design signals) -> design_description
  - Operation-heavy modules (business/hybrid module types dominant) -> user_manual
  - Balanced -> hybrid
  - Same batch siblings must not share type + skeleton (checked separately).

Writes document_plan into 草稿/材料证据计划.json (safe_write). Never edits prose.
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Deterministic document-type decision, runs at material-plan stage."

import argparse
import json
import re
import sys
from pathlib import Path

ALGO_PATH_RE = re.compile(r"(strategy|chain|algorithm|engine|solver|matrix|priority|rule|calc|merge|dispatch)", re.I)
DESIGN_SECTIONS = [
    "引言（编写目的/背景/术语）",
    "总体设计（架构/模块划分/接口设计）",
    "数据设计（核心实体/表关系/字典）",
    "核心算法与机制设计（由 A 级代码证据推导）",
    "界面设计与操作说明",
    "部署与运行",
]
USER_SECTIONS = [
    "手册说明（适用角色/阅读方式）",
    "快速上手",
    "按角色的功能详解（真实页面与操作）",
    "常见业务场景",
    "故障排查",
    "附录（术语）",
]
HYBRID_SECTIONS = [
    "引言",
    "系统概述与总体设计",
    "核心业务机制设计",
    "术语表",
    "按角色的功能操作详解",
    "常见场景与故障排查",
]


def algo_signal_count(plan: dict) -> int:
    n = 0
    for e in plan.get("code_evidence", []):
        if not e.get("selected"):
            continue
        p = e.get("path", "")
        if e.get("grade") == "A" and ALGO_PATH_RE.search(p):
            n += 1
    return n


def module_type_counts(business: dict) -> dict:
    counts = {"registry": 0, "business": 0, "hybrid": 0, "other": 0}
    for m in business.get("manual_modules", []):
        t = m.get("module_type", "other")
        counts[t] = counts.get(t, 0) + 1
    return counts


def decide(plan: dict, business: dict, occupied: set[str]) -> tuple[str, str, list[str]]:
    algo = algo_signal_count(plan)
    counts = module_type_counts(business)
    biz_heavy = counts["business"] + counts["hybrid"] >= counts["registry"]

    if algo >= 3:
        t = "hybrid" if biz_heavy else "design_description"
        # 同批次冲突分流：类型被兄弟占用时，算法最密集保设计说明书，其余降为操作手册
        if t in occupied:
            t = "user_manual"
            sections = USER_SECTIONS
            reason = f"同批次差异化：本任务算法类证据 {algo} 个，但同批次已占用 design_description/hybrid，选操作手册按角色展开真实页面与流程（业务型 {counts['business']} 个、台账型 {counts['registry']} 个）。"
            return t, reason, sections
        if t == "design_description":
            reason = f"算法密集：A 级算法类代码证据 {algo} 个（策略族/责任链/引擎类路径），操作型模块占比低。设计说明书最能体现独创性。"
        else:
            reason = f"算法与操作并重：A 级算法类证据 {algo} 个，业务型模块 {counts['business']} 个。混合型文档兼顾设计独创性与操作真实性。"
        return t, reason, DESIGN_SECTIONS if t == "design_description" else HYBRID_SECTIONS
    t = "user_manual"
    reason = f"操作密集：算法类证据 {algo} 个，台账/操作型模块占主导（台账型 {counts['registry']} 个）。操作手册按角色组织真实页面与流程。"
    return t, reason, USER_SECTIONS


def sibling_types(plan_path: Path) -> list[str]:
    """Document types chosen by sibling tasks in the same submission batch."""
    parent = plan_path.parent.parent.parent if plan_path.parent.name == "草稿" else plan_path.parent.parent
    out = []
    for d in parent.iterdir():
        if not d.is_dir():
            continue
        sp = d / "草稿" / "材料证据计划.json"
        if sp == plan_path or not sp.exists():
            continue
        try:
            t = json.loads(sp.read_text(encoding="utf-8")).get("document_plan", {}).get("document_type")
        except Exception:
            t = ""
        if t:
            out.append(t)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--business", required=True)
    parser.add_argument("--confirm", action="store_true", help="写入计划；缺省只预览")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    business = json.loads(Path(args.business).read_text(encoding="utf-8"))

    sibs = sibling_types(plan_path)
    t, reason, sections = decide(plan, business, set(sibs))
    clash = [s for s in sibs if s == t]
    clash_note = f"⚠ 同批次已有 {len(clash)} 个任务使用 {t}，需在 structure_reason 中说明骨架差异" if clash else ""

    doc_plan = {
        "document_type": t,
        "structure_reason": reason,
        "sections": sections,
        "batch_note": clash_note,
    }
    print(f"建议文档类型: {t}")
    print(f"选择依据: {reason}")
    print(f"骨架要素: {' | '.join(sections)}")
    if clash_note:
        print(clash_note)

    if args.confirm:
        plan["document_plan"] = doc_plan
        from safe_write import safe_write
        tmp = plan_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = safe_write(plan_path, tmp)
        tmp.unlink(missing_ok=True)
        if not ok:
            raise SystemExit("STOP_FOR_USER: 写入材料证据计划.json 失败（内容为空被拒）")
        print(f"OK document_plan written: {plan_path}")
    else:
        print("（未写入。加 --confirm 写入材料证据计划.json）")


if __name__ == "__main__":
    main()
