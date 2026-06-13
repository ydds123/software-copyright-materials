#!/usr/bin/env python3
"""Business model normalization for operation manual generation."""

from __future__ import annotations

import re
from typing import Any

_ZH = {
    "zh049": "NEXT_ACTION: 操作手册页面模块[",
    "zh050": "]缺少 `",
    "zh051": "`。请回到业务理解阶段，",
    "zh052": "NEXT_ACTION: manual_modules 第 ",
    "zh053": " 项不是对象，无法生成真实操作手册。请补全 title、purpose、entry、operation_steps、feedback 等字段。",
    "zh054": "功能模块 ",
    "zh055": "]缺少 `usage` 或 `usage_scenario`。请回到业务理解阶段，",
    "zh056": "进入",
    "zh057": "页面查看列表",
    "zh058": "通过",
    "zh059": "执行操作",
    "zh060": "填写",
    "zh061": "点击",
    "zh062": "操作单条记录",
    "zh063": "页面",
    "zh064": "按提示完成",
    "zh065": "相关操作",
    "zh066": "请在此处插入[",
    "zh067": "]页面或操作结果截图",
    "zh068": "【截图预留：",
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


def plain_feature_name(name: str) -> str:
    value = plain_manual_text(str(name))
    value = value.replace("Chat", "对话")
    return value.strip() or "核心功能"


def clean_field(value: str, default: str) -> str:
    text = plain_manual_text(str(value or "")).strip()
    if not text or text == "待用户确认":
        return default
    return text + ("。" if not text.endswith(("。", "！", "？")) else "")


def as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [plain_manual_text(str(item)).strip() for item in value if str(item).strip()]
    text = plain_manual_text(str(value)).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[；;\n]+", text) if item.strip()]


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
    result: list[str] = []
    for role in roles:
        if role and role not in result:
            result.append(role)
        if len(result) >= 8:
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


def required_module_text(item: dict[str, Any], field: str, title: str) -> str:
    value = plain_manual_text(str(item.get(field) or "")).strip()
    if not value:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"{_ZH["zh049"]}{title}{_ZH["zh050"]}{field}{_ZH["zh051"]}"
            "由模型根据真实页面证据补全 manual_modules 后再生成操作手册。"
        )
    return value


def required_module_list(item: dict[str, Any], field: str, title: str) -> list[str]:
    values = as_text_list(item.get(field))
    if not values:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"{_ZH["zh049"]}{title}{_ZH["zh050"]}{field}{_ZH["zh051"]}"
            "由模型根据真实页面证据补全 manual_modules 后再生成操作手册。"
        )
    return values


def normalize_manual_modules(
    business: dict[str, Any] | None,
    fallback_modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    manual_modules = business.get("manual_modules") if business else []
    if not manual_modules:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 业务理解缺少 `manual_modules`。不要由脚本按 auth/query/form 等模板猜测操作手册。"
            "请模型阅读项目真实页面、路由、按钮、输入项、提示和结果反馈，补全 manual_modules 后再生成操作手册。"
        )

    modules: list[dict[str, Any]] = []
    default_roles = target_user_roles(business)
    for index, item in enumerate(manual_modules, start=1):
        if not isinstance(item, dict):
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"{_ZH["zh052"]}{index}{_ZH["zh053"]}"
            )
        title = plain_feature_name(item.get("title") or item.get("feature") or f"{_ZH["zh054"]}{index}")
        purpose = required_module_text(item, "purpose", title)
        entry = required_module_text(item, "entry", title)
        usage = plain_manual_text(
            str(item.get("usage") or item.get("usage_scenario") or item.get("description") or "")
        ).strip()
        if not usage:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"{_ZH["zh049"]}{title}{_ZH["zh055"]}"
                "补充用户在什么场景下会使用该页面、处理什么具体事务，再生成操作手册。"
            )
        evidence = required_module_list(item, "evidence", title)
        module_type = item.get("module_type", "")

        visible_elements = as_text_list(item.get("visible_elements"))
        if not visible_elements and module_type in ("registry", "business", "hybrid"):
            registry = item.get("registry") if isinstance(item.get("registry"), dict) else {}
            lst = registry.get("list") if isinstance(registry.get("list"), dict) else {}
            for field in ("columns", "filters", "top_actions", "row_actions"):
                visible_elements.extend(as_text_list(lst.get(field)))
            create = registry.get("create") if isinstance(registry.get("create"), dict) else {}
            for section in create.get("form_sections") or []:
                if isinstance(section, dict):
                    visible_elements.extend(as_text_list(section.get("fields")))
            operation = item.get("business_operation") if isinstance(item.get("business_operation"), dict) else {}
            for phase in operation.get("operation_chain") or []:
                if not isinstance(phase, dict):
                    continue
                for sub_operation in phase.get("sub_operations") or []:
                    if isinstance(sub_operation, dict):
                        visible_elements.extend(as_text_list(sub_operation.get("visible_controls")))
        visible_elements = list(dict.fromkeys(value for value in visible_elements if value))
        if not visible_elements:
            visible_elements = required_module_list(item, "visible_elements", title)

        # For registry/business/hybrid: derive steps from rich structure if operation_steps not explicitly provided
        if module_type in ("registry", "business", "hybrid"):
            steps = as_text_list(item.get("operation_steps"))
            if not steps and module_type in ("registry", "hybrid"):
                # Derive from registry structure
                registry = item.get("registry") if isinstance(item.get("registry"), dict) else {}
                lst = registry.get("list") if isinstance(registry.get("list"), dict) else {}
                row_actions = as_text_list(lst.get("row_actions"))
                top_actions = as_text_list(lst.get("top_actions"))
                create = registry.get("create") if isinstance(registry.get("create"), dict) else {}
                sections = create.get("form_sections") or []
                steps = [f"{_ZH["zh056"]}{title}{_ZH["zh057"]}"] + [f"{_ZH["zh058"]}{a}{_ZH["zh059"]}" for a in top_actions]
                for s in sections[:2]:
                    fields = as_text_list(s.get("fields"))
                    if fields:
                        steps.append(f"{_ZH["zh060"]}{s.get('section_name','信息')}: {', '.join(fields[:6])}")
                for a in row_actions:
                    steps.append(f"{_ZH["zh061"]}{a}{_ZH["zh062"]}")
            if not steps:
                steps = [f"{_ZH["zh056"]}{title}{_ZH["zh063"]}", f"{_ZH["zh064"]}{title}{_ZH["zh065"]}"]

            feedback = as_text_list(item.get("feedback"))
            validation_rules = as_text_list(item.get("validation_rules"))
            registry = item.get("registry") if isinstance(item.get("registry"), dict) else {}
            create = registry.get("create") if isinstance(registry.get("create"), dict) else {}
            validation_rules.extend(as_text_list(create.get("rules")))
            for section in create.get("form_sections") or []:
                if isinstance(section, dict):
                    validation_rules.extend(as_text_list(section.get("rules")))
            operation = item.get("business_operation") if isinstance(item.get("business_operation"), dict) else {}
            for phase in operation.get("operation_chain") or []:
                if not isinstance(phase, dict):
                    continue
                for sub_operation in phase.get("sub_operations") or []:
                    if not isinstance(sub_operation, dict):
                        continue
                    constraint = plain_manual_text(str(sub_operation.get("constraint") or "")).strip()
                    outcome = plain_manual_text(str(sub_operation.get("outcome") or "")).strip()
                    if constraint:
                        validation_rules.append(constraint)
                    if outcome:
                        feedback.append(outcome)
            scenarios = item.get("crud_scenarios") if isinstance(item.get("crud_scenarios"), dict) else {}
            for scenario in scenarios.values():
                if not isinstance(scenario, dict):
                    continue
                for scenario_step in scenario.get("steps") or []:
                    if not isinstance(scenario_step, dict):
                        continue
                    response = plain_manual_text(str(scenario_step.get("system_response") or "")).strip()
                    handling = plain_manual_text(str(scenario_step.get("error_handling") or "")).strip()
                    if response:
                        feedback.append(response)
                    if handling:
                        validation_rules.append(handling)
            validation_rules = list(dict.fromkeys(value for value in validation_rules if value))
            feedback = list(dict.fromkeys(value for value in feedback if value))
            if not validation_rules:
                validation_rules = required_module_list(item, "validation_rules", title)
            if not feedback:
                feedback = required_module_list(item, "feedback", title)
        else:
            steps = required_module_list(item, "operation_steps", title)
            validation_rules = required_module_list(item, "validation_rules", title)
            feedback = required_module_list(item, "feedback", title)
        actors = as_text_list(
            item.get("actors")
            or item.get("applicable_users")
            or item.get("roles")
            or item.get("target_users")
            or default_roles[:2]
        )
        if not actors:
            actors = ["相关业务用户"]
        screenshot_note = plain_manual_text(str(item.get("screenshot") or "")).strip()
        if not screenshot_note:
            screenshot_note = f"{_ZH["zh066"]}{title}{_ZH["zh067"]}"
        modules.append(
            {
                "feature": title,
                "raw_feature": title,
                "evidence": evidence,
                "purpose": purpose + ("。" if not purpose.endswith(("。", "！", "？")) else ""),
                "entry": entry + ("。" if not entry.endswith(("。", "！", "？")) else ""),
                "usage": usage,
                "actors": actors,
                "visible_elements": visible_elements,
                "steps": steps,
                "crud_scenarios": item.get("crud_scenarios"),
                "module_type": item.get("module_type"),
                "registry": item.get("registry"),
                "business_operation": item.get("business_operation"),
                "subtasks": item.get("subtasks") or item.get("tasks") or [],
                "operation_name": plain_manual_text(str(item.get("operation_name") or item.get("primary_action") or "")),
                "field_focus": plain_manual_text(str(item.get("field_focus") or item.get("key_fields") or "")),
                "validation_rules": validation_rules,
                "feedback": feedback,
                "result": "；".join(feedback),
                "role_chain": plain_manual_text(str(item.get("role_chain") or "")),
                "upstream_dependency": plain_manual_text(str(item.get("upstream_dependency") or "")),
                "downstream_impact": plain_manual_text(str(item.get("downstream_impact") or "")),
                "screenshot": f"{_ZH["zh068"]}{screenshot_note.strip('。')}。】",
            }
        )
    return modules


def require_business_input_quality(business: dict[str, Any] | None) -> None:
    issues = business_input_quality_issues(business)
    if not issues:
        return
    lines = [
        "STOP_FOR_USER",
        "NEXT_ACTION: 业务理解不足以支撑高质量操作手册。请补充以下内容后再重新生成：",
    ]
    lines.extend(f"{index}. {issue}" for index, issue in enumerate(issues, start=1))
    raise SystemExit("\n".join(lines))


def normalize_target_users(business: dict[str, Any] | None) -> list[dict[str, str]]:
    raw_users = business.get("target_users") if business else None
    rows: list[dict[str, str]] = []
    if isinstance(raw_users, list):
        for item in raw_users:
            if isinstance(item, dict):
                role = str(item.get("role") or item.get("name") or item.get("user_type") or "").strip()
                focus = str(item.get("focus") or item.get("usage") or item.get("main_usage") or item.get("responsibility") or "").strip()
                if role:
                    rows.append({"role": plain_manual_text(role), "usage": plain_manual_text(focus or audience_usage_text(role))})
            elif isinstance(item, str) and item.strip():
                role = plain_manual_text(item.strip())
                rows.append({"role": role, "usage": audience_usage_text(role)})
    if not rows:
        rows.append({"role": "业务用户", "usage": "按岗位权限进入相关页面，完成本人负责的查询、提交和结果确认工作。"})
    return rows


def audience_usage_text(role: str) -> str:
    value = str(role or "")
    if "管理员" in value or "管理" in value:
        return "负责维护基础资料、配置业务规则、分配权限或任务，并跟踪系统整体运行情况。"
    if "经办" in value or "操作" in value or "现场" in value or "执行" in value:
        return "重点处理本人负责的业务记录，按页面要求填写信息、提交结果并查看处理反馈。"
    if "审核" in value or "审批" in value or "复核" in value or "验收" in value:
        return "负责查看待处理事项，核对提交内容，填写审核意见并确认通过、退回或补正结果。"
    if "负责人" in value or "领导" in value or "主管" in value:
        return "重点查看任务进度、业务统计、异常事项和处理结果，用于掌握部门或整体业务运行情况。"
    if "统计" in value or "报表" in value or "监管" in value:
        return "重点查看查询统计、报表导出和数据汇总结果，用于分析业务运行情况或完成报送。"
    return "按岗位权限进入相关页面，完成本人负责的业务查询、数据维护、任务处理和结果确认。"


def normalize_system_requirements(business: dict[str, Any] | None) -> list[dict[str, str]]:
    raw_items = business.get("system_requirements") if business else None
    rows: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                name = str(item.get("item") or item.get("name") or "").strip()
                minimum = str(item.get("minimum") or item.get("min") or "").strip()
                recommended = str(item.get("recommended") or item.get("recommend") or "").strip()
                if name:
                    rows.append(
                        {
                            "item": plain_manual_text(name),
                            "minimum": plain_manual_text(minimum or "按实际部署环境配置"),
                            "recommended": plain_manual_text(recommended or minimum or "按实际部署环境配置"),
                        }
                    )
    if not rows:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 业务理解缺少 `system_requirements`。请根据真实项目运行形态和已确认申请表环境补全后再生成操作手册。"
        )
    return rows


def normalize_faq(business: dict[str, Any] | None, software_name: str) -> list[dict[str, str]]:
    raw_items = business.get("faq") if business else None
    items: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                question = str(item.get("question") or item.get("q") or "").strip()
                answer = str(item.get("answer") or item.get("a") or "").strip()
                if question and answer:
                    items.append({"question": plain_manual_text(question), "answer": plain_manual_text(answer)})
    if not items:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 业务理解缺少 `faq`。请根据当前软件真实使用场景补全常见问题后再生成操作手册。"
        )
    return items


def normalize_glossary(business: dict[str, Any] | None, modules: list[dict[str, Any]], software_name: str) -> list[dict[str, str]]:
    raw_items = business.get("glossary") if business else None
    items: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                term = str(item.get("term") or item.get("name") or "").strip()
                definition = str(item.get("definition") or item.get("description") or "").strip()
                if term and definition:
                    items.append({"term": plain_manual_text(term), "definition": plain_manual_text(definition)})
    if items:
        return items
    raise SystemExit(
        "STOP_FOR_USER\n"
        "NEXT_ACTION: 业务理解缺少 `glossary`。请根据当前软件真实业务对象和页面术语补全术语表后再生成操作手册。"
    )


def describe_related_doc(name: str) -> str:
    if "总体" in name:
        return "说明软件整体功能、页面组成、运行环境和业务边界。"
    if "详细" in name:
        return "说明各功能页面、输入输出、状态变化和处理规则。"
    if "测试" in name or "案例" in name:
        return "记录主要功能的操作场景、预期结果和异常提示。"
    return "记录与本软件功能、操作或验证相关的配套说明。"


def normalize_related_documents(business: dict[str, Any] | None) -> list[dict[str, str]]:
    raw_items = business.get("related_documents") if business else None
    rows: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("title") or item.get("document") or "").strip()
                target = str(item.get("target") or item.get("path") or item.get("file") or "").strip()
                description = str(item.get("description") or item.get("purpose") or "").strip()
                if name:
                    rows.append(
                        {
                            "name": plain_manual_text(name),
                            "target": plain_manual_text(target or f"《{name}》"),
                            "description": plain_manual_text(description or describe_related_doc(name)),
                        }
                    )
            elif str(item).strip():
                name = str(item).strip()
                rows.append(
                    {
                        "name": plain_manual_text(name),
                        "target": f"《{plain_manual_text(name)}》",
                        "description": describe_related_doc(name),
                    }
                )
    if not rows:
        for name in ("总体设计", "详细设计", "测试案例"):
            rows.append({"name": name, "target": f"《{name}》", "description": describe_related_doc(name)})
    return rows
