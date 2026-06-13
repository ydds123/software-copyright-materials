# Software Copyright Materials

用于根据真实软件项目生成中国软件著作权申请资料的 Codex Skill。

该 Skill 会分析项目源码和业务证据，分阶段生成业务理解、操作手册、代码材料和申请表信息。在用户逐阶段确认后，输出可提交整理的正式资料。

## 主要能力

- 分析项目技术栈、源码结构、页面、路由、接口和主要功能
- 根据真实项目证据形成业务理解，避免套用通用模板
- 引导补全软件全称、版本号、著作权人、软硬件环境等申请信息
- 选择并提取能够体现软件功能和运行逻辑的真实源码
- 生成面向普通用户的操作手册草稿
- 生成申请表信息、程序鉴别材料 DOCX 和文档鉴别材料 DOCX
- 对文件完整性、代码真实性、业务真实性和格式一致性进行验证

## 工作原则

- **材料来源真实**：代码材料必须来自待申请项目源码，不编造代码。
- **分阶段确认**：先确认业务理解和操作手册，再进行代码选择、抽取和申请字段确认。
- **先草稿后正式资料**：先生成可审阅的 Markdown，确认后再生成正式资料。
- **输出集中管理**：生成内容统一写入 `<项目>/<年份>年软件著作权申请资料/<软件全称>/`。
- **规则来源唯一**：同类规则只保留一个主入口，避免多个规范文件互相冲突。
- **自动检查不代替语义审查**：脚本负责结构、格式和可计算门禁，模型负责真实性、业务闭环和表达质量。

## 架构概览

Skill 按职责分为五层：

```text
执行编排层
└── SKILL.md：定义阶段顺序、人工确认边界和停止条件

规则与知识层
└── references/：定义业务理解、操作手册、申请字段、代码材料等规则

自动化脚本层
└── scripts/：执行项目分析、草稿生成、质量检查、门禁和正式资料构建

DOCX 基础设施层
└── vendor/docx-toolkit/：提供 OpenXML DOCX 创建、预览、修复和校验能力

任务产物层
└── <项目>/<年份>年软件著作权申请资料/<软件全称>/：保存当前申请任务的证据、草稿和正式资料
```

操作手册阶段采用三份固定规则和两份任务期主文件：

```text
固定规则
├── references/manual_workflow.md        唯一流程入口
├── references/manual_authoring_spec.md  唯一正文构建规范
└── references/manual_quality_spec.md    唯一内容审查规范

任务期主文件
├── 草稿/操作手册写作计划.json           写作上下文与覆盖计划
└── 草稿/操作手册审查报告.json           自检、交叉引用和语义审查结论
```

## 环境要求

- Codex
- Python 3.10+
- [`python-docx`](https://pypi.org/project/python-docx/)

可选环境：

- .NET SDK 8.0+：用于完整 OpenXML DOCX 生成和校验
- Node.js（含 `npm`/`npx`）：用于安装和调用飞书 CLI
- `lark-cli` 与 `whiteboard-cli`：用于在指定飞书在线文档中生成和导出技术图表

安装 Python 依赖：

```powershell
python -m pip install python-docx
```

### 飞书 CLI 安装与配置

飞书技术图表功能按两步检查：

1. 检查 `lark-cli` 是否安装，并确认用户授权有效。
2. 检查是否指定一个当前用户可编辑的飞书在线文档，用于集中存放画板。

推荐安装并配置：

```powershell
npx @larksuite/cli@latest install
lark-cli config init --new
lark-cli auth login --recommend
lark-cli auth status --verify
```

也可以使用 npm 全局安装：

```powershell
npm install -g @larksuite/cli
```

同时安装官方 Agent Skills：

```powershell
npx skills add larksuite/cli -y -g
```

检查画板转换工具：

```powershell
npx -y @larksuite/whiteboard-cli@^0.2.10 -v
```

运行软著环境检查时指定在线文档：

```powershell
python scripts/check_environment.py `
  --out-dir "<任务目录>" `
  --feishu-doc "https://example.feishu.cn/wiki/<token>"
```

不使用飞书画板时，必须显式跳过：

```powershell
python scripts/check_environment.py --out-dir "<任务目录>" --skip-feishu
```

常用文档调用示例：

```powershell
lark-cli docs +fetch --api-version v2 --doc "<URL-or-token>" --as user
```

详细说明见 [`references/feishu_cli_setup.md`](references/feishu_cli_setup.md)。

## 安装

将仓库克隆到 Codex Skills 目录：

```powershell
git clone https://github.com/ydds123/software-copyright-materials.git `
  "$HOME\.codex\skills\software-copyright-materials"
```

如果目标目录已经存在，可以在目录中拉取最新版本：

```powershell
git -C "$HOME\.codex\skills\software-copyright-materials" pull
```

## 使用方式

在 Codex 中导入或打开待申请的软件项目，然后提出软著资料生成请求，例如：

```text
请根据这个项目生成软件著作权申请资料。
```

也可以明确指定需要的内容：

```text
帮我生成这个项目的软著代码材料和操作手册。
```

Skill 会按门禁逐步推进。每到需要确认的阶段，会停止并列出需要确认的具体事项；确认后再继续下一阶段。

## 工作流

| 阶段 | 主要动作 | 核心产物或门禁 |
|---|---|---|
| 1. 初始化与环境检查 | 创建任务目录，检查 Python、DOCX、飞书等能力 | `任务登记.json`、`环境检查.md/json`、`environment` |
| 2. 项目分析 | 识别项目、子项目、技术栈、源码规模和候选证据 | `analysis/project.json` |
| 3. 业务理解 | 模型阅读项目证据，形成产品组成、业务闭环、角色和模块理解 | `草稿/业务理解.md/json`、`business` |
| 4. 操作手册 | 建立写作计划，模型直接撰写正文，执行自动检查和语义审查 | `操作手册写作计划.json`、`操作手册.md`、`操作手册审查报告.json`、`content-quality`、`manual` |
| 5. 代码选择与抽取 | 按已确认的操作手册模块选择真实源码并生成程序鉴别材料 | `代码文件选择.json`、`code-selection`、代码草稿 |
| 6. 申请字段 | 根据项目、业务理解和代码材料生成并确认申请字段 | `申请表信息.md`、`application-fields` |
| 7. 截图与图表 | 用户选择截图方式；可生成、导入或明确跳过 | `用户截图/截图准备清单.md`、`截图/截图清单.json`、`screenshot-method` |
| 8. 草稿总确认 | 检查业务、手册、代码、申请字段和截图口径一致 | `markdown` |
| 9. 正式资料 | 生成申请信息、程序鉴别材料和文档鉴别材料并验证 | `正式资料/` |

主要门禁依赖如下：

```text
business
└── manual-draft
    └── content-quality
        └── manual
            ├── code-selection
            │   ├── extract-code
            │   └── application-info
            └── screenshot-method

application-fields + code-selection + screenshot-method + content-quality + manual
└── markdown
    └── build-final
```

## 输出结构

每个任务的主要输出位于：

```text
<项目>/<年份>年软件著作权申请资料/<软件全称>/
├── 任务登记.json                  # 项目、软件名称、任务路径和创建时间
├── 门禁状态.json                  # 各阶段人工确认的唯一状态来源
├── 环境检查.md
├── 环境检查.json
├── analysis/
│   ├── project.json               # 项目技术栈、源码规模和子项目分析
│   └── reference_profile.json     # 用户指定参照手册时生成
├── 草稿/
│   ├── 业务理解.md
│   ├── 业务理解.json
│   ├── 操作手册写作计划.json
│   ├── 操作手册.md
│   ├── 操作手册审查报告.json
│   ├── 代码文件选择.json
│   └── 申请表信息.md
├── 截图/
│   └── 截图清单.json               # 自动截图或导出结果清单
├── 用户截图/
│   └── 截图准备清单.md             # 用户自行截图时的页面准备清单
└── 正式资料/
    ├── 申请表信息.md
    ├── <软件全称>_程序鉴别材料.docx
    └── <软件全称>_文档鉴别材料.docx
```

其中：

- `analysis/` 保存机器分析结果和可复用的结构化证据。
- `草稿/` 保存需要模型补写、脚本验证和用户确认的材料。
- `截图/` 保存工具生成或导出的截图、图表。
- `用户截图/` 保存用户自行提供的截图，避免与自动生成内容混淆。
- `正式资料/` 只保存最终提交材料，不保存分析文件和中间报告。

## 仓库结构

```text
.
├── SKILL.md                         # Skill 主入口；定义完整工作流、门禁和强制规则
├── README.md                        # 安装、使用、架构和仓库说明
├── agents/
│   └── openai.yaml                  # Codex 中展示的名称、简介和默认提示词
│
├── references/
│   ├── business_understanding_rules.md  # 业务理解的证据、闭环和模型写作规则
│   ├── module_classification_rules.md   # 台账型、业务型、混合型模块分类与字段要求
│   ├── 业务理解模型稿模板.json          # 业务理解 JSON 的静态填写骨架
│   ├── application_fields.md            # 申请表字段、来源、字数和一致性规则
│   ├── code_selection_rules.md          # 代码文件候选、选择和覆盖规则
│   ├── copyright_material_rules.md      # 程序鉴别材料分页和真实性规则
│   ├── manual_workflow.md               # 操作手册阶段唯一流程入口
│   ├── manual_authoring_spec.md         # 操作手册正文构建规范
│   ├── manual_quality_spec.md           # 操作手册质量审查和 Gate 映射
│   ├── 目标态样本手册.md               # 条件读取的高质量写作样本
│   └── feishu_cli_setup.md              # 飞书 CLI、授权和跳过规则
│
├── scripts/
│   ├── common.py                        # 路径、JSON、源码遍历等共享工具
│   ├── safe_write.py                    # 拒绝空文件覆盖的安全写入工具
│   ├── init_task.py                     # 创建标准任务目录和任务登记
│   ├── check_environment.py             # 检查 Python、DOCX、飞书等环境
│   ├── analyze_project.py               # 分析项目、子项目、技术栈和源码规模
│   ├── generate_business_context.py     # 校验并输出业务理解 Markdown/JSON
│   ├── manual_model.py                  # 业务理解和手册模块结构标准化
│   ├── evidence_router.py               # 将证据缺口路由到具体源码文件
│   ├── generate_manual_draft.py         # 验证模型撰写的操作手册，不生成正文
│   ├── manual_audit.py                  # 维护统一写作计划和统一审查报告
│   ├── manual_quality.py                # 操作手册基础质量规则
│   ├── content_quality_check.py         # 操作手册自动 Gate 和语义审查入口
│   ├── extract_reference_profile.py     # 提取参照手册结构画像
│   ├── compare_reference.py             # 对比当前手册与参照手册
│   ├── propose_code_selection.py        # 生成代码文件候选与模块覆盖建议
│   ├── extract_code_material.py         # 从真实源码提取程序鉴别材料内容
│   ├── generate_application_info.py     # 生成申请表信息草稿
│   ├── capture_screenshots.py           # 截图清单和截图文件整理
│   ├── build_docx_from_md.py            # 生成正式申请信息和 DOCX 材料
│   ├── gate_check.py                    # 检查某步骤的前置门禁
│   ├── confirm_stage.py                 # 记录用户确认并写入门禁状态
│   └── gate_dispatcher.py               # 在受保护脚本执行前拦截未满足门禁
│
└── vendor/
    └── docx-toolkit/
        ├── SKILL.md                     # DOCX 工具自身的使用规则
        ├── scripts/                     # 环境检查、预览和 OpenXML CLI
        ├── references/                  # DOCX 创建、编辑、模板和排版指南
        └── assets/                      # XSD、模板等校验资源
```

### 目录职责边界

| 目录 | 负责什么 | 不负责什么 |
|---|---|---|
| `references/` | 保存稳定规则、字段定义和写作参考 | 不保存任务结果，不执行自动化 |
| `scripts/` | 分析、验证、生成和门禁控制 | 不保存项目专属规则，不编造业务内容 |
| `vendor/docx-toolkit/` | 提供通用 DOCX/OpenXML 能力 | 不决定软著业务口径和操作手册内容 |
| 任务目录 `analysis/` | 保存项目分析和结构化证据 | 不保存最终提交文件 |
| 任务目录 `草稿/` | 保存待审查、待确认的业务材料 | 不直接作为最终提交目录 |
| 任务目录 `正式资料/` | 保存确认后的最终材料 | 不保存临时文件和分析报告 |

### `vendor/docx-toolkit` 的作用

`vendor` 表示随仓库内置的第三方或独立工具。`docx-toolkit` 基于 .NET OpenXML SDK，负责：

- 创建、编辑和格式化 DOCX。
- 处理标题、表格、图片、页眉页脚、页码和分节。
- 校验 Word 内部 XML 结构和元素顺序。
- 预览、修复和验证正式 DOCX。

业务脚本通过它完成正式 Word 的结构校验，但软著材料内容、业务判断和门禁仍由当前 Skill 决定。

## 注意事项

- 生成材料不能替代软件著作权登记机构的正式审查。
- 正式提交前，请人工核对软件名称、版本号、著作权人、日期和运行环境。
- 若跳过截图，操作手册会保留截图预留位置，但可能需要在提交前补充。
- 不同登记场景的材料要求可能变化，请以办理时的官方要求为准。
