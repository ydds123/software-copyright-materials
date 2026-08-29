#!/usr/bin/env python3
"""Generate the material evidence plan draft (1a.1 planning layer).

The evidence plan is the single planning-layer source of truth. It
inventories code candidates with grade hints, ownership scan results
(署名三分法), feature mapping from business context, and a readable
Markdown companion. Nothing is auto-selected: the model fills in
selection/reason, then the user confirms via confirm_stage.py.

Outputs (into --out-dir, default 草稿/):
  材料证据计划.json
  材料证据计划.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    COPYRIGHT_CODE_EXTS,
    ensure_dir,
    is_known_config_file,
    iter_project_files,
    read_json,
    read_text,
    rel,
    resolve_draft_dir,
    write_json,
)
from evidence_plan_common import (
    aggregate_roots_digest,
    classify_author,
    crud_method_hits,
    file_sha256,
    scan_author_tags,
    suggest_grade,
)

SCHEMA_VERSION = 3
RULESET_VERSION = "originality-v1"

PLAN_FILE = "材料证据计划.json"
PLAN_MD_FILE = "材料证据计划.md"


def collect_code_candidates(roots: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Scan every code file under all input roots and build evidence entries."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for root in roots:
        root_path = Path(root["path"])
        if not root_path.exists():
            continue
        for path in iter_project_files(root_path, COPYRIGHT_CODE_EXTS):
            if is_known_config_file(path):
                continue
            rel_path = rel(path, root_path)
            key = (root["root_id"], rel_path)
            if key in seen:
                continue
            seen.add(key)
            text = read_text(path, limit=200_000)
            grade_hint, signals = suggest_grade(path, text)
            authors = scan_author_tags(text)
            author_categories = []
            for a in authors:
                cat = classify_author(a)
                if cat:
                    author_categories.append({"author": a, "category": cat})
            candidates.append(
                {
                    "evidence_id": f"C-{len(candidates) + 1:03d}",
                    "root_id": root["root_id"],
                    "path": rel_path,
                    "line_count": len(text.splitlines()) if text else 0,
                    "sha256": file_sha256(path),
                    "source_kind": "unknown",
                    "grade_hint": grade_hint,
                    "signals": signals,
                    "author_declaration": {
                        "found_author_tags": authors,
                        "categories": author_categories,
                        "resolution": "",
                        "resolution_basis": "",
                    },
                    "mapped_features": [],
                    "selection_reason": "",
                    "selected": False,
                }
            )
    return candidates


def extract_features(business: dict[str, Any] | None, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build feature list from business context manual_modules (or fallback)."""
    features: list[dict[str, Any]] = []
    if business and isinstance(business, dict):
        modules = business.get("manual_modules") or []
        for idx, m in enumerate(modules, start=1):
            if not isinstance(m, dict):
                continue
            title = str(m.get("title") or m.get("feature") or f"模块{idx}").strip()
            evidence = m.get("evidence") or []
            matched = []
            for e in evidence:
                ep = str(e).replace("\\", "/").strip()
                for c in candidates:
                    cand_path = c["path"].replace("\\", "/")
                    if cand_path.endswith(ep) or ep.endswith(cand_path):
                        matched.append(c["evidence_id"])
                        c["mapped_features"] = list(dict.fromkeys(c["mapped_features"] + [f"F-{idx:03d}"]))
            features.append(
                {
                    "feature_id": f"F-{idx:03d}",
                    "name": title,
                    "importance": "core",
                    "claim": "",
                    "code_evidence": list(dict.fromkeys(matched)),
                    "document_sections": [],
                    "visual_evidence": [],
                    "visual_status": "required",
                    "verification": "needs_review",
                }
            )
    if not features:
        # Fallback: one feature per module root directory found among candidates
        module_paths: list[str] = []
        for c in candidates:
            parts = c["path"].split("/")
            if len(parts) >= 2:
                module_paths.append(parts[0])
        for idx, mod in enumerate(dict.fromkeys(module_paths), start=1):
            features.append(
                {
                    "feature_id": f"F-{idx:03d}",
                    "name": mod,
                    "importance": "supporting",
                    "claim": "模块级占位功能，待模型补全业务语义",
                    "code_evidence": [],
                    "document_sections": [],
                    "visual_evidence": [],
                    "visual_status": "required",
                    "verification": "needs_review",
                }
            )
    return features


def extract_fact_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract verifiable fact candidates from code (first version: enums & CRUD stats)."""
    facts: list[dict[str, Any]] = []
    enum_files = [c for c in candidates if c["signals"] and any(s in c["signals"] for s in ("enum",)) or c["path"].endswith("Enum.java")]
    for c in enum_files[:30]:
        facts.append(
            {
                "fact_id": f"T-{len(facts) + 1:03d}",
                "subject": c["path"],
                "predicate": "枚举定义",
                "value": f"见 {c['path']}",
                "source": "code",
                "source_ref": c["evidence_id"],
                "document_locations": [],
                "type": "enum",
                "status": "candidate",
            }
        )
    crud_count = sum(1 for c in candidates if "crud_six_piece" in c["signals"])
    if crud_count:
        facts.append(
            {
                "fact_id": f"T-{len(facts) + 1:03d}",
                "subject": "源码材料",
                "predicate": "CRUD 六件套文件数",
                "value": crud_count,
                "source": "code",
                "source_ref": "",
                "document_locations": [],
                "type": "count",
                "status": "candidate",
            }
        )
    return facts


def write_plan_md(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# 材料证据计划",
        "",
        f"- 软件名称：{plan['software_scope'].get('name') or '待填写'}",
        f"- 版本号：{plan['software_scope'].get('version') or '待填写'}",
        f"- 计划状态：待模型补全选材与理由，待用户确认",
        "",
        "```text",
        "STOP_FOR_USER",
        "NEXT_ACTION: 模型补全 code_evidence 的 selected/selection_reason/source_kind/grade 与 features 的映射后，运行 evidence_plan_check.py 校验；通过后由用户确认 material-plan 门禁。",
        "```",
        "",
        "## 一、输入根",
        "",
    ]
    for root in plan["input_roots"]:
        lines.append(f"- `{root['root_id']}`: {root['path']}")
    lines.extend(["", "## 二、功能与代码证据映射", ""])
    lines.append("| 功能 | 核心度 | 代码证据 | 校验 |")
    lines.append("| --- | --- | --- | --- |")
    for f in plan["features"]:
        ev = "、".join(f["code_evidence"]) or "（未映射，需补全）"
        lines.append(f"| {f['name']} | {f['importance']} | {ev} | {f['verification']} |")
    lines.extend(["", "## 三、署名风险（三分法）", ""])
    risky = [
        c
        for c in plan["code_evidence"]
        if c["author_declaration"]["categories"]
    ]
    if risky:
        lines.append("| 文件 | 署名 | 类别 | 建议处理 |")
        lines.append("| --- | --- | --- | --- |")
        for c in risky[:50]:
            for entry in c["author_declaration"]["categories"]:
                cat = entry["category"]
                advice = {
                    "framework": "情况一：禁止改署名，移出材料或人工核实",
                    "ai_tool": "默认情况三：移出材料；用户声明自研后可改署名（情况二）",
                }.get(cat, "")
                lines.append(f"| `{c['path']}` | {entry['author']} | {cat} | {advice} |")
    else:
        lines.append("（无命中标签库的署名）")
    lines.extend(["", "## 四、事实断言候选", ""])
    for t in plan["fact_assertions"]:
        lines.append(f"- `{t['fact_id']}` {t['subject']} {t['predicate']}={t['value']} [{t['type']}]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_plan(
    roots: list[dict[str, str]],
    business: dict[str, Any] | None,
    software_name: str,
    version: str,
    batch_id: str,
    team_members: list[str],
) -> dict[str, Any]:
    candidates = collect_code_candidates(roots)
    features = extract_features(business, candidates)
    facts = extract_fact_candidates(candidates)
    plan = {
        "schema_version": SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "submission_batch_id": batch_id,
        "sibling_application_ids": [],
        "team_members": team_members,
        "input_roots": roots,
        "input_digests": {
            "aggregate": aggregate_roots_digest(roots),
        },
        "software_scope": {
            "name": software_name,
            "version": version,
            "included_boundaries": [],
            "excluded_boundaries": [],
        },
        "features": features,
        "code_evidence": candidates,
        "fact_assertions": facts,
        "document_plan": {
            "document_type": "",
            "structure_reason": "",
            "sections": [],
            "protected_facts": [],
        },
        "blockers": [],
        "warnings": [],
    }
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Primary source root")
    parser.add_argument("--extra-roots", nargs="*", default=[], help="Additional source roots (each pair id:path)")
    parser.add_argument("--business-context", help="Business context JSON with manual_modules")
    parser.add_argument("--software-name", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--team-members", nargs="*", default=[], help="Confirmed team member author names")
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--confirm", action="store_true", help="Accepted for backward compatibility")
    args = parser.parse_args()

    project = Path(args.project)
    if not project.exists():
        raise SystemExit(f"Project not found: {project}")

    roots = [{"root_id": "primary", "path": str(project.resolve())}]
    for extra in args.extra_roots:
        if ":" in extra:
            root_id, path = extra.split(":", 1)
        else:
            root_id, path = f"root-{len(roots) + 1}", extra
        roots.append({"root_id": root_id, "path": path})

    business = None
    if args.business_context:
        bc = Path(args.business_context)
        if bc.exists():
            business = read_json(bc)
        else:
            raise SystemExit(f"Business context not found: {bc}")

    out_dir = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)
    ensure_dir(out_dir)

    plan = build_plan(
        roots=roots,
        business=business,
        software_name=args.software_name,
        version=args.version,
        batch_id=args.batch_id,
        team_members=args.team_members,
    )
    write_json(out_dir / PLAN_FILE, plan)
    write_plan_md(out_dir / PLAN_MD_FILE, plan)

    print(f"OK evidence plan draft: {out_dir}")
    print(f"Code candidates: {len(plan['code_evidence'])}")
    print(f"Features: {len(plan['features'])}")
    print(f"Fact candidates: {len(plan['fact_assertions'])}")
    risky = [c for c in plan["code_evidence"] if c["author_declaration"]["categories"]]
    print(f"Ownership risks: {len(risky)}")
    for c in risky[:20]:
        tags = ", ".join(e["category"] for e in c["author_declaration"]["categories"])
        print(f"  RISK [{tags}] {c['root_id']}/{c['path']}")
    print("STOP_FOR_USER")
    print("NEXT_ACTION: 模型补全计划选材后运行 evidence_plan_check.py 校验，再让用户确认 material-plan 门禁。")


if __name__ == "__main__":
    main()
