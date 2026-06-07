#!/usr/bin/env python3
"""Evidence-gap router for operation manual generation.

When model JSON is missing structured fields, this module does NOT generate
placeholder text via keyword matching.  Instead it produces *reading instructions*
that point back to specific evidence files (module["evidence"]), telling the
model exactly what to extract from where.

Every gap is recorded in EVIDENCE_GAPS so the self-review loop can enforce
that gap count reaches zero before the manual is confirmed.
"""

from __future__ import annotations

import re
from typing import Any

from manual_model import as_text_list, plain_manual_text


# ---------------------------------------------------------------------------
# Global evidence-gap accumulator
# ---------------------------------------------------------------------------

EVIDENCE_GAPS: list[dict[str, Any]] = []


def reset_evidence_gaps() -> None:
    EVIDENCE_GAPS.clear()


def record_evidence_gap(
    module_title: str,
    missing_field: str,
    evidence_files: list[str],
    extraction_hint: str,
) -> None:
    EVIDENCE_GAPS.append(
        {
            "module": module_title,
            "missing_field": missing_field,
            "evidence_files": evidence_files,
            "extraction_hint": extraction_hint,
        }
    )


def evidence_gap_events() -> list[dict[str, Any]]:
    return list(EVIDENCE_GAPS)


def evidence_gap_summary() -> dict[str, Any]:
    by_module: dict[str, int] = {}
    by_field: dict[str, int] = {}
    for gap in EVIDENCE_GAPS:
        module = str(gap.get("module") or "")
        field = str(gap.get("missing_field") or "")
        if module:
            by_module[module] = by_module.get(module, 0) + 1
        if field:
            by_field[field] = by_field.get(field, 0) + 1
    return {
        "count": len(EVIDENCE_GAPS),
        "by_module": by_module,
        "by_field": by_field,
        "gaps": evidence_gap_events(),
    }


def evidence_gap_issues(summary: dict[str, Any]) -> list[str]:
    if not summary.get("count"):
        return []
    issues: list[str] = []
    for gap in summary.get("gaps") or []:
        module = gap.get("module", "?")
        field = gap.get("missing_field", "?")
        files = gap.get("evidence_files") or []
        hint = gap.get("extraction_hint", "")
        file_list = "、".join(str(f) for f in files[:3]) if files else "无证据文件"
        issues.append(
            f"证据缺失: {module} 缺少 {field}。"
            f"请阅读 {file_list}，{hint}，补全后重新渲染。"
        )
    return issues


# ---------------------------------------------------------------------------
# Lightweight structural inference (NOT content generation)
# ---------------------------------------------------------------------------

def _module_entry_path(module: dict[str, Any], title: str) -> str:
    """Derive menu path from the model-provided entry field or evidence paths.

    This is structural inference: we're locating WHERE a page lives in the menu
    hierarchy, not guessing WHAT it does.
    """
    entry = str(module.get("entry") or "").strip().strip("。；;，, ")
    if entry and entry != title:
        return entry
    # Fall back to evidence-path inference
    for e in as_text_list(module.get("evidence")):
        m = re.search(r"src/views/([\w]+)/", e.replace("\\", "/"))
        if m:
            return f"从左侧菜单进入「{title}」"
    return f"从左侧菜单进入「{title}」"


# ---------------------------------------------------------------------------
# Exported functions called by the renderer
# ---------------------------------------------------------------------------

def module_actor_text(module_or_title: Any) -> str:
    """Return the actor names for a module, or record an evidence gap.

    When actors are missing from the model JSON this no longer returns a
    generic placeholder like "相关业务用户" — it records exactly which files
    to read to find the real roles.
    """
    if isinstance(module_or_title, dict):
        actors = as_text_list(module_or_title.get("actors"))
        if actors:
            return "、".join(actors[:3])
        title = str(module_or_title.get("feature") or module_or_title.get("title") or "未知模块")
        evidence = as_text_list(module_or_title.get("evidence"))
    else:
        title = str(module_or_title or "未知模块")
        evidence = []

    vue_files = [e for e in evidence if e.endswith(".vue")]
    primary = vue_files[0] if vue_files else (evidence[0] if evidence else None)

    record_evidence_gap(
        module_title=title,
        missing_field=f"manual_modules[{title}].actors",
        evidence_files=[primary] if primary else [],
        extraction_hint=(
            "查找页面中权限判断指令（v-permission、v-if 角色判断）、"
            "页面面包屑/标题中隐含的角色信息、操作按钮的显隐条件，"
            "提取该页面的实际使用角色"
        ),
    )
    return "[待补充: 适用用户]"


def flow_result_text(flow: str, index: int) -> str:
    """Return the result text for a flow step, or record an evidence gap.

    No longer keyword-matches "创建计划，系统完成相应处理并进入下一步".
    """
    value = (flow or "").strip().strip("。；;，, ")
    if not value:
        return f"[待补充: 第{index}步操作结果]"

    record_evidence_gap(
        module_title=f"operation_flow[{index}]",
        missing_field="operation_flow[{index}].result",
        evidence_files=[],
        extraction_hint=(
            f"从流程步骤对应的页面或 API 代码中，查找操作完成后的页面跳转、"
            f"状态变更、提示信息（message.success/error）等反馈逻辑"
        ),
    )
    short = value[:25] + ("..." if len(value) > 25 else "")
    return f"[待补充: '{short}' 的操作结果]"


# ---------------------------------------------------------------------------
# Core: evidence-gap report (replaces _fallback_operation_tables)
# ---------------------------------------------------------------------------

def _evidence_gap_report(module: dict[str, Any], feature: str) -> str:
    """Generate a structured gap report pointing back to evidence files.

    Called by the renderer when a module has no registry, business_operation,
    or crud_scenarios structure.  Instead of faking operation-step tables from
    keywords, this produces a reading instruction that tells the model exactly
    which files to read and what to extract from each.

    The model must read the listed files, fill the corresponding fields in
    业务理解.json, and re-render until evidence_gaps.count reaches zero.
    """
    evidence = as_text_list(module.get("evidence"))
    if not evidence:
        evidence = ["[无证据文件 — 请在业务理解 JSON 中为模块添加 evidence 字段]"]

    # Categorise evidence files for targeted extraction hints
    vue_files = [e for e in evidence if e.endswith(".vue")]
    ts_files = [e for e in evidence if e.endswith((".ts", ".js"))]
    api_files = [e for e in ts_files if "api" in e.lower()]
    other_files = [e for e in evidence if e not in vue_files and e not in ts_files]

    def _best(main: list[str], fallback: list[str]) -> str:
        pool = main or fallback
        return pool[0] if pool else evidence[0]

    # Build the evidence-gap table rows
    gaps: list[dict[str, str]] = []

    # 1. List view (columns, filters, top/row actions)
    ui_file = _best(vue_files, evidence)
    gaps.append({
        "content": "列表视图：表格列定义、搜索筛选条件、顶部操作按钮、行操作按钮",
        "file": ui_file,
        "hint": "查找 <el-table-column> 的 prop/label、搜索栏的 <el-form-item>、表格上方和每行的操作按钮（<el-button>）",
    })

    # 2. Create/edit form
    if vue_files:
        gaps.append({
            "content": "新增/编辑表单：表单字段分组、条件显隐区域、必填项标记",
            "file": vue_files[0],
            "hint": "查找 <el-form> 的 model/rules、<el-form-item> 的 label/prop/required、v-if 条件渲染的分组区域",
        })

    # 3. Validation rules
    if vue_files or ts_files:
        gaps.append({
            "content": "输入校验规则：必填项、格式校验、唯一性约束",
            "file": _best(vue_files, ts_files),
            "hint": "查找 el-form rules 定义、validator 自定义校验函数、input 的 maxlength/min 属性",
        })

    # 4. Operation feedback (success/error messages)
    if api_files or ts_files:
        gaps.append({
            "content": "操作结果反馈：保存/提交/删除后的成功提示、失败提示、页面跳转",
            "file": _best(api_files, ts_files),
            "hint": "查找 API 调用处的 .then()/.catch() 回调、message.success()/message.error() 文案、router.push() 跳转目标",
        })
    elif vue_files:
        gaps.append({
            "content": "操作结果反馈：保存/提交/删除后的成功提示、失败提示、页面跳转",
            "file": vue_files[0],
            "hint": "查找组件方法中的 $message.success()/$message.error() 调用、this.$router.push() 跳转",
        })

    # 5. Page-visible elements
    if vue_files:
        gaps.append({
            "content": "页面可见元素：面包屑、页面标题、统计卡片、状态标签、数据展示区域",
            "file": vue_files[0],
            "hint": "查找 <el-breadcrumb>、页面标题 <h1>/<div class='title'>、<el-tag> 状态标签、非表格的数据展示区",
        })

    # 6. Business object lifecycle (for business-type modules)
    gaps.append({
        "content": "业务对象状态流转：对象生命周期中的所有状态及状态变更条件",
        "file": _best(other_files or vue_files, evidence),
        "hint": "查找状态枚举定义（Java enum / TS enum / constants）、状态变更的条件判断逻辑（if/switch）、状态变更的触发动作",
    })

    # Record each gap
    for gap in gaps:
        record_evidence_gap(
            module_title=feature,
            missing_field=f"manual_modules[{feature}].{gap['content'].split('：')[0]}",
            evidence_files=[gap["file"]],
            extraction_hint=gap["hint"],
        )

    # Build the markdown report
    lines: list[str] = [
        "",
        "> **⚠ 证据缺失 — 需回到源码补充**",
        ">",
        f"> 模块「{feature}」缺少结构化操作数据（registry / business_operation / crud_scenarios），",
        "> 无法生成操作步骤表。请按以下指引从项目源码中提取信息：",
        "",
        "| 缺失内容 | 证据文件 | 提取指引 |",
        "| --- | --- | --- |",
    ]
    for gap in gaps:
        lines.append(f"| {gap['content']} | `{gap['file']}` | {gap['hint']} |")

    lines.extend([
        "",
        f"> **NEXT_ACTION**: 读取上述证据文件，将提取的信息填入 `业务理解.json`",
        f"> → `manual_modules` → `{feature}` 的对应字段后，",
        "> 重新运行 `generate_manual_draft.py` 渲染。",
        "",
    ])

    return "\n".join(lines)
