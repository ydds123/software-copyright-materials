#!/usr/bin/env python3
"""Extract structural/narrative quality profile from a reference operation manual.

Produces a JSON profile describing:
- Section hierarchy: which headings exist and their depth
- Module chapter patterns: table types present per module, char density
- Narrative patterns: paragraph density, FAQ depth, glossary format
- This profile drives the comparison gate (compare_reference.py) and can
  be used to tighten quality thresholds in manual_template_profile.json.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def extract_section_tree(text: str) -> dict[str, Any]:
    """Extract heading hierarchy from the manual."""
    headings: list[dict[str, str | int]] = []
    for m in re.finditer(r"^(#{2,4})\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$", text, re.MULTILINE):
        level = len(m.group(1))  # ## = 2, ### = 3, #### = 4
        headings.append({
            "level": level,
            "number": m.group(2),
            "title": m.group(3).strip(),
        })
    return {
        "h2_count": sum(1 for h in headings if h["level"] == 2),
        "h3_count": sum(1 for h in headings if h["level"] == 3),
        "h4_count": sum(1 for h in headings if h["level"] == 4),
        "headings": headings,
    }


def extract_module_chapters(text: str) -> list[dict[str, Any]]:
    """Find all module operation chapters (under section 6) and profile them."""
    # Find section 6 content
    m6 = re.search(r"^##\s+6\s+.+?\n(.*?)(?=^##\s+7\s+)", text, re.MULTILINE | re.DOTALL)
    if not m6:
        return []

    section6 = m6.group(1)
    modules: list[dict[str, Any]] = []

    # Split by ### headings
    parts = re.split(r"^(?=###\s+\d+\.\d+\s+)", section6, flags=re.MULTILINE)
    for part in parts:
        if not part.strip():
            continue
        heading_match = re.match(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$", part, re.MULTILINE)
        if not heading_match:
            continue
        module_num = heading_match.group(1)
        module_name = heading_match.group(2).strip()

        # Detect module type tag
        type_match = re.search(r">\s*\*{0,2}模块类型[：:]\s*(.+?)\*{0,2}\s*", part)
        module_type_tag = type_match.group(1).strip() if type_match else None

        # Count tables
        tables = list(re.finditer(r"^\|.+\|$", part, re.MULTILINE))
        table_lines = len(tables)

        # Find specific table types
        has_list_table = bool(re.search(r"列表展示字段|列表界面", part))
        has_form_table = bool(re.search(r"字段名称\s*\|\s*字段类型", part))
        has_step_table = bool(re.search(r"操作步骤\s*\|\s*用户操作", part))
        has_exception_table = bool(re.search(r"异常功能逻辑|异常情况", part))
        has_module_purpose_para = bool(re.search(r"本模块", part))

        # Count 操作路径
        has_operation_path = bool(re.search(r"操作路径[：:]", part))

        # Char density
        char_count = len(part)

        modules.append({
            "number": module_num,
            "name": module_name,
            "module_type_tag": module_type_tag,
            "char_count": char_count,
            "table_lines": table_lines,
            "has_list_table": has_list_table,
            "has_form_table": has_form_table,
            "has_step_table": has_step_table,
            "has_exception_table": has_exception_table,
            "has_module_purpose_para": has_module_purpose_para,
            "has_operation_path": has_operation_path,
        })

    return modules


def extract_narrative_metrics(text: str) -> dict[str, Any]:
    """Extract paragraph density and narrative patterns."""
    # Count continuous prose paragraphs (non-table, non-heading, non-blank lines)
    paragraphs = re.findall(
        r"(?<!\|)(?<!#)(?<!\n\n)(?:\S.{50,}?)(?=\n\n|\n$|\Z)",
        text,
        re.MULTILINE,
    )

    # FAQ section depth
    faq_section = re.search(
        r"(?m)^##\s+\d+\s+常见问题解答\s*$\n(.*?)(?=\Z|^##\s+\d+\s+)",
        text, re.DOTALL,
    )
    faq_count = 0
    faq_avg_answer_chars = 0
    if faq_section:
        faq_questions = re.findall(r"\*\*问[：:].+?\*\*", faq_section.group(1))
        faq_count = len(faq_questions)
        # Rough answer length estimate
        if faq_count:
            faq_answers = re.split(r"\*\*问[：:].+?\*\*", faq_section.group(1))
            answers_text = " ".join(faq_answers[1:])  # skip pre-first-question text
            faq_avg_answer_chars = len(answers_text) // max(faq_count, 1)

    # Glossary section
    glossary_section = re.search(
        r"(?m)^##\s+\d+\s+术语表\s*$\n(.*?)(?=\Z|^##\s+\d+\s+)",
        text, re.DOTALL,
    )
    glossary_terms = 0
    if glossary_section:
        glossary_terms = len(re.findall(r"^\|.+\|.+", glossary_section.group(1), re.MULTILINE))

    # System intro: check for continuous narrative paragraphs (not bullet points)
    intro_section = re.search(
        r"^##\s+1\s+系统简介\s*$\n(.*?)(?=^##\s+2\s+)",
        text, re.MULTILINE | re.DOTALL,
    )
    intro_paras = 0
    if intro_section:
        intro_paras = len(re.findall(r"\n\n(?!\||#|【)", intro_section.group(1)))

    return {
        "total_chars": len(text),
        "paragraph_count": len(paragraphs),
        "intro_narrative_paragraphs": intro_paras,
        "faq_count": faq_count,
        "faq_avg_answer_chars": faq_avg_answer_chars,
        "glossary_terms": glossary_terms,
    }


def extract_profile(reference_path: Path) -> dict[str, Any]:
    """Extract complete reference profile from a manual .md file."""
    text = reference_path.read_text(encoding="utf-8")
    sections = extract_section_tree(text)
    modules = extract_module_chapters(text)
    narrative = extract_narrative_metrics(text)

    # Derive expected module structure based on module type tags
    expected_tables_by_type: dict[str, list[str]] = {}
    for mod in modules:
        tag = mod.get("module_type_tag") or ""
        if "台账型" in tag:
            expected = ["list_view", "form_fields", "step_table", "exception_table"]
        elif "业务型" in tag:
            expected = ["step_table", "exception_table"]
        elif "混合型" in tag:
            expected = ["list_view", "form_fields", "step_table", "exception_table"]
        else:
            expected = ["step_table", "exception_table"]
        expected_tables_by_type[mod["name"]] = expected

    # Module char density baseline (median across modules)
    module_chars = [m["char_count"] for m in modules]
    median_module_chars = sorted(module_chars)[len(module_chars) // 2] if module_chars else 0

    profile = {
        "reference_path": str(reference_path),
        "sections": sections,
        "module_count": len(modules),
        "modules": modules,
        "narrative": narrative,
        "expected_tables_by_type": expected_tables_by_type,
        "median_module_chars": median_module_chars,
        "expected_faq_count": narrative["faq_count"],
        "expected_glossary_terms": narrative["glossary_terms"],
    }

    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract reference profile from a manual .md")
    parser.add_argument("--reference", required=True, type=Path, help="Path to reference manual .md")
    parser.add_argument("--out", required=True, type=Path, help="Output JSON profile path")
    args = parser.parse_args()

    if not args.reference.exists():
        raise SystemExit(f"Reference file not found: {args.reference}")

    profile = extract_profile(args.reference)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: reference profile extracted → {args.out}")
    print(f"  Modules: {profile['module_count']}")
    print(f"  FAQ count: {profile['narrative']['faq_count']}")
    print(f"  Glossary terms: {profile['narrative']['glossary_terms']}")
    print(f"  Median module chars: {profile['median_module_chars']}")


if __name__ == "__main__":
    main()
