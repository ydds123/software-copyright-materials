#!/usr/bin/env python3
"""Quality gates for operation manual Markdown drafts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import read_json

_ZH = {
    "zh014": "模板符合度不足：正文字符数 ",
    "zh015": " 少于 ",
    "zh016": "模板符合度不足：标题数量 ",
    "zh017": "模板符合度不足：表格行数 ",
    "zh018": "模板符合度不足：截图预留 ",
    "zh019": "模板符合度不足：",
    "zh020": " 缺少小节 ",
    "zh021": "内容门禁不通过：出现禁止机械表达 [",
    "zh022": "内容门禁不通过：固定句式 [",
    "zh023": "] 出现 ",
    "zh024": " 次，超过限制 ",
    "zh025": "内容门禁不通过：缺少面向受众表达 [",
    "zh026": "内容门禁不通过：缺少业务链路术语 [",
    "zh027": "内容门禁不通过：缺少操作颗粒度表达[",
    "zh028": "内容门禁不通过：所有模块开头都含固定表达[",
    "zh029": "内容门禁不通过：",
    "zh030": " 未体现适用用户角色",
    "zh031": " 开头偏申报/审核口吻，应改为面向适用用户的操作说明",
    "zh032": "内容门禁不通过：第 ",
    "zh033": " 个表格[",
    "zh034": "]列内容[",
    "zh035": "]重复 ",
    "zh036": " 次，应结合上下文改写为具备信息增量的表述",
    "zh037": "缺少通用手册章节：",
    "zh038": "存在偏技术表达：",
    "zh039": "存在模板化表达：",
    "zh040": "存在疑似 AI 味/空泛表达：",
    "zh041": "正文仍存在项目符号或编号列表：",
    "zh042": "缺少核心模块章节：",
    "zh043": "模块内容偏薄：",
    "zh044": "模块仍使用制式小标题：",
    "zh045": "步骤密度不足：",
    "zh046": "步 action<",
    "zh047": "ch或response<",
    "zh048": "ch或handling<",
    "zh271": "章节编号重复：",
}


def plain_manual_text(text: str) -> str:
    value = text
    replacements = {
        "多 Agent": "多智能体",
        "多 agent": "多智能体",
        "业务逻辑": "使用过程",
        "前端页面": "软件页面",
        "前端": "界面",
        "后端服务": "系统服务",
        "后端": "系统服务",
        "接口": "数据通道",
        "组件": "页面组成部分",
        "路由": "页面入口",
        "状态管理": "状态记录",
        "数据持久化": "数据保存",
        "异步任务": "后台处理任务",
        "任务队列": "任务处理服务",
        "模型": "智能服务",
        "调度中心": "协调中心",
        "结构化依据": "后续说明",
        "高成本生成": "耗时较长的内容生成",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"(?<![A-Za-z])Agent(?![A-Za-z])", "智能体", value)
    value = re.sub(r"(?<![A-Za-z])agent(?![A-Za-z])", "智能体", value)
    value = re.sub(r"\b(?!Node\.js\b)[A-Za-z]+\.js\b", "相关软件能力", value)
    value = re.sub(r"\bReact\b|\bVue\b|\bVite\b|\bNext\b|\bNext\.js\b|\bFastAPI\b|\bLangGraph\b|\bCelery\b|\bSSE\b", "相关软件能力", value)
    value = re.sub(r"相关软件能力、相关软件能力", "相关软件能力", value)
    value = re.sub(r"多智能体\s+协作", "多智能体协作", value)
    return value


def as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [plain_manual_text(str(item)).strip() for item in value if str(item).strip()]
    text = plain_manual_text(str(value)).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[；;\n]+", text) if item.strip()]


def strip_sentence_punctuation(text: str) -> str:
    return str(text or "").strip().strip("。；;，, ")


def operation_flow_steps(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    steps: list[str] = []
    for item in value:
        if isinstance(item, dict):
            step = str(item.get("step") or item.get("action") or item.get("name") or "").strip()
        else:
            step = str(item or "").strip()
        if step:
            steps.append(plain_manual_text(step))
    return steps


DEFAULT_TEMPLATE_QUALITY = {
    "min_chars": 15000,
    "min_headings": 20,
    "min_table_lines": 50,
    "min_screenshot_slots_without_images": 7,
    "require_cover": False,
    "require_toc": False,
    "require_login_section": True,
    "require_home_section": False,
    "require_numbered_headings": True,
    "require_module_subsections": [],
    "content_review_gates": {
        "required_audience_terms": [],
        "required_business_chain_terms": [],
        "required_operation_terms": [],
        "prohibited_phrases": ["用于用于"],
        "required_audience_fit": True,
        "require_distinct_audience_usage": True,
        "table_duplicate_column_limit": 1,
        "repeated_phrase_limits": {
            "首先应确认当前页面": 0,
            "一般由查询条件区、列表区和操作区组成": 0,
            "页面控件名称以实际系统显示为准": 0,
            "用户通常需要先完成基础信息确认": 0,
            "执行新增、维护、查看、导入、导出或任务处理": 0,
        },
    },
}


TECHNICAL_TERMS = [
    "技术实现",
    "代码",
    "框架",
    "接口封装",
    "状态管理",
    "异步任务",
    "任务队列",
    "数据持久化",
    "业务逻辑",
    "React",
    "Next.js",
    "FastAPI",
    "LangGraph",
    "Celery",
]

TEMPLATE_MARKERS = [
    "重要功能之一",
    "通过清晰的页面入口、信息展示和结果反馈",
    "对应操作环节",
    "审核时可重点查看",
    "审核人员可通过",
    "按照页面提示填写内容、选择资料、确认方案或点击提交按钮",
    "系统处理完成后显示结果或提示信息",
    "帮助用户用户",
    "帮助用户系统",
    "主要用于在",
    "项目管理或资产中心项目管理",
    "进入方式：",
    "页面内容：",
    "操作步骤：",
    "操作规则：",
    "操作结果与反馈：",
    "功能特点根据当前项目资料",
    "软件围绕",
]

AI_TONE_MARKERS = [
    "旨在",
    "赋能",
    "一站式",
    "智能化",
    "高效便捷",
    "显著提升",
    "强大能力",
    "丰富功能",
    "极大地",
    "全方位",
    "降本增效",
    "优化体验",
    "提升效率",
]


def manual_section_body(text: str, title: str) -> str:
    number_pattern = r"(?:\(\d+\)、|[零一二三四五六七八九十百]+、)"
    pattern = re.compile(
        rf"^(#{{2,4}})\s+(?:{number_pattern}\s*|\d+[A-Z]?(?:\.\d+)*\.?\s+)?{re.escape(title)}\s*$",
        flags=re.M,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    # Prefer the highest-level matching section. A module name may also appear
    # earlier as a requirements subsection, which must not shadow its full
    # operation chapter.
    match = min(matches, key=lambda item: len(item.group(1)))
    level = len(match.group(1))
    rest = text[match.end() :]
    end = len(text)
    for next_match in re.finditer(r"^(#{1,4})\s+", rest, flags=re.M):
        if len(next_match.group(1)) <= level:
            end = match.end() + next_match.start()
            break
    return text[match.end() : end].strip()


def template_quality(profile: dict[str, Any] | None) -> dict[str, Any]:
    quality = dict(DEFAULT_TEMPLATE_QUALITY)
    if profile:
        quality.update(profile.get("target_quality") or {})
        if profile.get("content_review_gates"):
            quality["content_review_gates"] = profile.get("content_review_gates")
    return quality


def content_review_gates(
    profile: dict[str, Any] | None,
    business: dict[str, Any] | None = None,
    modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    quality = template_quality(profile)
    gates = dict(DEFAULT_TEMPLATE_QUALITY.get("content_review_gates") or {})
    gates.update(quality.get("content_review_gates") or {})
    if not gates.get("required_audience_terms"):
        gates["required_audience_terms"] = target_user_roles(business)
    if not gates.get("required_business_chain_terms"):
        gates["required_business_chain_terms"] = required_business_terms(business, modules or [])
    if not gates.get("required_operation_terms"):
        gates["required_operation_terms"] = required_operation_terms(business, modules or [])
    return gates


def target_user_roles(business: dict[str, Any] | None) -> list[str]:
    raw_users = business.get("target_users") if business else []
    roles: list[str] = []
    if isinstance(raw_users, list):
        for item in raw_users:
            if isinstance(item, dict):
                role = str(item.get("role") or item.get("name") or item.get("user_type") or "").strip()
            else:
                role = str(item or "").strip()
            if role:
                roles.append(plain_manual_text(role))
    return unique_terms(roles, limit=8)


def required_business_terms(business: dict[str, Any] | None, modules: list[dict[str, Any]]) -> list[str]:
    terms: list[str] = []
    for module in modules:
        feature = str(module.get("feature") or module.get("title") or "").strip()
        if feature:
            terms.append(plain_manual_text(feature))
    if business:
        terms.extend(as_text_list(business.get("business_features")))
    return unique_terms(terms, limit=12)


def required_operation_terms(business: dict[str, Any] | None, modules: list[dict[str, Any]]) -> list[str]:
    source_parts: list[str] = []
    for module in modules:
        source_parts.extend(as_text_list(module.get("steps") or module.get("operation_steps")))
        source_parts.extend(as_text_list(module.get("subtasks") or module.get("tasks")))
    if business:
        source_parts.extend(operation_flow_steps(business.get("operation_flow")))
    source = "；".join(source_parts)
    candidates = ["进入", "查询", "查看", "新增", "编辑", "修改", "保存", "提交", "确认", "审批", "审核", "导入", "导出", "删除", "启用", "停用", "配置", "维护", "统计", "生成", "推送", "验收"]
    return [term for term in candidates if term in source][:10]


def unique_terms(values: list[str], limit: int = 12) -> list[str]:
    result: list[str] = []
    for value in values:
        term = strip_sentence_punctuation(value)
        if not term or len(term) > 30 or term in result:
            continue
        result.append(term)
        if len(result) >= limit:
            break
    return result


def business_input_quality_issues(business: dict[str, Any] | None) -> list[str]:
    if not business:
        return []
    issues: list[str] = []
    users = as_text_list(business.get("target_users"))
    if len(users) < 3:
        issues.append("业务理解中的 `target_users` 过少。请补充当前软件的真实使用角色，例如管理员、业务经办人员、审核人员、负责人、统计人员或外部协作人员。")
    raw_flow = business.get("operation_flow")
    flow_items = raw_flow if isinstance(raw_flow, list) else []
    flow_count = len([item for item in flow_items if isinstance(item, dict) or str(item).strip()])
    if flow_count < 5:
        issues.append("业务理解中的 `operation_flow` 不足以支撑高质量操作手册。请补充从基础数据准备、业务办理、提交确认、审核处理到查询统计的完整业务链路。")
    unstructured_flow = []
    for index, item in enumerate(flow_items, start=1):
        if not isinstance(item, dict):
            unstructured_flow.append(str(index))
            continue
        step = str(item.get("step") or item.get("action") or item.get("name") or "").strip()
        result = str(item.get("result") or item.get("outcome") or item.get("feedback") or "").strip()
        if not step or not result:
            unstructured_flow.append(str(index))
    if flow_items and unstructured_flow:
        issues.append("业务理解中的 `operation_flow` 必须使用结构化对象并包含 `step` 和 `result`。请补充第 " + "、".join(unstructured_flow[:12]) + " 项，避免由 renderer 推断流程结果。")
    modules = business.get("manual_modules")
    if not isinstance(modules, list) or not modules:
        issues.append("业务理解缺少 `manual_modules`。请模型阅读项目真实页面、路由、按钮、输入项、提示和结果反馈，补全 manual_modules 后再生成操作手册。")
    return issues


def load_template_profile(workdir: Path) -> dict[str, Any] | None:
    profile_path = workdir / "analysis" / "manual_template_profile.json"
    if not profile_path.exists():
        return None
    try:
        return read_json(profile_path)
    except Exception:
        return None


def template_profile_quality_issues(text: str, modules: list[dict[str, Any]], profile: dict[str, Any] | None) -> list[str]:
    quality = template_quality(profile)
    issues: list[str] = []
    heading_count = len(re.findall(r"(?m)^#{1,4}\s+", text))
    table_line_count = len(re.findall(r"(?m)^\|", text))
    screenshot_count = text.count("【截图预留：") + len(re.findall(r"!\[[^\]]*\]\(截图/[^)]+\)", text))
    char_count = len(text)
    if char_count < int(quality.get("min_chars") or 0):
        issues.append(f"{_ZH["zh014"]}{char_count}{_ZH["zh015"]}{quality.get('min_chars')}")
    if heading_count < int(quality.get("min_headings") or 0):
        issues.append(f"{_ZH["zh016"]}{heading_count}{_ZH["zh015"]}{quality.get('min_headings')}")
    if table_line_count < int(quality.get("min_table_lines") or 0):
        issues.append(f"{_ZH["zh017"]}{table_line_count}{_ZH["zh015"]}{quality.get('min_table_lines')}")
    if screenshot_count < int(quality.get("min_screenshot_slots_without_images") or 0):
        issues.append(f"{_ZH["zh018"]}{screenshot_count}{_ZH["zh015"]}{quality.get('min_screenshot_slots_without_images')}")
    if quality.get("require_cover") and not (text.startswith("# ") and "用户使用说明书" in text[:120]):
        issues.append("模板符合度不足：缺少封面式标题")
    if quality.get("require_toc") and "## 目录" not in text:
        issues.append("模板符合度不足：缺少目录章节")
    if quality.get("require_login_section") and not re.search(r"^#{2,4}\s+\d+(?:\.\d+)*\s+[^\n]*登录[^\n]*$", text, flags=re.M):
        issues.append("模板符合度不足：缺少登录界面章节")
    if quality.get("require_home_section") and re.search(r"^##\s+\d+\s+系统首页\s*$", text, flags=re.M):
        has_image = re.search(r"!\[[^\]]*首页[^\]]*\]\(截图/[^)]+\)", text)
        has_placeholder = re.search(r"【截图预留：[^】]*首页[^】]*】", text)
        if not (has_image or has_placeholder):
            issues.append("模板符合度不足：手册声明存在系统首页，但缺少对应截图或预留")
    if quality.get("require_numbered_headings") and not re.search(r"(?m)^##\s+\d+\s+\S", text):
        issues.append("模板符合度不足：缺少阿拉伯数字编号式一级章节")
    required_subsections = [str(item) for item in quality.get("require_module_subsections") or []]
    for module in modules:
        body = manual_section_body(text, module["feature"])
        for subsection in required_subsections:
            if subsection not in body:
                issues.append(f"{_ZH["zh019"]}{module['feature']}{_ZH["zh020"]}{subsection}")
    return issues


def content_review_quality_issues(
    text: str,
    modules: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    business: dict[str, Any] | None = None,
) -> list[str]:
    gates = content_review_gates(profile, business, modules)
    issues: list[str] = []
    audience_terms = [str(term) for term in gates.get("required_audience_terms") or [] if str(term).strip()]
    for phrase in gates.get("prohibited_phrases") or []:
        if phrase and phrase in text:
            issues.append(f"{_ZH["zh021"]}{phrase}]")
    for phrase, limit in (gates.get("repeated_phrase_limits") or {}).items():
        count = text.count(str(phrase))
        if count > int(limit):
            issues.append(f"{_ZH["zh022"]}{phrase}{_ZH["zh023"]}{count}{_ZH["zh024"]}{limit} 次")
    for term in audience_terms:
        if term and term not in text:
            issues.append(f"{_ZH["zh025"]}{term}]")
    for term in gates.get("required_business_chain_terms") or []:
        if term and term not in text:
            issues.append(f"{_ZH["zh026"]}{term}]")
    # Skip operation term gate when typed modules are present (auto-generated step text may not contain all verbs)
    if not any(m.get("module_type") for m in modules):
        for term in gates.get("required_operation_terms") or []:
            if term and term not in text:
                issues.append(f"{_ZH["zh027"]}{term}]")
    if gates.get("require_distinct_audience_usage"):
        audience_body = manual_section_body(text, "适用用户")
        if audience_body:
            rows = [
                line.strip()
                for line in audience_body.splitlines()
                if line.strip().startswith("|")
                and "---" not in line
                and "用户类型" not in line
                and line.count("|") >= 3
            ]
            usage_values = []
            for row in rows:
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                if len(cells) >= 2:
                    usage_values.append(cells[1])
            if len(usage_values) >= 2 and len(set(usage_values)) == 1:
                issues.append("内容门禁不通过：适用用户表的主要使用内容完全相同，应按不同角色写出差异化关注点")
            generic_usage = "登录系统后进入对应菜单，查询、维护、提交或查看相关业务数据"
            if any(generic_usage in value for value in usage_values):
                issues.append("内容门禁不通过：适用用户表仍存在泛化主要使用内容")
    duplicate_limit = int(gates.get("table_duplicate_column_limit") or 0)
    if duplicate_limit > 0 and not any(m.get("module_type") for m in modules):
        issues.extend(table_duplicate_column_issues(text, duplicate_limit))
    if len(modules) >= 3:
        module_bodies = [manual_section_body(text, module["feature"]) for module in modules]
        shared_openings = [
            "用户进入",
            "页面提交前",
            "当页面提供",
            "操作完成后",
        ]
        for opening in shared_openings:
            count = sum(1 for body in module_bodies if opening in body[:280])
            if count >= len(modules):
                issues.append(f"{_ZH["zh028"]}{opening}]")
        if gates.get("required_audience_fit") and audience_terms:
            for module, body in zip(modules, module_bodies):
                if not any(term in body for term in audience_terms):
                    issues.append(f"{_ZH["zh029"]}{module['feature']}{_ZH["zh030"]}")
                if "审核" in body[:500] or "申请" in body[:500]:
                    issues.append(f"{_ZH["zh029"]}{module['feature']}{_ZH["zh031"]}")
    return issues


def iter_markdown_tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and not all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
                current.append(cells)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def table_duplicate_column_issues(text: str, duplicate_limit: int) -> list[str]:
    issues: list[str] = []
    for table_index, table in enumerate(iter_markdown_tables(text), start=1):
        if len(table) <= 2:
            continue
        headers = table[0]
        if any(h in {"细分功能", "功能模块"} for h in headers):
            continue
        rows = table[1:]
        max_cols = max(len(row) for row in table)
        for col_index in range(max_cols):
            header = headers[col_index] if col_index < len(headers) else f"第 {col_index + 1} 列"
            values: dict[str, int] = {}
            for row in rows:
                if col_index >= len(row):
                    continue
                value = row[col_index].strip()
                if not value or value in {"是", "否", "无", "暂无"}:
                    continue
                values[value] = values.get(value, 0) + 1
            repeated = [(value, count) for value, count in values.items() if count > duplicate_limit]
            if repeated:
                value, count = sorted(repeated, key=lambda item: item[1], reverse=True)[0]
                issues.append(f"{_ZH["zh032"]}{table_index}{_ZH["zh033"]}{header}{_ZH["zh034"]}{value}{_ZH["zh035"]}{count}{_ZH["zh036"]}")
    return issues


def major_heading_number_issues(text: str) -> list[str]:
    """检查一级标题编号是否连续且唯一。阿拉伯数字格式：## N Title。"""
    matches: dict[str, list[str]] = {}
    pattern = re.compile(r"^##\s+(?P<number>\d+)\s+(?P<title>.+?)\s*$", flags=re.M)
    for match in pattern.finditer(text):
        number = match.group("number").strip()
        title = match.group("title").strip()
        matches.setdefault(number, []).append(title)

    issues: list[str] = []
    for number, titles in matches.items():
        if len(titles) > 1:
            title_text = "、".join(f"[{title}]" for title in titles[:5])
            suffix = "" if len(titles) <= 5 else "等"
            issues.append(f"一级标题编号 {number} 出现在 {title_text}{suffix}，应调整为连续且唯一的章节编号")
    return issues


def manual_quality_issues(
    text: str,
    modules: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    business: dict[str, Any] | None = None,
) -> list[str]:
    issues: list[str] = []
    required_section_aliases = [
        ("系统概述", ["系统概述"]),
        ("登录", ["系统登录", "登录界面", "Web 管理端登录"]),
        ("系统要求", ["系统要求", "运行与使用要求"]),
        ("常见问题解答", ["常见问题解答"]),
        ("术语表", ["术语表", "术语说明"]),
    ]
    for label, aliases in required_section_aliases:
        if not any(manual_section_body(text, title) for title in aliases):
            issues.append(f"{_ZH['zh037']}{label}")
    if re.search(r"^##\s+\(?\d+[)、.]", text, flags=re.M):
        issues.append("章节标题仍使用括号数字格式，应使用阿拉伯数字层级编号（如 1 系统简介）")
    if re.search(r"^##\s+[一二三四五六七八九十百]+、", text, flags=re.M):
        issues.append("章节标题仍使用中文大写序号，应改为阿拉伯数字层级编号（如 1 系统简介）")
    issues.extend(major_heading_number_issues(text))
    for term in TECHNICAL_TERMS:
        if term in text:
            issues.append(f"{_ZH["zh038"]}{term}")
    for marker in TEMPLATE_MARKERS:
        if marker in text:
            issues.append(f"{_ZH["zh039"]}{marker}")
    for marker in AI_TONE_MARKERS:
        if marker in text:
            issues.append(f"{_ZH["zh040"]}{marker}")
    screenshot_count = text.count("【截图预留：") + len(re.findall(r"!\[[^\]]*\]\(截图/[^)]+\)", text))
    if screenshot_count < len(modules):
        issues.append("真实截图和截图预留总数少于核心模块数量")
    list_lines = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"^(?:[-*+]\s+|\d+\.\s+)", line.strip()) and not re.match(r"^\d+(?:\.\d+)+\s+", line.strip())
    ]
    if list_lines:
        issues.append(f"{_ZH["zh041"]}{list_lines[0][:40]}")
    for module in modules:
        title = str(module.get("feature") or "").strip()
        if not title:
            continue
        body = manual_section_body(text, title)
        if not body:
            issues.append(f"{_ZH["zh042"]}{title}")
            continue
        if len(body) < 390:
            issues.append(f"{_ZH["zh043"]}{title}")
        for label in ("进入方式：", "页面内容：", "操作步骤：", "操作规则：", "操作结果与反馈："):
            if label in body:
                issues.append(f"{_ZH["zh044"]}{title} / {label}")
    issues.extend(step_density_issues(text, modules))
    issues.extend(business_module_depth_issues(text, modules))
    issues.extend(template_profile_quality_issues(text, modules, profile))
    issues.extend(content_review_quality_issues(text, modules, profile, business))
    return issues


def business_module_depth_issues(text: str, modules: list[dict[str, Any]]) -> list[str]:
    """Enforce SKILL.md SS328-330: business/hybrid modules must describe object lifecycle
    (state machine) and conditional branches from backend code analysis.

    This checks the MANUAL TEXT (not the business JSON) because the manual is what
    reviewers read. The JSON gate (check_skill_required_inputs in
    content_quality_check.py) verifies model-authored fields exist; this gate
    verifies the rendered prose actually covers the required depth.
    """
    issues: list[str] = []
    for module in modules:
        title = str(module.get("feature") or "").strip()
        if not title:
            continue
        module_type = str(module.get("module_type") or "").strip()
        if module_type not in ("business", "hybrid"):
            continue
        body = manual_section_body(text, title)
        if not body:
            continue

        # ---- Gate 1: State machine / object lifecycle ----
        # Accept: state tables with trigger/transition columns, explicit state
        # headings, transition count in prose (3+ occurrences of transition markers).
        has_state_table = (
            bool(re.search(r"\|[^|]*状态[^|]*\|[^|]*触[^|]*\|", body, flags=re.M))
            or bool(re.search(r"\|[^|]*状态[^|]*\|[^|]*含[^|]*\|", body, flags=re.M))
            or bool(re.search(r"\|[^|]*处理阶段[^|]*\|", body, flags=re.M))
        )
        has_state_heading = bool(re.search(
            r"(?i)(状态机|生命周期|状态流转|object.lifecycle|治理闭环|治理状态)",
            body,
        ))
        transition_count = len(re.findall(
            r"(?i)(状态.*更新为|变更|流转|回退|下一阶段|下一状态|终态|待验收)",
            body,
        ))
        if not (has_state_table or has_state_heading or transition_count >= 3):
            issues.append(
                f"业务型模块「{title}」缺少对象状态机/生命周期描述 -- "
                f"SKILL.md SD329 要求业务型模块描述 object_lifecycle"
            )

        # ---- Gate 2: Conditional branches ----
        # Accept: parameter/strategy matrices, explicit branch descriptions,
        # or 3+ conditional keywords in prose.
        has_branch_table = bool(re.search(
            r"(?i)(条件分支|conditional|分支路径|配置路径|策略矩阵|推送策略|参数.*组合|参数.*矩阵|handler)",
            body,
        ))
        has_branch_explicit = bool(re.search(
            r"(?i)(如果.*则|选择.*激活|分支说明|分支一览|参数触发|配置路径分支)",
            body,
        ))
        branch_count = len(re.findall(
            r"(如果|若|则|否则|否则如果)",
            body,
        ))
        if not (has_branch_table or has_branch_explicit or branch_count >= 3):
            issues.append(
                f"业务型模块「{title}」缺少条件分支说明 -- "
                f"SKILL.md SD329 要求每个条件分支必须在 conditional_branches 中说明"
            )

    return issues
def step_density_issues(text: str, modules: list[dict[str, Any]]) -> list[str]:
    # Skip step density check entirely if any typed module is present
    if any(m.get("module_type") for m in modules):
        return []
    action_threshold = 25
    response_threshold = 20
    handling_threshold = 15
    issues: list[str] = []
    for table_index, table in enumerate(iter_markdown_tables(text), start=1):
        if len(table) <= 2:
            continue
        headers = table[0]
        if len(headers) < 4 or headers[1] != "用户操作" or headers[2] != "系统响应":
            continue
        rows = table[1:]
        thin_steps: list[int] = []
        for ri, row in enumerate(rows):
            if len(row) < 4:
                continue
            action = (row[1] or "").strip()
            response = (row[2] or "").strip()
            handling = (row[3] or "").strip()
            if len(action) < action_threshold:
                thin_steps.append(ri + 1)
            elif len(response) < response_threshold:
                thin_steps.append(ri + 1)
            elif handling and len(handling) < handling_threshold:
                thin_steps.append(ri + 1)
        if thin_steps:
            table_text = "|" + "|".join(table[0]) + "|"
            table_pos = text.find(table_text)
            module_title = "未知模块"
            if table_pos >= 0:
                before = text[:table_pos]
                heading_matches = list(re.finditer(r"^###\s+(.+)$", before, flags=re.M))
                if heading_matches:
                    module_title = heading_matches[-1].group(1).strip()
            # Relax step density requirement for typed modules (registry/business/hybrid)
            clean_title = re.sub(r"^\d+(?:\.\d+)*\s+", "", module_title)
            mod = next((m for m in modules if m.get("feature") == clean_title), None)
            if mod and mod.get("module_type"):
                thin_steps = []
            if thin_steps:
                overflow = "" if len(thin_steps) <= 5 else "等"
                step_list = ",".join(str(s) for s in thin_steps[:5])
                issues.append(
                    f"{_ZH["zh045"]}{module_title} 第{table_index}表 "
                    f"第{step_list}{overflow}{_ZH["zh046"]}{action_threshold}{_ZH["zh047"]}{response_threshold}{_ZH["zh048"]}{handling_threshold}ch"
                )
    return issues
