#!/usr/bin/env python3
"""Markdown table renderers for operation manual modules."""

from __future__ import annotations

import re
from typing import Any

_ZH = {
    "zh173": "列表刷新，显示符合条件的记录。",
    "zh174": "系统保存",
    "zh175": "信息，返回列表页面并提示保存成功。",
    "zh176": "状态更新为\"已发布\"。",
    "zh177": "状态更新为\"已上架\"，学员端可查看。",
    "zh178": "状态更新为\"已下架\"。",
    "zh179": "目标记录从",
    "zh180": "列表中移除。",
    "zh181": "系统更新",
    "zh182": "信息并刷新列表。",
    "zh183": "系统处理导入文件，返回",
    "zh184": "数据导入结果。",
    "zh185": "系统生成",
    "zh186": "导出文件供下载。",
    "zh187": "系统记录",
    "zh188": "处理结果并更新状态。",
    "zh189": "系统完成操作并显示",
    "zh190": "处理结果。",
    "zh191": "根据页面红色提示补充",
    "zh192": "的必填字段后重新提交。",
    "zh193": "修改",
    "zh194": "的重复内容后重新提交；仍提示重复则联系管理员核实数据。",
    "zh195": "若保存失败，根据",
    "zh196": "页面的红色提示修正字段格式或补全必填内容后重新提交。",
    "zh197": "若提示无法删除，确认该",
    "zh198": "记录未被其他业务引用，解除关联后重试。",
    "zh199": "若发布失败，检查",
    "zh200": "的关联内容是否已配置完整，确认后重新发布。",
    "zh201": "若上传失败，确认文件格式和大小符合",
    "zh202": "页面的限制要求后重新上传。",
    "zh203": "操作失败，根据页面提示修正后重试；持续异常则联系系统管理员。",
    "zh207": " | 进入",
    "zh208": "页面 | 系统展示表格数据，包含",
    "zh209": "等列 | 若页面加载失败，检查网络或刷新页面 |",
    "zh210": " | 通过搜索栏按",
    "zh211": "等条件筛选 | 表格自动刷新，仅显示符合条件的记录 | 若无匹配结果，表格显示为空，可更换筛选条件 |",
    "zh212": " | 使用顶部操作按钮执行操作（",
    "zh213": "） | 根据所选操作弹出对应对话框或执行功能 | 若操作失败，系统提示具体错误原因 |",
    "zh214": " | 点击表格每行的操作按钮（",
    "zh215": "） | 执行对应行操作，弹出详情或编辑框 | 若操作不适用当前记录，按钮置灰或提示不可操作 |",
    "zh221": " | 下载导入模板（Excel） | 系统生成预设格式的空白模板 | 若模板格式异常，请确认浏览器支持文件下载 |",
    "zh222": " | 点击导入，选择填好的Excel文件上传 | 系统逐行校验后批量写入，返回成功/失败条数 | 若数据格式不符，提示具体错误行号和原因 |",
    "zh223": "前置条件：使用",
    "zh224": "前需满足 ",
    "zh225": "时）",
}


TABLE_RENDER_WARNINGS: dict[str, int] = {}


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


def md_cell(value: Any) -> str:
    return plain_manual_text(str(value or "")).replace("|", "／").replace("\n", " ").strip()








def _registry_tables(module: dict[str, Any]) -> str | None:
    """Render registry-type modules: list + create form + edit/detail as operation tables."""
    registry = module.get("registry")
    if not isinstance(registry, dict):
        return None

    result_parts: list[str] = []
    global_idx = 1

    # --- List view ---
    lst = registry.get("list")
    if isinstance(lst, dict):
        columns = as_text_list(lst.get("columns"))
        filters = as_text_list(lst.get("filters"))
        top_actions = as_text_list(lst.get("top_actions"))
        row_actions = as_text_list(lst.get("row_actions"))

        result_parts.append("查看列表：")
        result_parts.append("")
        result_parts.append("| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |")
        result_parts.append("| --- | --- | --- | --- |")

        # Step 1: enter page
        title = module.get("feature", "")
        result_parts.append(f"| {global_idx}{_ZH["zh207"]}{title}{_ZH["zh208"]}{', '.join(columns[:5])}{_ZH["zh209"]}")
        global_idx += 1

        # Step 2: filter
        if filters:
            f_joined = "、".join(filters[:6])
            result_parts.append(f"| {global_idx}{_ZH["zh210"]}{f_joined}{_ZH["zh211"]}")
            global_idx += 1

        # Step 3: top actions
        if top_actions:
            a_joined = "、".join(top_actions)
            result_parts.append(f"| {global_idx}{_ZH["zh212"]}{a_joined}{_ZH["zh213"]}")
            global_idx += 1

        # Step 4: row actions
        if row_actions:
            ra_joined = "、".join(row_actions)
            result_parts.append(f"| {global_idx}{_ZH["zh214"]}{ra_joined}{_ZH["zh215"]}")
            global_idx += 1

        result_parts.append("")

    # --- Create form ---
    create = registry.get("create")
    if isinstance(create, dict):
        form_sections = create.get("form_sections") or []
        rules = as_text_list(create.get("rules"))
        if not form_sections:
            fields = as_text_list(create.get("fields"))
            if fields:
                form_sections = [{"section_name": "基本信息", "fields": fields}]

        result_parts.append("新增记录：")
        result_parts.append("")
        result_parts.append("| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |")
        result_parts.append("| --- | --- | --- | --- |")

        step_num = global_idx
        feature = module.get("feature", "")
        for section in form_sections:
            section_name = section.get("section_name", "填写信息")
            fields = as_text_list(section.get("fields"))
            conditional = section.get("conditional_on", "")

            # Module-specific system response and error handling
            field_sample = fields[0] if fields else "信息"
            sys_resp = f"系统校验{feature}{section_name}的{field_sample}等字段是否合规"
            err_handling = f"若{field_sample}格式不符或必填项为空，提交时提示具体错误并要求补充"

            if conditional:
                result_parts.append(f"| {step_num} | {conditional}时，填写{section_name}：{', '.join(fields[:8])} | 表单区域动态展开 | 若未满足条件，该区域不显示 |")
            else:
                result_parts.append(f"| {step_num} | 填写{section_name}：{', '.join(fields[:8])} | {sys_resp} | {err_handling} |")
            step_num += 1

        # Validation rules summary
        if rules:
            rules_sample = "、".join(rules[:3])
            result_parts.append(f"| {step_num} | 确认所有必填项已填写，点击保存 | 数据校验通过后{feature}记录保存至数据库，列表刷新 | {rules_sample} |")
            step_num += 1

        result_parts.append("")

    # --- Import/Export ---
    ie = registry.get("import_export")
    if isinstance(ie, dict) and ie.get("supports_import"):
        result_parts.append("导入导出：")
        result_parts.append("")
        result_parts.append("| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |")
        result_parts.append("| --- | --- | --- | --- |")
        if ie.get("import_template_download"):
            result_parts.append(f"| {global_idx}{_ZH["zh221"]}")
            global_idx += 1
        result_parts.append(f"| {global_idx}{_ZH["zh222"]}")
        global_idx += 1
        result_parts.append("")

    return "\n".join(result_parts)


def _business_operation_tables(module: dict[str, Any]) -> str | None:
    """Render business-type modules: operation_chain broken into stages."""
    bo = module.get("business_operation")
    if not isinstance(bo, dict):
        return None

    result_parts: list[str] = []
    global_idx = 1

    # --- Entry conditions ---
    conditions = as_text_list(bo.get("entry_conditions"))
    if conditions:
        title = module.get("feature", "")
        result_parts.append(f"{_ZH["zh223"]}{title}{_ZH["zh224"]}" + "；".join(conditions))
        result_parts.append("")

    # --- Operation chain ---
    chain = bo.get("operation_chain")
    if isinstance(chain, list):
        for phase in chain:
            if not isinstance(phase, dict):
                continue
            phase_name = phase.get("phase", "")
            sub_ops = phase.get("sub_operations")
            if not isinstance(sub_ops, list) or not sub_ops:
                continue

            result_parts.append(f"{phase_name}：")
            result_parts.append("")
            result_parts.append("| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |")
            result_parts.append("| --- | --- | --- | --- |")

            for sub in sub_ops:
                if not isinstance(sub, dict):
                    continue
                action = sub.get("action", "")
                constraint = sub.get("constraint", "")
                outcome = sub.get("outcome", "")
                cond = sub.get("conditional_on", "")
                prefix = f"（{cond}{_ZH["zh225"]}" if cond else ""

                name = sub.get("name", "")
                label = f"{name}: " if name else ""
                user_action = f"{label}{prefix}{action}"
                feature = module.get("feature", "")

                # WARN when model-provided fields are missing — no silent fallback
                if not outcome:
                    TABLE_RENDER_WARNINGS["missing_outcome"] = TABLE_RENDER_WARNINGS.get("missing_outcome", 0) + 1
                if not constraint:
                    TABLE_RENDER_WARNINGS["missing_constraint"] = TABLE_RENDER_WARNINGS.get("missing_constraint", 0) + 1

                system_resp = outcome or f"[WARNING:{feature}/{name},缺少outcome,请回到业务理解阶段补全]"
                handling = constraint or f"[WARNING:{feature}/{name},缺少constraint,请回到业务理解阶段补全]"

                result_parts.append(f"| {global_idx} | {md_cell(user_action)} | {md_cell(system_resp)} | {md_cell(handling)} |")
                global_idx += 1

            result_parts.append("")

    # --- Conditional branches (separate section) ---
    chain_phases = chain if isinstance(chain, list) else []
    all_branches: list[dict[str, Any]] = []
    for phase in chain_phases:
        branches = phase.get("conditional_branches")
        if isinstance(branches, list):
            all_branches.extend(branches)

    if all_branches:
        result_parts.append("条件分支说明：")
        result_parts.append("")
        for b in all_branches:
            cond = b.get("condition", "")
            then = b.get("then", "")
            else_path = b.get("else", "")
            if cond:
                line = f"当{cond}时，{then}。"
                if else_path:
                    line += f"当不满足该条件时，{else_path}。"
                result_parts.append(line)
        result_parts.append("")

    return "\n".join(result_parts)


def _crud_scenario_tables(module: dict[str, Any]) -> str | None:
    scenarios = module.get("crud_scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        return None
    result_parts: list[str] = []
    global_idx = 1
    for group_name, group_data in scenarios.items():
        if not isinstance(group_data, dict):
            continue
        steps = group_data.get("steps")
        if not isinstance(steps, list) or not steps:
            continue
        result_parts.append(f"{group_name}：")
        result_parts.append("")
        result_parts.append("| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |")
        result_parts.append("| --- | --- | --- | --- |")
        for step in steps:
            if not isinstance(step, dict):
                continue
            action = md_cell(step.get("action", ""))
            response = md_cell(step.get("system_response", ""))
            handling = md_cell(step.get("error_handling", ""))
            result_parts.append(f"| {global_idx} | {action} | {response} | {handling} |")
            global_idx += 1
        result_parts.append("")
    return "\n".join(result_parts)


