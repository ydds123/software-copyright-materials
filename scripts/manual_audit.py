#!/usr/bin/env python3
"""Unified planning and review artifacts for model-authored operation manuals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import read_json, write_json


PLAN_FILE = "操作手册写作计划.json"
REVIEW_FILE = "操作手册审查报告.json"

CROSS_REFERENCE_ITEMS = [
    "功能清单",
    "业务声明",
    "术语一致性",
    "状态值完备性",
    "截图引用",
    "按钮/字段名一致性",
    "FAQ 覆盖",
]

SEMANTIC_ITEMS = [
    "前后表述一致性",
    "状态机闭环",
    "角色路径完整",
    "FAQ覆盖矛盾检测",
    "功能清单与详情一致性",
]


def _load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _target_users(business: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in business.get("target_users") or []:
        if isinstance(item, dict):
            role = str(item.get("role") or item.get("name") or item.get("user_type") or "").strip()
            scenario = str(item.get("focus") or item.get("usage") or item.get("main_usage") or item.get("responsibility") or "").strip()
        else:
            role = str(item or "").strip()
            scenario = ""
        if role:
            rows.append({"role": role, "typical_scenario": scenario, "questions": []})
    return rows


def _terminology(business: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in business.get("glossary") or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("name") or "").strip()
        if term:
            rows.append({
                "standard_name": term,
                "definition": str(item.get("definition") or item.get("description") or "").strip(),
                "forbidden_aliases": item.get("forbidden_aliases") or [],
            })
    return rows


def _modules(business: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in business.get("manual_modules") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("feature") or "").strip()
        if not title:
            continue
        rows.append({
            "title": title,
            "module_type": item.get("module_type"),
            "client_endpoint": item.get("client_endpoint"),
            "entry": item.get("entry"),
            "evidence": item.get("evidence") or [],
            "completeness_review": item.get("completeness_review") or {"status": "pending"},
        })
    return rows


def build_writing_plan(business: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "草稿/业务理解.json",
        "terminology": _terminology(business),
        "chapter_responsibilities": [
            {"chapter": "系统简介", "responsibility": "说明定位、角色和完整业务链路", "excluded": "具体操作步骤"},
            {"chapter": "系统概述", "responsibility": "说明目标、范围、产品组成和结构", "excluded": "重复展开功能操作"},
            {"chapter": "功能清单", "responsibility": "汇总模块、细分功能和业务作用", "excluded": "操作步骤和异常处理"},
            {"chapter": "功能操作", "responsibility": "说明真实页面、用户动作、反馈和异常处理", "excluded": "重复系统定位"},
            {"chapter": "典型使用流程", "responsibility": "串联跨模块、跨角色和跨端流程", "excluded": "逐字段重复模块章节"},
            {"chapter": "常见问题解答", "responsibility": "回答真实使用问题", "excluded": "与正文矛盾或重复的大段说明"},
        ],
        "reader_coverage": _target_users(business),
        "modules": _modules(business),
        "menu_paths": {
            str(item.get("title") or item.get("feature") or ""): item.get("entry")
            for item in business.get("manual_modules") or []
            if isinstance(item, dict) and (item.get("title") or item.get("feature"))
        },
    }


def ensure_writing_plan(out_dir: Path, business: dict[str, Any]) -> dict[str, Any]:
    path = out_dir / PLAN_FILE
    plan = _load_optional(path)
    if plan:
        return plan
    plan = build_writing_plan(business)
    write_json(path, plan)
    return plan


def empty_checks(names: list[str]) -> dict[str, dict[str, str]]:
    return {name: {"status": "pending", "note": ""} for name in names}


def _legacy_markdown_checks(path: Path, names: list[str]) -> dict[str, dict[str, str]] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    unresolved = ("❌", "未通过", "TODO", "待处理", "待修复")
    if any(marker in text for marker in unresolved):
        return None
    if any(name not in text for name in names):
        return None
    return {name: {"status": "pass", "note": f"由旧版 {path.name} 迁移"} for name in names}


def _section_is_pending(section: Any, names: list[str]) -> bool:
    checks = section.get("checks") if isinstance(section, dict) else None
    if not isinstance(checks, dict):
        return True
    return all(
        str((checks.get(name) or {}).get("status") if isinstance(checks.get(name), dict) else checks.get(name) or "").lower()
        in {"", "pending"}
        for name in names
    )


def update_review_report(
    out_dir: Path,
    records: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    profile_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = out_dir / REVIEW_FILE
    report = _load_optional(path)
    report.setdefault("schema_version", 1)
    report["self_review"] = {
        "rounds": records,
        "module_count": len(modules),
        "template_profile": profile_summary,
    }
    report.setdefault("cross_reference", {"checks": empty_checks(CROSS_REFERENCE_ITEMS)})
    report.setdefault("semantic_consistency", {"checks": empty_checks(SEMANTIC_ITEMS)})
    if _section_is_pending(report.get("cross_reference"), CROSS_REFERENCE_ITEMS):
        legacy_cross = _legacy_markdown_checks(out_dir / "交叉引用验证报告.md", CROSS_REFERENCE_ITEMS)
        if legacy_cross:
            report["cross_reference"] = {"checks": legacy_cross}
    if _section_is_pending(report.get("semantic_consistency"), SEMANTIC_ITEMS):
        legacy_semantic = _legacy_markdown_checks(out_dir / "语义一致性审查报告.md", SEMANTIC_ITEMS)
        if legacy_semantic:
            report["semantic_consistency"] = {"checks": legacy_semantic}
    report.setdefault("reference_comparison", {})
    report["passed"] = review_report_passed(report)
    write_json(path, report)
    return report


def checks_pass(section: Any, required: list[str]) -> tuple[bool, list[str]]:
    checks = section.get("checks") if isinstance(section, dict) else None
    if not isinstance(checks, dict):
        return False, required
    missing = []
    for name in required:
        item = checks.get(name)
        status = str(item.get("status") if isinstance(item, dict) else item or "").lower()
        if status not in {"pass", "passed", "ok", "通过"}:
            missing.append(name)
    return not missing, missing


def review_report_passed(report: dict[str, Any]) -> bool:
    rounds = ((report.get("self_review") or {}).get("rounds") or [])
    self_ok = bool(rounds) and all(not (item.get("issues") or []) for item in rounds if isinstance(item, dict))
    cross_ok = checks_pass(report.get("cross_reference"), CROSS_REFERENCE_ITEMS)[0]
    semantic_ok = checks_pass(report.get("semantic_consistency"), SEMANTIC_ITEMS)[0]
    return self_ok and cross_ok and semantic_ok


def load_review_report(draft_dir: Path) -> dict[str, Any]:
    return _load_optional(draft_dir / REVIEW_FILE)


def plan_aliases(plan: dict[str, Any]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for item in plan.get("terminology") or []:
        if not isinstance(item, dict):
            continue
        standard = str(item.get("standard_name") or "").strip()
        aliases = item.get("forbidden_aliases") or []
        if isinstance(aliases, str):
            aliases = [value.strip() for value in aliases.replace(",", "、").split("、") if value.strip()]
        if standard:
            rows.append((standard, [str(value).strip() for value in aliases if str(value).strip()]))
    return rows
