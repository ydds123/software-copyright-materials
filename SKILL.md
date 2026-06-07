---
name: software-copyright-materials
description: >
  Generate guided Chinese software copyright application materials from a real project.
  Use this skill when the user asks for 软件著作权, 软著申请资料, 软著代码材料,
  操作手册, 申请表信息, or wants Word/TXT materials for software copyright registration.
  The workflow analyzes the imported project, extracts real source code, creates Markdown
  drafts for user confirmation, then uses bundled DOCX tooling to produce final
  Word documents and TXT.
user-invocable: true
compatibility: >
  Requires Python 3.10+ with python-docx (pip install python-docx).
  Optional: .NET SDK 8.0+ for full OpenXML DOCX validation (run vendor/docx-toolkit/scripts/setup.sh).
allowed-tools: >
  Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
metadata:
  short-description: 生成软著申请资料 Word/TXT
  author: Fokkyp
  version: "1.0"
  repository: https://github.com/Fokkyp/SoftwareCopyright-Skill
---

## ⛔ 执行模式：分阶段交付，不是一次性交付

本 skill 按门禁分段执行。**每生成一个需要用户确认的文件后，必须立即停止当前 turn，等待用户确认。** 禁止在同一 turn 中跨越两个连续门禁。

核心约束：

- **每个 turn 最多推进一个门禁**：生成文件 → 输出 `STOP_FOR_USER` → 终止当前 turn → 等用户回复 → 运行 `confirm_stage.py` → 进入下一阶段
- **禁止在用户确认前生成依赖下游文件**。业务理解未确认 → 不得写申请表、操作手册或代码选择。申请表未确认 → 不得以此为口径生成正式 Word。
- **违反此规则的产出物视为无效草稿**，需要回退到上一个已确认门禁，按确认后的口径重新生成。

## 门禁状态卡（每个 turn 开始前自检）

执行任何生成动作前，先回答：**上一个必须确认的门禁是否已确认？**

```
1. environment     → 环境检查报告已生成，用户已选择方案
2. project         → 项目目录已唯一确定或用户已选择
3. business        → 业务理解.md 已生成，用户已确认行业/功能/口径 ⬜
4. application-fields → 申请表字段已补全并确认            ⬜
5. code-selection  → 代码文件选择已确认                   ⬜
6. screenshot-method → 截图方式已选择                      ⬜
7. markdown        → 全部草稿已确认，可进入 Word 生成      ⬜
```

当前活跃门禁 = 卡片中第一个未确认 (⬜) 的条目。**只能处理当前活跃门禁的上游生成工作；不得越过它生成下游文件。**

## STOP 输出格式（强制）

每个门禁的 STOP_FOR_USER 必须按以下格式输出，缺一不可：

```text
STOP_FOR_USER

停在哪个门禁：<门禁名> — 「<门禁描述>」

需要你确认以下 N 点：

1. <具体决策项，用疑问句，如「软件全称『承包商安全管理系统』是否确认？」>
2. <具体决策项>
...

NEXT_ACTION: 确认以上 N 点后，运行 confirm_stage.py --stage <门禁名> --confirm
```

禁止模糊表述——不要写「请确认业务理解」，要写「请确认业务理解中的以下 3 点：1.软件全称、2.模块数量、3.流程顺序」。不要写「确认后继续」，要写具体命令 `confirm_stage.py --stage business --confirm`。

如果上一个门禁未确认就生成了文件（如 business 未确认就写了操作手册），这些文件必须在门禁确认后重新验证或重写——因为上游口径的变化会使下游文件失效。

---

# 软著申请资料生成

这个 skill 生成可审阅、可追溯的软著申请资料。核心原则：

- 固定输出目录：当前工作目录下的 `软件著作权申请资料/`。不要默认写到 `/tmp`、`/private/tmp` 或其他临时目录。
- 只有测试 skill 自身时才允许显式指定临时目录；面向用户生成材料时必须写入当前目录。
- 先生成 Markdown 草稿，用户确认后再生成正式 Word/TXT。
- 正式 Word/TXT 只能写入 `软件著作权申请资料/正式资料/`，不要散落在输出目录根部。
- 正式 Word/TXT 的文字一律使用默认黑色字体，不生成蓝色超链接、主题色标题或其他彩色文字；Markdown 链接写入 Word 时必须转成普通文本。
- 正式资料中的软件名称必须与 `草稿/申请表信息.md` 的“软件全称”字段一致；正式生成时以已确认的申请表软件全称为准。
- 正式代码 Word 页眉中的版本号必须与 `草稿/申请表信息.md` 的“版本号”字段一致；正式生成时以已确认的申请表版本号为准。
- 代码材料必须来自真实项目源码，禁止 AI 编造代码。
- 写申请表和操作手册前，必须先形成模型研判后的 `草稿/业务理解.md/json`，理解软件业务、行业、目标用户、核心价值和操作流程。
- 脚本只能收集项目证据、校验字段和生成文件；行业判断、功能抽取、代码抽取选择、操作手册结构必须由模型阅读项目后决定，不得依赖脚本关键字表或固定范本。
- 优先抽取前端代码：入口、路由、页面、核心组件、接口封装、状态管理、工具函数。
- 生成代码材料前，必须先生成代码文件候选清单；模型理解项目后填写抽取文件和选择理由，再让用户确认或修改。
- 代码优先抽取模型和用户确认的、最能体现软件真实功能和运行逻辑的源码；不足 60 页时，从其他相关源码文件补充到 60 页；候选源码仍不足 60 页时，才生成全部代码文档。
- 操作手册成稿应像真实软件随附的操作说明，而不是研发说明、功能清单或 AI 生成的汇总文。
- 操作手册草稿必须按传统软著操作手册骨架组织：系统简介、系统概述、功能清单、系统要求、术语表、按真实页面/流程逐章操作、典型使用流程、常见问题解答。一级章节标题使用中文大写序号，例如 `一、系统简介`，不得使用 `(1)、系统简介`。常见问题解答至少覆盖 8 个问题，分 Web 管理端（3+）、App 巡检端（3+）、跨岗位（2+）三个层级，不可低于此数量。其他条款同前。
- 每个核心页面都要用普通用户视角说明页面用途、进入位置、用户可见内容、用户动作、输入限制或异常提示、结果反馈和截图预留。不得把章节写成“进入方式：/页面内容：/操作步骤：/操作规则：/操作结果与反馈：”这种字段模板；这些信息要自然合并到段落里。避免代码、框架、接口、状态管理、异步任务等技术化表达；撰写过程中由 agent 自行循环检查、扩写和修正，完整草稿完成后只向用户发起一次整体确认。
- 操作手册必须去除明显“AI 味”：避免空泛赞美、营销口号、万能句式、每章同一结构、头中尾固定结构、过度对称的排比、没有项目细节的正确废话、频繁使用“旨在、赋能、一站式、智能化、高效便捷、显著提升、强大能力、丰富功能”等套话。每段都应能回答“这个项目里这个功能具体做什么、用户看见什么、操作后有什么结果”。
- 操作手册内容门禁必须参考 `references/manual_quality_gates.md`：确保适用用户表职责差异化、核心模块具备适用用户感、表格同列内容具备信息增量。若同一表格同一列内容重复出现 2 次及以上，不要简单换同义词或加豁免，应结合当前行上下文重写为有区分度的用途、处理方式、预期结果或反馈。
- 操作手册生成必须同步输出 `草稿/操作手册自检记录.md` 和 `草稿/操作手册自检记录.json`，记录初稿、按项目流程扩写、去制式表达等自检轮次；如果前 3 轮仍发现问题，必须继续补写修正，直到问题清零或记录无法自动修复的原因后再停止。
- 截图方式必须先让用户选择：Chrome DevTools MCP、Codex Computer Use、用户自行截图。用户选完后，再检查当前 MCP / Computer Use 能力是否可用；如果用户说现在不截图、先跳过截图或截图失败，操作手册仍必须保留清晰可见的截图预留位置，正式 Word 中也要能看到。
- 申请表信息中的硬件/系统环境必须让用户确认或填写，不能硬编码。
- Word 生成能力必须使用本 skill 内置的 `vendor/docx-toolkit`；不得引用外部 DOCX 目录。

## 强制人工门禁

凡是涉及用户选择、确认或补充信息的阶段，必须先停止当前执行，不得继续调用下一步脚本。即使处于自动审核、自动继续或无人值守模式，也必须把 `STOP_FOR_USER` 和 `NEXT_ACTION` 原样告知用户，并等待用户输入后再继续。

禁止使用“用户未选择则默认继续”的逻辑。用户回复确认后，先用确认脚本记录对应门禁，再进入下一阶段：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py --workdir 软件著作权申请资料 --stage <阶段名> --note "<用户确认内容>"
```

必须停住的门禁：

- `environment`：完整 DOCX 环境缺失时，用户必须选择“安装完整环境”或“使用基础 DOCX 兜底继续”。
- `project`：存在多个项目候选目录时，用户必须指定项目目录。
- `business`：`草稿/业务理解.md` 生成后，用户必须确认行业、目标用户、核心功能和申请口径。
- `application-fields`：`草稿/申请表信息.md` 生成后，用户必须补全并确认硬件、系统环境、著作权人、日期等字段。
- `code-selection`：`草稿/代码文件选择.json` 生成后，用户必须确认或修改抽取文件。确认时脚本会输出模块覆盖软警告——有模块在操作手册中描述但无对应代码覆盖时需在 `model_reason` 中说明原因，必要时回到业务理解阶段补充 `evidence`。
- `screenshot-method`：操作手册截图前，用户必须在 Chrome DevTools MCP、Codex Computer Use、用户自行截图三种方式中选择一种；如果用户明确说“现在不截图/先跳过截图”，记录为 `skip`。
- `markdown`：全部 Markdown 草稿完成后，用户必须确认可以进入 Word/TXT 生成。

## 工作流

**元规则：本 skill 是分阶段交付模式，不是一次性交付模式。** 每个 Step 生成文件后，必须立即停止当前 turn，输出 `STOP_FOR_USER`，等待用户输入。禁止在同一 turn 中连续执行两个会产出需确认文件的步骤。禁止在用户确认业务理解之前开始撰写申请表或操作手册——如果做了，那些文件在上游口径调整后就是废稿。

### 0. 登记任务

每个软著申请是一个独立任务。创建任务目录并初始化：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/init_task.py \
  --task-dir <任务根目录>/<软著名称> \
  --software-name "<软件全称>"
```

输出：

- 创建标准目录结构：`软件著作权申请资料/{analysis,草稿,正式资料,截图,用户截图}/`
- 写入 `<任务根目录>/<软著名称>/任务登记.json`，记录软件名称、任务路径和创建时间

任务登记后，后续所有脚本的 `--out-dir` / `--workdir` 参数均指向该任务下的 `软件著作权申请资料` 或其子目录。示例：

```bash
--out-dir "<任务根目录>/<软著名称>/软件著作权申请资料"
--out-dir "<任务根目录>/<软著名称>/软件著作权申请资料/草稿"
--workdir "<任务根目录>/<软著名称>/软件著作权申请资料"
```

### 1. 启动环境检查

检查运行能力：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/check_environment.py \
  --out-dir <任务根目录>/<软著名称>/软件著作权申请资料
```

输出：

- `软件著作权申请资料/环境检查.md`
- `软件著作权申请资料/环境检查.json`

环境检查必须告诉用户：

- 当前会在”当前目录/软件著作权申请资料”下生成材料。
- Markdown 草稿、TXT、基础 DOCX 是否可用。
- 内置 `vendor/docx-toolkit` 的完整 OpenXML 环境是否可用。
- **lark-cli 和 whiteboard-cli 是否可用**（用于生成技术图表到飞书画板）。
- 如 `.NET SDK` 缺失，询问用户是否安装完整环境。
- 如 lark-cli 或 whiteboard-cli 不可用，告知用户技术图表功能将降级为 Markdown 文本描述。

用户选择：

- 如果用户愿意安装完整环境，按 `${CLAUDE_SKILL_DIR}/vendor/docx-toolkit/scripts/setup.sh` 的要求安装依赖，再继续。完整环境生成和校验更规范。
- 如果用户不安装，继续使用兜底方案生成 Markdown、TXT 和基础 DOCX。
- 如果完整 DOCX 环境缺失，必须停止并等待用户选择；不得自动继续。
- 如果 lark-cli 或 whiteboard-cli 不可用，不阻塞流程，但需在环境检查报告中标注”技术图表功能降级”。

用户回复后记录门禁：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage environment \
  --note "<用户选择>"
```

不要等到最后验证阶段才发现完整 DOCX 环境不可用；这个信息必须在流程开始时给出。

### 2. 定位项目

用户通常会把项目放在当前文件夹下。先扫描当前目录，避开本 skill、自身输出目录、`node_modules`、构建产物和隐藏目录，找到最可能的项目根目录。

如果有多个候选项目，必须停止并询问用户选择；如果只有一个明显候选项目，可以直接使用。

### 3. 分析项目

运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze_project.py \
  --project <项目目录> \
  --out 软件著作权申请资料/analysis/project.json
```

分析内容包括：

- `package.json`、README、脚本命令、依赖
- 前端框架和主要编程语言
- 入口文件、路由、页面、组件、接口、状态管理
- 源码文件数量和源程序行数
- 软件名称候选、主要功能候选、运行命令候选

### 4. 形成业务理解

在写申请表和操作手册前，先让脚本收集项目证据：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_business_context.py \
  --project <项目目录> \
  --analysis 软件著作权申请资料/analysis/project.json \
  --software-name "<软件全称>" \
  --out-dir 软件著作权申请资料/草稿
```

输出：

- `草稿/业务理解证据.md`
- `草稿/业务理解证据.json`
- `草稿/业务理解模型稿模板.json`

这一步只收集证据，不决定最终业务口径。

#### 4a. 产品组成声明与闭环验证（在编写业务理解之前执行）

模型在编写 `业务理解.md` 之前，必须先执行以下两项验证，将结果写入 `草稿/业务理解.md` 的"产品组成与闭环验证"章节。

**一、产品组成声明**

回答三个问题：

1. 这个产品由几个端组成？（Web 管理端？App 端？服务端？每个端分别面向谁？）
2. 每个端分别在哪个代码仓库中？（给出绝对路径，如有多个仓库全部列出）
3. 每个端的模块分别在仓库的哪个目录下？（给出相对路径）

必须覆盖所有端。禁止因为当前扫描的仓库是 Web 端就只列出 Web 端的模块——如果项目下同时存在 `welleyao-hse-app`（Android）、`welleyao-hse-web`（Web 前端）、`welleyao-hse-plus`（后端服务），三个仓库的模块都必须覆盖。

**二、闭环验证**

在列出功能模块后，写出从初始配置到最终结果的完整闭环链路，格式为一条连续箭头链：

```
模块A → 模块B → 模块C(Web端) → App端：模块D → 模块E → 模块F → 模块G(Web端)
```

然后逐环节验证：**闭环链路中的每个节点在模块列表中都有对应的功能说明条目，且逻辑上能前后衔接。** 如果某个节点缺失（如 App 端的"现场签到"在模块列表中没有独立条目），必须在模块列表中补充该节点后再继续。

闭环验证的重点：
- 数据流是否完整：台账型模块维护的数据被哪个下游业务模块引用？
- 操作流是否完整：用户在一个模块中的操作结果是否触发下一个模块的行为？
- 端间切换是否完整：Web 端配置的数据是否被 App 端使用？App 端采集的数据是否回流到 Web 端？
- 角色切换是否完整：每个环节的操作者是谁？角色是否在过程中发生了切换？

验证结论写入 `草稿/业务理解.md`——通过时写明链路和每个节点的对应模块，不通过时写明缺失节点并补充后重新验证。

接下来必须由模型阅读 `业务理解证据.md/json`、README、PRD/BRD、页面文案、路由、接口、必要源码和用户补充资料，以 `references/业务理解模型稿模板.json` 为骨架，自行判断：

- 应该重点读取哪些文档和源码
- 软件属于什么行业 / 领域
- 目标用户是谁
- 核心价值是什么
- 哪些功能应写入软著申请资料
- 典型操作流程如何组织
- 操作手册适合采用什么章节结构
- 申请表建议口径如何表达

模型不得用脚本关键字表决定行业、功能和结构；不得把用户给的范本文案、测试项目名称、测试项目流程写成通用规则。

编写业务理解模型稿和 `业务理解.md` 时，必须读取 `references/business_understanding_rules.md` 和 `references/module_classification_rules.md`。前者包含业务主线与逆向场景的写作要求，后者定义模块的台账型/业务型/混合型分类标准和对应的 JSON 结构。

模型完成研判后，按以下顺序执行：

- `product_positioning`
- `industry`
- `target_users`
- `core_value`
- `business_features`
- `business_feature_details`
- `operation_flow`（对象列表；每项必须包含 `step` 和 `result`，不再使用字符串列表）
- `application_purpose`
- `main_functions`
- `technical_characteristics`
- `manual_sections`
- `manual_modules`
- `system_requirements`
- `faq`
- `glossary`

其中 `manual_modules` 是操作手册的核心输入。模型在填写之前，必须先阅读 `references/module_classification_rules.md`，判定每个模块是台账型、业务型还是混合型，再按对应结构填写：

- **台账型**（纯CRUD，如设备管理、NFC、二维码、工作日历）→ 用 `registry` 结构，逐项枚举 columns/filters/top_actions/row_actions/form_sections，**不准用"等"字省略**。
- **业务型**（有状态流转或操作链路，如巡检计划、任务执行、签到、检查项）→ 用 `business_operation` 结构，描述 `object_lifecycle`（对象状态机）和 `operation_chain`（操作阶段链），每个条件分支必须分别在 `conditional_branches` 中说明。
- **混合型**（台账面+业务配置面，如巡检点管理）→ 同时填 `registry` 和 `business_operation`，每条配置路径（双重预防路径/设备检查路径/包保路径等）分别列出，标注该路径引用了哪些台账模块的数据。

脚本不得按 `auth/query/form` 等分类模板自动补入口、步骤或反馈；缺少 `manual_modules` 或关键字段时必须停止让模型回到项目证据中补写。

`operation_flow` 也属于业务理解主路径，必须由模型写成结构化对象列表。每一项至少包含：

```json
{"step": "用户或业务对象实际发生的流程动作", "result": "该动作完成后的页面反馈、状态变化或后续流转结果"}
```

不得让 renderer 根据流程动作临时生成“系统完成相应处理并进入下一步”这类结果句。若旧模型稿仍使用字符串列表，必须回到业务理解 JSON 补 `step/result` 后再生成操作手册。

模型填写完 `manual_modules` 后，必须输出 `草稿/模块完整性自检记录.json`，逐模块记录分类结果、源码行数、操作数量和条件分支覆盖，有 WARNING 的模块在业务理解确认前清零。

`application_purpose`、`main_functions`、`technical_characteristics` 三个字段需特别注意：2026 年 3 月新政要求申请表"主要功能描述"不少于 500 字（上限 1300 字），必须覆盖研发背景、核心技术架构、功能模块及应用场景。业务理解阶段就必须输出足够丰满的文本，不得在申请表生成时再用模板扩写。

`manual_sections` 只允许补充当前软件本身的用途、业务场景、页面组织或用户流程，不要写“本操作手册用于……”“面向软著审核……”“不描述代码实现……”这类解释文档写作方式的元话语。最终操作手册应像真实软件说明书，而不是生成过程说明。

然后运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_business_context.py \
  --project <项目目录> \
  --analysis 软件著作权申请资料/analysis/project.json \
  --software-name "<软件全称>" \
  --out-dir 软件著作权申请资料/草稿 \
  --model-context <模型生成的业务理解JSON>
```

输出：

- `草稿/业务理解.md`
- `草稿/业务理解.json`

最终业务理解必须覆盖：

- 产品定位
- 面向领域 / 行业
- 目标用户
- 核心价值
- 主要业务功能
- 典型操作流程
- 申请表建议口径
- 证据来源
- 操作手册结构建议

#### 4a. 获取菜单路径数据（操作手册操作路径的来源）

在撰写操作手册前，模型必须从以下来源之一提取真实的菜单层级结构，供后续每个功能模块的"操作路径"字段使用：

1. **后端 SQL 迁移脚本（优先）**：搜索 `script/sql/` 目录中最新的 `sys_menu` 或 `sys_menu ` INSERT 语句。提取每个菜单项的 `menu_name`（菜单名称）、`parent_id`（父级 ID）和 `menu_type`（M=目录/C=菜单/F=按钮）。通过 `parent_id` 构建完整的菜单层级树——从 `parent_id=0` 的顶级菜单开始，递归找出每个 C 类型（菜单）节点的父级路径。示例输出：`承包商管理 → 承包商公司`（从 SQL 中 parent_id 链路 `0 → 1838388165828063234 → 1838389607351627778` 解析得出）。

2. **前端路由文件（备选）**：读取 `router/index.ts`，解析每个路由对象的 `meta.title` 和嵌套层级。

3. **兜底**：若以上来源均不可用，在业务理解中标注"菜单数据不可获取，操作路径使用兜底表述"。操作手册中写"从系统菜单进入对应功能页面"，不准编造假路径。

提取的菜单路径数据写入 `草稿/业务理解.md` 中每个功能说明的"操作路径"字段，或单独输出为 `草稿/菜单路径映射.json`，供操作手册撰写时逐模块引用。

如果项目材料不足、业务类型较新，或用户明确希望参考竞品，可联网搜索相近产品和行业资料；外部调研只用于理解行业表达，不能编造项目不存在的功能。调研摘要应写入业务理解草稿，并区分“项目证据”和“行业参考”。

生成 `业务理解.md/json` 后必须立即停止当前 turn，输出 `STOP_FOR_USER` 和 `NEXT_ACTION`，等待用户确认或修改。**业务理解确认前，禁止开始撰写申请表、操作手册或代码选择。** 如果业务理解仍不充分，先请用户补充产品说明。用户确认后运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage business \
  --note "<用户确认内容>"
```

### 5. 引导用户确认字段

**前置检查**：
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir 软件著作权申请资料 --before application-fields
```
如果 exit != 0，停止并等待用户确认 business 门禁。

根据分析结果，向用户确认：

- 软件全称
- 版本号
- 著作权人
- 开发完成日期
- 首次发表日期或未发表
- 开发硬件环境
- 运行硬件环境
- 开发操作系统
- 运行平台/操作系统
- 开发工具（IDE 或编辑器名称）
- 运行支撑环境/支持软件（项目运行所需 Node.js、Python、Docker、数据库、浏览器、中间件或外部服务）
- 软件分类
- 软件技术特点选项
- 经办人姓名
- 经办人身份证号码
- 经办人职务
- AI开发限制声明（需手抄"未使用 AI 开发编写代码、撰写文档或生成登记申请材料"）

项目可推断字段可以先给建议值；硬件/系统环境必须允许用户选择建议值或手动填写。字段口径必须区分清楚：

- 软件全称：必须由用户确认。最终正式资料文件名、代码 Word 页眉、操作手册标题和正文中的软件名称，都必须与 `申请表信息.md` 的“软件全称”字段一致。
- 版本号：必须由用户确认。优先读取项目配置中的版本号作为证据；如果项目版本号小于 V1.0（例如 V0.1.0、V0.9.0），必须明确询问用户“软著首次提交通常写 V1.0，本次填写 V1.0 还是项目当前版本号”。最终 `申请表信息.md` 的“版本号”字段就是正式资料版本号。
- 软件开发环境 / 开发工具：填写 IDE 或编辑器名称，例如 Visual Studio Code、WebStorm、IntelliJ IDEA、Cursor；不要把 React、Next.js、Vite、TypeScript 等技术栈写到此字段。
- 开发该软件的操作系统：填写实际开发电脑的操作系统版本，例如 Windows 10、Windows 11、macOS 14、macOS 15。
- 该软件的运行平台 / 操作系统：填写软件运行所在的操作系统版本，例如 Windows 10/11 或 macOS 13及以上版本。
- 软件运行支撑环境 / 支持软件：填写项目运行依赖的软件环境，例如 Node.js、Python、Docker、PostgreSQL、Redis、浏览器、中间件、外部模型或云服务。
- 开发的硬件环境：优先读取当前电脑 CPU、内存、硬盘、架构等配置作为建议值；读取不到时让用户填写。
- 运行的硬件环境：默认可沿用开发硬件环境建议值，也可以按实际部署或运行设备修改。

此阶段需要先停止当前 turn、输出 `STOP_FOR_USER`，等待用户输入字段值；收到用户回复后，可整理为 `answers` JSON 传入申请表草稿生成。申请表草稿生成后再次停止，等待用户确认全部字段。申请表字段的最终门禁在 `草稿/申请表信息.md` 生成并确认后记录。

### 6. 生成操作手册草稿

**前置条件：business 门禁已确认。**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir 软件著作权申请资料 --before manual-draft
```
如果 exit != 0，停止并等待用户确认 business 门禁。如果 `草稿/业务理解.md` 尚未经用户确认，禁止开始此步骤——操作手册依赖业务理解中的 `manual_modules` 和功能口径，在业务理解未确认前生成的任何操作手册内容都可能在口径调整后作废。

在代码选择之前先生成操作手册草稿。操作手册描述了软件"做什么"，代码材料应展示这些功能"怎么做"——操作手册的功能模块（`manual_modules`）是代码文件选择的驱动源。

运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_manual_draft.py \
  --analysis 软件著作权申请资料/analysis/project.json \
  --business-context 软件著作权申请资料/草稿/业务理解.json \
  --software-name "<软件全称>" \
  --version "<版本号>" \
  --out-dir 软件著作权申请资料/草稿
```

生成或调整操作手册时，必须读取 `references/manual_structure.md`、`references/manual_quality_gates.md`、`references/module_skeleton.md` 和 `references/manual_content_quality_sop.md`。前三者说明章节骨架、写作口径和四表一图模板；后者定义**模块分类与深度差异**——台账型模块（纯 CRUD）仅需标准四表并注明下游影响，业务型模块（含审批流转、状态机、多角色协同）必须深挖后端代码逻辑、理清完整业务链路、用表格化方式呈现（操作步骤表、状态流转表、处理项变化表），所有技术术语翻译为业务语言。**功能清单不是一次写完的——完成各模块细节后必须回头迭代升级功能清单，用深挖到的链路细节补全业务型模块的子功能描述。**

操作手册草稿不得照抄用户提供的范本文案或旧项目内容，但应吸收其结构特点：先写系统简介、功能特点和系统要求，再按真实页面或核心流程逐章说明操作，最后写常见问题解答和术语表。一级章节标题使用中文大写序号；功能特点和页面操作章节必须以段落展开，不用项目符号和编号列表堆信息。必须基于模型写入 `草稿/业务理解.json` 的 `manual_modules` 组织章节；`manual_sections` 只用于补充说明性段落，不应用来反复插入同一批功能模块。各功能章节必须写清页面用途、进入位置、用户看到的控件和数据、实际操作、输入限制或异常提示、操作结果和截图预留。语言要面向普通用户，说明"这个页面是干嘛的、用户怎么进入、用户点什么/填什么、操作后看到什么"，不要写代码实现、框架名称、接口封装、状态管理、异步队列等技术细节。撰写时由 agent 自行检查章节是否完整、内容是否过薄、语言是否过于技术化，并在草稿内部完成必要补写。

生成脚本必须同时写出 `草稿/操作手册自检记录.md` 和 `草稿/操作手册自检记录.json`。自检记录至少包含：

- 第 1 轮：初稿生成，检查章节完整性、截图预留、模块内容厚度和技术化表达。
- 第 2 轮：按项目真实运行流程扩写模块说明，补足上下游衔接关系。
- 第 3 轮：去除制式表达和 AI 味，重点检查重复句式、统一套话、空泛赞美、营销口号、过度整齐的排比和没有项目细节的正确废话。
- 内容门禁：检查适用用户表是否职责差异化、核心模块是否面向适用用户、表格同列内容是否重复且缺少信息增量，并检查 `evidence_gaps.count` 是否为 0。
- 后续轮次：如果仍有问题，继续补写、去重、改写，不能把未修正的问题直接交给用户。

操作手册的模块写作必须从 `草稿/业务理解.json` 的行业、目标用户、核心价值、业务功能、典型操作流程和 `manual_modules` 出发。不同模块要写出各自的业务作用、入口、控件、规则和反馈，不能统一套用"进入页面、填写内容、提交按钮、查看结果"的固定句式，也不能使用"进入方式：/页面内容：/操作步骤：/操作规则：/操作结果与反馈："这类字段标题；相近模块也要结合项目真实业务区分各自的操作目的和结果。自检时必须检查是否把同一批模块在多个章节中重复展开；如发现重复，改为每个真实页面或流程独立成章。不得把测试项目的功能名称、业务流程或示例文案写成通用规则。

当前操作手册生成链路已拆为模型层、渲染层、表格层、证据路由层和质量层。业务内容只能来自 `业务理解.json`；`manual_renderer.py` 只渲染结构化模型；`evidence_router.py` 不生成操作内容，只记录缺失字段的证据文件指引——当模型 JSON 缺少结构化数据时，输出指向具体源码文件的阅读指令，引导模型回到代码中提取真实信息，而非通过关键词匹配编造文本。若 `操作手册自检记录.json` 中任一轮 `evidence_gaps.count > 0`，必须按指引读取对应证据文件，补全业务理解 JSON 后重新渲染，直到 gap count 为 0 或已向用户说明具体缺失证据。

> **说明**：此步骤生成操作手册草稿用于稳定 `manual_modules` 的语义内容，为下一步代码选择提供模块-代码覆盖依据。操作手册的最终用户确认仍在后面的 markdown 门禁统一进行。

### 7. 确认代码文件选择（基于操作手册模块）

**前置检查**：
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir 软件著作权申请资料 --before code-selection
```
如果 exit != 0，停止并等待用户确认 business 门禁。

操作手册草稿稳定后，代码文件选择必须以 `manual_modules[].evidence` 为驱动源——优先选择这些在业务理解阶段已确认为各模块真实代码证据的文件。

运行候选文件分析时，必须传入业务理解上下文以建立模块-代码依赖：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/propose_code_selection.py \
  --project <项目目录> \
  --analysis 软件著作权申请资料/analysis/project.json \
  --business-context 软件著作权申请资料/草稿/业务理解.json \
  --out-dir 软件著作权申请资料/草稿
```

当 `--business-context` 可用时，脚本会：
- 从 `manual_modules` 中提取 `evidence` 文件路径
- 与候选文件交叉比对，在 `代码文件候选清单.md` 中输出「模块代码覆盖」章节
- 标记有 evidence 但在候选池中缺失的模块、以及无任何 evidence 的模块

输出：

- `草稿/代码文件候选清单.md`：给用户看的候选说明，含模块代码覆盖表。
- `草稿/代码文件选择.json`：可编辑的选择文件。

模型在填写 `selected` 和 `model_reason` 时必须：

1. **优先选择** `manual_modules[].evidence` 中列出的文件
2. 对于 evidence 文件不在候选池中的模块，在 `model_reason` 中说明原因
3. 补充文件（不属任何模块 evidence 的文件）必须在 `model_reason` 中标注为"补充——不属特定模块"
4. 确保每个操作手册功能模块至少有一个 evidence 文件被选中（若 evidence 在候选池中存在）

模型选择时还必须读取 `references/code_selection_rules.md` 中的「模块-代码依赖规则」和「AI 生成代码规避规则」。

模型选择通常优先考虑前端入口、页面、核心组件、业务交互、数据请求、状态处理等能给审核员看懂软件功能的代码；如果相关前端代码不足 60 页，再补充后端服务、业务处理等相关源码。补充文件同样必须写入 `代码文件选择.json` 并由用户确认。不要默认抽取全量代码库。代码材料按完整文件原样复制，不支持只抽取某个文件的中间行段。

`草稿/代码文件选择.md` 和 `草稿/代码文件选择.json` 生成后必须立即停止当前 turn，输出 `STOP_FOR_USER` 和 `NEXT_ACTION`，等待用户确认或修改文件选择。用户确认并记录 `code-selection` 门禁后，代码抽取只读取 `代码文件选择.json` 中选中的完整文件。用户确认后运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage code-selection \
  --note "<用户确认内容>"
```

### 8. 生成代码材料与申请表信息

**前置检查**：
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir 软件著作权申请资料 --before extract-code
```
如果 exit != 0，停止并等待用户确认 code-selection 门禁。

运行代码材料抽取：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/extract_code_material.py \
  --project <项目目录> \
  --analysis 软件著作权申请资料/analysis/project.json \
  --selection 软件著作权申请资料/草稿/代码文件选择.json \
  --software-name "<软件全称>" \
  --version "<版本号>" \
  --out-dir 软件著作权申请资料/草稿
```

代码分页规则：

- 每页默认 50 行，并在 Word 中使用紧凑固定行距，尽量减少长行折行造成的页面溢出。
- 总页数 `>= 60`：生成 `代码-前30页.md` 和 `代码-后30页.md`。
- 总页数 `< 60` 且候选源码已用尽：只生成 `代码-全部.md`。
- 总页数 `< 60` 但候选清单还有可补充源码：停止并要求用户在 `代码文件选择.json` 中继续选择补充文件。
- 不为大项目生成超大“全量备份 Word”。
- 同时生成 `代码提取清单.md` 和 `代码提取清单.json`，用于追溯代码来源。

生成申请表信息草稿：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_application_info.py \
  --analysis 软件著作权申请资料/analysis/project.json \
  --code-manifest 软件著作权申请资料/草稿/代码提取清单.json \
  --business-context 软件著作权申请资料/草稿/业务理解.json \
  --software-name "<软件全称>" \
  --version "<版本号>" \
  --out-dir 软件著作权申请资料/草稿
```

生成后必须停止，让用户检查并补全 `草稿/申请表信息.md`。字段补全并确认后运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage application-fields \
  --note “<用户确认内容>”
```

> **说明**：操作手册草稿已在上一步（步骤 6）生成，此处不再重复。申请表的”主要功能描述”等字段必须与操作手册中描述的功能模块保持一致。

### 9. 生成技术图表（飞书画板）

**前置检查**：开始生成图表前，必须运行 `lark-cli auth status --verify` 确认 user token 有效且 `tokenStatus` 为 `valid`。如 user token 已过期（`tokenStatus: expired`），停止并提示用户运行 `lark-cli auth login`。不得以 bot 身份创建画板——bot 的 `board:whiteboard:node:create` scope 存在，但目标知识库文档的编辑权限仅对 user 开放。

2026 年新政要求操作手册需包含软件结构图、功能流程图、逻辑框图、接口设计说明等技术图表。图表统一绘制到飞书知识库画板，一个画板一张图，便于嵌入操作手册和后续维护。

**PlantUML 解析限制**：飞书画板的 PlantUML 解析器不支持 `left to right direction` 水平布局指令。分模块操作流程图（分图）使用默认纵向活动图即可，无需尝试改为横向布局。总图中的泳道图（`\|actor\|`）仅用于核心业务流程图（需跨角色表达），其他模块分图使用无泳道的纯活动图（`start → :step; → stop`）。

图表按**总分结构**组织：

**总图（4 张，覆盖系统全局）**：

| # | 图表名称 | 图型 | 内容来源 |
|---|---|---|---|
| 1 | 系统架构图 | Deployment + Component | 项目技术栈、部署拓扑、客户端/服务端/数据层关系 |
| 2 | 功能模块图 | Component / Package | 项目所有功能模块的分层结构和包依赖关系 |
| 3 | 核心业务流程图 | Activity（泳道图） | 项目最核心的一条正向业务全链路，按角色分泳道，串联各模块 |
| 4 | 数据模型关系图 | Class | 核心业务实体及其关联关系（Entity / Domain Model） |

总图从全局视角交代系统整体技术方案，四张图各自覆盖不同维度：部署拓扑、模块划分、业务流程、数据设计。

**分图（按功能模块逐张展开）**：

在总图之后，为操作手册中每个核心功能模块单独生成一张**功能使用流程图**。分图用 Activity 图或泳道图表达**该模块内的具体操作步骤和分支逻辑**，而非全局流程。

分图的模块来源 = 业务理解阶段确认的 `manual_modules`。每个模块的流程图必须基于该模块的 `crud_scenarios` 或 `operation_steps` 绘制，体现”用户动作 → 系统响应 → 异常分支”的完整操作链路。

> **判断原则**：总图回答”这个系统是什么、由哪些部分组成”，分图回答”用户在每个功能里具体怎么操作”。分模块操作流程图取代操作手册中的表格化操作步骤，让审核员通过图表即可理解每个功能模块的用户操作路径。

**画板命名规则**：`软著名称-图表名称`。
- 总图：`化桉企业培训管理系统-系统架构图`、`化桉企业培训管理系统-功能模块图`、…
- 分图：`化桉企业培训管理系统-线上培训管理操作流程`、`化桉企业培训管理系统-考试管理操作流程`、…

**统一目标文档**：所有画板创建到以下飞书知识库页面：
```
https://my.feishu.cn/wiki/CWDqw6vMwidfGhkvOjWc2uAcnHf
```
> 该文档仅用于集中存放软著技术图表画板，不存放其他内容。总图和分图全部写入此文档，按先总后分的顺序排列。

**图表数量预估**（以化桉企业培训管理系统为例）：

| 类型 | 数量 | 说明 |
|---|---|---|
| 总图 | 4 张 | 系统架构、功能模块、核心业务流程、数据模型 |
| 分图 | ≈模块数 | 每个 `manual_modules` 条目对应一张操作流程图 |
| **合计** | **4 + N** | N = 核心功能模块数，通常 6-12 张分图 |

**生成流程**：

**Step 1 — 读取项目证据**：模型在完成业务理解（Step 4）和代码选择（Step 7）后，已掌握项目的技术栈、模块结构、核心 API 调用链和业务流程。总图基于系统全局证据绘制；分图基于 `manual_modules` 中每个模块的 `crud_scenarios`/`operation_steps`/`validation_rules` 绘制。

**Step 2 — 选择渲染路径**：

| 图表类型 | 适用场景 | 渲染路径 |
|---|---|---|
| 活动图、泳道图、时序图、类图、用例图 | 分图（操作流程图）、核心业务流程图、数据模型图 | PlantUML 直接写入 |
| 架构图、部署图、组件图、包图 | 总图（系统架构图、功能模块图）| SVG 路径（`routes/svg.md`）|

> PlantUML 路径适用于结构清晰的 UML 图型，`lark-cli whiteboard +update --input_format plantuml` 原生支持。
> SVG 路径适用于需要自由布局和视觉设计的架构类图表，通过 whiteboard-cli 渲染为 OpenAPI 再写入。

**Step 3 — 创建画板并写入**：

对每张图表，依次执行：

```bash
# 1. 在目标文档末尾追加空白画板
lark-cli docs +update --api-version v2 \
  --doc CWDqw6vMwidfGhkvOjWc2uAcnHf \
  --command append \
  --content '<whiteboard type=”blank”></whiteboard>' \
  --as user
```

从响应 `data.new_blocks` 中找到 `block_type == “whiteboard”` 的条目，提取其 `board_token`。

**3a. PlantUML 路径**（活动图/泳道图/时序图/类图/用例图）：

```bash
cat <<'PUML' | lark-cli whiteboard +update \
  --whiteboard-token <board_token> \
  --input_format plantuml --source - \
  --overwrite --as user
@startuml
... PlantUML 代码 ...
@enduml
PUML
```

**3b. SVG 路径**（架构图/部署图/组件图）：

遵循 `lark-whiteboard` skill 的 `routes/svg.md` 完整流程：
- 阅读 `routes/svg.md`
- 创作 SVG → 保存 `diagrams/<timestamp>/diagram.svg`
- 渲染审查：`npx -y @larksuite/whiteboard-cli@^0.2.10 -i <dir>/diagram.svg -f svg --check`
- 导出并写入：`npx -y @larksuite/whiteboard-cli@^0.2.10 -i <dir>/diagram.svg -f svg --to openapi --format json | lark-cli whiteboard +update --whiteboard-token <token> --source - --input_format raw --overwrite --as user`

**生成顺序**：先画总图（全局认知先立住），再按 `manual_modules` 顺序逐张画分图。

**Step 4 — 记录画板引用**：

每张图表完成后，将其画板链接记录到 `草稿/技术图表清单.md`：

```markdown
## 总图
| # | 图表名称 | 画板链接 |
|---|---------|---------|
| 1 | 系统架构图 | https://my.feishu.cn/whiteboard/<board_token> |
| 2 | 功能模块图 | ... |
| 3 | 核心业务流程图 | ... |
| 4 | 数据模型关系图 | ... |

## 分图（功能操作流程）
| # | 图表名称 | 对应模块 | 画板链接 |
|---|---------|---------|---------|
| 5 | 课程管理操作流程 | coursesInfo | ... |
| 6 | 线上培训管理操作流程 | onlineTrainingManagement | ... |
| ... | ... | ... | ... |
```

> **注意**：图表生成发生在操作手册 Markdown 草稿撰写期间。模型先完成总图 → 写入操作手册骨架 → 再逐章写功能操作章节并同步生成对应分图 → 最后整体确认。

### 10. 导出图表并嵌入 Markdown 草稿

全部图表生成完毕后，将飞书画板批量导出为 PNG，嵌入操作手册 Markdown 草稿的对应位置。`build_docx_from_md.py` 在生成正式 Word 时会自动读取 `![alt](path)` 语法、调用 python-docx 的 `add_picture()` 将图片插入文档——无需手动拼接。

**Step 1 — 批量导出 PNG**：

对 `草稿/技术图表清单.md` 中记录的每张图表，依次运行：

```bash
lark-cli whiteboard +query \
  --whiteboard-token <board_token> \
  --output_as image \
  --output 软件著作权申请资料/截图/<图表名称>.png \
  --overwrite --as user
```

导出后的文件命名与画板命名一致：
```
软件著作权申请资料/截图/
├── 系统架构图.png
├── 功能模块图.png
├── 核心业务流程图.png
├── 数据模型关系图.png
├── 课程管理操作流程.png
├── 线上培训管理操作流程.png
├── 考试管理操作流程.png
├── 试卷管理操作流程.png
└── ...
```

**Step 2 — 更新 Markdown 草稿**：

在操作手册 Markdown 中，用 `![图表名称](截图/文件名.png)` 替换原有的文字占位：

- **总图**：插入到"五、系统架构概述"章节，每张总图一段文字说明后紧跟一张图。

  ```markdown
  ## 五、系统架构概述
  
  本系统采用客户端-服务端分层架构...（文字说明）
  
  ![系统架构图](截图/系统架构图.png)
  
  系统功能模块按业务域划分为以下层级...（文字说明）
  
  ![功能模块图](截图/功能模块图.png)
  ```

- **分图**：插入到各功能操作章节的开头，在操作步骤表之前先展示流程图，让读者通过图表理解整体操作路径后再看文字细节。

  ```markdown
  ## 六、课程管理
  
  课程管理模块用于管理员创建和维护企业培训课程体系...
  
  ![课程管理操作流程](截图/课程管理操作流程.png)
  
  ### 操作步骤
  
  | 步骤 | 用户操作 | 系统响应 | 异常处理 |
  |---|---|---|---|
  | ... | ... | ... | ... |
  ```

> **分图定位原则**：流程图放在对应模块章节的功能说明段落之后、操作步骤表之前。流程图表达"这个模块干什么、分哪些分支"，操作步骤表写清"每一步的具体动作和反馈"——图表和表格互不替代、形成互补。

**Step 3 — 更新图表清单**：

在 `草稿/技术图表清单.md` 中补录本地文件路径列，便于追溯：

```markdown
## 总图
| # | 图表名称 | 画板链接 | 本地文件 |
|---|---------|---------|---------|
| 1 | 系统架构图 | https://... | 截图/系统架构图.png |
| ... | ... | ... | ... |

## 分图（功能操作流程）
| # | 图表名称 | 对应模块 | 画板链接 | 本地文件 |
|---|---------|---------|---------|---------|
| 5 | 课程管理操作流程 | coursesInfo | https://... | 截图/课程管理操作流程.png |
| ... | ... | ... | ... | ... |
```

> **说明**：`build_docx_from_md.py` (Step 14) 在将 Markdown 转为 Word 时，自动解析 `![alt](path)` 语法。如果图片文件存在则用 python-docx 的 `add_picture()` 插入（宽度 5.8 英寸），如果缺失则插入占位文字 `[截图缺失：path]`。因此只要 PNG 已正确导出到 `截图/` 目录、且 Markdown 中的相对路径正确，正式 Word 就会自动包含所有图表。

### 11. 模型审查渲染输出

操作手册由脚本根据模型 JSON 渲染生成。渲染器不会做语义判断，因此可能在以下方面出现偏差：

- **行业/定位文案**：渲染器虽然从模型 JSON 取 `industry` 和 `core_value`，但如果模型 JSON 中包含不相关行业的术语残留，渲染输出会被污染。
- **模块分组标题**：渲染器根据 `manual_sections` 中 `include_operation_modules: true` 的章节标题分组。如果分组名称和模块内容不匹配，说明模型 JSON 的章节结构需要调整。
- **适用用户表**：渲染器从 `target_users` 取 `role` 和 `usage` 来渲染用户表。如果渲染结果出现 `{'role': ...}` 等 Python dict 字面量，说明渲染函数未正确处理——需模型检查并确认格式。
- **操作路径**：渲染器直接从 `entry` 字段取菜单路径。如果出现英文路由名，说明模型 JSON 的 entry 字段需要改为中文菜单路径。
- **兜底文案残留**：渲染器在模型 JSON 缺失 `outcome`/`constraint` 字段时会输出 `[WARNING: ...]` 占位符。出现此类占位符时，必须回到业务理解阶段补全对应字段，不能直接进入确认门禁。

模型在操作手册 Markdown 生成后，必须阅读 `草稿/操作手册.md`，逐一检查以上 5 项。发现问题时直接修改模型 JSON（通常是 `业务理解模型稿.json` 中的 `manual_sections`、`manual_modules`、`target_users`、`product_positioning`、`core_value`、`industry` 字段），然后重新渲染业务理解并重新生成操作手册。该循环最多 2 次——超过 2 次仍存在 WARNING 占位符时，必须告知用户具体缺失项并停止。

### 12. 选择并获取截图

操作手册草稿完成后，先停止并让用户选择截图方式，必须给出三种选项：

1. Chrome DevTools MCP：适合已在浏览器中打开的 Web 项目，优先用于网页全页截图。
2. Codex Computer Use：适合需要通过桌面应用或浏览器界面点击、切换、查看状态后截图的场景。
3. 用户自行截图：用户自己把 PNG/JPG/JPEG/WebP 图片放入 `软件著作权申请资料/用户截图/`，agent 只负责整理和引用。

**2026 年新政重要变更**：操作手册截图已从”建议”升级为强制要求。审核系统要求操作手册必须包含完整的登录界面及操作步骤截图，且截图中的软件名称、公司 Logo 必须与申请表信息保持绝对一致。不再提供”跳过截图”作为推荐的默认选项——跳过截图可能导致补正或驳回。若用户确实无法截图（如项目未运行），仍可记录为 `skip` 并保留可见截图占位符，但必须在 `生成报告.md` 中标注截图缺失的补正风险。

用户选择后，先记录门禁：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage screenshot-method \
  --method <chrome-devtools|computer-use|user-supplied|skip> \
  --note “<用户选择>”
```

然后按用户选择检查当前能力并执行：

- 选择 Chrome DevTools MCP：先用工具发现能力检查当前环境是否有 `mcp__chrome_devtools__` 的 `list_pages`、`take_snapshot`、`take_screenshot`。可用时，先 `list_pages` 确认当前浏览器页面，再按页面/路由截图保存到 `软件著作权申请资料/截图/`；不可用时停止，告知用户需要重新选择截图方式或手动提供截图。
- 选择 Codex Computer Use：先用工具发现能力检查当前环境是否有 `mcp__computer_use__` 的 `get_app_state`、`click`、`press_key`。可用时，先 `get_app_state` 查看目标应用或浏览器当前状态，再按操作手册需要导航和截图；如果当前 Computer Use 只能返回会话内截图而不能直接保存图片文件，则说明限制，并让用户改选 Chrome DevTools MCP 或把截图放入 `用户截图/`。
- 选择用户自行截图：创建 `软件著作权申请资料/用户截图/`，提示用户把截图文件放入该目录；用户放入后运行下面的整理命令，把图片复制到 `软件著作权申请资料/截图/` 并生成 `截图清单.json`。
- 选择跳过截图：仅在用户明确声明”当前无法截图”时允许，必须告知用户这可能触发补正；正式操作手册中保留可见的截图预留文字 `【截图预留：请在此处插入”xxx”页面或操作结果截图。】`，并在生成报告中标注”截图未插入，存在补正风险”。

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/capture_screenshots.py \
  --manual-dir 软件著作权申请资料/用户截图 \
  --out-dir 软件著作权申请资料/截图
```

截图一致性检查：截图成功后，在插入操作手册前，必须确认：
- 截图中的软件名称是否与 `草稿/申请表信息.md` 的”软件全称”一致。
- 截图中的公司 Logo 或版权归属标识是否与著作权人信息一致。
- 是否包含登录界面截图（2026 新政强制要求）。

截图成功后，把截图引用补入 `草稿/操作手册.md`；截图失败或用户选择暂不提供截图时，继续生成带截图预留位的文字版，并在报告中说明”操作手册截图未生成或未插入，已保留截图预留位置，存在补正风险”。

### 13. 用户确认 Markdown

**内容质量门禁（强制执行）**。在进入 markdown 门禁确认前，必须先运行内容质量自查：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/content_quality_check.py --manual 软件著作权申请资料/草稿/操作手册.md
```

四项自动检查（技术术语清除 / 表格密度 / 功能清单迭代 / 业务模块表格化）。exit 0 = 通过，exit 1 = 存在必须修复的问题。exit != 0 时必须逐条修复后重新运行，直到通过为止。通过后：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py --workdir 软件著作权申请资料 --stage content-quality --note "内容质量检查通过" --confirm
```

然后运行 gate_check 确认 markdown 门禁的全部前置条件（application-fields + code-selection + screenshot-method + content-quality）均已确认。全部通过后继续用户确认。

生成 Word 前，必须让用户确认 `软件著作权申请资料/草稿/` 下的 Markdown。

重点检查：

- 软件名称和版本号是否一致
- 代码材料前30页、后30页页眉软件名称是否与 `申请表信息.md` 的”软件全称”一致
- 代码材料前30页、后30页页眉版本号是否与 `申请表信息.md` 的”版本号”一致
- 操作手册 Word 页眉是否与代码材料页眉一致，均使用 `申请表信息.md` 的”软件全称”和”版本号”
- `业务理解.md` 是否准确反映软件真实业务、行业和目标用户
- `申请表信息.md` 中”待用户确认”的字段是否已确认
- 申请表是否包含 AI 开发限制声明、经办人姓名、身份证号码、职务等 2026 新政新增字段
- 代码材料是否只来自用户确认的完整文件
- 操作手册是否符合审核员阅读场景，普通读者是否能看懂模块用途和操作方式
- 操作手册每个章节是否有段落内容，核心模块是否写清模块用途、操作过程和结果反馈，是否避免过度技术化语言
- **技术图表**：总图 4 张是否齐全（系统架构图、功能模块图、核心业务流程图、数据模型关系图）；分图是否覆盖所有核心功能模块且与 `manual_modules` 一一对应；每张分图是否体现”用户动作 → 系统响应 → 异常分支”的完整链路
- **图表嵌入**：`草稿/操作手册.md` 中总图的 `![图片](截图/xxx.png)` 引用是否已在”系统架构概述”章节；分图引用是否已在各自对应功能操作章节的开头（功能说明段落之后、操作步骤表之前）；`草稿/技术图表清单.md` 是否包含本地文件路径列
- **图表一致性**：图表中的系统名称、模块名称是否与操作手册和申请表一致；图表中的角色名称是否与业务理解的目标用户一致；分图的模块操作路径是否可回溯到对应的真实页面代码
- 截图是否正确；截图中的软件名称和 Logo 是否与申请表信息一致；是否包含登录界面截图（2026 新政强制要求）
- 若用户跳过截图，正式操作手册是否保留可见截图预留位置，生成报告是否标注补正风险

用户确认后，必须记录 `markdown` 门禁；未记录时不得生成正式 Word/TXT。

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/confirm_stage.py \
  --workdir 软件著作权申请资料 \
  --stage markdown \
  --note "<用户确认内容>"
```

### 14. 生成正式 Word/TXT

**前置检查**：
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gate_check.py --workdir 软件著作权申请资料 --before build-final
```
如果 exit != 0，停止并等待用户确认 markdown 门禁。

用户确认后运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_docx_from_md.py \
  --workdir 软件著作权申请资料 \
  --software-name "<软件全称>" \
  --version "<版本号>"
```

正式生成脚本必须重新读取 `草稿/申请表信息.md` 中已确认的“软件全称”和“版本号”，并用它们生成正式资料文件名、代码 Word 页眉和操作手册 Word 页眉。操作手册页眉必须与代码材料页眉格式一致：左侧为“软件全称 版本号”，右侧为“第 <页码> 页”。若命令参数 `--software-name` / `--version` 与申请表字段不同，以申请表字段为准，并在 `正式资料/生成报告.md` 中记录提示。

输出：

- `正式资料/申请表信息.txt`
- 代码达到或超过 60 页：
  - `正式资料/<软件全称>-代码(前30页).docx`
  - `正式资料/<软件全称>-代码(后30页).docx`
- 代码不足 60 页：
  - `正式资料/<软件全称>-代码(全部).docx`
- `正式资料/<软件全称>_操作手册.docx`
- `正式资料/生成报告.md`

### 15. 三轮验证

至少执行三轮验证并修复发现的问题：

1. 文件完整性：目标 Word/TXT 是否存在且非空；`草稿/技术图表清单.md` 中记录的每张图表是否都有对应的导出 PNG 文件；PNG 是否非零字节。
2. 代码真实性：抽样检查代码片段能回溯到项目源码。
3. 业务真实性：申请表和操作手册中的行业、目标用户、主要功能、操作流程能回溯到业务理解文档和项目证据。
4. 图表真实性：总图的技术架构是否与项目实际部署方案一致；功能模块图的包层级是否与项目源码结构吻合；分图的模块操作路径是否能回溯到对应的 `manual_modules` 和真实页面/API 的代码证据。
5. 图表嵌入完整性：正式 Word 中总图（系统架构概述章节）和分图（各功能操作章节）是否均已正确嵌入且可辨识；图片是否未变形、未截断。
6. 一致性和格式：软件名称、版本号、页数规则、申请表字段、操作手册标题、截图引用是否一致；图表中的软件名称/模块名称/角色名称是否与操作手册和申请表一致。

可用命令：

```bash
python3 -m py_compile ${CLAUDE_SKILL_DIR}/scripts/*.py
bash ${CLAUDE_SKILL_DIR}/vendor/docx-toolkit/scripts/docx_preview.sh <生成的docx>
```

完整 DOCX 环境检查和安装必须直接恢复/构建 `${CLAUDE_SKILL_DIR}/vendor/docx-toolkit/scripts/dotnet/DocxToolkit.Cli/DocxToolkit.Cli.csproj`，不要对 `vendor/docx-toolkit/scripts/dotnet` 目录或 `.slnx` 文件执行隐式 restore/build。

如果 `环境检查.md` 或 `${CLAUDE_SKILL_DIR}/vendor/docx-toolkit/scripts/env_check.sh` 显示 `.NET SDK` 缺失，说明完整 DOCX OpenXML 校验环境未就绪。用户明确选择不安装并记录 `environment` 门禁后，继续生成 Markdown、TXT 和基础 DOCX，并在报告中说明当前使用兜底路径。

## 何时询问用户

以下场景必须询问并停止，等待用户输入后再继续：

- 多个项目候选目录需要选择。
- 启动环境检查发现完整 DOCX 环境缺失时，询问用户是否安装完整环境。
- 业务理解草稿生成后，请用户确认软件用途、行业、目标用户、核心功能和申请口径。
- 软件全称、著作权人、日期、硬件/系统环境等登记字段需要确认。
- 代码文件候选清单生成后，需要用户确认或修改 `代码文件选择.json`。
- 操作手册截图前，需要用户在 Chrome DevTools MCP、Codex Computer Use、用户自行截图三种方式中选择一种；选择后再检查对应工具是否可用。
- 用户是否确认 Markdown 草稿并进入 Word 生成。
