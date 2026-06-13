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

1. 初始化任务并检查生成环境
2. 定位并分析真实项目
3. 形成业务理解，等待用户确认
4. 生成操作手册，按需嵌入技术图表，质检并确认
5. 选择并确认代码文件
6. 提取代码并生成申请表草稿
7. 补全并确认申请表字段
8. 选择截图方式并整理或保留截图预留
9. 确认全部 Markdown 草稿
10. 生成正式资料并执行验证

## 输出结构

每个任务的主要输出位于：

```text
<项目>/<年份>年软件著作权申请资料/<软件全称>/
├── analysis/
├── 草稿/
├── 截图/
├── 用户截图/
└── 正式资料/
```

正式资料通常包括：

```text
正式资料/
├── 申请表信息.md
├── <软件全称>_程序鉴别材料.docx
└── <软件全称>_文档鉴别材料.docx
```

## 仓库结构

```text
.
├── SKILL.md                 # Skill 工作流与执行规则
├── agents/openai.yaml       # Agent 配置
├── scripts/                 # 分析、生成、门禁和校验脚本
├── references/
│   ├── manual_workflow.md       # 操作手册阶段唯一流程入口
│   ├── manual_authoring_spec.md # 操作手册正文构建规范
│   ├── manual_quality_spec.md   # 操作手册质量审查规范
│   └── ...                      # 其他阶段的活跃规则与条件参考
└── vendor/docx-toolkit/     # 内置 DOCX 生成与校验工具
```

## 注意事项

- 生成材料不能替代软件著作权登记机构的正式审查。
- 正式提交前，请人工核对软件名称、版本号、著作权人、日期和运行环境。
- 若跳过截图，操作手册会保留截图预留位置，但可能需要在提交前补充。
- 不同登记场景的材料要求可能变化，请以办理时的官方要求为准。
