#!/usr/bin/env python3
"""Compare a generated operation manual against a reference profile.

Outputs an actionable gap report covering:
- Section structure (missing sections, depth gaps)
- Module chapter quality (char density, missing table types, missing patterns)
- Narrative quality (paragraph count, FAQ depth, glossary coverage)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# Reuse the extraction logic from extract_reference_profile
import sys as _sys
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in _sys.path:
    _sys.path.insert(0, str(_script_dir))

try:
    from extract_reference_profile import extract_module_chapters, extract_narrative_metrics, extract_section_tree
except ImportError:
    # Fallback: inline minimal extraction if import fails in some envs
    def extract_section_tree(text: str) -> dict[str, Any]:
        headings = []
        for m in re.finditer(r"^(#{2,4})\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$", text, re.MULTILINE):
            headings.append({"level": len(m.group(1)), "number": m.group(2), "title": m.group(3).strip()})
        return {"h2_count": sum(1 for h in headings if h["level"] == 2), "headings": headings}

    def extract_module_chapters(text: str) -> list[dict[str, Any]]:
        m6 = re.search(r"^##\s+6\s+.+?\n(.*?)(?=^##\s+7\s+)", text, re.MULTILINE | re.DOTALL)
        if not m6:
            return []
        parts = re.split(r"^(?=###\s+\d+\.\d+\s+)", m6.group(1), flags=re.MULTILINE)
        modules = []
        for part in parts:
            hm = re.match(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$", part, re.MULTILINE)
            if not hm:
                continue
            modules.append({
                "number": hm.group(1),
                "name": hm.group(2).strip(),
                "module_type_tag": (re.search(r">\s*\*{0,2}模块类型[：:]\s*(.+?)\*{0,2}\s*", part) or [None, None])[1],
                "char_count": len(part),
                "table_lines": len(re.findall(r"^\|.+\|$", part, re.MULTILINE)),
                "has_list_table": bool(re.search(r"列表展示字段|列表界面", part)),
                "has_form_table": bool(re.search(r"字段名称\s*\|\s*字段类型", part)),
                "has_step_table": bool(re.search(r"操作步骤\s*\|\s*用户操作", part)),
                "has_exception_table": bool(re.search(r"异常功能逻辑|异常情况", part)),
                "has_module_purpose_para": bool(re.search(r"本模块", part)),
                "has_operation_path": bool(re.search(r"操作路径[：:]", part)),
            })
        return modules

    def extract_narrative_metrics(text: str) -> dict[str, Any]:
        faq_s = re.search(r"(?m)^##\s+\d+\s+常见问题解答\s*$\n(.*?)(?=\Z|^##\s+\d+\s+)", text, re.DOTALL)
        faq_count = 0
        if faq_s:
            faq_count = len(re.findall(r"\*\*问[：:].+?\*\*", faq_s.group(1)))
        glossary_s = re.search(r"(?m)^##\s+\d+\s+术语表\s*$\n(.*?)(?=\Z|^##\s+\d+\s+)", text, re.DOTALL)
        glossary_terms = 0
        if glossary_s:
            glossary_terms = len(re.findall(r"^\|.+\|.+", glossary_s.group(1), re.MULTILINE))
        intro_s = re.search(r"^##\s+1\s+系统简介\s*$\n(.*?)(?=^##\s+2\s+)", text, re.MULTILINE | re.DOTALL)
        intro_paras = 0
        if intro_s:
            intro_paras = len(re.findall(r"\n\n(?!\||#|【)", intro_s.group(1)))
        return {
            "total_chars": len(text),
            "faq_count": faq_count,
            "glossary_terms": glossary_terms,
            "intro_narrative_paragraphs": intro_paras,
        }


def _normalize_name(name: str) -> str:
    """Strip module type suffixes and whitespace for fuzzy matching between reference and target."""
    return name.strip()


def _find_matching_target_module(ref_name: str, target_modules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find target module matching reference by name similarity."""
    ref_normalized = _normalize_name(ref_name)
    for tm in target_modules:
        target_normalized = _normalize_name(tm["name"])
        # Exact match first
        if ref_normalized == target_normalized:
            return tm
        # Contains match
        if ref_normalized in target_normalized or target_normalized in ref_normalized:
            return tm
    return None


def _find_module_has_table(module_name: str, table_key: str, target_modules: list[dict[str, Any]]) -> bool:
    """Check if a specific module has a given table type."""
    for tm in target_modules:
        if _normalize_name(tm["name"]) == _normalize_name(module_name):
            key_map = {
                "list_table": "has_list_table",
                "form_table": "has_form_table",
                "step_table": "has_step_table",
                "exception_table": "has_exception_table",
            }
            return bool(tm.get(key_map.get(table_key, table_key)))
    return False


def compare(reference_path: Path, target_path: Path) -> dict[str, Any]:
    """Compare target manual against reference, produce gap report."""
    ref_text = reference_path.read_text(encoding="utf-8")
    target_text = target_path.read_text(encoding="utf-8")

    ref_sections = extract_section_tree(ref_text)
    target_sections = extract_section_tree(target_text)
    ref_modules = extract_module_chapters(ref_text)
    target_modules = extract_module_chapters(target_text)
    ref_narrative = extract_narrative_metrics(ref_text)
    target_narrative = extract_narrative_metrics(target_text)

    gaps: list[dict[str, str]] = []  # {severity, category, detail}
    warnings: list[dict[str, str]] = []

    # ── 1. Section structure comparison ──
    ref_h2_titles = {h["title"] for h in ref_sections.get("headings", []) if h["level"] == 2}
    target_h2_titles = {h["title"] for h in target_sections.get("headings", []) if h["level"] == 2}
    missing_sections = ref_h2_titles - target_h2_titles
    for s in missing_sections:
        gaps.append({"severity": "error", "category": "section_structure", "detail": f"缺少参照手册中的一级章节：{s}"})

    extra_sections = target_h2_titles - ref_h2_titles
    for s in extra_sections:
        warnings.append({"severity": "warn", "category": "section_structure", "detail": f"目标手册比参照多出一级章节：{s}"})

    # ── 2. Module chapter comparison ──
    # Compare structural patterns per module TYPE, not by name.
    # Build reference patterns by module type
    ref_type_patterns: dict[str, dict[str, float]] = {}
    for ref_mod in ref_modules:
        tag = ref_mod.get("module_type_tag") or "未知"
        base = "台账型" if "台账" in tag else ("业务型" if "业务" in tag else ("混合型" if "混合" in tag else "未知"))
        if base not in ref_type_patterns:
            ref_type_patterns[base] = {"count": 0, "char_total": 0, "list_table": 0, "form_table": 0, "step_table": 0, "exception_table": 0, "purpose_para": 0, "operation_path": 0}
        p = ref_type_patterns[base]
        p["count"] += 1
        p["char_total"] += ref_mod["char_count"]
        if ref_mod["has_list_table"]: p["list_table"] += 1
        if ref_mod["has_form_table"]: p["form_table"] += 1
        if ref_mod["has_step_table"]: p["step_table"] += 1
        if ref_mod["has_exception_table"]: p["exception_table"] += 1
        if ref_mod["has_module_purpose_para"]: p["purpose_para"] += 1
        if ref_mod["has_operation_path"]: p["operation_path"] += 1

    # Classify target modules by type
    target_type_patterns: dict[str, dict[str, Any]] = {}
    for target_mod in target_modules:
        tag = target_mod.get("module_type_tag") or "未知"
        base = "台账型" if "台账" in tag else ("业务型" if "业务" in tag else ("混合型" if "混合" in tag else "未知"))
        if base not in target_type_patterns:
            target_type_patterns[base] = {"count": 0, "char_total": 0, "list_table": 0, "form_table": 0, "step_table": 0, "exception_table": 0, "purpose_para": 0, "operation_path": 0, "modules": []}
        p = target_type_patterns[base]
        p["count"] += 1
        p["char_total"] += target_mod["char_count"]
        if target_mod["has_list_table"]: p["list_table"] += 1
        if target_mod["has_form_table"]: p["form_table"] += 1
        if target_mod["has_step_table"]: p["step_table"] += 1
        if target_mod["has_exception_table"]: p["exception_table"] += 1
        if target_mod["has_module_purpose_para"]: p["purpose_para"] += 1
        if target_mod["has_operation_path"]: p["operation_path"] += 1
        p["modules"].append(target_mod["name"])

    # Compare per type: every reference type should exist in target
    for rtype, rp in ref_type_patterns.items():
        if rtype == "未知":
            continue
        tp = target_type_patterns.get(rtype)
        if not tp:
            # Fallback: check if target has modules at all
            if target_modules:
                warnings.append({
                    "severity": "warn",
                    "category": "module_type_missing",
                    "detail": '参照手册中存在「' + rtype + '」模块，但目标手册未标记模块类型。建议为每个模块添加「> 模块类型：台账型/业务型」标签'
                })
            continue

        # Char density: median chars per module of this type
        ref_avg_chars = rp["char_total"] / rp["count"]
        target_avg_chars = tp["char_total"] / tp["count"]
        if target_avg_chars < ref_avg_chars * 0.5:
            gaps.append({
                "severity": "error",
                "category": "module_type_depth",
                "detail": '「' + rtype + '」模块平均内容偏薄：目标每模块' + str(int(target_avg_chars)) + '字 vs 参照' + str(int(ref_avg_chars)) + '字（低于50%）'
            })
        elif target_avg_chars < ref_avg_chars * 0.75:
            warnings.append({
                "severity": "warn",
                "category": "module_type_depth",
                "detail": '「' + rtype + '」模块平均内容偏薄：目标每模块' + str(int(target_avg_chars)) + '字 vs 参照' + str(int(ref_avg_chars)) + '字（低于75%）'
            })

        # Table coverage: expected tables per this type
        target_modules_of_type = tp.get("modules", [])
        for table_key, table_label, ref_ratio in [
            ("list_table", "列表界面表", rp["list_table"] / rp["count"]),
            ("form_table", "新增/修改字段表", rp["form_table"] / rp["count"]),
            ("step_table", "4列操作步骤表", rp["step_table"] / rp["count"]),
            ("exception_table", "异常功能逻辑表", rp["exception_table"] / rp["count"]),
        ]:
            if ref_ratio >= 0.8 and tp[table_key] < tp["count"] * 0.8:
                missing_mods = [m for m in target_modules_of_type if not _find_module_has_table(m, table_key, target_modules)]
                gaps.append({
                    "severity": "error",
                    "category": "module_table_missing",
                    "detail": '「' + rtype + '」模块中缺少' + table_label + '（参照同类模块中该表覆盖率为' + str(int(ref_ratio * 100)) + '%）：' + "、".join(missing_mods[:4])
                })

        # Operation path
        if rp["operation_path"] / rp["count"] >= 0.8 and tp["operation_path"] < tp["count"] * 0.8:
            warnings.append({
                "severity": "warn",
                "category": "module_pattern",
                "detail": '「' + rtype + '」模块中部分缺少操作路径声明'
            })

    # ── 3. Narrative quality comparison ──
    if target_narrative["faq_count"] < ref_narrative["faq_count"]:
        gaps.append({
            "severity": "error",
            "category": "faq_count",
            "detail": f"FAQ数量不足：目标{target_narrative['faq_count']}条 vs 参照{ref_narrative['faq_count']}条"
        })

    if target_narrative["glossary_terms"] < ref_narrative["glossary_terms"] * 0.5:
        gaps.append({
            "severity": "error",
            "category": "glossary_depth",
            "detail": f"术语表覆盖不足：目标{target_narrative['glossary_terms']}条 vs 参照{ref_narrative['glossary_terms']}条"
        })

    if target_narrative["intro_narrative_paragraphs"] < ref_narrative["intro_narrative_paragraphs"] * 0.5:
        gaps.append({
            "severity": "error",
            "category": "intro_narrative",
            "detail": f"系统简介叙事段落不足：目标{target_narrative['intro_narrative_paragraphs']}段 vs 参照{ref_narrative['intro_narrative_paragraphs']}段"
        })

    # ── 4. Overall density ──
    ref_total = ref_narrative["total_chars"]
    target_total = target_narrative["total_chars"]
    if target_total < ref_total * 0.5:
        gaps.append({
            "severity": "error",
            "category": "overall_density",
            "detail": f"总体内容厚度不足：目标{target_total}字 vs 参照{ref_total}字（低于50%）"
        })
    elif target_total < ref_total * 0.75:
        warnings.append({
            "severity": "warn",
            "category": "overall_density",
            "detail": f"总体内容偏薄：目标{target_total}字 vs 参照{ref_total}字（低于75%）"
        })

    errors = [g for g in gaps if g["severity"] == "error"]
    return {
        "reference_path": str(reference_path),
        "target_path": str(target_path),
        "passed": len(errors) == 0,
        "total_gaps": len(gaps),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "ref_metrics": {
            "total_chars": ref_narrative["total_chars"],
            "module_count": len(ref_modules),
            "faq_count": ref_narrative["faq_count"],
            "glossary_terms": ref_narrative["glossary_terms"],
        },
        "target_metrics": {
            "total_chars": target_narrative["total_chars"],
            "module_count": len(target_modules),
            "faq_count": target_narrative["faq_count"],
            "glossary_terms": target_narrative["glossary_terms"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare manual against reference profile")
    parser.add_argument("--reference", required=True, type=Path, help="Path to reference manual .md")
    parser.add_argument("--target", required=True, type=Path, help="Path to generated manual .md")
    parser.add_argument("--out", type=Path, help="Output JSON report path (optional)")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if gaps found")
    args = parser.parse_args()

    if not args.reference.exists():
        raise SystemExit(f"Reference file not found: {args.reference}")
    if not args.target.exists():
        raise SystemExit(f"Target file not found: {args.target}")

    result = compare(args.reference, args.target)

    # Print report
    print("=" * 60)
    print("参照手册对比报告")
    print("=" * 60)
    print()
    print(f"参照: {result['reference_path']}")
    print(f"目标: {result['target_path']}")
    print()
    print(f"结果: {'PASSED' if result['passed'] else 'FAILED'}")
    print(f"  {result['error_count']} errors, {result['warning_count']} warnings")
    print()
    print("--- 指标对比 ---")
    print(f"  总字数:  目标 {result['target_metrics']['total_chars']} vs 参照 {result['ref_metrics']['total_chars']}")
    print(f"  模块数:  目标 {result['target_metrics']['module_count']} vs 参照 {result['ref_metrics']['module_count']}")
    print(f"  FAQ 数:  目标 {result['target_metrics']['faq_count']} vs 参照 {result['ref_metrics']['faq_count']}")
    print(f"  术语数:  目标 {result['target_metrics']['glossary_terms']} vs 参照 {result['ref_metrics']['glossary_terms']}")

    if result["errors"]:
        print()
        print("--- ERROR ---")
        for e in result["errors"]:
            print(f"  ❌ [{e['category']}] {e['detail']}")

    if result["warnings"]:
        print()
        print("--- WARNING ---")
        for w in result["warnings"]:
            print(f"  ⚠️  [{w['category']}] {w['detail']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nReport saved → {args.out}")

    if args.strict and not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
