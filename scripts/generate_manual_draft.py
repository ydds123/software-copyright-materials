#!/usr/bin/env python3
"""Validate a model-authored operation manual and produce unified review records.

Operation manuals are authored directly by the model in 草稿/操作手册.md. This
script validates the existing markdown against quality gates and writes planning
and review artifacts, but does not generate content.
"""

from __future__ import annotations

import argparse
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate existing manual text and return self-review records and modules."""
    require_business_input_quality(business)
    modules = normalize_manual_modules(business, [])

    records: list[dict[str, Any]] = []

    def review_round(round_no: int, action: str) -> None:
        reset_evidence_gaps()
        gap_summary = evidence_gap_summary()
        issues = manual_quality_issues(text, modules, profile, business)
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

    return records, modules


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

    records, modules = validate_manual(text, analysis, args.software_name, args.version, business)

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
