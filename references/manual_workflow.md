# 操作手册工作流

本文件是操作手册阶段的唯一流程入口，只回答三个问题：何时开始、读取什么、产出什么。

具体写作规则见 `manual_authoring_spec.md`；具体审查规则见 `manual_quality_spec.md`；示例仅在需要时读取 `目标态样本手册.md`。

## 1. 前置条件

- `business` 门禁已确认。
- 任务目录中存在 `analysis/project.json`、`草稿/业务理解.md` 和 `草稿/业务理解.json`。
- `草稿/业务理解.json` 已包含 `product_composition`、`closed_loop_validation`、`target_users`、`operation_flow`、`manual_modules`、`system_requirements`、`faq` 和 `glossary`。
- 每个 `manual_modules` 条目已标注模块类型、客户端、真实入口和源码证据。

开始前运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir <任务目录> --before manual-draft
```

## 2. 默认读取集

创建操作手册时，默认只读取：

1. `references/manual_workflow.md`
2. `references/manual_authoring_spec.md`
3. `草稿/业务理解.json`
4. `manual_modules[].evidence` 指向的必要项目源码

如 `草稿/业务理解.json` 已提供完整菜单路径、页面字段、状态和反馈，不重复扫描无关项目文件。

以下文件按条件读取：

- `references/目标态样本手册.md`：首次编写、模块写法不确定或质量检查发现内容模板化时读取。
- 用户指定的参照手册：仅在用户明确指定时读取并运行参照对比。
- `草稿/菜单路径映射.json`：业务理解未内嵌完整菜单路径时读取。
- `截图/*.png`、`草稿/技术图表清单.md`：用户选择生成或提供图表、截图时读取。

## 3. 创建顺序

1. 基于 `草稿/业务理解.json` 和项目证据建立 `草稿/操作手册写作计划.json`，其中包含术语标准、章节职责边界、读者覆盖矩阵、模块清单和菜单路径。
2. 按 `manual_authoring_spec.md` 直接编写 `草稿/操作手册.md`。
3. 对业务型和混合型模块回读必要源码，补全状态流转、条件分支、角色切换和结果反馈。
4. 完成各模块后回写功能清单，使功能概要与正文细节一致。
5. 如用户选择生成图表或截图，在内容质量确认前嵌入并核对位置。

操作手册正文由模型直接编写，不由模板渲染器生成。

## 4. 创建阶段产物

必须存在：

- `草稿/操作手册.md`
- `草稿/操作手册写作计划.json`：合并术语标准、章节职责边界、读者覆盖矩阵、模块完整性和菜单路径。
- `草稿/操作手册审查报告.json`：合并自检轮次、交叉引用、语义一致性和条件参照对比结论。

迁移期间脚本仍可读取以下旧版兼容文件，但新任务不再创建它们：`术语标准表.md`、`章节职责边界.md`、`读者覆盖矩阵.md`、`模块完整性自检记录.json`、`交叉引用验证报告.md`、`语义一致性审查报告.md`、`操作手册自检记录.md`、`操作手册自检记录.json`。

## 5. 验证顺序

先验证已有操作手册并生成自检记录：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_manual_draft.py \
  --analysis analysis/project.json \
  --business-context 草稿/业务理解.json \
  --software-name "<软件全称>" \
  --version "<版本号>" \
  --out-dir 草稿
```

再运行内容质量检查：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/content_quality_check.py --manual 草稿/操作手册.md
```

质量检查必须返回 0 errors。检查失败时，按 `manual_quality_spec.md` 修正后重新运行。

## 6. 确认门禁

内容质量通过后记录 `content-quality` 门禁，然后立即停止并让用户确认完整操作手册。用户确认后记录 `manual` 门禁：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir <任务目录> \
  --stage content-quality \
  --note "内容质量检查通过" --confirm

python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir <任务目录> \
  --stage manual \
  --note "<用户确认内容>" --confirm
```

未确认 `manual` 门禁前，不得开始代码选择或代码抽取。

## 7. 条件分支

- 缺少业务证据：回到业务理解阶段补全 `manual_modules[].evidence`，不得编造。
- 无法取得真实菜单路径：写“从系统菜单进入对应功能页面”，不得根据源码目录猜测。
- 用户跳过截图：保留清晰截图预留，并标注补正风险。
- 用户指定参照手册：运行 `extract_reference_profile.py` 和 `compare_reference.py --strict`，0 errors 后再确认手册。
