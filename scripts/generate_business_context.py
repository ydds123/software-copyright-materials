#!/usr/bin/env python3
"""Collect project evidence and write a model-authored business context."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import confirm_params, ensure_dir, iter_project_files, read_json, read_text, rel, resolve_draft_dir, resolve_task_dir, write_json


DOC_EXTS = {".md", ".txt", ".rst", ".adoc"}
MAX_DOC_CHARS = 80_000
MAX_DOCS = 40


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_md(text: str) -> str:
    text = re.sub(r"`{3}.*?`{3}", " ", text, flags=re.S)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"[>#*_`|]", " ", text)
    return normalize_space(text)


def skip_doc(path: Path, project: Path) -> bool:
    r = rel(path, project).lower()
    skip_parts = (
        "node_modules",
        ".git/",
        "dist/",
        "build/",
        ".next/",
        "coverage/",
        "软件著作权申请资料",
    )
    return any(part in r for part in skip_parts)


def extract_headings(text: str, limit: int = 24) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("#"):
            title = clean.lstrip("#").strip()
            if title and title not in headings:
                headings.append(title[:120])
        if len(headings) >= limit:
            break
    return headings


def extract_opening(text: str, limit: int = 900) -> str:
    clean = strip_md(text)
    return clean[:limit].strip()


def collect_documents(project: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in iter_project_files(project, DOC_EXTS):
        if skip_doc(path, project):
            continue
        try:
            text = read_text(path, limit=MAX_DOC_CHARS)
        except Exception:
            continue
        if not text.strip():
            continue
        docs.append(
            {
                "path": rel(path, project),
                "size": path.stat().st_size,
                "headings": extract_headings(text),
                "opening": extract_opening(text),
            }
        )
    docs.sort(key=lambda item: (item["path"].count("/"), item["path"]))
    return docs[:MAX_DOCS]


def collect_code_evidence(analysis: dict[str, Any]) -> dict[str, Any]:
    source = analysis.get("source") or {}
    categorized = source.get("categorized_files") or {}
    return {
        "project_name": analysis.get("project_name"),
        "software_name_candidate": analysis.get("software_name_candidate"),
        "frameworks": analysis.get("frameworks") or [],
        "language": analysis.get("language"),
        "routes": analysis.get("routes") or [],
        "feature_name_candidates": analysis.get("feature_candidates") or [],
        "entry_files": categorized.get("entry") or [],
        "page_files": categorized.get("page") or [],
        "component_files": categorized.get("component") or [],
        "api_files": categorized.get("api") or [],
        "run_command_candidates": analysis.get("run_command_candidates") or [],
        "package": analysis.get("package") or {},
    }


def build_evidence(project: Path, analysis: dict[str, Any], software_name: str, web_notes: str) -> dict[str, Any]:
    return {
        "software_name": software_name,
        "project_root": str(project.resolve()),
        "instruction": (
            "本文件只收集证据，不决定行业、功能或手册结构。"
            "请由模型阅读这些证据以及必要的项目源码后，另行编写业务理解模型稿。"
        ),
        "documents": collect_documents(project),
        "code_evidence": collect_code_evidence(analysis),
        "external_research_notes": web_notes,
    }


def write_evidence_md(path: Path, evidence: dict[str, Any]) -> None:
    lines = [
        "# 业务理解证据",
        "",
        f"- 软件名称：{evidence['software_name']}",
        f"- 项目目录：`{evidence['project_root']}`",
        "",
        "本文件只列出可供模型研判的项目证据，不代表最终申报口径。",
        "模型需要自行判断应阅读哪些文档、抽取哪些功能、采用什么操作手册结构。",
        "",
        "## 代码与页面证据",
        "",
    ]
    code = evidence["code_evidence"]
    for key in ("frameworks", "language", "routes", "feature_name_candidates", "entry_files", "page_files", "component_files", "api_files"):
        value = code.get(key)
        if value:
            lines.append(f"- {key}：{value}")
    lines.extend(["", "## 文档证据", ""])
    for doc in evidence["documents"]:
        lines.extend(
            [
                f"### {doc['path']}",
                "",
                f"- 大小：{doc['size']} bytes",
                f"- 标题线索：{'；'.join(doc['headings']) if doc['headings'] else '无'}",
                "",
                doc["opening"],
                "",
            ]
        )
    if evidence.get("external_research_notes"):
        lines.extend(["## 外部调研摘要", "", evidence["external_research_notes"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def load_model_context(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid model context JSON: {path}")
    return data


def required_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise SystemExit(f"Model context field must be a list: {field}")
    items = [item for item in value if (isinstance(item, (dict, list)) or str(item).strip())]
    if not items:
        raise SystemExit(f"Model context field cannot be empty: {field}")
    return items


def normalize_operation_flow(value: Any) -> list[dict[str, str]]:
    items = required_list(value, "operation_flow")
    result: list[dict[str, str]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise SystemExit(
                f"operation_flow item {index} must be an object with step and result; "
                "do not use string-only flow items."
            )
        step = str(item.get("step") or item.get("action") or item.get("name") or "").strip()
        outcome = str(item.get("result") or item.get("outcome") or item.get("feedback") or "").strip()
        if not step:
            raise SystemExit(f"operation_flow item {index} missing field: step")
        if not outcome:
            raise SystemExit(f"operation_flow item {index} missing field: result")
        result.append({"step": step, "result": outcome})
    return result


def required_text(data: dict[str, Any], field: str) -> str:
    value = str(data.get(field) or "").strip()
    if not value:
        raise SystemExit(f"Model context field cannot be empty: {field}")
    return value


def normalize_model_context(model: dict[str, Any], evidence: dict[str, Any], web_notes: str) -> dict[str, Any]:
    """Validate and normalize the model-authored business context JSON.

    All validation errors are collected first, then reported together
    so the model can fix everything in a single pass.
    """
    errors: list[str] = []

    def _check(condition: bool, msg: str) -> None:
        if not condition:
            errors.append(msg)

    # ── business_features ──
    features = model.get("business_features")
    features_ok = isinstance(features, list) and any(
        isinstance(item, (dict, list)) or str(item).strip() for item in (features or [])
    )
    _check(features_ok, "business_features 必须是非空列表")
    if features_ok:
        features = [f for f in features if isinstance(f, (dict, list)) or str(f).strip()]

    # ── business_feature_details ──
    details = model.get("business_feature_details") or {}
    _check(isinstance(details, dict), "business_feature_details 必须是对象")
    if isinstance(details, dict) and isinstance(features, list):
        missing_details = [f for f in features if not str(details.get(f) or "").strip()]
        if missing_details:
            errors.append(f"business_feature_details 缺少以下功能的说明：{'、'.join(missing_details[:12])}")

    # ── manual_sections ──
    sections = model.get("manual_sections")
    _check((sections is None) or isinstance(sections, list), "manual_sections 必须是列表或省略")

    # ── manual_modules (core) ──
    manual_modules = model.get("manual_modules")
    _check(isinstance(manual_modules, list) and len(manual_modules or []) > 0, "manual_modules 必须是非空列表")

    if isinstance(manual_modules, list):
        for index, module in enumerate(manual_modules, start=1):
            if not isinstance(module, dict):
                errors.append(f"manual_modules[{index}] 必须是对象")
                continue
            title = str(module.get("title") or module.get("feature") or "").strip()
            label = f"manual_modules[{index}] ({title or 'untitled'})"

            # Required common fields
            for field in ("title", "purpose", "usage", "entry"):
                if field == "title":
                    _check(bool(title), f"{label} 缺少字段: title")
                    continue
                value = module.get(field)
                if field == "usage" and not str(value or "").strip():
                    value = module.get("usage_scenario")
                has_value = any(str(item).strip() for item in value) if isinstance(value, list) else bool(str(value or "").strip())
                _check(has_value, f"{label} 缺少字段: {field}")

            # Type-specific checks
            module_type = module.get("module_type", "")
            if module_type in ("registry", "hybrid"):
                _check(isinstance(module.get("registry"), dict), f"{label}: registry/hybrid 类型必须包含 'registry' 对象")
            elif module_type == "business":
                _check(isinstance(module.get("business_operation"), dict), f"{label}: business 类型必须包含 'business_operation' 对象")
            else:
                # Old-style: require operation_steps and feedback
                for field in ("operation_steps", "feedback"):
                    value = module.get(field)
                    has_value = any(str(item).strip() for item in value) if isinstance(value, list) else bool(str(value or "").strip())
                    _check(has_value, f"{label} 缺少字段: {field}")

            # client_endpoint is always required (web/app/screen)
            ep = str(module.get("client_endpoint") or "").strip()
            _check(ep in ("web", "app", "screen"), f"{label}: client_endpoint 必须为 web、app 或 screen（当前值：'{ep}'）")

    # ── operation_flow ──
    op_flow = model.get("operation_flow")
    _check(isinstance(op_flow, list) and len(op_flow or []) > 0, "operation_flow 必须是非空列表")
    if isinstance(op_flow, list):
        for i, item in enumerate(op_flow, start=1):
            if not isinstance(item, dict):
                errors.append(f"operation_flow[{i}] 必须是包含 step 和 result 的对象（不能用纯字符串）")
                continue
            _check(bool(str(item.get("step") or item.get("action") or "").strip()), f"operation_flow[{i}] 缺少字段: step")
            _check(bool(str(item.get("result") or item.get("outcome") or "").strip()), f"operation_flow[{i}] 缺少字段: result")

    # ── top-level text fields ──
    for field in ("product_positioning", "industry", "core_value", "application_purpose", "main_functions", "technical_characteristics"):
        _check(bool(str(model.get(field) or "").strip()), f"顶层字段不能为空: {field}")

    # ── system_requirements ──
    system_requirements = model.get("system_requirements") or []
    _check(isinstance(system_requirements, list) and len(system_requirements) > 0, "system_requirements 必须是非空列表")

    # ── faq ──
    faq = model.get("faq")
    _check(isinstance(faq, list) and len(faq or []) > 0, "faq 必须是非空列表")

    # ── glossary ──
    glossary = model.get("glossary")
    _check(isinstance(glossary, list) and len(glossary or []) > 0, "glossary 必须是非空列表")

    # ── target_users ──
    tu = model.get("target_users")
    _check(isinstance(tu, list) and len(tu or []) > 0, "target_users 必须是非空列表")

    # ── system_endpoints ──
    se = model.get("system_endpoints")
    if isinstance(se, list) and se:
        for ep in se:
            _check(str(ep).strip() in ("web", "app", "screen"), f"system_endpoints 中的值必须为 web/app/screen（当前：'{ep}'）")
    else:
        se = ["web"]  # default: single-endpoint web system

    # ── product composition and closed-loop validation ──
    product_composition = model.get("product_composition")
    _check(
        isinstance(product_composition, list) and len(product_composition or []) > 0,
        "product_composition 必须是非空列表",
    )
    if isinstance(product_composition, list):
        for index, item in enumerate(product_composition, start=1):
            label = f"product_composition[{index}]"
            _check(isinstance(item, dict), f"{label} 必须是对象")
            if not isinstance(item, dict):
                continue
            for field in ("endpoint", "audience", "repository"):
                _check(bool(item.get(field)), f"{label} 缺少字段: {field}")
            _check(
                isinstance(item.get("module_paths"), list) and len(item.get("module_paths") or []) > 0,
                f"{label}.module_paths 必须是非空列表",
            )

    closed_loop = model.get("closed_loop_validation")
    _check(isinstance(closed_loop, dict), "closed_loop_validation 必须是对象")
    if isinstance(closed_loop, dict):
        _check(
            isinstance(closed_loop.get("chain"), list) and len(closed_loop.get("chain") or []) > 0,
            "closed_loop_validation.chain 必须是非空列表",
        )
        _check(
            isinstance(closed_loop.get("node_mapping"), list) and len(closed_loop.get("node_mapping") or []) > 0,
            "closed_loop_validation.node_mapping 必须是非空列表",
        )
        _check(bool(str(closed_loop.get("conclusion") or "").strip()), "closed_loop_validation.conclusion 不能为空")
        mappings = closed_loop.get("node_mapping") if isinstance(closed_loop.get("node_mapping"), list) else []
        mapped_nodes: set[str] = set()
        for index, item in enumerate(mappings, start=1):
            label = f"closed_loop_validation.node_mapping[{index}]"
            _check(isinstance(item, dict), f"{label} 必须是对象")
            if not isinstance(item, dict):
                continue
            for field in ("node", "module", "role", "result"):
                _check(bool(str(item.get(field) or "").strip()), f"{label} 缺少字段: {field}")
            mapped_nodes.add(str(item.get("node") or "").strip())
        chain_nodes = {str(node).strip() for node in closed_loop.get("chain") or [] if str(node).strip()}
        missing_nodes = sorted(chain_nodes - mapped_nodes)
        if missing_nodes:
            errors.append("closed_loop_validation.node_mapping 缺少链路节点：" + "、".join(missing_nodes))

    # ── Report all errors at once ──
    if errors:
        numbered = "\n".join(f"  {i}. {e}" for i, e in enumerate(errors, start=1))
        raise SystemExit(
            f"STOP_FOR_USER\n"
            f"NEXT_ACTION: 业务理解模型稿有以下 {len(errors)} 个问题，请逐一修复后重新运行：\n"
            f"{numbered}"
        )

    # ── Build context (all checks passed) ──
    features_clean = features if isinstance(features, list) else []
    sections_clean = sections if isinstance(sections, list) else []
    modules_clean = manual_modules if isinstance(manual_modules, list) else []
    context = {
        "software_name": evidence["software_name"],
        "business_understanding_required": True,
        "source_documents": [{"path": doc["path"], "size": doc["size"]} for doc in evidence["documents"]],
        "project_evidence_file": "业务理解证据.md",
        "product_positioning": required_text(model, "product_positioning"),
        "industry": required_text(model, "industry"),
        "target_users": required_list(model.get("target_users"), "target_users"),
        "system_endpoints": se,
        "product_composition": product_composition,
        "closed_loop_validation": closed_loop,
        "core_value": required_text(model, "core_value"),
        "business_features": features_clean,
        "business_feature_details": {feature: str(details.get(feature)).strip() for feature in features_clean} if isinstance(details, dict) else {},
        "operation_flow": normalize_operation_flow(model.get("operation_flow")),
        "application_purpose": required_text(model, "application_purpose"),
        "main_functions": required_text(model, "main_functions"),
        "technical_characteristics": required_text(model, "technical_characteristics"),
        "software_technical_option": str(model.get("software_technical_option") or "应用软件"),
        "software_category": str(model.get("software_category") or "应用软件"),
        "manual_sections": sections_clean,
        "manual_modules": modules_clean,
        "system_requirements": system_requirements,
        "faq": faq,
        "glossary": glossary,
        "model_authored": True,
        "external_research_notes": web_notes,
        "confirmation_required": True,
        "user_confirmed": False,
        "confirmation_stage": "business",
        "next_action": "请确认 草稿/业务理解.md 中的软件用途、行业、目标用户、核心功能、手册结构和申请口径；确认后运行 confirm_stage.py --stage business --confirm。",
        "review_notes": [
            "请确认模型判断的行业领域、目标用户和主要功能是否符合实际申报口径。",
            "请确认操作手册结构是否按真实页面和流程展开，而不是套用抽象功能列表。",
        ],
    }
    return context


def write_context_md(path: Path, context: dict[str, Any]) -> None:
    lines = [
        "# 业务理解",
        "",
        f"- 软件名称：{context['software_name']}",
        f"- 产品定位：{context['product_positioning']}",
        f"- 面向领域 / 行业：{context['industry']}",
        f"- 核心价值：{context['core_value']}",
        f"- 证据文件：`{context['project_evidence_file']}`",
        "",
        "## 产品组成与闭环验证",
        "",
        "### 产品组成",
        "",
    ]
    for item in context["product_composition"]:
        module_paths = "、".join(str(path) for path in item.get("module_paths") or [])
        lines.append(
            f"- {item.get('endpoint', '')}：面向{item.get('audience', '')}；"
            f"仓库 `{item.get('repository', '')}`；模块目录：{module_paths}"
        )
    closed_loop = context["closed_loop_validation"]
    lines.extend(
        [
            "",
            "### 闭环验证",
            "",
            " → ".join(str(node) for node in closed_loop.get("chain") or []),
            "",
        ]
    )
    for item in closed_loop.get("node_mapping") or []:
        lines.append(
            f"- {item.get('node', '')}：对应模块 {item.get('module', '')}；"
            f"操作者 {item.get('role', '')}；结果 {item.get('result', '')}"
        )
    lines.extend(
        [
            "",
            f"- 验证结论：{closed_loop.get('conclusion', '')}",
            "",
        "## 目标用户",
        "",
        ]
    )
    lines.extend(f"- {item}" for item in context["target_users"])
    lines.extend(["", "## 主要业务功能", ""])
    lines.extend(f"- {item}" for item in context["business_features"])
    lines.extend(["", "## 功能说明", ""])
    for item in context["business_features"]:
        lines.append(f"- {item}：{context['business_feature_details'].get(item, '')}")
    lines.extend(["", "## 典型操作流程", ""])
    for i, item in enumerate(context["operation_flow"], start=1):
        if isinstance(item, dict):
            lines.append(f"{i}. {item.get('step', '')}：{item.get('result', '')}")
        else:
            lines.append(f"{i}. {item}")
    if context.get("manual_sections"):
        lines.extend(["", "## 操作手册结构建议", ""])
        for i, section in enumerate(context["manual_sections"], start=1):
            if isinstance(section, dict):
                title = section.get("title") or f"章节 {i}"
                intent = section.get("intent") or ""
            else:
                title = str(section)
                intent = ""
            lines.append(f"{i}. {title}" + (f"：{intent}" if intent else ""))
    if context.get("manual_modules"):
        lines.extend(["", "## 操作手册页面/流程模块", ""])
        for i, module in enumerate(context["manual_modules"], start=1):
            if not isinstance(module, dict):
                lines.append(f"{i}. {module}")
                continue
            title = module.get("title") or module.get("feature") or f"模块 {i}"
            usage = module.get("usage") or module.get("usage_scenario") or ""
            entry = module.get("entry") or ""
            steps = module.get("operation_steps") or module.get("steps") or []
            lines.append(f"{i}. {title}" + (f"：{entry}" if entry else ""))
            if usage:
                lines.append(f"   - 使用场景：{usage}")
            if steps:
                lines.append(f"   - 操作要点：{'；'.join(str(item) for item in steps[:4])}")
    lines.extend(
        [
            "",
            "## 申请表建议口径",
            "",
            f"- 开发目的：{context['application_purpose']}",
            f"- 软件的主要功能：{context['main_functions']}",
            f"- 技术特点：{context['technical_characteristics']}",
            f"- 软件的技术特点选项：{context['software_technical_option']}",
            f"- 软件分类：{context['software_category']}",
            "",
            "## 证据来源",
            "",
        ]
    )
    lines.extend(f"- `{item['path']}`" for item in context["source_documents"])
    lines.extend(["", "## 待确认", ""])
    lines.extend(f"- {item}" for item in context["review_notes"])
    lines.extend(
        [
            "",
            "```text",
            "STOP_FOR_USER",
            f"NEXT_ACTION: {context['next_action']}",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--software-name", required=True)
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--web-notes", help="Optional plain-text notes from external/competitor research")
    parser.add_argument("--model-context", help="Model-authored business context JSON (skip if using --from-json)")
    parser.add_argument("--from-json", help="Path to existing 业务理解.json to re-render 业务理解.md from")
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    args = parser.parse_args()

    project = Path(args.project)
    analysis = read_json(Path(args.analysis))
    web_notes = read_text(Path(args.web_notes)) if args.web_notes else ""

    task_dir = args.task_dir
    if not task_dir:
        found = resolve_task_dir()
        task_dir = str(found) if found else None
    out_dir = Path(args.out_dir) if args.out_dir else (resolve_draft_dir(task_dir) if task_dir else None)
    if out_dir is None:
        raise SystemExit("找不到任务目录。请用 --task-dir 指定。")
    ensure_dir(out_dir)

    confirm_params({"输出目录": str(out_dir), "软件名称": args.software_name, "项目目录": str(project), "任务目录": str(task_dir or out_dir.parent.parent)}, args.confirm)

    evidence = build_evidence(project, analysis, args.software_name, web_notes)
    write_json(out_dir / "业务理解证据.json", evidence)
    write_evidence_md(out_dir / "业务理解证据.md", evidence)

    if not args.model_context and not args.from_json:
        print(f"OK business evidence: {out_dir / '业务理解证据.md'}")
        print("NEXT_ACTION: 模型需要阅读业务理解证据和项目源码，以 references/业务理解模型稿模板.json 为骨架，自行编写业务理解模型稿 JSON，然后用 --model-context 生成业务理解.md/json。")
        return

    if args.from_json:
        context = read_json(Path(args.from_json))
        write_json(out_dir / "业务理解.json", context)
        write_context_md(out_dir / "业务理解.md", context)
        print(f"OK business context (from JSON): {out_dir / '业务理解.md'}")
        print(f"Features: {len(context.get('business_features', []))}")
        print("STOP_FOR_USER")
        print(f"NEXT_ACTION: {context.get('next_action', '请确认业务理解')}")
        return

    model = load_model_context(Path(args.model_context))
    context = normalize_model_context(model, evidence, web_notes)
    write_json(out_dir / "业务理解.json", context)
    write_context_md(out_dir / "业务理解.md", context)
    print(f"OK business context: {out_dir / '业务理解.md'}")
    print(f"Features: {len(context['business_features'])}")
    print("STOP_FOR_USER")
    print(f"NEXT_ACTION: {context['next_action']}")


if __name__ == "__main__":
    main()
