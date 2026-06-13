#!/usr/bin/env python3
"""Content quality checker for operation manual — enforces SOP self-check criteria.

Each gate carries a self-identifying profile that maps it back to the SKILL.md
rule it implements, states what it can check, and — critically — what it cannot
check. Gaps between SKILL.md rules and implemented gates are listed as
NOT IMPLEMENTED table so coverage is auditable at a glance.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from manual_quality import major_heading_number_issues
from manual_audit import (
    CROSS_REFERENCE_ITEMS,
    PLAN_FILE,
    REVIEW_FILE,
    SEMANTIC_ITEMS,
    checks_pass,
    load_review_report,
    plan_aliases,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 门禁职责映射表 — 每条记录把 SKILL.md 规则绑定到可执行的门禁编号
# "capability" = 这个门禁实际检查什么
# "limitation" = 这个门禁无法检查什么（正则/形式检查的天花板）
# NOT IMPLEMENTED = SKILL 写了规则但代码里没有对应检查
# ═══════════════════════════════════════════════════════════════════════════════

GATE_PROFILES: list[dict] = [
    # ── gates with implementations ──
    {
        "gate": 1,
        "name": "技术术语禁词检查",
        "skill_ref": "manual_quality_spec Q-W04",
        "capability": "正则匹配黑名单中的技术术语（框架名/数据库名/中间件名）— 阻止其出现在操作手册正文",
        "limitation": "黑名单外的技术术语不受检查；无法判断术语是否在上下文中有业务必要性（如系统要求节中列举数据库名是合理的）",
        "implemented": True,
    },
    {
        "gate": 2,
        "name": "章节编号检查",
        "skill_ref": "manual_quality_spec Q-C01",
        "capability": "验证一级标题编号唯一且连续；检测括号数字格式和中文大写序号",
        "limitation": "不检查标题内容是否与章节职责边界一致（见 gate 7 章节边界违例）",
        "implemented": True,
    },
    {
        "gate": 3,
        "name": "表格密度检查",
        "skill_ref": "manual_quality_spec Q-W02",
        "capability": "计数表格行数和长文本块数—表格数量应主导功能操作章节",
        "limitation": "只计数，不判断表格内容质量；一张填满兜底句的表格和一张信息丰富的表格计数相同",
        "implemented": True,
    },
    {
        "gate": 4,
        "name": "功能清单检查",
        "skill_ref": "manual_quality_spec Q-C01/Q-I02 + manual_authoring_spec §4 功能清单",
        "capability": "检查功能清单每行≥30字；总计≥10行",
        "limitation": "不检查每行的功能描述是否与§6操作章节的实际内容一致（见 gate 20 维度5）",
        "implemented": True,
    },
    {
        "gate": 5,
        "name": "业务模块表格化检查",
        "skill_ref": "manual_quality_spec Q-C02",
        "capability": "检查审批类模块是否含操作步骤表或状态流转表",
        "limitation": "仅检查硬编码的§7.2审批模块—不适用于其他业务型模块的通用检查",
        "implemented": True,
    },
    {
        "gate": 6,
        "name": "业务截图覆盖检查",
        "skill_ref": "manual_quality_spec Q-C04/Q-T03",
        "capability": "检查真实截图数+截图预留数≥模块数；验证引用PNG文件存在且非空",
        "limitation": "不检查截图内容与章节描述是否匹配（如截图中的按钮文字是否与操作步骤表一致）",
        "implemented": True,
    },
    {
        "gate": 7,
        "name": "模型审查占位符检查",
        "skill_ref": "manual_quality_spec Q-C01",
        "capability": "检测[WARNING: ...]占位符—出现即表示正文仍包含未解决的字段缺失提示",
        "limitation": "不检查字段内容是否来自真实项目证据（那在业务理解阶段保证）",
        "implemented": True,
    },
    {
        "gate": 8,
        "name": "AI 套话检查",
        "skill_ref": "manual_quality_spec Q-W03",
        "capability": "正则匹配夸大/营销/虚指/填充句/万能结尾/过度排比等AI味表达",
        "limitation": "黑名单外的AI句型不受检查；新出现的AI写作模式无法被旧规则查出",
        "implemented": True,
    },
    {
        "gate": 9,
        "name": "角色贯穿检查",
        "skill_ref": "manual_quality_spec Q-C03/Q-W01",
        "capability": "检查每个核心模块的正文中是否出现了目标用户角色名",
        "limitation": "只检查角色关键词是否出现—不检查角色对应的操作描述是否正确（如把安全管理员的权限写在了门卫的操作说明里）",
        "implemented": True,
    },
    {
        "gate": 10,
        "name": "多端覆盖检查",
        "skill_ref": "manual_quality_spec Q-C02",
        "capability": "检查系统简介中声明的端（Web/App/大屏）在功能操作章节是否有对应标题",
        "limitation": "只检查标题存在—不检查该端的操作内容是否完整（如App端只有一句描述没有操作步骤表）",
        "implemented": True,
    },
    {
        "gate": 11,
        "name": "简介-功能清单对等检查",
        "skill_ref": "manual_quality_spec Q-I02",
        "capability": "系统简介中的每个功能段落是否在功能清单中有对应行",
        "limitation": "只检查模块名是否出现—不检查描述内容是否一致",
        "implemented": True,
    },
    {
        "gate": 12,
        "name": "登录及首页检查",
        "skill_ref": "manual_quality_spec Q-C01/Q-C04",
        "capability": "检查登录章节存在 + 登录截图或预留存在",
        "limitation": "不检查登录页面的描述是否与实际系统登录流程一致",
        "implemented": True,
    },
    {
        "gate": 13,
        "name": "代码-手册关联性检查",
        "skill_ref": "manual_quality_spec Q-T01",
        "capability": "检查每个操作手册模块是否有对应的选中代码文件覆盖",
        "limitation": "不检查代码文件内容是否真正实现了手册中描述的功能",
        "implemented": True,
    },
    {
        "gate": 14,
        "name": "交叉引用验证报告检查",
        "skill_ref": "manual_quality_spec Q-I02/Q-I04",
        "capability": "优先检查草稿/操作手册审查报告.json 的七项交叉引用结论；兼容旧版报告",
        "limitation": "不检查结论内容的正确性—只检查七项结论是否齐全且通过",
        "implemented": True,
    },
    {
        "gate": 15,
        "name": "Skill 结构化输入与审计产物检查",
        "skill_ref": "manual_quality_spec Q-C01/Q-C02",
        "capability": "检查 7 个强制审计文件存在 + 业务理解.json 主输入字段完整 + 四列操作步骤表≥业务型模块数",
        "limitation": "只检查文件存在和字段非空—不检查自检记录的轮次内容是否真实执行",
        "implemented": True,
    },
    {
        "gate": 16,
        "name": "表格信息增量检查",
        "skill_ref": "manual_quality_spec Q-W02 表格信息增量",
        "capability": "检测同表格中同列内容重复出现≥2次——要求结合行上下文改写为有区分度的表述",
        "limitation": "只检查字符串重复—无法判断两个近似但不同的表述（如'联系管理员处理'和'请管理员协助解决'）是否构成实质重复",
        "implemented": True,
    },
    {
        "gate": 17,
        "name": "证据缺口清零检查",
        "skill_ref": "manual_quality_spec Q-T01",
        "capability": "检查每个 manual_module 是否有非空 evidence 文件路径",
        "limitation": "只检查文件路径是否存在—不检查路径指向的文件是否真的包含该模块的业务逻辑代码",
        "implemented": True,
    },
    {
        "gate": 18,
        "name": "术语一致性扫描",
        "skill_ref": "manual_quality_spec Q-I01",
        "capability": "优先对照草稿/操作手册写作计划.json 的 terminology，在手册正文中搜索禁止别名；兼容旧版术语标准表",
        "limitation": "只检查术语表中已列出的别名—如果术语表本身不完整或遗漏了某个常见的错误叫法，门禁放行",
        "implemented": True,
    },
    {
        "gate": 19,
        "name": "截图位置上图下文",
        "skill_ref": "manual_quality_spec Q-W05 图片位置",
        "capability": "检查新增页面截图是否在新增/修改界面表之前而非模块末尾异常逻辑表之后",
        "limitation": "只检测两个关键位置信号（异常功能逻辑前后 + 模块边界）—不检查截图与文字描述的具体对位关系",
        "implemented": True,
    },
    {
        "gate": 20,
        "name": "语义一致性审查",
        "skill_ref": "manual_quality_spec Q-I02/Q-I03/Q-I04/Q-I05",
        "capability": "强制执行五维度语义审查——前后表述一致/状态机闭环/角色路径完整/FAQ矛盾检测/功能清单与详情一致。门禁只检查审查报告是否存在且无❌——实际审查由模型完成",
        "limitation": "审查质量取决于模型是否认真通读手册全文——门禁只保证审查框架被覆盖，不保证每个维度都被深入检查",
        "implemented": True,
    },
    {
        "gate": 21,
        "name": "代码泄漏检查",
        "skill_ref": "manual_quality_spec Q-W04",
        "capability": "正则检测手册正文中的代码泄漏——camelCase/PascalCase标识符、URL路径、Java注解、SQL关键字、变量命名模式。每处标记为error——要求根据后端语义翻译为非技术背景人员能理解的中文",
        "limitation": "术语表中声明的缩写（如NFC/GPS/UDP）和必要的技术描述（如WebSocket实时推送）可能被误报——需人工判断是否豁免。不检查截图中的文字——截图内容的校验需要视觉识别",
        "implemented": True,
    },
    {
        "gate": 22,
        "name": "数据字典/内部标识符泄漏检查",
        "skill_ref": "manual_quality_spec Q-W04",
        "capability": "正则检测 `snake_case_identifier` 格式的代码引用出现在'数据字典''系统字段''字典'等上下文附近——标记为warn要求替换为中文",
        "limitation": "不检查反引号外的代码泄漏（由 gate 21 处理）。仅匹配出现在'数据字典'等提示词附近的——独立出现的snake_case且不在API路径/Java包路径上下文中可能漏过",
        "implemented": True,
    },
    # ── NOT IMPLEMENTED: SKILL rules with no automated gate ──
    {
        "gate": None,
        "name": "台账型字段逐项枚举",
        "skill_ref": "manual_authoring_spec §6.1 + manual_quality_spec Q-T01",
        "implemented": False,
        "reason": "需要提取每个台账型模块的列表列并与实际页面源码比对——需要源码访问和语义匹配，不适合正则",
    },
    {
        "gate": None,
        "name": "章节边界违例检查",
        "skill_ref": "manual_quality_spec Q-I05",
        "implemented": False,
        "reason": "需要语义理解两个章节是否描述了同一功能—正则只能匹配完全相同的字符串",
    },
    {
        "gate": None,
        "name": "读者覆盖缺口检查",
        "skill_ref": "manual_quality_spec Q-C03",
        "implemented": False,
        "reason": "需要把每个读者问题映射到手册中的具体段落—语义匹配非正则",
    },
    {
        "gate": None,
        "name": "自检记录轮次内容审查",
        "skill_ref": "manual_quality_spec §6",
        "implemented": False,
        "reason": "gate 15 只检查自检记录文件是否存在—轮次内容的质量需要模型在撰写时保证",
    },
    {
        "gate": None,
        "name": "申请表主要功能描述与操作手册一致性",
        "skill_ref": "manual_quality_spec Q-I02",
        "implemented": False,
        "reason": "需要在生成申请表后交叉比对两处文本—适合作为正式资料生成前的手动检查项",
    },
    {
        "gate": None,
        "name": "截图内容一致性",
        "skill_ref": "manual_quality_spec Q-T03",
        "implemented": False,
        "reason": "需要OCR或视觉识别—不适合正则",
    },
    {
        "gate": None,
        "name": "操作手册自检记录证据缺口",
        "skill_ref": "manual_quality_spec Q-T01",
        "implemented": False,
        "reason": "gate 17 只检查模块级 evidence 文件路径—gap 内容需要模型执行读取和补写",
    },
]
FORBIDDEN_TERMS: list[tuple[str, str, str]] = [
    # (regex pattern, term description, severity: error/warn)
    (r'\bFlowable\b', "工作流引擎名称", "error"),
    (r'\bBPMN\b(?!\s*流程)', "BPMN（应写为'审批流程'）", "error"),
    (r'\bSpring\s+(Boot|Event|Cloud)', "Spring 框架名称", "error"),
    (r'\bListener\b', "事件监听器（应写为'处理'或'响应'）", "error"),
    (r'\bCountDownLatch\b', "Java 并发工具类名", "error"),
    (r'\bRESTful\b', "RESTful（应写为'接口调用'）", "error"),
    (r'\bMySQL\b', "数据库名（应写为'数据存储'）", "warn"),
    (r'\bRedis\b', "缓存组件名", "warn"),
    (r'\bMapper\b', "数据访问层名称", "warn"),
    (r'\bService\b', "服务层名称", "warn"),
    (r'\bVue\s*3\b', "前端框架名", "warn"),
    (r'\bTypeScript\b', "编程语言名", "warn"),
    (r'\bElement\s*Plus\b', "UI 组件库名", "warn"),
    (r'\bController\b', "控制器层名称", "warn"),
    (r'工作流引擎', "应写为'审批流程'", "error"),
    (r'流程定义键|process.*key', "应写为'审批流程配置'", "error"),
    (r'快照副本|DATA_TYPE_SNAPSHOT', "应写为'提交快照'", "error"),
    (r'Spring\s*Event', "应写为'系统通知'或'自动触发'", "error"),
    (r'Event\s*Listener', "应写为'处理'或'响应'", "error"),
]


def load_markdown(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_forbidden_terms(text: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for pattern, desc, severity in FORBIDDEN_TERMS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(text), m.end() + 20)
            ctx = text[ctx_start:ctx_end].replace('\n', ' ').strip()
            msg = f"  [{severity}] {desc}: \"{m.group()}\" → context: ...{ctx}..."
            if severity == "error":
                errors.append(msg)
            else:
                warnings.append(msg)
    return errors, warnings


def check_table_density(text: str) -> tuple[bool, str]:
    """Check that tables dominate over long paragraphs in function chapters."""
    # Find the Web 管理端功能操作 section
    sections = re.split(r'^### 7\.\d ', text, flags=re.M)
    large_text_blocks = 0
    table_count = 0

    for sec in sections:
        lines = sec.split('\n')
        # Count tables: sequences of | lines
        in_table = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and '---' not in stripped:
                if not in_table:
                    table_count += 1
                    in_table = True
            elif not stripped.startswith('|'):
                in_table = False

        # Find long paragraph blocks (>3 consecutive non-table, non-heading lines)
        consecutive_text = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('|') and not stripped.startswith('#') and not stripped.startswith('【'):
                consecutive_text += 1
            else:
                if consecutive_text > 3:
                    large_text_blocks += 1
                consecutive_text = 0
        if consecutive_text > 3:
            large_text_blocks += 1

    ratio = f"tables={table_count}, long-text-blocks={large_text_blocks}"
    if table_count > large_text_blocks * 2:
        return True, f"OK: {ratio} — tables dominate"
    elif table_count >= large_text_blocks:
        return True, f"WEAK: {ratio} — tables and text roughly balanced, could use more tables"
    else:
        return False, f"LOW: {ratio} — text dominates, consider converting long paragraphs to tables"


def check_chart_coverage(text: str, manual_path: Path | None = None) -> tuple[bool, str]:
    """Check real business screenshot coverage and verify referenced files.

    Technical diagrams and real screenshots are optional supporting material.
    When screenshots are skipped, clear placeholders remain acceptable.
    """
    images = re.findall(r'!\[[^\]]*\]\(截图/[^)]+\)', text)
    placeholders = re.findall(r'【截图预留：[^】]+】', text)
    if not images and not placeholders:
        return False, "没有真实业务截图或清晰的截图预留"
    if not any("登录" in item for item in [*images, *placeholders]):
        return False, "缺少登录界面截图或清晰预留"

    operation_chapters = len(re.findall(r'^##\s+\d+\s+(?!系统简介|系统概述|运行与使用要求|常见问题解答|使用与数据管理注意事项).+', text, re.M))
    minimum = max(5, operation_chapters)
    if len(images) + len(placeholders) < minimum:
        return False, f"业务页面截图或预留共 {len(images) + len(placeholders)} 张，少于主要操作章节覆盖下限 {minimum} 张"

    # ── Per-module form screenshot check ──
    # For modules that have a 新增/修改字段表 or 表单, verify a form screenshot exists
    text_lines = text.split("\n")
    all_screenshots = images + placeholders

    # Find all module sections (### N.N)
    module_starts = []
    for i, line in enumerate(text_lines):
        if re.match(r'^### \d+[A-Z]?\.\d+ ', line):
            module_starts.append((i, line.strip()))

    modules_without_form_screenshot = []
    for idx, (start_i, heading) in enumerate(module_starts):
        # Get module body (from this heading to next ### or ##)
        end_i = module_starts[idx + 1][0] if idx + 1 < len(module_starts) else len(text_lines)
        for j in range(start_i + 1, end_i):
            if text_lines[j].startswith("## "):
                end_i = j
                break
        body = "\n".join(text_lines[start_i:end_i])

        # Does this module have a form/field table? (新增/修改界面 or 字段表)
        has_form_section = bool(re.search(r'(新增|修改|字段表|字段名称|对话框|录入)', body))
        if not has_form_section:
            continue

        # Does this module have a screenshot?
        module_name = re.sub(r'^### \d+[A-Z]?\.\d+ ', '', heading)
        has_screenshot = any(
            module_name[:4] in sc for sc in all_screenshots
        ) or any(
            sc in body for sc in all_screenshots  # check if screenshot is in this module's body
        )
        # More precise: check if any screenshot or placeholder falls within this module's body
        has_screenshot_in_body = False
        for sc in all_screenshots:
            sc_line_idx = -1
            for k in range(start_i, end_i):
                if sc in text_lines[k]:
                    sc_line_idx = k
                    break
            if sc_line_idx >= 0:
                has_screenshot_in_body = True
                break

        if not has_screenshot_in_body:
            modules_without_form_screenshot.append(module_name[:30])

    if modules_without_form_screenshot:
        return False, (
            f"以下模块有新增/修改表单但缺少对应截图：{'、'.join(modules_without_form_screenshot[:5])}"
            f"——每个含表单的模块应至少有一张表单截图（紧接字段表之后）"
        )

    # Phase 2: verify PNG files exist on disk
    if manual_path and manual_path.exists():
        screenshot_dir = manual_path.parent.parent / "截图"
        if screenshot_dir.exists():
            for img_ref in images:
                filename = img_ref.split('/')[-1].rstrip(')')
                png_path = screenshot_dir / filename
                if not png_path.exists():
                    return False, f"图表文件缺失: 截图/{filename}（Markdown 中有引用但文件不存在）"
                if png_path.stat().st_size == 0:
                    return False, f"图表文件为空: 截图/{filename}"

    return True, f"OK: {len(images)} 张真实业务截图，{len(placeholders)} 个截图预留，引用文件均有效"


def check_feature_list(text: str) -> tuple[bool, str]:
    """Check that 功能清单 has sub-function detail (SOP item 7)."""
    # Find 功能清单 section (chapter number varies, match by title)
    m = re.search(
        r'^#{2,4}\s+(?:\d+(?:\.\d+)*\s+|[一二三四五六七八九十]+、)?功能清单\s*$\n(.*?)(?=^#{2,4}\s+)',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return False, "功能清单 section not found"

    section = m.group(1)
    lines = section.strip().split('\n')

    # Count table rows (skip header and separator)
    rows = [l for l in lines if l.startswith('|') and '---' not in l and '功能模块' not in l and '序号' not in l]
    if len(rows) < 10:
        return False, f"功能清单 only has {len(rows)} data rows — need at least 10 sub-function entries"

    # Check each row has meaningful detail
    short_rows = []
    for r in rows:
        cols = [c.strip() for c in r.split('|')[1:-1]]
        if len(cols) >= 2:
            detail = cols[-1]  # 功能说明 column
            if len(detail) < 30:
                short_rows.append(cols[0] if cols else '?')

    if short_rows:
        return False, f"功能清单中以下行功能说明过短 (<30字): {', '.join(short_rows[:5])}"

    return True, f"OK: {len(rows)} sub-function rows, all with sufficient detail"


def check_approval_has_flow_table(text: str) -> tuple[bool, str]:
    """Verify that business-type modules (审批) have operation flow tables, not just long paragraphs."""
    # Find 7.2 section (contractor company management)
    m = re.search(r'### 7\.2 .*?\n(.*?)(?=### 7\.3 )', text, re.DOTALL)
    if not m:
        return True, "7.2 section not found — skipping"

    section = m.group(1)
    # Only flag approval modules — skip non-approval sections (大屏, stats, etc.)
    if '审批' not in section and '签批' not in section and '备案' not in section:
        return True, "7.2 section is not an approval module — skipping"

    # Check for operation step table (步骤 | 用户操作 | 系统响应)
    if '操作步骤 | 用户操作 | 系统响应' in section:
        return True, "审批部分有操作步骤三列表"

    # Check for status flow table
    if '备案状态 | 含义 | 对应公司类型' in section or '备案状态 | 含义' in section:
        return True, "审批部分有状态流转表"

    # Check if there are at least 3 tables in the approval section
    table_count = len(re.findall(r'^\|.*\|', section, re.M))
    if table_count >= 4:
        return True, f"审批部分有 {table_count} 张表，符合表格化要求"

    return False, "审批部分缺少操作步骤表或状态流转表——请用表格替代长段落"


def check_code_leakage(text: str) -> tuple[list[str], list[str]]:
    """Gate 21 — detect code-level identifiers, paths, and patterns that leaked
    into the operation manual. Must be translated to plain Chinese per SKILL §6.

    Returns (errors, warnings). Errors are definitive; warnings need judgment.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── comment-syntax leakage: if // /* <!-- appear in manual, it's
    #     copy-paste from source code without translation — hard error
    comment_errors: list[str] = []
    for pattern, label, fix_hint in [
        (r'//\s*\S', "单行注释 `//`", "代码注释语法——应翻译为中文陈述句或直接删除"),
        (r'/\*[\s\S]*?\*/', "块注释 `/* */`", "代码注释块——应翻译为中文陈述句或直接删除"),
        (r'<!--[\s\S]*?-->', "HTML注释 `<!-- -->`", "HTML注释——应删除"),
        (r'@(author|date|param|return|throws|since|see|deprecated)\b',
         "Javadoc 注解", "代码文档注释标签——应写为该注解说明的中文表述"),
    ]:
        for m in re.finditer(pattern, text):
            ctx = text[max(0,m.start()-25):min(len(text),m.end()+25)].replace('\n',' ').strip()
            comment_errors.append(
                f"  [{label}] \"{m.group()[:60]}\" → {fix_hint}  context: ...{ctx}..."
            )
    if comment_errors:
        comment_errors.insert(0,
            f"  [注释语法泄漏] 手册正文中检测到 {len(comment_errors)} 处代码注释语法——"
            f"这是从源码复制粘贴未翻译的明确信号。请逐条将注释内容翻译为中文陈述句或删除。")
    errors.extend(comment_errors)

    # ── definitive: these should never appear in a user-facing manual ──
    error_patterns: list[tuple[str, str, str]] = [
        # Java/Spring annotations and keywords
        (r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping|RestController|Autowired|Validated|Component|Service\b)',
         "Java 注解（如 @GetMapping）", "HTTP请求方法注解——应写为'接口调用'或'页面请求'"),
        # PascalCase class/component/Handler names — Capital-start compound word
        (r'\b[A-Z][a-z]+(?:[A-Z][a-z]+){2,}\b',
         "PascalCase 类名/Handler 名", "后端类名——应写为该类的中文功能说明（如'立即推送且指定执行人的处理器'→'即时推送+指定人员'）"),
        # camelCase variable names — lower-start compound word
        (r'\b[a-z]+[A-Z][a-zA-Z]{4,}\b',
         "camelCase 标识符", "代码变量/函数名——应写为该字段的中文名称或用途说明"),
        # Single-word CamelCase nouns that are code concepts
        (r'\b(Handler|Controller|Service\b|Mapper\b|Repository\b|Factory\b|Strategy\b|Adapter\b|Listener\b)',
         "设计模式/分层术语", "后端架构术语——应写为'处理模块''数据访问'或省略"),
        # Standalone Assigned/Unassigned patterns
        (r'\b(WithoutAssign|AndAssign|AndCustomCycle|WithAssign)\b',
         "代码枚举值", "参数枚举标识——应写为'不指定人员模式''指定人员模式''自定义周期模式'"),
        # URL paths with slashes
        (r'/(inspection|system|personposition|alertMg|basicinfo|jobslip|education|contractorInfo|shuangyufang)/\w+(/\w+)*',
         "API 路径", "后端接口路由——应写为功能页面的操作路径或菜单入口"),
        # SQL keywords in prose
        (r'\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|ORDER BY|sys_menu|sys_dict)\b',
         "SQL 关键字", "数据库查询语句——应写为数据操作或配置的通俗描述"),
        # Java package paths
        (r'com\.welleyao\.[a-z.]{10,}',
         "Java 包路径", "后端模块的包名——应写为该模块的功能说明"),
        # File extensions in prose
        (r'\b\.java\b|\b\.vue\b|\b\.tsx?\b|\b\.kt\b',
         "源码文件后缀名", "源代码文件类型——应写为对应的功能组成说明"),
        # Config/property names in lowerCamel
        (r'\b(isImmediatelyPush|taskGenerateStartTime|taskGenerateEndTime|pushUserIds|isCustomCycle|cycleInterval|cycleUnit|troubleshootType|isPackageDuty|taskType|deptId|inspectionPlanId)\b',
         "数据库字段名", "后端模型属性——应写为该字段的中文含义"),
        # Framework references
        (r'\b(MyBatis|Netty|Spring Boot|Sa-Token|EasyExcel|Lombok|Hutool)\b',
         "框架名称", "技术框架——应写为该框架提供的功能说明或省略"),
    ]
    # ── advisory: may be acceptable in context (e.g. system requirements section) ──
    warn_patterns: list[tuple[str, str, str]] = [
        (r'\b(WebSocket|WebRTC|RTSP|UWB|UDP|LoRa)\b',
         "技术协议缩写", "仅在术语表和系统要求中有必要时保留——正文中优先使用白话说明。NFC/GPS 作为签到方式属于业务术语，不在本检查范围"),
        (r'\b(MySQL|Redis|RocketMQ|Kafka|RabbitMQ|Nginx|JDK|JVM)\b',
         "中间件/组件名称", "仅在系统要求节中列举运行环境时保留——功能操作章节不得出现"),
    ]

    for pattern, label, fix_hint in error_patterns:
        for m in re.finditer(pattern, text):
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 30)
            ctx = text[ctx_start:ctx_end].replace('\n', ' ').strip()
            # Skip if match is inside backtick-delimited inline annotation.
            # `` `cycleInterval`（间隔数）`` is deliberate field documentation, not leakage.
            opening_bt = text.rfind('`', 0, m.start())
            closing_bt = text.find('`', m.start())
            if (opening_bt >= 0 and closing_bt >= 0
                    and opening_bt < m.start() < closing_bt):
                continue
            # Skip if this appears in system requirements section (§4)
            line_start = text.rfind('\n', 0, m.start()) + 1
            prev_text = text[:line_start]
            h2_match = list(re.finditer(r'^##\s+\d+\s+(.+)', prev_text, flags=re.M))
            section_title = h2_match[-1].group(1) if h2_match else ''
            if '系统要求' in section_title:
                continue  # System requirements section is the ONE allowed place
            errors.append(
                f"  [{label}] \"{m.group()}\" → {fix_hint}  context: ...{ctx}..."
            )

    for pattern, label, fix_hint in warn_patterns:
        for m in re.finditer(pattern, text):
            line_start = text.rfind('\n', 0, m.start()) + 1
            prev_text = text[:line_start]
            h2_match = list(re.finditer(r'^##\s+\d+\s+(.+)', prev_text, flags=re.M))
            section_title = h2_match[-1].group(1) if h2_match else ''
            if '系统要求' in section_title or '术语表' in section_title:
                continue  # OK in these sections
            ctx = text[max(0,m.start()-30):min(len(text),m.end()+30)].replace('\n',' ').strip()
            warnings.append(
                f"  [{label}] \"{m.group()}\" → {fix_hint}  context: ...{ctx}..."
            )

    return errors, warnings


def check_model_warning_placeholders(text: str) -> tuple[bool, str]:
    """Check for unreplaced [WARNING: ...] / [FIXME: ...] / [...待补全...] placeholders.

    These are injected by manual renderers/fallback when model JSON misses required fields.
    Their presence means the model hasn't completed the review loop (SKILL Step 11).
    """
    patterns = [
        (r'\[WARNING:', "模型审查占位符"),
        (r'\[FIXME:', "待修复标记"),
        (r'\.\.\.待补全\.\.\.', "待补全占位符"),
        (r'\[MISSING:', "缺失字段标记"),
    ]
    for pattern, label in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return False, f"仍有 {label}：{matches[0][:80]}"
    return True, "OK: 无模型审查占位符"


def check_ai_slop_phrases(text: str) -> tuple[list[str], list[str]]:
    """Scan for AI-generated fluff using Humanizer-influenced pattern categories.

    Pattern sources:
      - Humanizer #1:  Significance inflation (grandiose framing)
      - Humanizer #4:  Promotional / marketing language
      - Humanizer #5:  Vague attributions (虚指)
      - Humanizer #7:  AI vocabulary (高频连接词/过渡词)
      - Humanizer #10: Artificial lists (过度排比)
      - Humanizer #22: Signposting announcements (引导句)
      - Humanizer #25: Chatbot artifacts (客套残留)
      - Humanizer #28: Filler phrases (填充句)
      - Humanizer #29: Excessive hedging (过度弱化)
      - Humanizer #30: Generic conclusions (万能结尾)
    """
    errors: list[str] = []
    warnings: list[str] = []

    AI_SLOP: list[tuple[str, str, str]] = [
        # ── 夸大 / 营销 (Humanizer #1 #4) ──
        (r'旨在', "夸大：'旨在'（直接陈述，不宣告目的）", "error"),
        (r'赋能', "营销：'赋能'", "error"),
        (r'深度赋能', "营销：'深度赋能'", "error"),
        (r'赋能.{0,10}(企业|行业|团队|组织)', "营销：'赋能XX'", "error"),
        (r'一站式', "营销：'一站式'", "error"),
        (r'智能化', "营销：'智能化'", "error"),
        (r'高效便捷', "营销：'高效便捷'", "error"),
        (r'高效[的地]', "营销：'高效地...'", "warn"),
        (r'显著提升', "夸大：'显著提升'", "error"),
        (r'强大能力', "夸大：'强大能力'", "error"),
        (r'丰富功能', "夸大：'丰富功能'", "error"),
        (r'无缝衔接', "夸大：'无缝衔接'", "error"),
        (r'极致', "夸大：'极致'", "error"),
        (r'引领', "夸大：'引领'", "error"),
        (r'全方位', "夸大：'全方位'", "warn"),
        (r'全面覆盖', "夸大：'全面覆盖'", "warn"),
        (r'端到端', "营销：'端到端'", "warn"),
        (r'闭环管理', "夸大：'闭环管理'（应写为具体业务环节描述）", "warn"),
        (r'保驾护航', "夸大：'保驾护航'（删掉）", "error"),
        (r'坚实(基础|保障|后盾)', "夸大：'坚实XX'", "warn"),
        (r'有力(支撑|保障)', "夸大：'有力XX'", "warn"),
        (r'奠定了.{0,6}(坚实|牢固|稳固|重要)', "夸大：'奠定了……基础'", "error"),

        # ── 虚指 (Humanizer #5) ──
        # Note: "根据" is a compound preposition ("based on"), not vague attribution.
        # Only standalone 据 + short gap is the flag pattern.
        (r'(?:^|[^根依])据(?:行业|领域|相关|最新|不完全|初步|有关|消息|人士).{0,4}(?:分析|统计|调查|研究|报告|显示|表明)', "虚指：'据行业分析'（无具体来源则删）", "warn"),
        (r'(行业|领域|业界).{0,4}(普遍|公认|一致)', "虚指：'行业普遍认为'（无数据支撑则删）", "warn"),
        (r'(众所周知|毋庸置疑|不言而喻)', "虚指：'众所周知'（删掉）", "error"),
        (r'专家.{0,3}(指出|认为|建议)', "虚指：'专家指出'（无名无姓则删）", "warn"),

        # ── AI 高频连接词 (Humanizer #7) ──
        (r'此外，', "AI 连接词：'此外，'（可用'同时''另外'或直接写下一句）", "warn"),
        (r'值得一提的是，', "AI 连接词：'值得一提的是，'（删掉直接写）", "error"),
        (r'值得注意的是，', "AI 连接词：'值得注意的是，'（删掉直接写）", "error"),
        (r'与此同时，', "AI 连接词：'与此同时，'（删掉或简化为'同时'）", "warn"),
        (r'换而言之，', "AI 连接词：'换而言之，'（删掉）", "error"),
        (r'总而言之，', "AI 结尾：'总而言之，'（删掉）", "error"),
        (r'综上所述，', "AI 结尾：'综上所述，'（删掉）", "error"),
        (r'不难看出，', "AI 连接词：'不难看出，'（删掉直接陈述结论）", "error"),
        (r'由此可见，', "AI 连接词：'由此可见，'", "warn"),

        # ── 填充句 (Humanizer #28) ──
        (r'为了(能够|可以|实现|达到|满足)', "填充：'为了能够'（简化为'为'或'以'）", "warn"),
        (r'通过.{2,15}的方式(来)?(进行|实现|完成)', "填充：'通过……的方式来进行'（简化为'以……'或'通过……'）", "warn"),
        (r'以此来实现', "填充：'以此来实现'（删掉或简化为'以'）", "error"),
        (r'从而(达到|实现|使得)', "填充：'从而达到'（简化为'使'或删掉）", "warn"),
        (r'以(便|利于|便于|期)(达到|实现|完成)', "填充：'以便于达到'（简化为'以'）", "warn"),
        (r'来进行', "填充：'来进行'（删掉，前接动词即可）", "warn"),
        (r'进行了?(相应的|相关的|必要的|有效的)', "填充：'进行了相应的处理'（删修饰词，写具体动作）", "warn"),

        # ── 引导句 (Humanizer #22) ──
        (r'^(#*\s*)?下面(我们)?(来)?(看一下|介绍一下|了解一下|看看)', "引导：'下面我们来介绍一下'（删掉直接写内容）", "error"),
        (r'^(#*\s*)?接下来(我们)?(来)?(看|介绍|了解)', "引导：'接下来我们来看'（删掉直接写内容）", "error"),
        (r'^(#*\s*)?本章(将|主要)?介绍', "引导：'本章介绍'（改为直接叙述该章的内容是什么）", "warn"),
        (r'^(#*\s*)?本节(将|主要)?介绍', "引导：'本节介绍'", "warn"),

        # ── 客套残留 (Humanizer #25) ──
        (r'希望(以上|本).{0,8}(对您|对你|有所帮助|有所助益)', "客套：'希望以上内容对您有帮助'（删掉）", "error"),
        (r'如有(疑问|问题|不明)', "客套：'如有疑问请联系……'（删掉，FAQ 不需结尾客套）", "warn"),
        (r'祝(您)?(使用|工作|生活|一切)愉快', "客套：'祝使用愉快'（删掉）", "error"),

        # ── 过度弱化 (Humanizer #29) ──
        (r'一般(来说|而言|来讲|情况|情况下)', "弱化：'一般来说'（有确切值则写确切值）", "warn"),
        (r'通常(来说|而言|情况|情况下|的|地)?', "弱化：'通常'（有确切值则写确切值）", "warn"),
        (r'大概(是|有)?', "弱化：'大概是'", "warn"),
        (r'比较(常见|常用|普遍|多)', "弱化：'比较常见'", "warn"),
        (r'(相对|较为)(而言|来说)?', "弱化：'相对而言'", "warn"),
        (r'可能(会|可以|能|需要|有|是)?', "弱化：'可能会'（确定则删'可能'）", "warn"),

        # ── 万能结尾 (Humanizer #30) ──
        (r'为(企业|行业|社会|用户|客户).{0,15}(做出|作出|提供|创造|贡献)', "空结尾：'为企业做出贡献'（改为具体结果）", "warn"),
        (r'助力(企业|行业|用户).{0,10}(发展|成长|进步|前行)', "空结尾：'助力企业发展'（改为具体结果）", "error"),
        (r'从而(更好地|有效的|高效地)', "空结尾：'从而更好地……'", "warn"),

        # ── 过度排比 (Humanizer #10) ──
        (r'高效.{0,4}、.{0,4}安全.{0,4}、.{0,4}可靠', "排比：'高效、安全、可靠'（改为自然列举）", "warn"),
        (r'简单、.{0,4}高效', "排比：'简单、高效'", "warn"),
        (r'便捷、.{0,4}高效', "排比：'便捷、高效'", "warn"),
    ]

    for pattern, desc, severity in AI_SLOP:
        matches = re.finditer(pattern, text)
        for m in matches:
            ctx_start = max(0, m.start() - 15)
            ctx_end = min(len(text), m.end() + 15)
            ctx = text[ctx_start:ctx_end].replace('\n', ' ').strip()
            msg = f"  [{severity}] {desc} → context: ...{ctx}..."
            if severity == "error":
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors, warnings


def check_role_penetration(text: str) -> tuple[bool, str]:
    """Verify that every module section body mentions at least one target user role.

    Each ### section under the Web/App operation chapters should read like
    it was written for a real person doing real work.  The simplest signal:
    at least one role term appears in the section body.
    """
    role_terms = [
        "安全管理员", "班组长", "巡检人员", "企业负责人",
        "整改责任人", "验收人", "管理员", "业务部门",
        "安全管理部门", "部门负责人", "现场操作人员",
        "门卫", "安保人员", "值班人员", "访客", "现场管理人员", "控制室值班人员",
    ]

    # Check detailed operation subsections, not overview/requirements/FAQ sections.
    module_sections = re.findall(
        r'^### (6B?\.\d+ .+?|(?:5|7|8|10)\.\d+ .+?)\n(.*?)(?=^### (?:5|6|7|8|10)\.\d+ |^## )',
        text, re.MULTILINE | re.DOTALL,
    )

    weak_modules: list[str] = []
    for title, body in module_sections:
        # Skip sections that are just placeholder headers
        if len(body.strip()) < 50:
            continue
        found = any(term in body for term in role_terms)
        if not found:
            weak_modules.append(title.strip())

    if weak_modules:
        return False, f"以下模块未体现用户角色：{'、'.join(weak_modules[:8])}"

    return True, f"OK: all {len(module_sections)} module sections reference target user roles"


def check_endpoint_coverage(text: str) -> tuple[bool, str]:
    """Verify that multi-endpoint systems have per-endpoint operation chapters.

    Heuristic: if the system intro mentions 大屏/App/移动端/Android, then the
    functional operation area (chapters 六 through 九) must contain section
    headers that explicitly reference those endpoints.
    """
    # Detect declared endpoints from system intro/summary areas
    declared_endpoints: set[str] = set()
    intro_text = text[:3000]  # System intro and overview are in first ~2K chars
    for pattern, label in [
        (r'大屏(展示端)?', "screen"),
        (r'安卓\s*(App)?端|App\s*端|Android\s*(App)?端|移动端', "app"),
        (r'Web\s*(管理)?端|浏览器', "web"),
    ]:
        if re.search(pattern, intro_text):
            declared_endpoints.add(label)

    # Web-endpoint is always implied if not explicitly stated
    if "web" not in declared_endpoints:
        declared_endpoints.add("web")

    if len(declared_endpoints) <= 1:
        return True, "OK: single-endpoint system — no multi-endpoint split required"

    # Check the complete heading set. Operation chapters may be organized by
    # business module instead of one fixed "某端功能操作" title.
    chapter_text = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    endpoint_chapter_map = {
        "web": r'Web\s*管理端|系统登录|定位卡管理|外来人员出入记录管理|实时位置与历史轨迹|地图与摄像头管理',
        "app": r'安卓\s*App|Android\s*App|App\s*端|移动端',
        "screen": r'人员定位大屏|大屏\s*(展示)?',
    }

    missing: list[str] = []
    for ep_label, pattern in endpoint_chapter_map.items():
        if ep_label not in declared_endpoints:
            continue
        if not re.search(pattern, chapter_text):
            missing.append(ep_label)

    if missing:
        label_map = {"web": "Web 管理端", "app": "App 端", "screen": "大屏展示端"}
        return False, (
            f"多端系统（{', '.join(label_map[e] for e in declared_endpoints)}）"
            f"缺少以下端的独立功能操作章节：{'、'.join(label_map[m] for m in missing)}"
        )

    return True, f"OK: {len(declared_endpoints)} endpoints each have dedicated operation chapters"


def check_intro_function_parity(text: str) -> tuple[bool, str]:
    """Verify that every function module in the 功能清单 table has a corresponding
    feature paragraph in the System Introduction (1 系统简介).

    This catches the common failure mode where the model writes a complete 功能清单
    table but omits feature paragraphs from the narrative intro — the two layers
    fall out of sync and the intro reads as a subset of what the system actually does.
    """
    # ── Phase 1: extract feature-paragraph titles from system intro ──
    m = re.search(r'## \d+ 系统简介\n(.*?)(?=\n## \d)', text, re.DOTALL)
    if not m:
        return True, "系统简介 section not found — skipping parity check"

    intro = m.group(1)
    # Skip past the leading boilerplate to where feature paragraphs begin
    for marker in ("其主要功能如下：", "如下：", "主要功能如下："):
        idx = intro.find(marker)
        if idx > 0:
            intro = intro[idx + len(marker):]
            break

    intro_titles: set[str] = set()
    for para in re.split(r'\n\n+', intro):
        clean = para.strip().replace('\n', ' ')
        if len(clean) < 60:
            continue
        # Feature paragraph title = text before first "。"
        first_period = clean.find('。')
        if first_period < 5 or first_period > 30:
            continue
        title = clean[:first_period]
        intro_titles.add(title)

    if not intro_titles:
        return True, "系统简介中未检测到功能段落 — skipping parity check"

    # ── Phase 2: extract function-module names from the function list table ──
    m2 = re.search(
        r'^#{2,4}\s+(?:\d+(?:\.\d+)*\s+|[一二三四五六七八九十]+、)?功能清单\s*$\n(.*?)(?=^#{2,4}\s+)',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m2:
        return True, "功能清单 section not found — skipping parity check"

    func_list = m2.group(1)
    func_modules: set[str] = set()
    for line in func_list.split('\n'):
        if not line.startswith('|') or '---' in line or '功能模块' in line or '序号' in line:
            continue
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) >= 2:
            func_modules.add(cols[1])  # col 1 = 功能模块 column

    if not func_modules:
        return True, "功能清单表中无数据行 — skipping parity check"

    # ── Phase 3: fuzzy-match — each function module should have a related intro paragraph ──
    uncovered: list[str] = []
    for fm in func_modules:
        # A module is "covered" if at least one intro paragraph title
        # shares ≥50% character overlap with the module name
        fm_chars = set(fm.replace(' ', ''))
        if not fm_chars:
            continue
        matches = []
        for it in intro_titles:
            it_chars = set(it.replace(' ', ''))
            overlap = len(fm_chars & it_chars)
            min_len = min(len(fm_chars), len(it_chars))
            if min_len > 0 and overlap / min_len >= 0.4:
                matches.append(it)
        if not matches:
            uncovered.append(fm)

    if uncovered:
        return False, (
            f"系统简介缺少以下功能模块的对应段落：{'、'.join(uncovered[:8])}"
        )

    return True, f"OK: all {len(func_modules)} function modules have corresponding intro paragraphs"


def check_code_manual_correlation(manual_path: Path) -> tuple[bool, str]:
    """Verify that the code file selection and operation manual modules are correlated.

    This is a sanity check, NOT a hard coverage gate.  Soft copyright review requires
    that the code materials demonstrate the software's actual functionality — not that
    every single page is represented in the code.  The check warns (not errors) on
    partial gaps, and only errors on two clear-cut failure modes:

    1. Zero modules have any selected evidence files (the code and manual are completely unrelated).
    2. Router/menu configuration files appear in the selected code (these are not source code).
    """
    # Derive workdir from manual path: 草稿/操作手册.md → 草稿/.. = workdir
    workdir = manual_path.parent.parent

    # ── Load code selection ──
    sel_path = workdir / "草稿/代码文件选择.json"
    if not sel_path.exists():
        return True, "代码文件选择.json 不存在 — skipping correlation check"

    try:
        with open(sel_path, encoding="utf-8") as f:
            sel = json.load(f)
    except Exception:
        return True, "代码文件选择.json 无法读取 — skipping correlation check"

    selected = [f for f in sel.get("files", []) if f.get("selected")]
    if not selected:
        return True, "无选中代码文件 — skipping correlation check"

    selected_paths = {f.get("path", "").replace("\\", "/") for f in selected}

    # ── Flag router/menu files in selected code ──
    ROUTER_PATTERNS = [
        r'/router/',
        r'/router\.',
        r'router\.(ts|js|tsx|jsx)$',
        r'menu\.(ts|js|tsx|jsx)$',
        r'/menu/',
        r'menuConfig',
        r'sys_menu',
        r'permission\.(ts|js)$',
        r'routeMap',
    ]
    router_hits: list[str] = []
    for sp in selected_paths:
        for pattern in ROUTER_PATTERNS:
            if re.search(pattern, sp, re.IGNORECASE):
                router_hits.append(sp)
                break

    if router_hits:
        return False, (
            f"选中代码中含 {len(router_hits)} 个路由/菜单配置文件（不是源码）："
            + "、".join(p.rsplit("/", 1)[-1] for p in router_hits[:5])
            + "——请从代码选择中移除"
        )

    # ── Load business context for manual_modules ──
    biz_path = workdir / "草稿/业务理解.json"
    if not biz_path.exists():
        return True, "业务理解.json 不存在 — skipping correlation check"

    try:
        with open(biz_path, encoding="utf-8") as f:
            biz = __import__("json").load(f)
    except Exception:
        return True, "业务理解.json 无法读取 — skipping correlation check"

    modules = biz.get("manual_modules") or []
    if not modules:
        return True, "manual_modules 为空 — skipping correlation check"

    # ── per-module coverage check ──
    covered: list[str] = []
    uncovered: list[str] = []
    for m in modules:
        title = m.get("title", "?")
        evidence = [
            e.replace("\\", "/")
            for e in (m.get("evidence") or [])
        ]
        if not evidence:
            uncovered.append(f"{title}(无evidence)")
            continue
        has_one = any(e in selected_paths for e in evidence)
        if has_one:
            covered.append(title)
        else:
            uncovered.append(title)

    if not covered:
        return False, (
            f"严重：全部 {len(modules)} 个模块在代码材料中均无对应文件覆盖——"
            "操作手册与代码材料完全脱节，审核将直接驳回"
        )

    if uncovered:
        return True, (
            f"WARNING: {len(uncovered)}/{len(modules)} 个模块无代码覆盖"
            f"（{'、'.join(uncovered[:4])}），但 {len(covered)} 个模块已有覆盖——"
            "审核可接受"
        )

    return True, (
        f"OK: all {len(modules)} modules have at least one selected evidence file"
        f" — code-manual correlation is complete"
    )




def check_login_and_homepage(text: str) -> tuple[bool, str]:
    """Verify login coverage; accept placeholders when screenshots are skipped."""
    login_heading = r'^#{2,4}\s+(?:\d+(?:\.\d+)*\s+)?[^\n]*登录[^\n]*$'
    has_login = bool(re.search(login_heading, text, re.MULTILINE))
    has_login_image = bool(re.search(r'!\[[^\]]*登录[^\]]*\]\(截图/[^)]+\)', text))
    has_login_placeholder = bool(re.search(r'【截图预留：[^】]*登录[^】]*】', text))
    if not has_login or not (has_login_image or has_login_placeholder):
        return False, "缺少登录操作章节或登录界面截图预留"

    claims_homepage = bool(re.search(r'^#{2,4}\s+(?:\d+(?:\.\d+)*\s+)?系统首页\s*$', text, re.MULTILINE))
    has_homepage_image = bool(re.search(r'!\[[^\]]*首页[^\]]*\]\(截图/[^)]+\)', text))
    has_homepage_placeholder = bool(re.search(r'【截图预留：[^】]*首页[^】]*】', text))
    if claims_homepage and not (has_homepage_image or has_homepage_placeholder):
        return False, "手册声明存在系统首页，但缺少对应截图或预留"
    return True, "OK: 登录章节及截图/预留齐全；系统首页按真实页面存在性检查"


def cross_reference_check(manual_path: Path) -> tuple[bool, str]:
    """Verify the unified report first, then fall back to the legacy Markdown report."""
    unified = load_review_report(manual_path.parent)
    if unified:
        ok, missing = checks_pass(unified.get("cross_reference"), CROSS_REFERENCE_ITEMS)
        if ok:
            return True, "OK: 统一审查报告中的七项交叉引用检查均通过"
        return False, "操作手册审查报告.json 中交叉引用检查未通过：" + "、".join(missing)

    report_path = manual_path.parent / "交叉引用验证报告.md"
    if not report_path.exists():
        return False, "缺少草稿/交叉引用验证报告.md"
    report = report_path.read_text(encoding="utf-8")
    required_items = [
        "功能清单",
        "业务声明",
        "术语一致性",
        "状态值完备性",
        "截图引用",
        "按钮/字段名一致性",
        "FAQ 覆盖",
    ]
    missing = [item for item in required_items if item not in report]
    if missing:
        return False, "交叉引用验证报告缺少检查项：" + "、".join(missing)
    unresolved_markers = ("❌", "未通过", "TODO", "待处理", "待修复")
    unresolved = [marker for marker in unresolved_markers if marker in report]
    if unresolved:
        return False, "交叉引用验证报告仍包含未解决标记：" + "、".join(unresolved)
    return True, "OK: 七项交叉引用验证报告完整且无未解决标记"


def check_skill_required_inputs(manual_path: Path, text: str) -> tuple[bool, str]:
    """Verify the structured business input and required audit artifacts."""
    workdir = manual_path.parent.parent
    draft_dir = workdir / "草稿"
    legacy_required_files = [
        "术语标准表.md",
        "章节职责边界.md",
        "读者覆盖矩阵.md",
        "交叉引用验证报告.md",
        "模块完整性自检记录.json",
        "操作手册自检记录.md",
        "操作手册自检记录.json",
    ]
    has_unified = (draft_dir / PLAN_FILE).exists() and (draft_dir / REVIEW_FILE).exists()
    if not has_unified:
        missing = [name for name in legacy_required_files if not (draft_dir / name).exists()]
        if missing:
            return False, (
                f"缺少统一审计文件 {PLAN_FILE}/{REVIEW_FILE}，且旧版兼容审计文件不完整："
                + "、".join(missing)
            )

    business_path = draft_dir / "业务理解.json"
    if not business_path.exists():
        return False, "缺少草稿/业务理解.json"
    try:
        business = json.loads(business_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"业务理解.json 无法解析：{exc}"

    required_lists = ["manual_modules", "operation_flow", "system_requirements", "faq", "glossary"]
    empty = [field for field in required_lists if not business.get(field)]
    if empty:
        return False, "业务理解.json 缺少结构化主输入：" + "、".join(empty)
    if not business.get("product_composition"):
        return False, "业务理解.json 缺少 product_composition"
    closed_loop = business.get("closed_loop_validation")
    if not isinstance(closed_loop, dict) or not closed_loop.get("chain") or not closed_loop.get("node_mapping") or not closed_loop.get("conclusion"):
        return False, "业务理解.json 缺少完整 closed_loop_validation"

    modules = business["manual_modules"]
    incomplete = []
    for module in modules:
        title = str(module.get("title") or "?")
        for field in ("module_type", "client_endpoint", "evidence", "purpose", "usage", "entry"):
            if not module.get(field):
                incomplete.append(f"{title}.{field}")
        if module.get("module_type") in {"registry", "hybrid"} and not module.get("registry"):
            incomplete.append(f"{title}.registry")
        if module.get("module_type") in {"business", "hybrid"} and not module.get("business_operation"):
            incomplete.append(f"{title}.business_operation")
    if incomplete:
        return False, "manual_modules 字段不完整：" + "、".join(incomplete[:8])

    step_tables = len(re.findall(r'^\|\s*操作步骤\s*\|\s*用户操作\s*\|\s*系统响应\s*\|\s*异常处理\s*\|', text, re.M))
    business_modules = [m for m in modules if m.get("module_type") == "business"]
    if step_tables < len(business_modules):
        return False, f"四列操作步骤表仅 {step_tables} 张，少于业务型模块数 {len(business_modules)}"
    if text.count("操作路径") < len({m.get("client_endpoint") for m in modules}):
        return False, "操作路径数量不足以覆盖全部客户端"

    artifact_mode = "统一审计文件" if has_unified else "旧版兼容审计文件"
    return True, f"OK: {len(modules)} 个结构化模块，{step_tables} 张四列步骤表，{artifact_mode}齐全"


def semantic_consistency_check(manual_path: Path) -> tuple[bool, str]:
    """Verify unified semantic checks first, then fall back to the legacy report."""
    unified = load_review_report(manual_path.parent)
    if unified:
        ok, missing = checks_pass(unified.get("semantic_consistency"), SEMANTIC_ITEMS)
        if ok:
            return True, "OK: 统一审查报告中的五维度语义一致性检查均通过"
        return False, "操作手册审查报告.json 中语义一致性检查未通过：" + "、".join(missing)

    semantic_report = manual_path.parent / "语义一致性审查报告.md"
    if not semantic_report.exists():
        return False, "缺少草稿/操作手册审查报告.json 或旧版语义一致性审查报告.md"
    report = semantic_report.read_text(encoding="utf-8")
    missing_sections = [item for item in SEMANTIC_ITEMS if item not in report]
    if missing_sections:
        return False, "语义一致性审查报告缺少检查项：" + "、".join(missing_sections)
    unresolved = re.findall(r"(❌|未通过|TODO|待修复|不一致)", report, flags=re.M)
    if unresolved:
        return False, f"语义一致性审查报告仍有 {len(unresolved)} 个未解决问题"
    return True, "OK: 旧版五维度语义一致性审查报告通过"




def _find_profile(gate_num: int) -> dict:
    for p in GATE_PROFILES:
        if p.get("gate") == gate_num:
            return p
    return {}

def _print_gate_header(gate_num: int, profiles: list[dict], suffix: str = "") -> None:
    p = _find_profile(gate_num)
    ref = p.get("skill_ref", "") if p else ""
    suffix_str = f" {suffix}" if suffix else ""
    total_checks = sum(1 for pp in GATE_PROFILES if pp.get("gate"))
    print(f"[gate {gate_num}/{total_checks}]{suffix_str}: {ref}" if ref else f"[gate {gate_num}/{total_checks}]{suffix_str}")

def print_profile_report() -> None:
    """Print the gate-to-SKILL coverage table and exit."""
    print("=" * 60)
    print("门禁→manual_quality_spec.md 规则映射报告")
    print("=" * 60)
    print()
    total = sum(1 for p in GATE_PROFILES if p.get("gate"))
    implemented = sum(1 for p in GATE_PROFILES if p.get("implemented") and p.get("gate"))
    not_impl = sum(1 for p in GATE_PROFILES if not p.get("implemented"))
    print(f"总计: {len(GATE_PROFILES)} 条规则 (其中 {implemented} 条已实现为可执行门禁，{not_impl} 条暂未实现)")
    print()
    for p in GATE_PROFILES:
        g = p.get("gate")
        name = p.get("name","")
        status = f"Gate {g}" if g else "❌ 未实现"
        print(f"  {status:12s}  {name}")
        print(f"  {'':12s}  SKILL: {p.get('skill_ref','')}")
        if p.get("implemented"):
            print(f"  {'':12s}  能力: {p.get('capability','')[:120]}")
            print(f"  {'':12s}  局限: {p.get('limitation','')[:120]}")
        else:
            print(f"  {'':12s}  原因: {p.get('reason','')[:120]}")
        print()
    sys.exit(0)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Content quality checker for operation manual")
    p.add_argument("--manual", help="Path to 草稿/操作手册.md")
    p.add_argument("--workdir", help="Path to 软件著作权申请资料 (auto-detected if omitted)")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--exit-on-warn", action="store_true", help="Treat warnings as errors")
    p.add_argument("--profile", action="store_true", help="Print gate-to-SKILL coverage report and exit")
    args = p.parse_args()

    if args.profile:
        print_profile_report()
        return

    if not args.manual:
        print("ERROR: --manual is required")
        sys.exit(1)

    manual_path = Path(args.manual)
    if not manual_path.exists():
        print(f"QUALITY CHECK ERROR: {manual_path} not found")
        sys.exit(1)

    text = load_markdown(str(manual_path))

    all_errors: list[str] = []
    all_warnings: list[str] = []

    print("=" * 60)
    print("操作手册内容质量自查")
    print("=" * 60)

    # ── 检查 1: 技术术语 ──
    _print_gate_header(1, GATE_PROFILES)
    errors, warnings = check_forbidden_terms(text)
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(e)
    if warnings:
        all_warnings.extend(warnings)
        for w in warnings:
            print(w)
    if not errors and not warnings:
        print("  OK — 无禁止术语")

    # ── 检查 2: 章节编号 ──
    print("\n[2/20] 章节编号检查")
    heading_issues = major_heading_number_issues(text)
    if heading_issues:
        all_errors.extend(heading_issues)
        for issue in heading_issues:
            print(f"  [error] {issue}")
    else:
        print("  OK: 一级章节编号唯一")

    # ── 检查 3: 表图密度 ──
    print("\n[3/20] 表格密度检查 (SOP #4)")
    ok, msg = check_table_density(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"表格密度不足: {msg}")

    # ── 检查 3: 功能清单 ──
    print("\n[4/20] 功能清单迭代检查 (SOP #7)")
    ok, msg = check_feature_list(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"功能清单质量不达标: {msg}")

    # ── 检查 4: 业务型模块表格化 ──
    print("\n**[5/20] 业务模块表格化检查** (SOP #5, #6)")
    ok, msg = check_approval_has_flow_table(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"审批模块表格化不达标: {msg}")

    # ── 检查 5: 真实业务截图覆盖 ──
    print("\n[6/20] 真实业务截图覆盖检查")
    ok, msg = check_chart_coverage(text, manual_path)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"业务截图覆盖不足: {msg}")

    # ── 检查 6: 模型审查占位符检查 (SOP Step 11) ──
    print("\n[7/20] 模型审查占位符检查 (SKILL Step 11)")
    ok, msg = check_model_warning_placeholders(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"模型审查不完整: {msg}")

    # ── 检查 8: AI 套话 ──
    print("\n[8/20] AI 套话检查 (manual_quality_spec Q-W03)")
    ai_errors, ai_warnings = check_ai_slop_phrases(text)
    if ai_errors:
        all_errors.extend(ai_errors)
        for e in ai_errors:
            print(e)
    if ai_warnings:
        all_warnings.extend(ai_warnings)
        for w in ai_warnings:
            print(w)
    if not ai_errors and not ai_warnings:
        print("  OK — 无 AI 套话")

    # ── 检查 9: 角色贯穿 ──
    print("\n[9/20] 角色贯穿检查 (manual_quality_spec Q-C03/Q-W01)")
    ok, msg = check_role_penetration(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"角色贯穿不足: {msg}")

    # ── 检查 10: 多端覆盖 (Humanizer 端维度) ──
    print("\n[10/20] 多端覆盖检查 (系统简介声明的端 → 功能操作章节)")
    ok, msg = check_endpoint_coverage(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"多端覆盖不足: {msg}")

    # ── 检查 11: 简介-功能清单对等检查 ──
    print("\n[11/20] 简介-功能清单对等检查 (系统简介段落 ↔ 功能清单行)")
    ok, msg = check_intro_function_parity(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"简介-功能清单不对等: {msg}")

    # - check 12: login and optional homepage
    print()
    print("[12/20] 登录及真实首页检查")
    ok, msg = check_login_and_homepage(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"登录或首页检查失败: {msg}")

    # ── 检查 13: 代码-手册关联性检查 ──
    print("\n[13/20] 代码-手册关联性检查 (操作手册模块 ↔ 选中代码文件)")
    ok, msg = check_code_manual_correlation(manual_path)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"代码-手册关联性不足: {msg}")

    print("\n[14/20] 交叉引用验证报告检查")
    ok, msg = cross_reference_check(manual_path)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"交叉引用验证不完整: {msg}")

    print("\n[15/20] Skill 结构化输入与审计产物检查")
    ok, msg = check_skill_required_inputs(manual_path, text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"Skill 规范完整性不足: {msg}")

    # ── 检查 16: 表格信息增量 (manual_quality_spec Q-W02) ──
    print("\n[16/20] 表格信息增量检查 (manual_quality_spec Q-W02)")
    try:
        from manual_quality import content_review_quality_issues as _crqi
        from manual_model import normalize_manual_modules
        draft_dir = manual_path.parent
        biz_path = draft_dir / "业务理解.json"
        biz = None
        if biz_path.exists():
            biz = json.loads(biz_path.read_text(encoding="utf-8"))
        if biz:
            modules = normalize_manual_modules(biz, [])
            gate_issues = _crqi(text, modules, None, biz)
            if gate_issues:
                all_errors.extend(gate_issues)
                for issue in gate_issues:
                    print(f"  [error] {issue}")
            else:
                print("  OK: 无表格信息增量问题")
        else:
            print("  SKIP: 无业务理解.json")
    except Exception as e:
        print(f"  WARN: 表格检查异常: {e}")

    # ── 检查 17: evidence_gaps 清零 (SKILL.md §4) ──
    print("\n[17/20] 证据缺口清零检查 (SKILL §4)")
    biz_path2 = manual_path.parent / "业务理解.json"
    if biz_path2.exists():
        try:
            biz2 = json.loads(biz_path2.read_text(encoding="utf-8"))
            gap_count = 0
            for module in biz2.get("manual_modules") or []:
                ev = module.get("evidence") or []
                if not ev:
                    gap_count += 1
            if gap_count > 0:
                err = f"evidence_gaps: {gap_count} 个模块缺少 evidence 文件路径 — 请补全源码证据"
                all_errors.append(err)
                print(f"  [error] {err}")
            else:
                print("  OK: 所有模块已标注 evidence 文件路径")
        except Exception:
            pass
    else:
        print("  SKIP: 无业务理解.json")

    # ── 检查 18: 术语一致性扫描 (SKILL.md §6 第5轮) ──
    print("\n[18/20] 术语一致性扫描 (SKILL §6 第5轮)")
    plan_path = manual_path.parent / PLAN_FILE
    term_path = manual_path.parent / "术语标准表.md"
    aliases_row = []
    if plan_path.exists():
        try:
            aliases_row = plan_aliases(json.loads(plan_path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  WARN: 统一写作计划术语扫描异常: {e}")
    elif term_path.exists():
        try:
            term_text = term_path.read_text(encoding="utf-8")
            import re as _re
            # Parse the term table: | 标准名称 | 禁止使用的别名 |
            in_table = False
            for line in term_text.split("\n"):
                if "标准名称" in line and "禁止" in line:
                    in_table = True
                    continue
                if in_table and line.startswith("|") and "---" not in line:
                    cols = [c.strip() for c in line.split("|")[1:-1]]
                    if len(cols) >= 2:
                        standard = cols[0]
                        forbidden = [a.strip() for a in cols[1].split("、")]
                        aliases_row.append((standard, forbidden))
        except Exception as e:
            print(f"  WARN: 术语扫描异常: {e}")
    violations = []
    for standard, fwords in aliases_row:
        for fw in fwords:
            if fw and fw in text:
                violations.append(f"「{fw}」应使用标准术语「{standard}」")
    if violations:
        for v in violations[:8]:
            all_warnings.append(v)
            print(f"  [warn] {v}")
    elif aliases_row:
        print("  OK: 未发现术语违规使用")
    else:
        print(f"  SKIP: {PLAN_FILE} 和旧版术语标准表均无可检查别名")

    # ── 检查 19: 截图位置门禁 (上图下文 + 字段表→截图→异常表顺序) ──
    print("\n[19/20] 截图位置门禁 (上图下文原则 + 字段-截图-异常表顺序)")
    screenshot_issues = []
    text_lines = text.split("\n")
    for i, line in enumerate(text_lines):
        if "【截图预留" not in line and "![" not in line:
            continue

        # Find context: preceding heading, next heading, surrounding text
        prev_heading = ""
        next_heading = ""
        prev_text_line = ""
        for j in range(i - 1, max(0, i - 60), -1):
            if text_lines[j].startswith("#### ") or text_lines[j].startswith("### "):
                prev_heading = text_lines[j].strip()
                break
            if text_lines[j].strip() and not text_lines[j].startswith("|") and not text_lines[j].startswith(">"):
                prev_text_line = text_lines[j].strip()
                break

        for j in range(i + 1, min(len(text_lines), i + 12)):
            stripped = text_lines[j].strip()
            if stripped.startswith("#### ") or stripped.startswith("### ") or stripped.startswith("## "):
                next_heading = stripped
                break

        # Determine screenshot type from description
        is_new_edit = bool(re.search(r"(新增|修改|表单|对话框|创建|录入|编辑|维度配置|字段)", line))
        is_login = bool(re.search(r"登录", line))
        is_list = bool(re.search(r"列表|看板|首页|界面", line))
        # Flow chart = PNG with 操作流程 or 数据模型/架构/功能模块/业务流程 in alt or filename
        is_flow_chart = bool(re.search(r"!\[.*(?:操作流程|数据模型|系统架构|功能模块|业务流程).*\]\(截图/", line))

        # ── Rule 1: 上图下文 — screenshot cannot be directly after heading with no text ──
        if prev_heading and not prev_text_line:
            # Check: is there descriptive text OR table rows between this heading and screenshot?
            has_content_between = False
            for j in range(i - 1, max(0, i - 80), -1):
                stripped = text_lines[j].strip()
                if stripped.startswith("#### ") or stripped.startswith("### "):
                    break
                # Tables, module-type tags, images, and long prose all count as intervening content
                if stripped and not stripped.startswith("!["):
                    if len(stripped) > 10 or stripped.startswith("|") or stripped.startswith(">"):
                        has_content_between = True
                        break
            if not has_content_between:
                screenshot_issues.append(f"L{i + 1}: 截图紧接标题无说明文字——应在功能描述之后")

        # ── Rule 2: 新增/修改表单截图 必须在字段表之后、异常表之前 ──
        if is_new_edit and next_heading:
            # Good: next heading is 异常逻辑、步骤表、下一个模块
            if "异常" in next_heading:
                pass  # OK — field table → screenshot → exception table
            elif next_heading.startswith("### 6.") or next_heading.startswith("## 7"):
                screenshot_issues.append(
                    f"L{i + 1}: 新增/修改表单截图放在模块末尾（下一节是「{next_heading}」）——应紧接字段表之后、异常逻辑表之前"
                )
            elif "步骤" in next_heading or "操作步骤" in next_heading:
                pass  # OK for business modules

        # ── Rule 3: 登录截图在描述之后、不能紧接标题 ──
        if is_login and prev_heading and prev_heading.startswith("### 6.1"):
            if not prev_text_line or prev_text_line.startswith("#"):
                screenshot_issues.append(f"L{i + 1}: 登录截图在标题后、描述前——应放在登录描述文字之后")

        # ── Rule 4: 列表页截图在模块末尾（下一个模块之前）— OK ──
        if is_list and next_heading and (next_heading.startswith("### 6.") or next_heading.startswith("## 7")):
            pass  # list screenshot at module boundary is fine

        # ── Rule 5: 流程图（PNG）在功能描述之后、截图之前 ──
        if is_flow_chart:
            # Flow chart should be after module purpose paragraph, not at module end
            if next_heading and ("异常" in next_heading or "操作步骤" in next_heading or "列表界面" in next_heading):
                pass  # OK — flow chart before detail sections
            elif next_heading and (next_heading.startswith("### 6.") or next_heading.startswith("## 7")):
                screenshot_issues.append(
                    f"L{i + 1}: 操作流程图放在模块末尾——应放在功能描述之后、第一个子节之前"
                )

    if screenshot_issues:
        for si in screenshot_issues:
            all_errors.append(si)
            print(f"  [error] {si}")
    else:
        print("  OK: 截图位置符合上图下文 + 字段-截图-异常表顺序")

    # ── 检查 19b: 截图归属校验 —— 提取截图描述中的模块名与所在章节标题交叉验证 ──
    screenshot_ownership_issues = []
    # Collect all section titles from the manual for cross-referencing
    section_titles = set()
    for line in text_lines:
        stripped = line.strip()
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            title = stripped[4:].strip()
            # Extract the Chinese text part (after number prefix like "6.1 ")
            clean = re.sub(r"^\d+[A-Z]?\.\d+\s+", "", title)
            if len(clean) >= 3:
                section_titles.add(clean)

    for i, line in enumerate(text_lines):
        if "【截图预留" not in line:
            continue
        # Find the enclosing ### heading (module section)
        section_title = "unknown"
        for j in range(i - 1, max(0, i - 150), -1):
            stripped = text_lines[j].strip()
            if stripped.startswith("### ") and not stripped.startswith("#### "):
                section_title = stripped[4:].strip()
                section_title = re.sub(r"^\d+[A-Z]?\.\d+\s+", "", section_title)
                break

        # Extract the subject phrase from the screenshot placeholder
        m = re.match(r"【截图预留：(.+?)(?:——|。|】)", line)
        if not m:
            continue
        screenshot_subject = m.group(1).strip()

        # Try to find which section the screenshot should belong to by matching
        # keywords from the subject against known section titles
        # Logic: if the subject contains words that clearly match a DIFFERENT section
        # title than where it's placed, flag it
        subject_lower = screenshot_subject
        for other_title in section_titles:
            if other_title == section_title:
                continue
            # Check if the screenshot subject seems to reference another module
            # Use longest common substring heuristic — if subject shares key chars with
            # another section title but not the current one
            common = len(set(other_title) & set(subject_lower))
            current_common = len(set(section_title) & set(subject_lower))
            # Only flag if the screenshot clearly belongs elsewhere (high overlap with other, low with current)
            if common > current_common + 2 and common >= 4:
                screenshot_ownership_issues.append(
                    f"L{i + 1}: 截图「{screenshot_subject[:50]}」疑似属于「{other_title}」而非当前章节「{section_title}」"
                )
                break

        # Also check against a keyword heuristic: login screenshot in non-login section
        login_keywords = ["登录"]
        for kw in login_keywords:
            if kw in screenshot_subject and kw not in section_title:
                screenshot_ownership_issues.append(
                    f"L{i + 1}: 截图含「{kw}」但放在「{section_title}」章节内——应移至登录界面章节"
                )
                break

    if screenshot_ownership_issues:
        for si in screenshot_ownership_issues:
            all_errors.append(si)
            print(f"  [error] {si}")
    else:
        print("  OK: 截图归属与模块章节一致")

    # ── 检查 20: 语义一致性审查 (模型审查 — 检查内容一致性/逻辑冲突/前后表述) ──
    print("\n[20/20] 语义一致性审查 (内容一致性 / 逻辑冲突 / 前后表述)")
    ok, msg = semantic_consistency_check(manual_path)
    print(f"  {msg}")
    if not ok:
        # Generate the review prompt for the model
        prompt_path = manual_path.parent / "语义一致性审查提示.md"
        prompt_lines = [
            "# 操作手册语义一致性审查提示",
            "",
            "你是本操作手册的逻辑审查员。请通读草稿/操作手册.md 全文，按以下 5 个维度逐一审查，",
            "将结论优先写入 草稿/操作手册审查报告.json 的 semantic_consistency.checks。",
            "旧任务也可继续写入 草稿/语义一致性审查报告.md。",
            "",
            "## 审查规则",
            "",
            "每个问题先引用手册中矛盾的两处原文（标注章节号），再给出修正建议。",
            "若某维度无问题，写「✅ 通过」。有问题的写「❌ 问题 N」并逐条编号。",
            "",
            "## 维度 1：前后表述一致性",
            "",
            "重点检查：同一功能模块在不同章节中的操作步骤数量、按钮名称、字段名称是否一致。",
            "例如：§3 功能清单说某模块有 5 步操作，§6 对应章节只展示了 3 步。",
            "例如：§6.2 说按钮叫\"新增\"，§6.3 说按钮叫\"创建\"——是否为同一按钮的不同叫法。",
            "",
            "## 维度 2：状态机闭环",
            "",
            "重点检查：每个业务型/混合型模块声明了哪些对象状态，所有状态是否都有入口和出口。",
            "例如：巡检任务声明了待执行→执行中→已完成/已逾期，但 FAQ 中只讲了逾期怎么处理——",
            "已完成之后是否可以重新打开？是否可能有\"已取消\"状态？如有矛盾标记。",
            "",
            "## 维度 3：角色路径完整",
            "",
            "重点检查：§1 和 §2 声明的每个目标用户角色，在 §6 功能操作中是否都有对应的操作路径。",
            "例如：声明了\"部门负责人\"角色但 §6 所有操作步骤都以\"安全管理员\"开头——部门负责人的操作入口在哪？",
            "",
            "## 维度 4：FAQ 覆盖矛盾检测",
            "",
            "重点检查：FAQ 的回答是否与 §6 操作步骤中的异常功能逻辑描述一致。",
            "例如：FAQ 说\"点击解绑按钮解除绑定关系后即可删除\"——但 §6.2 异常逻辑表说删除已绑定的卡需先解绑——",
            "两者是否一致？",
            "",
            "## 维度 5：功能清单与详情一致性",
            "",
            "重点检查：§3 功能清单中每个子功能的描述，是否在 §6 对应章节中有匹配的操作描述。",
            "例如：§3 第 12 行说\"支持强制顺序巡检\"——§6.4 巡检任务管理中是否描述了强制顺序的具体操作？",
            "如果没有对应操作描述，标记为遗漏。",
            "",
            "## 输出格式",
            "",
            "将五项结论写入草稿/操作手册审查报告.json 的 semantic_consistency.checks，使用以下格式：",
            "",
            "```json",
            '{"semantic_consistency": {"checks": {',
            '  "前后表述一致性": {"status": "pass", "note": "审查结论"},',
            '  "状态机闭环": {"status": "pass", "note": "审查结论"},',
            '  "角色路径完整": {"status": "pass", "note": "审查结论"},',
            '  "FAQ覆盖矛盾检测": {"status": "pass", "note": "审查结论"},',
            '  "功能清单与详情一致性": {"status": "pass", "note": "审查结论"}',
            "}}}",
            "```",
        ]
        prompt_path.write_text("\n".join(prompt_lines), encoding="utf-8")
        all_errors.append(msg)
        print("  [error] 模型审查未通过——已生成 草稿/语义一致性审查提示.md")
        print(f"  NEXT_ACTION: 模型阅读提示 → 更新 {REVIEW_FILE} → 重跑本检查")

    # ── 检查 21: 代码泄漏检查 ──
    print(); _print_gate_header(21, GATE_PROFILES)
    code_errors, code_warnings = check_code_leakage(text)
    if code_errors:
        all_errors.extend(code_errors)
        for e in code_errors:
            print(e)
    if code_warnings:
        all_warnings.extend(code_warnings)
        for w in code_warnings:
            print(w)
    if not code_errors and not code_warnings:
        print("  OK: 手册正文无代码泄漏——所有技术表达已翻译为中文")

    # ── 检查 22: 数据字典/内部引用泄漏 ──
    print(); _print_gate_header(22, GATE_PROFILES)
    dd_errors = 0
    # Catch: backtick-wrapped snake_case identifiers that are data-dict keys or internal codes
    # Pattern:  data字典 `xxx_yyy`  or  数据字典 `xxx`  or  字段 `xxx_yyy`
    for m in re.finditer(r'(?:数据字典|系统字段|字典|枚举)[^。]*?`([a-z_]{4,})`', text):
        dd_key = m.group(1)
        ctx = text[max(0,m.start()-10):min(len(text),m.end()+10)].replace('\n',' ')
        all_warnings.append(f"  [数据字典/内部引用] `{dd_key}` 是系统内部标识符——应替换为中文含义（如'设备风险等级字典'）  context: ...{ctx}...")
        dd_errors += 1
    if dd_errors:
        print(f"  [warn] {dd_errors} 处数据字典/内部标识符引用——应替换为对应的中文含义")
    else:
        print("  OK: 无数据字典或内部标识符泄漏")

    # ── 检查 23: 飞书图表可读性（PlantUML 中文防乱码）──
    print("\n[23/23] 飞书图表可读性检查 (PlantUML 中文防乱码)")
    screenshot_dir = manual_path.parent.parent / "截图"
    chart_checker = Path(__file__).resolve().parent / "check_plantuml_charts.py"
    if screenshot_dir.exists() and chart_checker.exists():
        png_files = list(screenshot_dir.glob("*.png"))
        if png_files:
            try:
                result = subprocess.run(
                    ["python3", str(chart_checker)],
                    capture_output=True, encoding="utf-8", timeout=300,
                    cwd=str(screenshot_dir),
                )
                if result.returncode != 0:
                    all_errors.append("飞书图表可读性检查未通过——PlantUML 中文节点过长导致渲染乱码。请重写画板后重新导出。")
                    print("  [error] 飞书图表可读性检查未通过——存在渲染乱码")
                    for line in result.stdout.strip().split("\n")[-10:]:
                        if "LONG" in line or "Total issues" in line:
                            print(f"    {line.strip()[:140]}")
                else:
                    print("  OK: 飞书图表可读性检查通过")
            except Exception as e:
                all_warnings.append(f"飞书图表检查脚本异常: {e}")
                print(f"  [warn] 飞书图表检查脚本异常: {e}")
        else:
            print("  SKIP: 截图目录为空")
    else:
        print("  SKIP: 截图目录或检查脚本不存在")

    # ── 判定 ──
    print("\n" + "=" * 60)
    total_errors = len(all_errors)
    total_warnings = len(all_warnings)
    print(f"结果: {total_errors} 个错误, {total_warnings} 个警告")

    if total_errors > 0:
        print("\n以下问题必须修复后才能通过质量门禁：")
        for e in all_errors:
            print(f"  ❌ {e}")
        print(f"\nSTOP: 请修复以上 {total_errors} 个问题后重新检查。")
        sys.exit(1)

    if total_warnings > 0 and args.exit_on_warn:
        print("\n以下警告需要修复（--exit-on-warn 已开启）：")
        for w in all_warnings:
            print(f"  ⚠️  {w}")
        sys.exit(1)

    print("\nQUALITY CHECK PASSED — 可以进入 markdown 门禁确认。")
    sys.exit(0)


if __name__ == "__main__":
    main()
