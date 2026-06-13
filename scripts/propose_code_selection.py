#!/usr/bin/env python3
"""Create an editable source-file evidence list before code extraction."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import COPYRIGHT_CODE_EXTS, FRONTEND_EXTS, confirm_params, ensure_dir, is_known_config_file, iter_project_files, read_json, rel, resolve_draft_dir, resolve_task_dir, write_json
from extract_code_material import LINES_PER_PAGE, SPLIT_THRESHOLD_PAGES, category_weight, should_skip_file


DEFAULT_MAX_FILES = 0


def require_confirmed_manual(out_dir: Path) -> None:
    for anchor in [out_dir, *out_dir.parents]:
        gate_path = anchor / "门禁状态.json"
        if not gate_path.exists():
            continue
        gates = read_json(gate_path)
        if gates.get("manual", {}).get("confirmed"):
            return
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 代码选择前必须先确认完整操作手册并记录 manual 门禁。"
        )
    raise SystemExit(
        "STOP_FOR_USER\n"
        "NEXT_ACTION: 找不到门禁状态文件。代码选择前必须先确认完整操作手册并记录 manual 门禁。"
    )


def evidence_for(path: Path, project: Path) -> str:
    priority, _ = category_weight(path, project)
    if priority == 0:
        return "入口文件证据"
    if priority == 10:
        return "路由文件证据"
    if priority == 20:
        return "页面文件证据"
    if priority == 30:
        return "数据交互文件证据"
    if priority == 40:
        return "状态或数据文件证据"
    if priority == 50:
        return "页面组成文件证据"
    if priority == 60:
        return "通用能力文件证据"
    if priority == 90:
        return "样式文件证据"
    if path.suffix.lower() not in FRONTEND_EXTS:
        return "补充源码证据"
    return "普通源码文件"


def extract_module_evidence(business: dict[str, Any] | None) -> dict[str, list[str]]:
    """Return {module_title: [evidence_path, ...]} from manual_modules."""
    if not business:
        return {}
    modules = business.get("manual_modules") or []
    result: dict[str, list[str]] = {}
    for m in modules:
        if not isinstance(m, dict):
            continue
        title = str(m.get("title") or m.get("feature") or "unknown").strip()
        evidence = m.get("evidence") or []
        paths = [str(p).strip().replace("\\", "/") for p in evidence if str(p).strip()]
        if paths:
            result[title] = paths
    return result


def compute_module_coverage(
    candidates: list[dict[str, Any]],
    evidence_map: dict[str, list[str]],
    project_root: str | None = None,
) -> dict[str, Any]:
    """Cross-reference manual module evidence files with candidate files."""
    all_candidate_paths = {c["path"].replace("\\", "/") for c in candidates}

    # Normalize evidence paths: strip absolute project-root prefix and backslash
    def _norm(p: str) -> str:
        path = p.replace("\\", "/")
        if project_root:
            prefix = project_root.replace("\\", "/").rstrip("/") + "/"
            if path.lower().startswith(prefix.lower()):
                path = path[len(prefix):]
        return path

    module_coverage: list[dict[str, Any]] = []
    for module_title, evidence_paths in evidence_map.items():
        normalized = [_norm(p) for p in evidence_paths]
        found = [p for p in normalized if p in all_candidate_paths]
        missing = [p for p in normalized if p not in all_candidate_paths]
        module_coverage.append({
            "module_title": module_title,
            "evidence_files_found": found,
            "evidence_files_missing": missing,
        })

    warnings: list[str] = []
    for mc in module_coverage:
        if mc["evidence_files_missing"]:
            warnings.append(
                f"模块 '{mc['module_title']}' 有 {len(mc['evidence_files_missing'])} 个 evidence 文件不在候选池中"
                f"：{', '.join(mc['evidence_files_missing'][:5])}"
            )
        if not mc["evidence_files_found"]:
            warnings.append(
                f"模块 '{mc['module_title']}' 的所有 evidence 文件均不在候选池中"
                f"——该模块内容无法被代码材料覆盖"
            )

    return {
        "business_context_available": True,
        "total_modules": len(evidence_map),
        "modules_with_coverage": sum(1 for mc in module_coverage if mc["evidence_files_found"]),
        "modules_without_coverage": sum(1 for mc in module_coverage if not mc["evidence_files_found"]),
        "module_code_coverage": module_coverage,
        "coverage_warnings": warnings,
        "instructions": (
            "模型选择文件时必须优先覆盖 manual_modules 中有 evidence 文件的模块。"
            "evidence 文件不在候选池中的模块须在 model_reason 中说明原因。"
            "未映射到任何模块的选中文件须在 model_reason 中标注为补充文件。"
        ),
    }


def build_candidates(project: Path) -> list[dict[str, Any]]:
    files = [p for p in iter_project_files(project, COPYRIGHT_CODE_EXTS) if not should_skip_file(p) and not is_known_config_file(p)]
    files.sort(key=lambda p: category_weight(p, project))
    candidates: list[dict[str, Any]] = []
    for path in files:
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            line_count = 0
        priority, _ = category_weight(path, project)
        candidates.append(
            {
                "path": rel(path, project),
                "selected": False,
                "line_count": line_count,
                "priority": priority,
                "selection_tier": "frontend" if path.suffix.lower() in FRONTEND_EXTS else "supplement",
                "evidence": evidence_for(path, project),
                "model_reason": "",
            }
        )
    return candidates


def selected_line_estimate(item: dict[str, Any]) -> int:
    return int(item.get("line_count") or 0) + 2


def selection_stats(candidates: list[dict[str, Any]]) -> dict[str, int]:
    selected_items = [item for item in candidates if item.get("selected")]
    return {
        "selected_count": len(selected_items),
        "selected_lines": sum(selected_line_estimate(item) for item in selected_items),
    }


def all_candidate_lines(candidates: list[dict[str, Any]]) -> int:
    return sum(selected_line_estimate(item) for item in candidates)


def write_selection_md(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# 代码文件候选清单",
        "",
        "请先确认要抽取哪些源码文件，再运行代码材料抽取。",
        "",
        "本清单只列出候选源码证据，不默认决定抽取文件。",
        "模型需要先理解项目业务、页面入口和源码职责，再填写 `selected/model_reason`。",
        f"当前已选约 {data['estimated_selected_pages']} 页，全部候选源码约 {data['estimated_all_candidate_pages']} 页。",
        "",
        "```text",
        "STOP_FOR_USER",
        "NEXT_ACTION: 请由模型先填写 草稿/代码文件选择.json 的抽取选择和选择理由，再让用户确认；确认后运行 confirm_stage.py --stage code-selection --confirm。",
        "```",
        "",
        "确认方式：",
        "",
        "1. 模型根据项目业务和代码入口选择最能体现软件功能的文件。",
        "2. 把需要抽取的文件设为 `selected: true`，并填写 `model_reason`。",
        "3. 代码材料按完整文件原样复制，不支持只抽取某个文件的中间行段。",
        "4. 用户确认模型选择后，再记录 `code-selection` 门禁。",
        "",
        "## 默认选中文件",
        "",
        "| 文件 | 行数 | 模型选择理由 |",
        "| --- | ---: | --- |",
    ]
    for item in data["files"]:
        if item.get("selected"):
            lines.append(f"| `{item['path']}` | {item['line_count']} | {item.get('model_reason') or '待模型填写'} |")

    lines.extend(["", "## 未选候选文件", "", "| 文件 | 行数 | 证据类型 |", "| --- | ---: | --- |"])
    for item in data["files"]:
        if not item.get("selected"):
            lines.append(f"| `{item['path']}` | {item['line_count']} | {item['evidence']} |")

    if data.get("module_code_coverage"):
        cov = data["module_code_coverage"]
        lines.extend([
            "",
            "## 模块代码覆盖（来自业务理解 manual_modules）",
            "",
            f"- 模块总数：{cov['total_modules']}",
            f"- 有代码覆盖的模块：{cov['modules_with_coverage']}",
            f"- 无代码覆盖的模块：{cov['modules_without_coverage']}",
            "",
            "| 模块 | evidence 文件（已找到） | evidence 文件（缺失） |",
            "| --- | --- | --- |",
        ])
        for mc in cov["module_code_coverage"]:
            found_str = "、".join(f"`{p}`" for p in mc["evidence_files_found"]) or "-"
            missing_str = "、".join(f"`{p}`" for p in mc["evidence_files_missing"]) or "-"
            lines.append(f"| {mc['module_title']} | {found_str} | {missing_str} |")
        if cov["coverage_warnings"]:
            lines.extend(["", "### 覆盖警告", ""])
            for w in cov["coverage_warnings"]:
                lines.append(f"- {w}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--analysis", help="Optional project analysis JSON; retained for workflow traceability")
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="Only limits candidate inventory size; does not auto-select files")
    parser.add_argument("--target-pages", type=int, default=SPLIT_THRESHOLD_PAGES)
    parser.add_argument("--lines-per-page", type=int, default=LINES_PER_PAGE)
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    parser.add_argument("--business-context", help="Business context JSON containing manual_modules for evidence cross-referencing")
    args = parser.parse_args()

    project = Path(args.project)
    if not project.exists():
        raise SystemExit(f"Project not found: {project}")
    if args.analysis and not Path(args.analysis).exists():
        raise SystemExit(f"Analysis JSON not found: {args.analysis}")

    out_dir = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)
    ensure_dir(out_dir)
    require_confirmed_manual(out_dir)
    candidates = build_candidates(project)
    target_lines = max(1, args.target_pages) * max(1, args.lines_per_page)
    if args.max_files:
        candidates = candidates[: args.max_files]
    stats = selection_stats(candidates)
    candidate_lines = all_candidate_lines(candidates)
    selected_pages = (stats["selected_lines"] + args.lines_per_page - 1) // args.lines_per_page if stats["selected_lines"] else 0
    all_pages = (candidate_lines + args.lines_per_page - 1) // args.lines_per_page if candidate_lines else 0

    coverage = None
    if args.business_context:
        bc_path = Path(args.business_context)
        if bc_path.exists():
            business = read_json(bc_path)
            if isinstance(business, dict):
                evidence_map = extract_module_evidence(business)
                if evidence_map:
                    coverage = compute_module_coverage(candidates, evidence_map, args.project)

    supplement_rule = (
        "模型优先选择 manual_modules 中 evidence 列出的源码文件，确保操作手册中每个功能模块都有对应代码覆盖；"
        "evidence 文件不足 60 页时再从其他相关源码补充；候选源码仍不足时才生成全部代码材料。"
    )
    next_action = (
        "模型必须优先选择 代码文件候选清单.md 中「模块代码覆盖」章节列出的 evidence 文件；"
        "补充文件须在 model_reason 中标注为补充。填写完成后让用户确认，再运行 confirm_stage.py --stage code-selection --confirm。"
    )
    data = {
        "project_root": str(project.resolve()),
        "selection_required": True,
        "model_selection_required": True,
        "confirmation_required": True,
        "user_confirmed": False,
        "target_pages": args.target_pages,
        "lines_per_page": args.lines_per_page,
        "target_lines": target_lines,
        "estimated_selected_lines": stats["selected_lines"],
        "estimated_selected_pages": selected_pages,
        "estimated_all_candidate_lines": candidate_lines,
        "estimated_all_candidate_pages": all_pages,
        "supplement_rule": supplement_rule,
        "confirmation_stage": "code-selection",
        "next_action": next_action,
        "instructions": "The script only inventories source files. The model must choose selected/model_reason before user confirmation. Selected files are copied in full.",
        "files": candidates,
    }
    if coverage:
        data["module_code_coverage"] = coverage
    write_json(out_dir / "代码文件选择.json", data)
    write_selection_md(out_dir / "代码文件候选清单.md", data)
    selected_count = sum(1 for item in candidates if item.get("selected"))
    print(f"OK code selection draft: {out_dir}")
    print(f"Candidates: {len(candidates)}")
    print(f"Model selected: {selected_count}")
    print(f"Estimated selected pages: {selected_pages}")
    print(f"Estimated all candidate pages: {all_pages}")
    if coverage:
        print(f"Module coverage: {coverage['modules_with_coverage']}/{coverage['total_modules']} modules have evidence files in candidate pool")
        for w in coverage["coverage_warnings"]:
            print(f"WARNING: {w}")
    print("STOP_FOR_USER")
    print(f"NEXT_ACTION: {data['next_action']}")


if __name__ == "__main__":
    main()
