#!/usr/bin/env python3
"""Validate a model-authored operation manual and produce unified review records.

Operation manuals are authored directly by the model in 草稿/操作手册.md. This
script validates the existing markdown against quality gates and writes planning
and review artifacts, but does not generate content.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import ensure_dir, read_json, resolve_draft_dir

from manual_quality import (
    manual_quality_issues,
    template_quality,
)

from manual_model import (
    normalize_manual_modules,
    require_business_input_quality,
)

from evidence_router import (
    evidence_gap_issues,
    evidence_gap_summary,
    reset_evidence_gaps,
)
from manual_audit import ensure_writing_plan, update_review_report


def read_existing_manual(out_dir: Path) -> str | None:
    """Read the model-authored manual if it exists."""
    path = out_dir / "操作手册.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def validate_manual(
    text: str,
    analysis: dict[str, Any],
    software_name: str,
    version: str,
    business: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    document_type: str = "",
    out_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate existing manual text and return self-review records and modules."""
    require_business_input_quality(business)
    modules = normalize_manual_modules(business, [])

    records: list[dict[str, Any]] = []

    def review_round(round_no: int, action: str) -> None:
        reset_evidence_gaps()
        gap_summary = evidence_gap_summary()
        issues = manual_quality_issues(text, modules, profile, business, document_type)
        issues.extend(evidence_gap_issues(gap_summary))
        records.append({
            "round": round_no,
            "action": action,
            "issues": issues,
            "evidence_gaps": gap_summary,
        })

    review_round(1, "初稿生成")
    review_round(2, "真实页面字段复核")
    review_round(3, "制式模板和 AI 味复核")
    review_round(4, "复核仍需模型回到业务理解补写")

    # 第 5 轮：防模板化复核（references/防模板化指南.md 的脚本化落地——草稿写完即强制执行，不依赖模型自觉读文档）
    anti_issues, anti_notes = anti_templating_issues(text, out_dir)
    records.append({
        "round": 5,
        "action": "防模板化复核",
        "issues": anti_issues,
        "notes": anti_notes,
        "evidence_gaps": [],
    })

    return records, modules


def anti_templating_issues(text: str, out_dir: Path | None) -> tuple[list[str], list[str]]:
    """防模板化指南的强制执行层。

    issues 非空会阻断 generate_manual_draft（STOP_FOR_USER），notes 仅记录提示。
    覆盖：单文档重复小节、超长自然段、截图名称含模块名前缀、同批同构（含本任务）。
    """
    import re as _re
    from collections import Counter as _Counter

    issues: list[str] = []
    notes: list[str] = []

    # 1) 本手册内重复小节（≥3 次）
    plain_titles: list[str] = []
    for line in text.splitlines():
        m = _re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip())
        if m:
            unnumbered = _re.sub(r"^\d+(?:\.\d+)*[、.\s]*", "", m.group(1).strip())
            plain_titles.append(unnumbered)
    for title, n in _Counter(plain_titles).items():
        if n >= 3:
            issues.append(
                f"重复小节「{title}」出现 {n} 次：过度对称是模板化特征，按模块加前缀个性化（防模板化指南 §1.2）"
            )

    # 2) 超长自然段（≥300 字阻断，180-300 提示）
    long_issues = long_notes = 0
    for para in text.split("\n\n"):
        s = para.strip()
        if not s or s.startswith(("#", "|", "【", "-", "**", ">", "!")):
            continue
        han = len(_re.findall(r"[\u4e00-\u9fff]", s))
        if han >= 300:
            long_issues += 1
        elif han >= 180:
            long_notes += 1
    if long_issues:
        issues.append(
            f"{long_issues} 个超过 300 字的自然段：按语义边界拆分为 40-120 字段落，首句做主题锚点（防模板化指南 §2）"
        )
    if long_notes:
        notes.append(f"{long_notes} 个 180-300 字段落偏长，建议按语义边界拆分（防模板化指南 §2）")

    # 3) 截图名称含模块名前缀（归属检查误报源）
    module_titles = [
        _re.sub(r"^#{3,4}\s+\d+(?:\.\d+)*\s*", "", line.strip())
        for line in text.splitlines()
        if _re.match(r"^#{3,4}\s+\d+(?:\.\d+)*\s+", line.strip())
    ]
    for m in _re.finditer(r'【截图预留：请在此处插入"([^"]+)"', text):
        shot_name = m.group(1)
        for mt in module_titles:
            if mt and len(mt) >= 4 and mt in shot_name and shot_name != mt:
                notes.append(
                    f"截图名称含模块名「{mt}」（{shot_name}）：归属检查会误判，改为小节级名称（防模板化指南 §4.2）"
                )
                break

    # 4) 同批同构（涉及本任务的问题升级为阻断）
    if out_dir and out_dir.exists():
        try:
            from batch_structure_check import run as batch_run
            sibling_manuals: list[Path] = []
            parent = out_dir.parent.parent
            if parent.exists():
                for d in parent.iterdir():
                    if not d.is_dir():
                        continue
                    sm = d / "草稿" / "操作手册.md"
                    if sm.exists() and sm != (out_dir / "操作手册.md"):
                        sibling_manuals.append(sm)
            if len(sibling_manuals) >= 1:
                report = batch_run([out_dir / "操作手册.md"] + sibling_manuals, batch_id=parent.name)
                my_name = out_dir.parent.name
                for e in report.get("errors") or []:
                    if my_name in e:
                        issues.append(f"同批确定性结构错误: {e}")
                    else:
                        notes.append(f"兄弟任务确定性错误（不阻断本任务）: {e}")
                for r in report.get("risks") or []:
                    involves_me = any(my_name in p for p in (r.get("pair") or []))
                    if involves_me and r.get("level") == "high":
                        notes.append(f"相似度高风险（需人工复核，不阻断）: {' 与 '.join(r.get('pair') or [])}: {r.get('detail','')}")
        except ImportError:
            pass

    return issues, notes


def write_review_records(
    out_dir: Path,
    records: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
) -> None:
    quality = template_quality(profile)
    profile_summary = None
    if profile:
        profile_summary = {
            "profile_version": profile.get("profile_version"),
            "source_docx": profile.get("source_docx"),
            "sample_metrics": profile.get("sample_metrics"),
            "target_quality": quality,
        }
    update_review_report(out_dir, records, modules, profile_summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a model-authored operation manual and produce self-review records."
    )
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--software-name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--business-context", help="Business context JSON")
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    analysis = read_json(Path(args.analysis))
    business = read_json(Path(args.business_context)) if args.business_context else None
    require_business_input_quality(business)
    out_dir = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)
    ensure_dir(out_dir)

    # Read the model-authored manual
    text = read_existing_manual(out_dir)
    if not text:
        print("STOP_FOR_USER")
        print(f"NEXT_ACTION: 模型尚未撰写操作手册。请在 {out_dir / '操作手册.md'} 中按 SKILL.md Step 6 规范撰写操作手册后重新运行本脚本。")
        raise SystemExit(1)

    # v1.6 document-type awareness: read the chosen type before validation
    plan_path = out_dir / "材料证据计划.json"
    doc_type = ""
    if plan_path.exists():
        try:
            dp = json.loads(plan_path.read_text(encoding="utf-8")).get("document_plan", {})
            doc_type = dp.get("document_type", "")
            print(f"document_type: {doc_type or '(未决策，请先运行 propose_document_plan.py --confirm)'}")
            if dp.get("sections"):
                print(f"sections contract: {' | '.join(dp['sections'])}")
        except Exception:
            pass

    records, modules = validate_manual(text, analysis, args.software_name, args.version, business, document_type=doc_type, out_dir=out_dir)

    ensure_writing_plan(out_dir, business or {})
    write_review_records(out_dir, records, modules)

    print(f"OK manual draft: {out_dir / '操作手册.md'}")
    print(f"OK unified manual plan: {out_dir / '操作手册写作计划.json'}")
    print(f"OK unified manual review: {out_dir / '操作手册审查报告.json'}")

    # Report coverage
    if business:
        biz_modules = business.get("manual_modules") or []
        with_rich = sum(1 for m in biz_modules if m.get("module_type") in ("registry", "business", "hybrid"))
        print(f"coverage: {with_rich}/{len(biz_modules)} modules have rich structure (crud_scenarios / registry / business_operation / hybrid)")

    for record in records:
        print(f"Review round {record['round']}: {record['action']} issues={len(record['issues'])}")

    if records[-1]["issues"]:
        print("STOP_FOR_USER")
        print("NEXT_ACTION: 操作手册自检仍有问题。请模型回到操作手册修正内容后重新运行本脚本。")
        raise SystemExit(1)

    print("STOP_FOR_USER")
    print("NEXT_ACTION: 请先运行 content_quality_check.py 并记录 content-quality 门禁，再确认完整操作手册草稿并运行 confirm_stage.py --stage manual --confirm。")


if __name__ == "__main__":
    main()
