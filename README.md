# Software Copyright Materials

根据真实软件项目生成中国软件著作权申请材料的 Codex / 通用 Agent Skill。

本 Skill 通过源码、页面、接口、配置和用户确认建立证据链，分阶段生成业务理解、操作手册、程序鉴别材料、申请表信息及正式 Word，并在提交前执行真实性、一致性、版式和批次风险检查。

仓库地址：<https://github.com/ydds123/software-copyright-materials>

## 核心能力

- 分析单仓库或多仓库项目的技术栈、源码规模、页面、路由、接口和业务模块。
- 基于真实代码证据形成业务理解、角色路径、操作闭环和术语标准。
- 按 A/B/C/D 等级评估代码代表性，建立“功能 → 代码证据”映射。
- 对选中源码记录 SHA-256、来源根、行段范围和署名风险，避免材料过期或边界混淆。
- 按项目类型选择用户手册、设计说明书或混合型文档，不套用固定章节模板。
- 生成前 30 页加后 30 页或全部源码形式的程序鉴别材料。
- 生成申请表信息、程序鉴别材料 DOCX 和文档鉴别材料 DOCX。
- 支持飞书画板技术图表，并以内容自适应 SVG 留存源文件，转换白底 PNG 供 Word 嵌入。
- 支持业务截图清单、视觉证据覆盖、重复图片检查和人工复核提示。
- 检查手册、申请表、代码清单、证据计划和最终 Word 的跨材料一致性。
- 生成软件边界说明、整批结构风险报告和提交就绪结论。

## 当前默认口径

### 新任务默认使用 v2 证据计划

新任务以 `草稿/材料证据计划.json`（`schema_version = 3`）作为选材层唯一真相来源。它支持：

- 多源码根与聚合规模；
- 核心功能及代码证据映射；
- A/B/C/D 证据等级；
- framework、ai_tool、team_member 署名风险三分法；
- 文件 SHA-256 和可选 `line_range`；
- 软件范围、事实断言、文档类型和视觉证据计划。

`代码文件选择.json` / `code-selection` 仅用于兼容旧任务。新任务使用 `material-plan` 门禁；计划确认后若文件、哈希或范围变化，下游确认必须重新执行。

### AI 声明由申请人决定

Skill 不自动填写“未使用 AI”，也不代签 AI 开发限制声明。申请表只保留人工处理提示，由申请人在正式提交前根据真实情况决定和签署。

### 参考素材采用 0+3

- 主体法定字段从唯一主数据口径取得；
- 技术与业务字段从当前项目代码、部署事实和用户确认取得；
- 质量校准使用固定 rubric、人工认证样本和全批结构画像。

全批画像只用于发现结构碰撞，不向新任务复制旧材料内容。主数据和认证样本是否读取由任务流程与用户授权决定，不宣称自动导入。

### 独立软件与批次治理

- 每项按独立软件申请；代码抽取后生成 `软件边界说明.md` 备案。
- 旧批次默认不返工。
- 文件缺失、编号错误、版本漂移、错误声明和精确重复粘贴属于确定性硬错误。
- 标题、表格结构和近似段落相似度只分高/中/低风险；高风险进入人工复核，不自动裁定合并或阻断。

## 工作原则

- **真实证据优先**：代码材料只能来自待申请项目，页面字段、按钮、校验和下游链路不得猜测。
- **分阶段确认**：每次只推进一个人工门禁；需要确认时立即停止。
- **先 Markdown 后 Word**：先生成可审阅草稿，全部确认后再生成正式材料。
- **门禁状态唯一**：`门禁状态.json` 只能由 `confirm_stage.py` 写入。
- **版本可追溯**：证据计划和代码清单记录哈希；源码变化后正式材料自动失效。
- **确定性与相似度分离**：可计算错误硬阻断，相似度仅作风险提示。
- **自动检查不替代语义审查**：脚本检查结构和一致性，模型与用户确认业务真实性和表达质量。
- **产物集中管理**：任务文件统一写入 `<项目>/<年份>年软件著作权申请资料/<软件全称>/`，不污染源码仓库。

## 工作流

新任务默认流程：

```text
初始化
  → environment
  → project（存在多个候选项目时）
  → business
  → content-quality
  → manual
  → material-plan
  → 代码抽取与软件边界备案
  → application-fields
  → screenshot-method
  → markdown
  → 正式 Word 构建
  → 最终件检查与 submission readiness
  → 整批风险复检
```

| 阶段 | 主要动作 | 核心产物或门禁 |
|---|---|---|
| 1. 初始化与环境检查 | 创建任务目录，检查 Python、DOCX、飞书及 SVG 转换能力 | `任务登记.json`、`环境检查.md/json`、`environment` |
| 2. 项目分析 | 识别项目、子项目、源码根、技术栈和候选证据 | `analysis/project.json`、条件式 `project` |
| 3. 业务理解 | 阅读项目证据，确认产品组成、业务闭环、角色、模块和手册范围 | `业务理解模型稿.json`、`业务理解.md/json`、`business` |
| 4. 文档规划与手册 | 确定文档类型、篇幅和章节职责，模型撰写并执行多轮审查 | `操作手册写作计划.json`、`篇幅规划.json`、`操作手册.md`、审查报告、`content-quality`、`manual` |
| 5. 材料证据计划 | 扫描多根源码，完成证据分级、功能映射、署名核验和哈希锁定 | `材料证据计划.md/json`、候选明细、`material-plan` |
| 6. 代码材料与边界 | 按确认计划抽取源码，验证前后 30 页覆盖并生成软件边界备案 | `代码-前后30页.md`、`代码提取清单.json`、`软件边界说明.md` |
| 7. 申请字段 | 对齐主体、版本、日期、环境、源程序量和主要功能 | `申请表信息.md`、字段对齐记录、`application-fields` |
| 8. 截图与技术图表 | 选择截图方式；生成视觉证据清单；可创建飞书图表并导出 SVG/PNG | `截图准备清单.md`、`技术图表清单.md`、`screenshot-method` |
| 9. 草稿总确认 | 运行逻辑和跨材料检查，确认全部 Markdown | `markdown` |
| 10. 正式资料与复检 | 生成 DOCX，验证代码页数、图片、名称版本、事实和提交状态 | `正式资料/`、`FINAL ARTIFACT PASS`、`SUBMISSION READY` |
| 11. 整批治理 | 对草稿和正式 DOCX 执行确定性检查与相似度风险分级 | `整批复检报告/` |

详细规则见 [`SKILL.md`](SKILL.md) 和 [`references/skill-full-spec.md`](references/skill-full-spec.md)。

## 环境要求

基础环境：

- Python 3.10+
- `python-docx`
- `pdfplumber`
- `PyYAML`
- `Pillow`

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

可选环境：

| 依赖 | 用途 | 缺失时行为 |
|---|---|---|
| .NET SDK 8.0+ | 完整 OpenXML DOCX 生成、预览和校验 | 可降级生成基础 DOCX，但会提示确认 |
| pandoc | Markdown / 文档预览辅助 | 不影响核心流程 |
| Node.js、npm、npx | 飞书画板和 SVG 转换 | 不生成图表时可由用户明确跳过 |
| `lark-cli` | 飞书文档与画板操作 | 未授权时停止并引导授权 |
| `whiteboard-cli` | 复杂图表写入飞书画板 | 缺失时停止或由用户明确跳过 |
| `sharp-cli` | SVG 转白底 PNG | 缺失时图表导出环境不完整 |
| human-writing | 模型化文风风险检查，不用于判定文本是否由 AI 生成 | 降级为基础文风检查 |
| DeepSeek 视觉模型 | 页面类型、真实数据和疑似设计稿辅助判断 | 降级为确定性检查与人工提示 |

> 使用 DeepSeek 视觉增强时，图片会发送到配置的外部 API。文件名预筛不等于完整 OCR 脱敏；涉及人员、电话、证件、地址等敏感信息时，应先人工脱敏。

运行依赖检测：

```powershell
python scripts/install_dependencies.py --check
python scripts/install_dependencies.py --install
```

## 飞书图表与 SVG 自适应导出

飞书 `preview` 快照会归一化为固定正方形画布，短图可能产生大面积底部空白。因此默认流程禁止使用 preview 作为 Word 图源：

```text
飞书画板
  → whiteboard +export --output-type svg
  → 保留同名自适应 SVG
  → sharp-cli 合并白色背景
  → 最大 2400×3200、fit=inside 等比例 PNG
  → Markdown 引用 PNG
  → Word 嵌入
```

检查工具：

```powershell
lark-cli --version
npx -y @larksuite/whiteboard-cli@^0.2.13 -v
npx -y sharp-cli --version
```

批量导出：

```powershell
python scripts/export_whiteboard_charts.py `
  --chart-list "<任务目录>/草稿/技术图表清单.md" `
  --output-dir "<任务目录>/截图" `
  --manual "<任务目录>/草稿/操作手册.md" `
  --width 2400 `
  --height 3200
```

脚本会：

- 从技术图表清单解析画板 token；
- 生成 `截图/<图表名称>.svg` 和同名白底 PNG；
- 自动更新 `技术图表清单.md` 的“SVG源文件 / Word图片”列；
- 自动将操作手册中的旧 JPG 或测试图引用切换到同名 PNG；
- 生成 `截图/技术图表SVG导出报告.json`。

每张 PNG 仍需通过视觉检查：中文清晰、连线完整、节点不重叠、内容不裁断、无固定画布空白。

飞书授权和目标文档配置见 [`references/feishu_cli_setup.md`](references/feishu_cli_setup.md)。只有用户明确要求时才能使用 `--skip-feishu`。

## 安装

推荐安装到通用 Agent Skills 目录：

```powershell
git clone https://github.com/ydds123/software-copyright-materials.git `
  "$HOME\.agents\skills\software-copyright-materials"
```

Codex 专用目录也可使用：

```powershell
git clone https://github.com/ydds123/software-copyright-materials.git `
  "$HOME\.codex\skills\software-copyright-materials"
```

更新已有安装：

```powershell
git -C "$HOME\.agents\skills\software-copyright-materials" pull --ff-only
```

## 使用方式

在 Agent 中打开待申请项目后提出请求，例如：

```text
请根据这个项目生成软件著作权申请资料。
```

也可以限定范围：

```text
请为 Web 管理端和大屏端生成一套独立的软件著作权材料，不纳入人员定位报警功能。
```

Skill 会在每个人工门禁停止，展示需要确认的业务口径或材料清单；用户确认后才继续。

## 任务输出结构

```text
<项目>/<年份>年软件著作权申请资料/<软件全称>/
├── 任务登记.json
├── 门禁状态.json
├── 环境检查.md
├── 环境检查.json
├── analysis/
│   ├── project.json
│   └── reference_profile.json                 # 仅使用指定参照材料时
├── 草稿/
│   ├── 业务理解模型稿.json
│   ├── 业务理解.md
│   ├── 业务理解.json
│   ├── 操作手册写作计划.json
│   ├── 篇幅规划.json
│   ├── 操作手册.md
│   ├── 操作手册审查报告.json
│   ├── 材料证据计划.md
│   ├── 材料证据计划.json
│   ├── 候选全量明细.json
│   ├── 独创性代表性审查报告.json
│   ├── 事实断言表.json
│   ├── 代码-前后30页.md
│   ├── 代码提取清单.json
│   ├── 软件边界说明.md
│   ├── 申请表信息.md
│   ├── 申请表字段对齐记录.md
│   └── 技术图表清单.md                    # 仅生成飞书图表时
├── 截图/
│   ├── <图表名称>.svg
│   ├── <图表名称>.png
│   ├── 技术图表SVG导出报告.json
│   └── 截图清单.json
├── 用户截图/
│   └── 截图准备清单.md
└── 正式资料/
    ├── 申请表信息.md
    ├── <软件全称>_程序鉴别材料.docx
    └── <软件全称>_文档鉴别材料.docx
```

并非每个任务都会生成所有可选文件。跨任务报告默认写入年份工作区下的独立目录，例如 `软件边界报告/` 和 `整批复检报告/`。

## 关键脚本

### 初始化与分析

| 脚本 | 用途 |
|---|---|
| `init_task.py` | 创建标准任务目录和任务登记 |
| `check_environment.py` | 检查 DOCX、飞书、SVG 转换和可选增强能力 |
| `analyze_project.py` | 分析项目结构、技术栈和源码规模 |
| `generate_business_context.py` | 校验并输出业务理解 Markdown/JSON |

### 文档规划与手册质量

| 脚本 | 用途 |
|---|---|
| `propose_document_plan.py` | 根据业务和代码特征建议文档类型 |
| `propose_coverage_plan.py` | 规划章节篇幅和功能覆盖 |
| `manual_model.py` | 标准化业务理解与手册模块结构 |
| `generate_manual_draft.py` | 对模型撰写的手册执行多轮检查 |
| `content_quality_check.py` | 执行结构、术语、截图、角色、语义等质量门禁 |
| `logic_consistency_check.py` | 检查编号、角色、状态和跨章节逻辑 |
| `human_writing_adapter.py` | 调用可选文风检查能力 |

### 证据计划与代码材料

| 脚本 | 用途 |
|---|---|
| `propose_evidence_plan.py` | 生成 v2 材料证据计划和候选明细 |
| `evidence_plan_check.py` | 校验证据映射、等级、署名、哈希与视觉申报 |
| `extract_code_material.py` | 按计划从真实源码抽取程序材料 |
| `verify_material_currency.py` | 检查源码与清单是否发生变化 |
| `verify_coverage_in_pages.py` | 检查前后 30 页是否覆盖确认的证据 |
| `code_boundary_report.py` | 生成任务级和整批软件边界说明 |
| `propose_code_selection.py` | legacy v1 代码选择兼容入口 |

### 截图、图表和视觉证据

| 脚本 | 用途 |
|---|---|
| `propose_screenshot_plan.py` | 生成基于真实页面的截图计划 |
| `capture_screenshots.py` | 整理截图及清单 |
| `visual_evidence_check.py` | 检查覆盖率、证据等级、重复和脱敏状态 |
| `visual_model_adapter.py` | 对接可选视觉模型 |
| `export_whiteboard_charts.py` | 批量导出自适应 SVG 并生成 Word PNG |

### 申请、门禁与最终验证

| 脚本 | 用途 |
|---|---|
| `generate_application_info.py` | 生成申请表草稿并执行字段约束 |
| `confirm_stage.py` | 校验并记录用户门禁确认 |
| `gate_check.py` / `gate_dispatcher.py` | 检查受保护步骤的前置门禁 |
| `cross_material_check.py` | 检查计划、手册、申请表和代码清单一致性 |
| `build_docx_from_md.py` | 生成正式 DOCX 并验证代码分页 |
| `final_artifact_check.py` | 从最终 DOCX/PDF 重新核对名称、版本、图片和事实 |
| `submission_readiness_check.py` | 汇总确定性检查并输出提交就绪状态 |
| `batch_structure_check.py` | 检查单稿重复和跨文档结构相似度 |
| `batch_risk_report.py` | 对草稿和正式 DOCX 生成整批风险报告 |

## 仓库结构

```text
.
├── AGENTS.md                 # 本仓库自动测试、提交和推送约定
├── SKILL.md                  # Agent 路由、门禁与最高优先级规则
├── README.md                 # 安装、能力、工作流和维护说明
├── manifest.json             # Skill 包元数据
├── requirements.txt          # Python 运行时依赖
├── agents/                   # 不同 Agent 平台的展示与接口配置
├── references/               # 业务、手册、申请、证据、路径和质量规则
├── scripts/                  # 分析、生成、检查、门禁和构建脚本
├── tests/                    # 回归测试
├── evals/                    # 触发与行为评估用例
├── failures/                 # 已知失败模式
├── reports/                  # 审查或安全报告快照
├── security/                 # 权限策略等安全资产
├── skill-ir/                 # Skill IR 示例
└── vendor/docx-toolkit/      # OpenXML DOCX 基础设施
```

`reports/` 中的报告属于生成时点快照，不能替代当前源码、依赖和测试的实时检查。

## 开发与验证

运行全部回归测试：

```powershell
python -m unittest discover -s tests -q
```

提交前至少检查：

```powershell
git diff --check
python -m unittest discover -s tests -q
```

本仓库约定：每次完成 Skill 调整后，在测试和敏感信息检查通过的前提下，自动提交并推送到 `origin/main`；禁止强制推送。详见 [`AGENTS.md`](AGENTS.md)。

## 注意事项

- 本 Skill 用于降低材料补正风险，不保证登记机关最终结论。
- 正式提交前必须人工核对软件名称、版本、著作权人、完成日期、运行环境和截图内容。
- 截图占位未回填时，系统可生成 Word，但会提示补正风险。
- 技术图表不能替代真实业务页面截图。
- DeepSeek 等外部视觉模型属于可选增强能力，使用前应确认数据合规和脱敏情况。
- 不同地区和时间的办理要求可能变化，应以提交时的官方要求为准。
