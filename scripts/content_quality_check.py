#!/usr/bin/env python3
"""Content quality checker for operation manual — enforces SOP self-check criteria."""

import json
import re
import sys
from pathlib import Path

from manual_quality import major_heading_number_issues


# ── SOP 第 3 项：禁止出现在操作手册中的技术术语 ──
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
    """Check that the manual has adequate chart coverage (overview + module flows).

    Two-phase check:
    1. Count image references in markdown
    2. If manual_path is provided, verify referenced PNG files actually exist on disk
    """
    images = re.findall(r'!\[[^\]]*\]\(截图/[^)]+\)', text)
    overview_count = sum(1 for img in images if any(k in img for k in ['系统架构', '功能模块', '核心业务', '数据模型']))
    flow_count = sum(1 for img in images if '操作流程' in img)

    if overview_count < 4:
        missing = 4 - overview_count
        return False, f"缺失 {missing} 张总图（系统架构图/功能模块图/核心业务流程图/数据模型关系图），必须 4 张齐全"

    module_count = len(re.findall(r'^### [678]\.\d ', text, re.M))
    if flow_count < module_count:
        missing = module_count - flow_count
        return False, f"缺失 {missing} 张模块操作流程图（共 {module_count} 个模块，仅有 {flow_count} 张流程图）"

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

    return True, f"OK: {overview_count} overview + {flow_count} module flow diagrams"


def check_feature_list(text: str) -> tuple[bool, str]:
    """Check that 功能清单 has sub-function detail (SOP item 7)."""
    # Find 功能清单 section (chapter number varies, match by title)
    m = re.search(r'## [一二三四五六七八九十]+、功能清单\n(.*?)(?=\n## )', text, re.DOTALL)
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
        "门卫", "安保人员", "值班人员", "访客",
    ]

    # Find all module sections (### N.N under 六/七/八 chapters only)
    # Skip architecture overview (2.3) and other non-operation sections
    module_sections = re.findall(
        r'^### ([678]\.\d+ .+?)\n(.*?)(?=^### [678]\.\d+ |^## )',
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
        (r'App\s*端|Android\s*(App)?端|移动端', "app"),
        (r'Web\s*(管理)?端|浏览器', "web"),
    ]:
        if re.search(pattern, intro_text):
            declared_endpoints.add(label)

    # Web-endpoint is always implied if not explicitly stated
    if "web" not in declared_endpoints:
        declared_endpoints.add("web")

    if len(declared_endpoints) <= 1:
        return True, "OK: single-endpoint system — no multi-endpoint split required"

    # Check that each declared endpoint has a corresponding operation chapter
    chapter_text = text[text.find("## 六"):]
    endpoint_chapter_map = {
        "web": r'Web\s*(管理)?端\s*(功能)?操作',
        "app": r'App\s*端\s*(功能)?操作|移动端\s*(功能)?操作',
        "screen": r'大屏\s*(展示)?端\s*(功能)?操作|大屏\s*(展示)?',
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
    feature paragraph in the System Introduction (一、系统简介).

    This catches the common failure mode where the model writes a complete 功能清单
    table but omits feature paragraphs from the narrative intro — the two layers
    fall out of sync and the intro reads as a subset of what the system actually does.
    """
    # ── Phase 1: extract feature-paragraph titles from system intro ──
    m = re.search(r'## 一、系统简介\n(.*?)(?=\n## 二)', text, re.DOTALL)
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
    m2 = re.search(r'## [一二三四五六七八九十]+、功能清单\n(.*?)(?=\n## )', text, re.DOTALL)
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


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Content quality checker for operation manual")
    p.add_argument("--manual", required=True, help="Path to 草稿/操作手册.md")
    p.add_argument("--workdir", help="Path to 软件著作权申请资料 (auto-detected if omitted)")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--exit-on-warn", action="store_true", help="Treat warnings as errors")
    args = p.parse_args()

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
    print("\n[1/12] 技术术语检查 (SOP #3)")
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
    print("\n[2/12] 章节编号检查")
    heading_issues = major_heading_number_issues(text)
    if heading_issues:
        all_errors.extend(heading_issues)
        for issue in heading_issues:
            print(f"  [error] {issue}")
    else:
        print("  OK: 一级章节编号唯一")

    # ── 检查 3: 表图密度 ──
    print("\n[3/12] 表格密度检查 (SOP #4)")
    ok, msg = check_table_density(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"表格密度不足: {msg}")

    # ── 检查 3: 功能清单 ──
    print("\n[4/12] 功能清单迭代检查 (SOP #7)")
    ok, msg = check_feature_list(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"功能清单质量不达标: {msg}")

    # ── 检查 4: 业务型模块表格化 ──
    print("\n**[5/12] 业务模块表格化检查** (SOP #5, #6)")
    ok, msg = check_approval_has_flow_table(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"审批模块表格化不达标: {msg}")

    # ── 检查 5: 图表覆盖 ──
    print("\n[6/12] 图表覆盖检查 (SOP 图表)")
    ok, msg = check_chart_coverage(text, manual_path)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"图表覆盖不足: {msg}")

    # ── 检查 6: 模型审查占位符检查 (SOP Step 11) ──
    print("\n[7/12] 模型审查占位符检查 (SKILL Step 11)")
    ok, msg = check_model_warning_placeholders(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"模型审查不完整: {msg}")

    # ── 检查 8: AI 套话 ──
    print("\n[8/12] AI 套话检查 (目标态样本手册 §叙事密度)")
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
    print("\n[9/12] 角色贯穿检查 (目标态样本手册 §叙事密度)")
    ok, msg = check_role_penetration(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"角色贯穿不足: {msg}")

    # ── 检查 10: 多端覆盖 (Humanizer 端维度) ──
    print("\n[10/12] 多端覆盖检查 (系统简介声明的端 → 功能操作章节)")
    ok, msg = check_endpoint_coverage(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"多端覆盖不足: {msg}")

    # ── 检查 11: 简介-功能清单对等检查 ──
    print("\n[11/12] 简介-功能清单对等检查 (系统简介段落 ↔ 功能清单行)")
    ok, msg = check_intro_function_parity(text)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"简介-功能清单不对等: {msg}")

    # ── 检查 12: 代码-手册关联性检查 ──
    print("\n[12/12] 代码-手册关联性检查 (操作手册模块 ↔ 选中代码文件)")
    ok, msg = check_code_manual_correlation(manual_path)
    print(f"  {msg}")
    if not ok:
        all_errors.append(f"代码-手册关联性不足: {msg}")

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

