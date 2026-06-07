#!/usr/bin/env python3
"""Markdown renderer for operation manual generation."""

from __future__ import annotations

import re
from typing import Any

from manual_model import (
    clean_field,
    normalize_faq,
    normalize_glossary,
    normalize_related_documents,
    normalize_system_requirements,
    normalize_target_users,
)

from evidence_router import (
    _evidence_gap_report,
    _module_entry_path,
    flow_result_text,
    module_actor_text,
)

from manual_tables import (
    _business_operation_tables,
    _crud_scenario_tables,
    _registry_tables,
    md_cell,
)

# ---- Chinese text constants for f-strings ----
# Edit Chinese text here, NOT in f-string literals.
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


def join_items(items: list[str], limit: int = 4) -> str:
    values = [str(item) for item in items if str(item).strip()]
    if not values:
        return "业务用户"
    return "、".join(values[:limit])


def feature_summary(feature: str, detail: str, software_name: str) -> str:
    clean_detail = normalize_detail(feature, detail)
    return clean_detail


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


def normalize_detail(feature: str, detail: str) -> str:
    value = plain_manual_text(detail or "").strip()
    value = re.sub(rf"^{re.escape(feature)}{_ZH["zh001"]}", "", value)
    value = re.sub(rf"^{re.escape(feature)}{_ZH["zh002"]}", "", value)
    value = re.sub(r"^主要用于", "", value)
    value = re.sub(rf"^{re.escape(feature)}[：:，, ]*", "", value)
    value = re.sub(rf"{_ZH["zh003"]}{re.escape(feature)}{_ZH["zh004"]}", "", value)
    value = re.sub(rf"{_ZH["zh005"]}{re.escape(feature)}{_ZH["zh006"]}", "", value)
    value = re.sub(rf"{_ZH["zh007"]}{re.escape(feature)}{_ZH["zh008"]}", "", value)
    value = re.sub(rf"{_ZH["zh009"]}{re.escape(feature)}{_ZH["zh010"]}", "", value)
    value = re.sub(rf"{_ZH["zh007"]}{re.escape(feature)}{_ZH["zh011"]}", "", value)
    value = re.sub(rf"{_ZH["zh012"]}{re.escape(feature)}{_ZH["zh013"]}", "", value)
    value = value.strip("。；; ，,")
    if not value or value == feature:
        value = "支撑软件中的相关业务处理，帮助用户完成信息查看、内容填写、结果确认或资料维护"
    return value + ("。" if not value.endswith("。") else "")


def as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [plain_manual_text(str(item)).strip() for item in value if str(item).strip()]
    text = plain_manual_text(str(value)).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[；;\n]+", text) if item.strip()]


def feature_phrase(modules: list[dict[str, Any]], limit: int = 5) -> str:
    names = [module["feature"] for module in modules if module.get("feature")]
    return "、".join(names[:limit]) if names else "主要业务处理"


def chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value <= 0:
        return str(value)
    if value < 10:
        return digits[value]
    if value == 10:
        return "十"
    if value < 20:
        return "十" + digits[value % 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return digits[tens] + "十" + (digits[ones] if ones else "")
    return str(value)


def section_heading(index: int, title: str) -> str:
    return f"## {chinese_number(index)}、{title}"


def strip_sentence_punctuation(text: str) -> str:
    return str(text or "").strip().strip("。；;，, ")


def natural_join(items: list[str], limit: int | None = None) -> str:
    values = [strip_sentence_punctuation(item) for item in items if strip_sentence_punctuation(item)]
    if limit is not None:
        values = values[:limit]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return "、".join(values[:-1]) + "和" + values[-1]


def ensure_sentence(text: str) -> str:
    value = strip_sentence_punctuation(plain_manual_text(text))
    if not value:
        return ""
    return value + "。"


def remove_opening_definition(text: str, software_name: str) -> str:
    value = plain_manual_text(text).strip()
    if not value:
        return ""
    sentences = re.findall(r"[^。！？]+[。！？]?", value)
    if sentences and sentences[0].startswith(software_name) and "是一款" in sentences[0]:
        sentences = sentences[1:]
    return "".join(sentences).strip()


def flow_step_text(item: Any) -> str:
    if isinstance(item, dict):
        return plain_manual_text(str(item.get("step") or item.get("action") or item.get("name") or "")).strip()
    return plain_manual_text(str(item)).strip()


def flow_result_value(item: Any, index: int) -> str:
    if isinstance(item, dict):
        result = plain_manual_text(str(item.get("result") or item.get("outcome") or item.get("feedback") or "")).strip()
        if result:
            return ensure_sentence(result)
        return flow_result_text(flow_step_text(item), index)
    return flow_result_text(str(item), index)


def flow_summary(flow: list[Any], modules: list[dict[str, Any]]) -> str:
    if flow:
        pieces = [strip_sentence_punctuation(flow_step_text(item)) for item in flow[:4]]
        pieces = [item for item in pieces if item]
        if pieces:
            return "；".join(pieces) + "。"
    names = [module["feature"] for module in modules[:4]]
    if names:
        return f"{_ZH["zh069"]}{natural_join(names)}{_ZH["zh070"]}"
    return "用户可按照页面提示完成主要业务操作。"


def clean_purpose_text(feature: str, purpose: str) -> str:
    value = strip_sentence_punctuation(plain_manual_text(purpose))
    value = re.sub(rf"^{re.escape(feature)}{_ZH["zh071"]}", "", value)
    value = re.sub(r"^[^，。；;]{1,30}(页面|功能|模块|环节|状态栏|面板)?(主要)?用于", "", value)
    value = re.sub(r"^用于", "", value)
    value = value.strip("。；;，, ")
    return value or "完成本页面相关操作"


def page_label(feature: str) -> str:
    value = strip_sentence_punctuation(feature)
    if value.startswith("用户") and len(value) > 2:
        value = value[2:]
    return value


def purpose_core_sentence(feature: str, purpose: str) -> str:
    value = clean_purpose_text(feature, purpose)
    label = page_label(feature)
    if re.match(r"^(展示|集中展示|承载|提供|处理|保存|记录|辅助)", value):
        return f"{label}{_ZH["zh063"]}{value}"
    if value.startswith("让用户"):
        return f"{label}{_ZH["zh063"]}{value}"
    return f"{_ZH["zh072"]}{label}{_ZH["zh063"]}{value}"


def purpose_sentence(feature: str, purpose: str) -> str:
    return purpose_core_sentence(feature, purpose) + "。"


def entry_sentence(entry: str) -> str:
    value = strip_sentence_punctuation(plain_manual_text(entry))
    if not value:
        return ""
    if value.startswith("用户"):
        return value + "。"
    if re.match(r"^(登录|创建|进入|打开|点击|完成|选择|提交)", value):
        return f"{_ZH["zh073"]}{value}。"
    if value.startswith("从"):
        return f"{_ZH["zh074"]}{value}。"
    if value.startswith("当"):
        return value + "。"
    return f"{_ZH["zh075"]}{value}。"


def visible_elements_sentence(items: list[str], feature: str, index: int) -> str:
    value = natural_join(items, limit=8)
    if not value:
        return ""
    variants = [
        f"{_ZH["zh076"]}{value}{_ZH["zh077"]}",
        f"{_ZH["zh078"]}{feature}{_ZH["zh079"]}{value}{_ZH["zh080"]}",
        f"{_ZH["zh081"]}{value}{_ZH["zh082"]}",
    ]
    return variants[(index - 1) % len(variants)]


def steps_sentence(steps: list[str], module_index: int) -> str:
    values = [strip_sentence_punctuation(step) for step in steps if strip_sentence_punctuation(step)]
    if not values:
        return ""
    connectors = ["先", "随后", "接着", "之后", "再", "继续"]
    parts: list[str] = []
    for step_index, step in enumerate(values):
        if step_index == len(values) - 1 and len(values) > 1:
            connector = "最后"
        else:
            connector = connectors[min(step_index, len(connectors) - 1)]
        parts.append(f"{connector}{step}")
    prefixes = ["实际操作时，用户", "使用该功能时，用户", "在该页面中，用户"]
    return prefixes[(module_index - 1) % len(prefixes)] + "，".join(parts) + "。"


def rules_feedback_sentence(rules: list[str], feedback: list[str], index: int) -> str:
    parts: list[str] = []
    rule_text = natural_join(rules, limit=6)
    if rule_text:
        rule_templates = [
            f"{_ZH["zh083"]}{rule_text}。",
            f"{_ZH["zh084"]}{rule_text}{_ZH["zh085"]}",
            f"{_ZH["zh086"]}{rule_text}{_ZH["zh087"]}",
        ]
        parts.append(rule_templates[(index - 1) % len(rule_templates)])
    feedback_text = natural_join(feedback, limit=6)
    if feedback_text:
        feedback_templates = [
            f"{_ZH["zh088"]}{feedback_text}。",
            f"{_ZH["zh089"]}{feedback_text}。",
            f"{_ZH["zh090"]}{feedback_text}。",
        ]
        parts.append(feedback_templates[(index - 1) % len(feedback_templates)])
    return "".join(parts)


def feature_paragraph(module: dict[str, Any], index: int) -> str:
    feature = module["feature"]
    purpose = clean_purpose_text(feature, module.get("purpose") or "")
    label = page_label(feature)
    core = purpose_core_sentence(feature, module.get("purpose") or "")
    elements = natural_join(as_text_list(module.get("visible_elements")), limit=5)
    feedback = natural_join(as_text_list(module.get("feedback")), limit=3)
    #── narrative fields (from role_chain/upstream/downstream) ──
    upstream = str(module.get("upstream_dependency") or "").strip()
    downstream = str(module.get("downstream_impact") or "").strip()
    chain_parts = []
    if upstream:
        chain_parts.append(upstream + "。")
    if downstream:
        chain_parts.append(downstream + "。")
    chain_text = "".join(chain_parts)
    if chain_text:
        variants = [
            f"{core}{_ZH["zh091"]}{elements or '相关业务信息'}{_ZH["zh092"]}{feedback or '相应的处理结果'}。{chain_text}",
            f"在{label}{_ZH["zh093"]}{purpose}{_ZH["zh094"]}{elements or '页面显示内容'}{_ZH["zh095"]}{feedback or '处理结果'}。{chain_text}",
            f"{label}{_ZH["zh096"]}{purpose}{_ZH["zh097"]}{elements or '必要的页面信息'}{_ZH["zh098"]}{feedback or '当前状态反馈'}。{chain_text}",
        ]
    else:
        variants = [
            f"{core}{_ZH["zh091"]}{elements or '相关业务信息'}{_ZH["zh092"]}{feedback or '相应的处理结果'}。",
            f"在{label}{_ZH["zh093"]}{purpose}{_ZH["zh094"]}{elements or '页面显示内容'}{_ZH["zh095"]}{feedback or '处理结果'}。",
            f"{label}{_ZH["zh096"]}{purpose}{_ZH["zh097"]}{elements or '必要的页面信息'}{_ZH["zh098"]}{feedback or '当前状态反馈'}。",
        ]
    return variants[(index - 1) % len(variants)]


def tidy_manual_output(text: str) -> str:
    replacements = {
        "用户主要处理处理": "用户主要处理",
        "主要处理承载一次": "主要围绕一次",
        "用户可以看到用户可以看到": "用户可以看到",
        "处理结束后会反馈空对话": "处理结束后会显示空对话",
        "在AI ": "在 AI ",
        "把StudioAgent": "把 StudioAgent",
        "页面上的StudioAgent": "页面上的 StudioAgent",
        "看到StudioAgent": "看到 StudioAgent",
        "提供StudioAgent": "提供 StudioAgent",
        "进入StudioAgent": "进入 StudioAgent",
        "保证StudioAgent": "保证 StudioAgent",
    }
    value = text
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"(?<=[\u4e00-\u9fff])([A-Za-z][A-Za-z0-9.+-]*)(?=[\u4e00-\u9fff])", r" \1 ", value)
    value = re.sub(r" {2,}", " ", value)
    return value


def append_modules_canonical(lines: list[str], modules: list[dict[str, Any]], start_index: int) -> int:
    for i, module in enumerate(modules, start=start_index):
        visible_elements = as_text_list(module.get("visible_elements"))
        validation_rules = as_text_list(module.get("validation_rules"))
        feedback = as_text_list(module.get("feedback")) or [module["result"]]
        lines.extend(
            [
                section_heading(i, module["feature"]),
                "",
                purpose_sentence(module["feature"], module["purpose"]) + entry_sentence(module["entry"]),
                "",
            ]
        )
        if module.get("usage"):
            lines.extend([ensure_sentence(module["usage"]), ""])
        # ── 定位与关联（叙事字段）──
        context_parts = []
        rc = str(module.get("role_chain") or "").strip()
        up = str(module.get("upstream_dependency") or "").strip()
        down = str(module.get("downstream_impact") or "").strip()
        if up:
            context_parts.append(up + "。")
        if down:
            context_parts.append(down + "。")
        if context_parts:
            prefix = f"{rc}{_ZH.get('zh104', '中涉及的用户角色——')}" if rc else "该模块在业务链路中的位置——"
            lines.extend([prefix + "".join(context_parts), ""])
        # ── 页面元素 ──
        element_text = visible_elements_sentence(visible_elements, module["feature"], i)
        if element_text:
            lines.extend([element_text, ""])
        step_text = steps_sentence(module["steps"], i)
        if step_text:
            lines.extend([step_text, ""])
        rule_feedback = rules_feedback_sentence(validation_rules, feedback, i)
        if rule_feedback:
            lines.extend([rule_feedback, ""])

        # Append operation tables when module_type is set
        module_type = module.get("module_type")
        if module_type == "registry":
            op_tables = _registry_tables(module)
        elif module_type == "business":
            op_tables = _business_operation_tables(module)
        elif module_type == "hybrid":
            reg_tables = _registry_tables(module)
            biz_tables = _business_operation_tables(module)
            op_tables = (reg_tables or "") + "\n" + (biz_tables or "")
            op_tables = op_tables.strip() or None
        else:
            op_tables = _crud_scenario_tables(module)
        if op_tables:
            lines.extend([op_tables, ""])

        lines.extend(["", module["screenshot"], ""])
    return start_index + len(modules)


def append_flow_canonical(lines: list[str], software_name: str, flow: list[str], start_index: int) -> int:
    lines.extend(
        [
            section_heading(start_index, "典型使用流程"),
            "",
            f"{_ZH["zh099"]}{software_name}{_ZH["zh100"]}",
            "",
            flow_summary(flow, []),
            "",
        ]
    )
    return start_index + 1


def append_table(lines: list[str], headers: list[str], rows: list[list[Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        safe = [md_cell(cell) for cell in row]
        lines.append("| " + " | ".join(safe) + " |")
    lines.append("")


def module_group(index: int, sections: list[Any] | None = None) -> str:
    # Use model-authored group labels if manual_sections provides explicit groups
    if sections:
        module_sections = [s for s in sections if isinstance(s, dict) and s.get("include_operation_modules")]
        if len(module_sections) >= 2:
            section_count = len(module_sections)
            total = 12
            per_group = max(1, total // section_count)
            group_idx = min((index - 1) // per_group, section_count - 1)
            raw = module_sections[group_idx].get("title", "")
            return re.sub(r'^[零一二三四五六七八九十百]+、', '', raw)
    # Default: domain-agnostic groups
    groups = [(3, "基础台账"), (6, "巡检点与配置"), (10, "计划与任务执行"), (99, "移动端操作")]
    for threshold, name in groups:
        if index <= threshold:
            return name
    return "移动端操作"


def module_summary_sentence(module: dict[str, Any]) -> str:
    title = module["feature"]
    purpose = clean_purpose_text(title, module["purpose"])
    usage = ensure_sentence(module.get("usage") or "")
    entry = entry_sentence(module.get("entry") or "")
    actor = module_actor_text(module)
    parts = [f"{actor}{_ZH["zh101"]}{title}{_ZH["zh102"]}{purpose}{_ZH["zh103"]}"]
    if usage:
        parts.append(usage)
    if entry:
        parts.append(entry)
    return "".join(parts)


def append_screenshot_placeholder(lines: list[str], module: dict[str, Any], label: str | None = None) -> None:
    caption = label or module.get("screenshot") or f"{module['feature']}{_ZH["zh104"]}"
    caption = re.sub(r"^【截图预留：", "", str(caption))
    caption = re.sub(r"。?】$", "", caption)
    lines.extend(
        [
            "",
            f"{_ZH["zh068"]}{strip_sentence_punctuation(caption)}。】",
            "",
        ]
    )


def module_number_index(number: str) -> int:
    match = re.search(r"(\d+)$", number)
    return int(match.group(1)) if match else 1




def module_business_hint(module: dict[str, Any]) -> str:
    title = module["feature"]
    usage = strip_sentence_punctuation(module.get("usage") or "")
    purpose = strip_sentence_punctuation(module.get("purpose") or "")
    entry = strip_sentence_punctuation(module.get("entry") or "")
    if usage:
        return f"{title}{_ZH["zh105"]}{usage}。"
    if purpose and entry:
        return f"{_ZH["zh106"]}{entry}{_ZH["zh107"]}{purpose}。"
    if purpose:
        return f"{_ZH["zh108"]}{purpose}。"
    return f"{_ZH["zh109"]}{title}{_ZH["zh110"]}"






















def _sub_feature_list(module: dict[str, Any]) -> list[str]:
    scenarios = module.get("crud_scenarios")
    if isinstance(scenarios, dict) and scenarios:
        return list(scenarios.keys())
    steps = as_text_list(module.get("steps") or module.get("operation_steps"))
    if steps:
        return steps[:4] if len(steps) <= 4 else steps[:4]
    return [module.get("purpose", "")[:30]]


def _sub_feature_descs(module: dict[str, Any], sub_items: list[str]) -> list[str]:
    scenarios = module.get("crud_scenarios")
    descs: list[str] = []
    if isinstance(scenarios, dict):
        for name in sub_items:
            group = scenarios.get(name, {})
            if isinstance(group, dict):
                summary = group.get("summary")
                if summary:
                    descs.append(summary)
                else:
                    descs.append(f"{_ZH["zh172"]}{name}{_ZH["zh065"]}")
    if not descs:
        purpose = strip_sentence_punctuation(module.get("purpose", ""))
        descs = [purpose] * len(sub_items)
    return descs




def append_module_detail(lines: list[str], module: dict[str, Any], number: str) -> None:
    title = module["feature"]
    purpose = clean_purpose_text(title, module["purpose"])
    usage = strip_sentence_punctuation(module.get("usage") or "")
    menu_path = _module_entry_path(module, title)

    lines.extend([f"### {number} {title}", ""])

    intro = f"{title}{_ZH["zh105"]}{purpose}。" if purpose else f"{title}{_ZH["zh227"]}"
    if usage:
        intro += f"{usage}。"
    lines.append(f"{_ZH["zh228"]}{intro}")
    lines.append("")

    lines.append(f"{_ZH["zh229"]}{menu_path}")
    lines.append("")

    # ── Narrative context (role_chain / upstream / downstream) ──
    rc = str(module.get("role_chain") or "").strip()
    up = str(module.get("upstream_dependency") or "").strip()
    down = str(module.get("downstream_impact") or "").strip()
    if up or down:
        context_parts = []
        if up:
            context_parts.append(f"使用前提：{up}。")
        if down:
            context_parts.append(f"下游影响：{down}。")
        if context_parts:
            lines.append(" ".join(context_parts))
            lines.append("")

    module_type = module.get("module_type")

    # Route to type-specific renderer first
    if module_type == "registry":
        op_tables = _registry_tables(module)
    elif module_type == "business":
        op_tables = _business_operation_tables(module)
    elif module_type == "hybrid":
        # Hybrid: render registry then business_operation, concatenated
        reg_tables = _registry_tables(module)
        biz_tables = _business_operation_tables(module)
        op_tables = (reg_tables or "") + "\n" + (biz_tables or "")
        op_tables = op_tables.strip() or None
    else:
        # Backward compatible: old-style crud_scenarios or fallback
        op_tables = _crud_scenario_tables(module) or _evidence_gap_report(module, title)

    if op_tables:
        lines.append(op_tables)
    else:
        lines.extend([
            "| 操作步骤 | 用户操作 | 系统响应 | 异常处理 |",
            "| --- | --- | --- | --- |",
            f"{_ZH["zh230"]}{title}{_ZH["zh231"]}",
            "",
        ])

    append_screenshot_placeholder(lines, module, module.get("screenshot"))
    lines.append(r"\newpage")
    lines.append("")


def render_manual_sample_style(
    software_name: str,
    version: str,
    industry: str,
    users: list[str],
    positioning: str,
    core_value: str,
    modules: list[dict[str, Any]],
    operation_flow: list[Any],
    manual_sections: list[Any] | None = None,
    business: dict[str, Any] | None = None,
) -> str:
    industry_text = "相关业务" if not industry or industry == "待用户确认" else industry
    user_text = join_items([(user.get("role") if isinstance(user, dict) else str(user)) for user in users if (isinstance(user, dict) and user.get("role")) or (isinstance(user, str) and user != "待用户确认")]) or "实际使用人员"
    related_documents = normalize_related_documents(business)
    system_rows = normalize_system_requirements(business)
    faq_items = normalize_faq(business, software_name)
    glossary_items = normalize_glossary(business, modules, software_name)
    user_rows = normalize_target_users(business)

    lines: list[str] = [
        f"# {software_name}",
        "",
        "# 用户使用说明书",
        "",
        f"{_ZH["zh232"]}{version}",
        "",
        "文档用途：用于说明系统运行环境、页面入口、主要功能、操作步骤、字段规则和结果反馈。",
        "",
        r"\newpage",
        "",
        "## 目录",
        "",
    ]
    append_table(
        lines,
        ["章节", "内容"],
        [
            ["1", "系统概述"],
            ["2", "登录界面"],
            ["3", "系统首页"],
            ["4", "功能模块"],
            ["5", "系统要求"],
            ["6", "典型使用流程"],
            ["7", "常见问题解答"],
            ["8", "术语表"],
        ],
    )
    lines.extend([r"\newpage", "", "## 1. 系统概述", ""])
    lines.extend(["### 1.1 系统目标", ""])
    lines.append(
        f"{software_name}是面向{industry_text}的业务系统。"
        f"{clean_field(core_value, '系统用于统一管理业务数据并跟踪处理结果。')}"
    )
    lines.append("")
    if positioning:
        lines.extend(["### 1.2 系统定位", "", ensure_sentence(remove_opening_definition(positioning, software_name)), ""])
    lines.extend(["### 1.3 适用用户", ""])
    append_table(lines, ["用户类型", "主要使用内容"], [[row["role"], row["usage"]] for row in user_rows])
    lines.extend(["### 1.4 相关文档", ""])
    append_table(lines, ["文档名称", "指向资料", "说明"], [[item["name"], item["target"], item["description"]] for item in related_documents])
    lines.extend(["### 1.5 功能特点", ""])
    feature_rows: list[list[str]] = []
    row_idx = 0
    for module in modules:
        feature = module["feature"]
        purpose = strip_sentence_punctuation(module["purpose"])
        sub_items = _sub_feature_list(module)
        sub_descs = _sub_feature_descs(module, sub_items)
        if not sub_items:
            sub_items = [purpose[:30] if len(purpose) > 30 else purpose]
            sub_descs = [purpose]
        for si, sub in enumerate(sub_items):
            row_idx += 1
            desc = sub_descs[si] if si < len(sub_descs) else purpose
            feature_rows.append([str(row_idx), feature, sub, desc])
    append_table(lines, ["序号", "功能模块", "细分功能", "功能说明"], feature_rows)
    lines.extend([r"\newpage", "", "## 2. 登录界面", ""])
    lines.append(
        f"用户通过浏览器访问{software_name}登录地址，在登录界面输入账号、密码或企业统一认证信息。"
        f"登录前应确认网络连接正常、账号已启用且当前用户具备访问{software_name}相关菜单的权限。"
    )
    lines.append("")
    append_table(
        lines,
        ["区域", "页面内容", "操作说明"],
        [
            ["账号输入区", "用户名、手机号或企业账号", "输入已分配的登录账号"],
            ["密码输入区", "密码或认证信息", "输入密码后按页面提示完成登录"],
            ["提示信息区", "错误提示、验证码提示或权限提示", "根据页面提示修正账号、密码或联系管理员"],
        ],
    )
    lines.extend(
        [
            "登录成功后，系统进入首页或默认工作台。若登录失败，页面会显示账号、密码、验证码、权限或网络相关提示，用户应按提示修正后再次登录。",
            "",
            "【截图预留：登录界面、账号输入区和登录结果提示。】",
            "",
            r"\newpage",
            "",
            "## 3. 系统首页",
            "",
        ]
    )
    lines.append(
        f"{_ZH["zh237"]}{software_name}{_ZH["zh238"]}"
        f"{user_text}{_ZH["zh239"]}"
    )
    lines.append("")
    append_table(
        lines,
        ["首页区域", "用户可见内容", "用途"],
        [
            ["导航菜单", "巡检管理、基础台账、统计报表等菜单", "进入具体业务页面"],
            ["工作提醒", "待处理任务、待处理事项", "提示用户优先处理事项"],
            ["统计区域", "任务完成、异常统计等概览", "帮助管理人员查看运行状态"],
        ],
    )
    lines.extend(["【截图预留：系统首页、导航菜单、待办提醒和统计概览。】", "", r"\newpage", "", "## 4. 功能模块", ""])
    group_names = []
    for idx, module in enumerate(modules, start=1):
        group = module_group(idx, manual_sections)
        if group not in group_names:
            group_names.append(group)
            lines.extend([f"### 4.{len(group_names)} {group}", ""])
            # Use section intent from manual_sections for group description
            section_intent = ""
            for s in (manual_sections or []):
                if isinstance(s, dict) and s.get("title") == group:
                    section_intent = s.get("intent", "")
                    break
            if section_intent:
                lines.append(section_intent)
            lines.append("")
        append_module_detail(lines, module, f"4.{len(group_names)}.{sum(1 for j in range(1, idx + 1) if module_group(j, manual_sections) == group)}")

    lines.extend(["## 5. 系统要求", ""])
    append_table(lines, ["系统要求", "最低配置", "推荐配置"], [[row["item"], row["minimum"], row["recommended"]] for row in system_rows])
    lines.append(f"{_ZH["zh241"]}{software_name}{_ZH["zh242"]}")
    lines.extend(["", r"\newpage", "", "## 6. 典型使用流程", ""])
    flow_rows = [[idx, flow_step_text(flow), flow_result_value(flow, idx)] for idx, flow in enumerate(operation_flow, start=1)]
    append_table(lines, ["步骤", "业务动作", "结果"], flow_rows)
    lines.append(
        "以上流程为典型使用路径，用户可根据岗位权限只处理其中与本人职责相关的页面。"
    )
    lines.extend(["", r"\newpage", "", "## 7. 常见问题解答", ""])
    append_table(lines, ["问题", "处理方法"], [[item["question"], item["answer"]] for item in faq_items])
    lines.extend(["## 8. 术语表", ""])
    append_table(lines, ["术语", "解释"], [[item["term"], item["definition"]] for item in glossary_items])
    append_stop(lines)
    return tidy_manual_output("\n".join(lines))


def render_manual_canonical(
    software_name: str,
    version: str,
    industry: str,
    users: list[str],
    positioning: str,
    core_value: str,
    modules: list[dict[str, Any]],
    operation_flow: list[Any],
    manual_sections: list[Any] | None = None,
    business: dict[str, Any] | None = None,
) -> str:
    industry_text = "相关业务" if not industry or industry == "待用户确认" else industry
    user_text = join_items([(user.get("role") if isinstance(user, dict) else str(user)) for user in users if (isinstance(user, dict) and user.get("role")) or (isinstance(user, str) and user != "待用户确认")]) or "实际使用人员"
    positioning_text = remove_opening_definition(positioning, software_name)
    core_value_text = clean_field(core_value, "软件可以帮助用户统一处理相关业务资料，并减少重复操作。")
    flow = operation_flow
    related_documents = normalize_related_documents(business)
    system_rows = normalize_system_requirements(business)
    faq_items = normalize_faq(business, software_name)
    glossary_items = normalize_glossary(business, modules, software_name)
    overview_paragraphs: list[str] = []
    for section in manual_sections or []:
        if isinstance(section, dict) and section.get("paragraphs") and len(overview_paragraphs) < 4:
            overview_paragraphs.extend(as_text_list(section.get("paragraphs"))[:2])

    lines = [f"# {software_name}{_ZH["zh243"]}", "", section_heading(1, "相关文档"), ""]
    lines.extend(["| 文档名称 | 指向资料 | 说明 |", "| --- | --- | --- |"])
    for item in related_documents:
        lines.append(f"| {item['name']} | {item['target']} | {item['description']} |")
    lines.extend(
        [
            "",
            section_heading(2, "说明"),
            "",
            f"{software_name} {version}{_ZH["zh244"]}{industry_text}{_ZH["zh245"]}",
            "",
            f"{_ZH["zh246"]}{user_text}{_ZH["zh247"]}{core_value_text}",
            "",
        ]
    )
    if positioning_text:
        lines.extend([positioning_text, ""])
    for paragraph in overview_paragraphs:
        lines.extend([paragraph, ""])
    lines.extend(
        [
            "本手册用于说明软件的用途、功能特点、运行要求和页面操作流程。各功能章节按用户能够看到的页面、入口、按钮、输入项、提示信息和处理结果进行说明。",
            "",
            section_heading(3, "功能特点"),
            "",
        ]
    )
    for i, module in enumerate(modules[:8], start=1):
        lines.extend([feature_paragraph(module, i), ""])
    lines.extend([section_heading(4, "系统要求"), "", "| 系统要求 | 最低配置 | 推荐配置 |", "| --- | --- | --- |"])
    for row in system_rows:
        lines.append(f"| {row['item']} | {row['minimum']} | {row['recommended']} |")
    lines.extend(
        [
            "",
            f"{_ZH["zh248"]}{software_name}{_ZH["zh249"]}",
            "",
        ]
    )
    next_index = append_modules_canonical(lines, modules, start_index=5)
    if flow:
        next_index = append_flow_canonical(lines, software_name, flow, start_index=next_index)
    lines.extend([section_heading(next_index, "常见问题解答"), ""])
    for item in faq_items:
        lines.extend([f"{_ZH["zh250"]}{item['question']}", f"{_ZH["zh251"]}{item['answer']}", ""])
    next_index += 1
    lines.extend([section_heading(next_index, "术语表"), "", "| 术语 | 解释 |", "| --- | --- |"])
    for item in glossary_items:
        lines.append(f"| {item['term']} | {item['definition']} |")
    lines.append("")
    append_stop(lines)
    return tidy_manual_output("\n".join(lines))


def append_stop(lines: list[str]) -> None:
    lines.extend(
        [
            "```text",
            "STOP_FOR_USER",
            "NEXT_ACTION: 请一次性确认完整操作手册草稿是否符合真实业务；必要时先统一修改段落内容，再运行 confirm_stage.py --stage markdown。",
            "```",
            "",
        ]
    )
