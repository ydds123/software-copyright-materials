# v1 / v2 路径决策表

## 决策矩阵

| 维度 | v1 legacy（代码文件选择.json） | v2 材料证据计划（材料证据计划.json） |
| --- | --- | --- |
| 触发方式 | 仅已有旧任务未生成计划文件时兼容 v1 | 新任务必须生成 `草稿/材料证据计划.json`，且 schema_version==3 时走 v2 |
| 抽取粒度 | 完整文件原样复制，不支持行段 | 支持 `line_range` 行段 |
| 版本锁定 | 无哈希，材料可能过期（由 `verify_material_currency.py` 事后校验） | 每文件 sha256，抽取时不一致即 STOP；计划确认后修改 → 下游确认全部失效 |
| 选材依据 | 候选池 + 模型填写 selected/model_reason | 功能→证据映射 + 等级信号 + 署名风险三分法（framework/ai_tool/team_member） |
| 适用场景 | 单仓库、模块边界清晰、材料一次性生成 | 多仓库（前端/后端/App）、需严格代表性管控、收到"模板化程度较高"补正后重提 |
| 前置门禁 | manual → code-selection | manual → material-plan（含 evidence_plan_check 硬规则） |
| 视觉证据 | 截图方式门禁即可 | 视觉证据申报清单 + 覆盖率硬阻断 |

## 选择规则

1. **新任务默认且必须 v2**：无论单仓库还是多仓库，均生成并确认材料证据计划；多仓库、版本锁定和补正重提场景尤其不得降级。
2. **v1 仅兼容旧任务**：只有历史任务已经使用 `代码文件选择.json` 且不返工时，才允许继续 legacy 路径；不得为新任务主动省略计划文件。
3. **路径切换**：v1 任务中途改走 v2，需先生成并确认 material-plan 门禁，再重做 code-selection 之后的所有下游。
4. 两条路径的输出物（代码-前后30页.md、代码提取清单、正式 docx）格式一致，仅选材与锁定机制不同。

## 两代路径共用的四道回归防线（v1.4 新增）

| 防线 | 脚本/位置 | 触发时机 |
| --- | --- | --- |
| #1 材料时效 | `scripts/verify_material_currency.py` | 生成正式资料前/审查时：清单与当前源码比对，过期即 exit 1 |
| #2 前后30页覆盖 | `scripts/verify_coverage_in_pages.py` | 抽取后：各模块 evidence 必须出现在材料页内且 ≥ min-lines |
| #3 覆盖硬阻断 | `confirm_stage.py`（code-selection） | 确认时：weak_modules 必须附 coverage_notes 说明 |
| #4 标注合规 | `confirm_stage.py`（code-selection） | 确认时：evidence 标注必须与 manual_modules.evidence 一致，补充文件必须标注 |
