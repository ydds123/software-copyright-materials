---
name: software-copyright-materials
description: >
  Generate guided Chinese software copyright application materials from a real project.
  Use this skill when the user asks for 软件著作权, 软著申请资料, 软著代码材料,
  操作手册, 申请表信息, or wants Word materials for software copyright registration.
  The workflow analyzes the imported project, extracts real source code, creates Markdown
  drafts for user confirmation, then uses bundled DOCX tooling to produce final
  Word documents.
allowed-tools: >
  Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
metadata:
  short-description: 生成软著申请资料和鉴别材料 Word
  author: Fokkyp
  version: "1.4"
  repository: https://github.com/ydds123/software-copyright-materials
---

# 软著申请资料生成（v1.4）

本文件是**路由与门禁入口**；完整规范见 `references/skill-full-spec.md`（原文全量）。

## 最高优先级规则（细节见 skill-full-spec.md）

1. **分阶段交付**：每 turn 最多一个门禁；生成需确认文件后必须 `STOP_FOR_USER`。
2. **文件编辑安全**：覆盖已存在文件只能 Write(tmp)→safe_write.py→rm(tmp) 或 Edit；禁 .bak；门禁状态只能经 confirm_stage.py。
3. **飞书不可擅自跳过**：无用户明确同意禁止 `--skip-feishu`。
4. 代码必须来自真实项目源码，禁 AI 编造；手册由模型直写。
5. 名称/版本以已确认申请表信息.md 为准；页眉 = 软件全称+版本号+页码。
6. 代码每页 50 行；≥60 取前30+后30；不足且候选有余则停止补选。
7. 2026 新政：AI 代码规避；AI 开发限制声明**留空不自动填**（由用户人工决定并签署，skill 不代填）；经办人字段待用户确认（见 application_fields.md，方案 v2 决策①）。
8. 参考素材按 0+3 拆分：口径对齐取主数据/同源 1 份；结构避让用全批画像；相似度只出风险等级不自动阻断（方案 v2 决策④，见 references/reference_materials.md）。
9. 软件边界：按独立软件申请，代码抽取后运行 code_boundary_report.py 生成「软件边界说明」备案（方案 v2 决策②）；旧批次不返工（决策③）。
10. 飞书图表默认以 SVG 自适应导出，保留 SVG 源文件，并用 `export_whiteboard_charts.py` 转为同名白底 PNG 供 Word 嵌入；禁止默认使用固定正方形画布的 preview 导出。

## 门禁状态卡（每 turn 自检）

environment→project(条件)→business→content-quality→manual→material-plan(替代code-selection)→application-fields→screenshot-method→markdown

## STOP 输出格式（每门禁强制）

```text
STOP_FOR_USER
停在哪个门禁：<门禁名> — 「<描述>」
需要你确认以下 N 点：1.… 2.…
NEXT_ACTION: confirm_stage.py --workdir <任务目录> --stage <门禁名> --note "…" --confirm
```

## 工作流骨架（v1.5 默认 v2；细则：skill-full-spec.md）

0 init_task.py 建目录 → 1 check_environment.py（environment 门禁）→ 2 定位项目（多候选问用户）→
3-4 analyze_project.py + generate_business_context.py + 模型研判 manual_modules(含 evidence)（business 门禁）→
5 预收集申请字段（法定字段查主数据表；参考 references/reference_materials.md 的 0+3 拆分）→
6 模型直写操作手册（文档类型驱动，禁固定骨架；质检+自检）（content-quality、manual 门禁）→
6b propose_evidence_plan.py（A/B/C/D 分级+署名三分法+sha256）→ 模型补全 → evidence_plan_check → 视觉申报前置（material-plan 门禁）→
6c propose_fact_assertions.py 事实断言候选 → 模型确认 →
7 extract_code_material.py --confirm 按计划抽取 →
7b code_boundary_report.py --workspace <年份目录> 生成软件边界说明备案（决策②）→
8b generate_application_info.py（application-fields 门禁；AI 声明留空）→
9-10 飞书图表（可选）：画板生成 → export_whiteboard_charts.py 自适应 SVG + 白底 PNG → 嵌入手册 →
12 截图（screenshot-method 门禁）→ 13 markdown 门禁（接线逻辑一致性）→
14 build_docx_from_md.py --confirm →
15 三轮验证 + final_artifact + submission_readiness（确定性硬门禁）+ batch_risk_report.py 整批复检（相似度风险分级，高风险人工复核）

legacy v1（propose_code_selection.py）仅旧任务兼容；新任务一律 v2。

## 不适用（Out of Scope）

不负责：普通代码编写/重构、与软著申报无关的文档转换、非中国著作权登记体系的法律咨询。

## references 地图

- `skill-full-spec.md`：完整原文规范（规则/STOP 格式/全部 Step 细节）
- `copyright_material_rules.md` / `code_selection_rules.md`：法规落地与代码抽取规则
- `manual_authoring_spec.md` / `manual_quality_spec.md`：手册写作（v1.5 起文档类型驱动、禁固定骨架）与质检
- `module_classification_rules.md` / `business_understanding_rules.md` / `application_fields.md`：模块分类、业务主线、字段口径
- `feishu_cli_setup.md` / `path-decision.md`：飞书配置、路径决策（新任务默认 v2）
- `reference_materials.md`：参考素材约定（0+3 结构版；含 4 项拍板决策：AI 声明空着、按独立软件申请、旧批次不处理、检测风险分级）
- `../scripts/`、`../tests/`、`../evals/`、`../failures/`、`../reports/`：脚本（含 gate_check）、测试、用例、失败记录、报告

## 何时询问用户（必须 STOP）

多候选项目；DOCX 环境缺失；业务理解；操作手册；申请字段（硬件/环境）；代码文件选择；截图方式；全部 Markdown。

## v1/v2 路径决策（详见 references/path-decision.md）

新任务默认 v2（证据计划，sha256 锁定）；legacy v1 仅旧任务兼容。
四道回归防线：verify_material_currency / verify_coverage_in_pages / confirm 硬阻断 / 标注合规。

## 依赖声明（环境检查时校验）

python-docx、pdfplumber（requirements.txt）；DOCX 校验需 .NET SDK；画板需 lark-cli+whiteboard-cli；SVG 转 Word 图片需 Node.js/npx+sharp-cli；human-writing（可选）。
