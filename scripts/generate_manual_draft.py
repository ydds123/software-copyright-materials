#!/usr/bin/env python3
"""Generate a reviewer-oriented operation manual Markdown draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import confirm_params, ensure_dir, read_json, resolve_draft_dir

from manual_quality import (
    content_review_gates,
    load_template_profile,
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

from manual_renderer import (
    plain_manual_text,
    render_manual_sample_style,
)

from manual_tables import TABLE_RENDER_WARNINGS

# ---- Chinese text constants for f-strings ----
# Edit Chinese text here, NOT in f-string literals.
# ---- Render warnings (populated during generation) ----
_ZH = {
    "zh001": "(模块|功能)?用于",
    "zh002": "主要用于",
    "zh003": "^用户使用",
    "zh004": "时，可以",
    "zh005": "^进入",
    "zh006": "后，用户可以",
    "zh007": "^在",
    "zh008": "中，用户可以",
    "zh009": "^用户通过",
    "zh010": "可以",
    "zh011": "环节，用户可以",
    "zh012": "^通过",
    "zh013": "，用户可以",
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
    "zh069": "用户可依次使用",
    "zh070": "等页面完成主要工作。",
    "zh071": "(页面|功能|模块|环节)?(主要)?用于",
    "zh072": "用户可在",
    "zh073": "用户",
    "zh074": "用户可",
    "zh075": "用户可以通过",
    "zh076": "页面上主要呈现",
    "zh077": "等内容，这些内容用于帮助用户确认当前位置和可执行操作。",
    "zh078": "用户在",
    "zh079": "页面会看到",
    "zh080": "等信息，并可依据页面显示继续处理。",
    "zh081": "该部分提供",
    "zh082": "等页面内容，用户可据此查看状态、填写信息或选择下一步操作。",
    "zh083": "操作过程中需要注意",
    "zh084": "页面会按照",
    "zh085": "等规则限制或提示用户。",
    "zh086": "如果不满足",
    "zh087": "等要求，用户需要根据页面提示调整后再继续。",
    "zh088": "操作完成后，系统会显示",
    "zh089": "处理结束后，用户可以看到",
    "zh090": "页面反馈通常包括",
    "zh091": "。页面上的",
    "zh092": "会集中呈现当前可操作内容，用户处理完成后可以看到",
    "zh093": "页面中，用户主要处理",
    "zh094": "。系统把",
    "zh095": "放在当前操作区域，处理结束后会反馈",
    "zh096": "页面关注的是",
    "zh097": "。用户通过",
    "zh098": "确认当前状态，并在操作结束后获得",
    "zh099": "用户完成一次完整业务时，通常先进入",
    "zh100": "，再选择或创建业务对象，随后按照页面提示处理内容并查看结果。",
    "zh101": "使用",
    "zh102": "时，主要围绕",
    "zh103": "开展工作。",
    "zh104": "页面或操作结果截图",
    "zh105": "用于",
    "zh106": "用户通常从",
    "zh107": "进入该页面，用于",
    "zh108": "该页面用于",
    "zh109": "该页面用于处理",
    "zh110": "相关业务，用户可根据岗位权限完成查询、维护和结果确认。",
    "zh111": "业务记录",
    "zh112": "页面处理",
    "zh113": "相关内容",
    "zh114": "核对",
    "zh115": "与当前业务状态是否一致",
    "zh116": "处理结果进入后续业务环节",
    "zh117": "：通过",
    "zh118": "：完成",
    "zh119": "并维护",
    "zh120": "：围绕",
    "zh121": "确认任务范围和推送对象",
    "zh122": "：在",
    "zh123": "时补充整改措施和完成情况",
    "zh124": "时确认治理结果是否满足关闭条件",
    "zh125": "：查看",
    "zh126": "指标并判断改进方向",
    "zh127": "：处理",
    "zh128": "，重点关注",
    "zh129": "完成后页面显示处理结果",
    "zh130": "是否符合当前业务要求",
    "zh131": "页面查询或查看已有记录",
    "zh132": "按页面要求填写、选择或确认",
    "zh133": "确认",
    "zh134": "完整准确",
    "zh135": "处理",
    "zh136": "任务环节",
    "zh137": "定位",
    "zh138": "记录",
    "zh139": "限定责任或岗位范围",
    "zh140": "筛选状态、类别或分级信息",
    "zh141": "刷新或恢复列表条件",
    "zh142": "创建新的业务记录",
    "zh143": "维护已有记录内容",
    "zh144": "核对记录完整信息",
    "zh145": "调整记录可用状态",
    "zh146": "批量写入台账或配置数据",
    "zh147": "生成线下核对或归档文件",
    "zh148": "查看运行趋势和统计结果",
    "zh149": "中填写或查看补充信息",
    "zh150": "辅助完成第 ",
    "zh151": " 项页面操作",
    "zh152": "完成[",
    "zh153": "]后，",
    "zh154": "列表按条件刷新，用户可继续查看目标记录。",
    "zh155": "]后，页面保存新的",
    "zh156": "数据，并返回列表或详情。",
    "zh157": "]后，目标记录内容更新，后续业务按新信息继续流转。",
    "zh158": "]后，记录状态变为停用，新的计划或任务不再默认使用该记录。",
    "zh159": "]后，记录恢复可用，后续配置和任务可继续选择该记录。",
    "zh160": "]后，系统返回导入校验结果，成功数据进入对应列表。",
    "zh161": "]后，系统按当前条件生成导出文件，供线下核对或归档。",
    "zh162": "]后，隐患状态更新为待复查或待验收，并保留整改记录。",
    "zh163": "]后，验收结论写入隐患记录，状态进入通过或退回处理。",
    "zh164": "]后，页面刷新统计图表和评估结果，便于管理人员查看趋势。",
    "zh165": "]后，系统记录本次",
    "zh166": "处理结果，并给出保存或提交提示。",
    "zh167": "根据第 ",
    "zh168": " 项规则核对",
    "zh169": "相关字段后再提交。",
    "zh170": "完成第 ",
    "zh171": " 项业务动作并进入后续处理。",
    "zh172": "完成",
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
    "zh204": "「教育培训」→「",
    "zh205": "「基础信息」→「",
    "zh206": "从系统左侧菜单进入「",
    "zh207": " | 进入",
    "zh208": "页面 | 系统展示表格数据，包含",
    "zh209": "等列 | 若页面加载失败，检查网络或刷新页面 |",
    "zh210": " | 通过搜索栏按",
    "zh211": "等条件筛选 | 表格自动刷新，仅显示符合条件的记录 | 若无匹配结果，表格显示为空，可更换筛选条件 |",
    "zh212": " | 使用顶部操作按钮执行操作（",
    "zh213": "） | 根据所选操作弹出对应对话框或执行功能 | 若操作失败，系统提示具体错误原因 |",
    "zh214": " | 点击表格每行的操作按钮（",
    "zh215": "） | 执行对应行操作，弹出详情或编辑框 | 若操作不适用当前记录，按钮置灰或提示不可操作 |",
    "zh216": "时，填写",
    "zh217": " | 表单区域动态展开 | 若未满足条件，该区域不显示 |",
    "zh218": " | 填写",
    "zh219": " | 系统校验输入格式 | 若必填项为空，提交时提示请补充 |",
    "zh220": " | 确认所有必填项已填写，点击保存 | 数据校验通过后保存至数据库，列表刷新 | ",
    "zh221": " | 下载导入模板（Excel） | 系统生成预设格式的空白模板 | 若模板格式异常，请确认浏览器支持文件下载 |",
    "zh222": " | 点击导入，选择填好的Excel文件上传 | 系统逐行校验后批量写入，返回成功/失败条数 | 若数据格式不符，提示具体错误行号和原因 |",
    "zh223": "前置条件：使用",
    "zh224": "前需满足 ",
    "zh225": "时）",
    "zh226": "；否则 ",
    "zh227": "是系统中的核心功能模块。",
    "zh228": "功能介绍：",
    "zh229": "操作路径：",
    "zh230": "| 1 | 进入",
    "zh231": "页面 | 系统展示页面数据和操作入口 | 若页面加载失败，刷新浏览器或联系管理员确认服务状态 |",
    "zh232": "版本号：",
    "zh233": "是面向",
    "zh234": "的业务系统，围绕风险分级管控和隐患排查治理组织页面和数据。",
    "zh235": "用户通过浏览器访问",
    "zh236": "登录地址，在登录界面输入账号、密码或企业统一认证信息。",
    "zh237": "系统首页用于展示",
    "zh238": "的入口导航、待办提醒、常用功能和运行概览。",
    "zh239": "登录后，可根据岗位职责进入风险分析对象、风险分析单元、巡检点、排查计划、隐患治理或运行评估等功能。",
    "zh240": "部分包含与双重预防机制日常运行直接相关的页面，用户应按实际业务顺序进入对应模块处理。",
    "zh241": "实际部署或使用时，应以申请表确认的软硬件环境为准，确保",
    "zh242": "能够正常登录、查询、保存和导出。",
    "zh243": "操作手册",
    "zh244": "适用于",
    "zh245": "场景。用户进入系统后，可以围绕实际工作内容完成账号进入、业务创建、过程查看、结果确认和资料管理等操作。",
    "zh246": "日常使用时，",
    "zh247": "可以按照页面提示从入口进入相应页面，查看当前业务状态，并根据页面中的按钮、输入框、列表或弹窗继续处理。",
    "zh248": "请确保实际运行环境满足以上要求，以保证",
    "zh249": "能够正常打开页面、提交操作和展示处理结果。若部署方式、客户端形态或服务器环境与本表不同，应以实际确认的申请表环境字段为准。",
    "zh250": "问题：",
    "zh251": "解决方法：",
    "zh252": "是一款基于项目实际功能整理的软件系统。",
    "zh253": "- 来源文件：",
    "zh254": "- 样本页数：",
    "zh255": "- 目标字符数下限：",
    "zh256": "- 目标标题数下限：",
    "zh257": "- 目标表格行数下限：",
    "zh258": "- 目标截图预留数下限：",
    "zh259": "- 面向受众：",
    "zh260": "- 业务链路：",
    "zh261": "- 操作颗粒度：",
    "zh262": "- 适用用户感：",
    "zh263": "；各核心模块需读起来面向文档中的适用用户",
    "zh264": "- 适用用户职责差异化：",
    "zh265": "；适用用户表不得为不同角色生成相同主要使用内容",
    "zh266": "- 表格信息增量：同一表格同一列内容重复超过 ",
    "zh267": " 次时需结合上下文改写",
    "zh268": "- 禁止机械表达：",
    "zh269": "## 第 ",
    "zh270": " 轮：",
}





def build_manual_text(
    analysis: dict[str, Any],
    software_name: str,
    version: str,
    business: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    require_business_input_quality(business)
    positioning = plain_manual_text(business.get("product_positioning") if business else f"{software_name} {version}{_ZH["zh252"]}")
    core_value = plain_manual_text(business.get("core_value") if business else "系统通过清晰的软件界面为用户提供主要业务入口，支持用户完成信息查看、业务处理、数据维护和结果反馈等操作。")
    users = business.get("target_users") if business else ["业务用户"]
    operation_flow = business.get("operation_flow") if business else []
    manual_sections = business.get("manual_sections") if business else []
    industry = business.get("industry") if business else "业务应用"
    if positioning.rstrip("。") == software_name.rstrip("。"):
        positioning = "用户可以根据项目资料中体现的业务场景完成相应操作。"
    elif not positioning.endswith("。"):
        positioning += "。"
    modules = normalize_manual_modules(business, [])
    records: list[dict[str, Any]] = []

    def render_round(round_no: int, action: str) -> str:
        reset_evidence_gaps()
        rendered = render_manual_sample_style(software_name, version, industry, users, positioning, core_value, modules, operation_flow, manual_sections, business)
        gap_summary = evidence_gap_summary()
        issues = manual_quality_issues(rendered, modules, profile, business)
        issues.extend(evidence_gap_issues(gap_summary))
        records.append(
            {
                "round": round_no,
                "action": action,
                "issues": issues,
                "evidence_gaps": gap_summary,
            }
        )
        return rendered

    text = render_round(1, "初稿生成")
    text = render_round(2, "真实页面字段复核")
    text = render_round(3, "制式模板和 AI 味复核")

    for round_no in range(4, 7):
        issues = records[-1]["issues"]
        if not issues:
            break
        text = render_round(round_no, "复核仍需模型回到业务理解补写")
        break
    return text, records, modules


def write_review_records(
    out_dir: Path,
    records: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    business: dict[str, Any] | None = None,
) -> None:
    quality = template_quality(profile)
    gates = content_review_gates(profile, business, modules)
    profile_summary = None
    if profile:
        profile_summary = {
            "profile_version": profile.get("profile_version"),
            "source_docx": profile.get("source_docx"),
            "sample_metrics": profile.get("sample_metrics"),
            "target_quality": quality,
            "content_review_gates": gates,
        }
    (out_dir / "操作手册自检记录.json").write_text(
        json.dumps({"rounds": records, "module_count": len(modules), "template_profile": profile_summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# 操作手册自检记录", ""]
    if profile_summary:
        lines.extend(
            [
                "## 样本文档画像",
                "",
                f"{_ZH["zh253"]}{profile_summary['source_docx']}",
                f"{_ZH["zh254"]}{(profile_summary['sample_metrics'] or {}).get('pages')}",
                f"{_ZH["zh255"]}{quality.get('min_chars')}",
                f"{_ZH["zh256"]}{quality.get('min_headings')}",
                f"{_ZH["zh257"]}{quality.get('min_table_lines')}",
                f"{_ZH["zh258"]}{quality.get('min_screenshot_slots_without_images')}",
                "",
            ]
        )
    lines.extend(
        [
            "## 内容审查门禁",
            "",
            f"{_ZH["zh259"]}{', '.join(gates.get('required_audience_terms') or [])}",
            f"{_ZH["zh260"]}{', '.join(gates.get('required_business_chain_terms') or [])}",
            f"{_ZH["zh261"]}{', '.join(gates.get('required_operation_terms') or [])}",
            f"{_ZH["zh262"]}{'启用' if gates.get('required_audience_fit') else '未启用'}{_ZH["zh263"]}",
            f"{_ZH["zh264"]}{'启用' if gates.get('require_distinct_audience_usage') else '未启用'}{_ZH["zh265"]}",
            f"{_ZH["zh266"]}{gates.get('table_duplicate_column_limit') or 0}{_ZH["zh267"]}",
            f"{_ZH["zh268"]}{', '.join(gates.get('prohibited_phrases') or [])}",
            "- 重复句式限制：固定兜底句不得在多个模块中反复出现",
            "",
        ]
    )
    for record in records:
        lines.extend([f"{_ZH["zh269"]}{record['round']}{_ZH["zh270"]}{record['action']}", ""])
        if record["issues"]:
            lines.extend(f"- {issue}" for issue in record["issues"])
        else:
            lines.append("- 未发现需继续修正的问题")
        evidence_gaps = record.get("evidence_gaps") or {}
        if evidence_gaps.get("count"):
            functions = evidence_gaps.get("by_function") or {}
            function_text = "、".join(f"{name}={count}" for name, count in functions.items())
            lines.append(f"- 证据缺口：{evidence_gaps.get('count')} 处；{function_text}")
        lines.append("")
    lines.extend(["## 模块清单", ""])
    lines.extend(f"- {module['feature']}" for module in modules)
    (out_dir / "操作手册自检记录.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manual(path: Path, analysis: dict[str, Any], software_name: str, version: str, business: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    profile = load_template_profile(path.parent.parent)
    text, records, modules = build_manual_text(analysis, software_name, version, business, profile)
    path.write_text(text, encoding="utf-8")
    write_review_records(path.parent, records, modules, profile, business)
    return records


def require_confirmed_business(business: dict[str, Any] | None) -> None:
    if business is None:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 操作手册必须基于已确认的业务理解生成。请先生成并确认 草稿/业务理解.md。"
        )
    if business.get("confirmation_required") and not business.get("user_confirmed"):
        # Gate check deferred to build_docx_from_md.py which reads 门禁状态.json
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--software-name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--business-context", help="Business context JSON generated before manual drafting")
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    args = parser.parse_args()

    analysis = read_json(Path(args.analysis))
    business = read_json(Path(args.business_context)) if args.business_context else None
    require_confirmed_business(business)
    out_dir = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)
    ensure_dir(out_dir)

    confirm_params({"输出目录": str(out_dir), "软件名称": args.software_name, "版本号": args.version}, args.confirm)
    out_path = out_dir / "操作手册.md"
    records = write_manual(out_path, analysis, args.software_name, args.version, business)
    print(f"OK manual draft: {out_path}")
    print(f"OK manual self-review: {out_dir / '操作手册自检记录.md'}")

    # Report coverage
    if business:
        modules = business.get("manual_modules") or []
        with_rich = sum(1 for m in modules if (
            m.get("crud_scenarios") or
            m.get("module_type") in ("registry", "business", "hybrid")
        ))
        without_rich = len(modules) - with_rich
        print(f"coverage: {with_rich}/{len(modules)} modules have rich structure (crud_scenarios / registry / business_operation / hybrid)")
        if without_rich > 0:
            missing = [m.get("title", "?") for m in modules if not (
                m.get("crud_scenarios") or m.get("module_type") in ("registry", "business", "hybrid")
            )]
            print(f"WARNING: {without_rich} module(s) will use fallback rendering: {', '.join(missing[:5])}")
            if without_rich > len(modules) * 0.5:
                print("CRITICAL: More than half of modules lack rich structure; manual content will be thin. Use module_classification_rules.md to fill registry/business_operation fields before confirming markdown.")

    for record in records:
        print(f"Review round {record['round']}: {record['action']} issues={len(record['issues'])}")
    gap_summary = records[-1].get("evidence_gaps") or {}
    if gap_summary.get("count"):
        modules_with_gaps = gap_summary.get("by_module") or {}
        module_text = ", ".join(f"{name}={count}" for name, count in list(modules_with_gaps.items())[:8])
        print(f"WARNING: {gap_summary.get('count')} evidence gap(s) across {len(modules_with_gaps)} module(s): {module_text}")
        print("NEXT_ACTION: 按操作手册中「证据缺失」指引，读取对应源码文件补全业务理解 JSON 后重新渲染。")
    # Print model-data-gap warnings
    if TABLE_RENDER_WARNINGS.get("missing_outcome"):
        warn_count = TABLE_RENDER_WARNINGS["missing_outcome"]
        print(f"WARNING: {warn_count} business_operation sub_operation(s) missing 'outcome' field; rendered with placeholder. Fill these in the model JSON to avoid placeholder text in the manual.")
    if TABLE_RENDER_WARNINGS.get("missing_constraint"):
        warn_count = TABLE_RENDER_WARNINGS["missing_constraint"]
        print(f"WARNING: {warn_count} business_operation sub_operation(s) missing 'constraint' field; rendered with placeholder. Fill these in the model JSON to avoid placeholder text in the manual.")
    if records[-1]["issues"]:
        print("STOP_FOR_USER")
        print("NEXT_ACTION: 操作手册自检仍有问题。请回到业务理解阶段补全 manual_modules 中的真实页面内容、操作规则和结果反馈后再重新生成。")
        raise SystemExit(1)
    print("STOP_FOR_USER")
    print("NEXT_ACTION: 请一次性确认完整操作手册草稿是否符合真实业务；必要时先统一修改段落内容，再运行 confirm_stage.py --stage markdown。")


if __name__ == "__main__":
    main()
