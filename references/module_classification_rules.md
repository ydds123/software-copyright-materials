# 模块分类规则

在填写 `manual_modules` 之前，模型必须先阅读每个模块对应的页面源码，判断其操作类型——是台账型、业务型还是混合型。不同分类对应不同的 JSON 结构模板。


## 生成链路边界

`manual_modules` 是操作手册正文的主输入。模型必须把真实页面证据整理成结构化字段，renderer 只负责排版渲染。若缺少字段，fallback 可以记录缺失位置和建议补全字段，但不应静默代替业务理解生成正式内容。

尤其要注意：

- 台账型和混合型模块应优先填写 `registry`，其中列表列、筛选项、顶部按钮、行按钮和表单分组均来自真实页面。
- 业务型和混合型模块应优先填写 `business_operation`，其中阶段、用户动作、系统反馈、结果变化和异常处理均来自真实页面或代码证据。
- 如果使用 `crud_scenarios`，每一步必须包含 `action`、`system_response` 和 `error_handling`。
- 不能只写 `operation_steps` 后依赖 fallback 推断系统响应和异常处理。

## 分类判断标准

### 台账型 — 操作对象是静态记录本身

**特征**：模块的核心操作是增删改查一条或多条数据记录，没有跨对象的状态流转。用户的每一个操作都是自足的——新增完就结束了，删除完就结束了，不触发下游业务流程。

**判断信号**（读到以下模式判定为台账型）：
- 页面主要是一个表格 + 搜索栏 + 新增/导入/导出按钮
- 表单字段逐一对应数据库列的属性配置
- 没有"下一步""提交审核""推送""下发"等跨状态操作
- 没有条件分支（不同的配置路径会导致不同的下游行为）
- 行操作主要是"修改/查看详情/删除"及其变体

**巡检系统中的台账型模块**：设备设施管理、二维码管理、NFC标签管理、工作日历管理、签到与巡检配置。

### 业务型 — 操作对象有生命周期或操作链路

**特征**：模块的核心不是管理一条记录，而是驱动一个业务流程——配置规则→生成任务→执行→结果→异常处理。用户操作之间存在严格的时序和条件依赖。

**判断信号**：
- 有显式的对象状态机（如任务状态：待认领→进行中→已完成）
- 有跨对象操作（如计划→推送→生成任务；巡检点→签到→检查项→完成）
- 有条件分支（不同配置路径激活不同的下游表单区域）
- 有物理/环境约束（NFC感应、GPS定位、拍照取证）
- 操作不能回退或回退有特定规则

**巡检系统中的业务型模块**：巡检计划管理、巡检任务管理(Web端)、Android巡检任务查看与认领、Android巡检点列表与签到、Android检查项执行、Android异常管理。

### 混合型 — 台账面 + 业务配置面

**特征**：模块有台账面（列表/搜索/导入导出），但核心价值不在台账——在创建或编辑时有一个复杂的配置链，不同配置路径激活完全不同的下游表单区域，最终产出的是一个"巡检方案"而非一条数据记录。

**判断信号**：
- 列表页是标准台账，但创建/编辑表单远超普通表单的复杂度（30+字段/多tab/条件显隐）
- 表单中有影响全局行为的开关（如双重预防机制开关、包保任务开关）
- 表单中引用了多个其他台账模块的数据（NFC标签、二维码、设备、排查库、分析单元）
- 保存操作产生的副作用不只是"数据库多一条记录"，而是"巡检方案配置生效"

**巡检系统中的混合型模块**：巡检点管理。

## 各分类的 JSON 结构

### 台账型模块结构

台账型沿用并强化原有的 `crud_scenarios` 结构。模型必须逐操作模式完整填写：

```json
{
  "title": "模块名称",
  "module_type": "registry",
  "evidence": ["页面文件路径"],
  "purpose": "该台账在软件中的用途。",
  "usage": "什么场景下使用。",
  "entry": "从哪里进入。",
  "registry": {
    "list": {
      "columns": ["逐列列出表格中所有列名"],
      "filters": ["逐项列出所有搜索条件"],
      "top_actions": ["逐项列出表格上方按钮"],
      "row_actions": ["逐项列出每行操作按钮"]
    },
    "create": {
      "form_sections": [
        {
          "section_name": "基本信息",
          "fields": ["字段1", "字段2", "..."]
        },
        {
          "section_name": "维保信息(如有)",
          "conditional_on": "是否定期维保=是",
          "fields": ["维保周期", "维保有效期起止", "维保内容"]
        }
      ],
      "rules": ["逐条列出必填项、格式校验、唯一性约束"]
    },
    "edit": {
      "same_as_create_plus": ["只读字段列表(如编码不可修改但显示)"]
    },
    "detail": {
      "info_sections": ["基本信息区", "维保记录区", "..."]
    },
    "import_export": {
      "supports_import": true,
      "import_template_download": true,
      "supports_export": true,
      "separate_import_for_sub_items": "设备检查项目单独导入(如有)"
    }
  },
  "screenshot": "截图预留说明"
}
```

**强制要求**：
- `columns`、`filters`、`top_actions`、`row_actions` 必须逐项枚举，不准用"等"字省略。
- 表单字段必须按实际表单分节（section）组织，条件显隐的字段放在对应的 `conditional_on` 下。
- 导入导出能力必须明确标注。

### 业务型模块结构

业务型不套用 CRUD。用 `business_operation` 描述操作链路：

```json
{
  "title": "模块名称",
  "module_type": "business",
  "evidence": ["页面文件路径", "Controller 路径(如有)"],
  "purpose": "该业务流程在软件中的用途。",
  "usage": "用户在什么业务场景下使用。",
  "entry": "从哪里进入。",
  "object_lifecycle": {
    "states": ["状态1", "状态2", "状态3", "..."]
  },
  "business_operation": {
    "entry_conditions": ["前置条件1", "前置条件2"],
    "operation_chain": [
      {
        "phase": "阶段名称(如: 配置周期规则)",
        "actor": "谁操作",
        "trigger": "触发动作(如: 点击新增计划)",
        "sub_operations": [
          {
            "name": "子步骤名称",
            "action": "用户具体操作",
            "visible_controls": ["涉及的表单控件"],
            "fork_condition": "如有分支条件则说明",
            "constraint": "限制条件",
            "outcome": "操作结果"
          }
        ],
        "conditional_branches": [
          {
            "condition": "当用户选择XXX时",
            "then": "显示/激活 哪些额外配置项",
            "else": "走哪条路径"
          }
        ]
      }
    ],
    "entry_points": {
      "list_view": "列表页可执行的操作(如: 查看巡检情况、删除)",
      "row_actions": ["每行可执行的操作"]
    }
  },
  "screenshot": "截图预留说明"
}
```

**强制要求**：
- `object_lifecycle` 必须列出该业务对象的所有状态（从代码中的状态字典或枚举获取）。
- `operation_chain` 必须按用户操作的时间顺序排列，不准跳过中间阶段。
- 有条件分支时必须在 `conditional_branches` 中说明两条路径的差异。
- `entry_conditions` 必须真实反映代码中的依赖关系（如"巡检点必须已存在"）。
- **每个 `sub_operation` 必须填写 `outcome` 和 `constraint`**。这两个字段直接渲染到操作手册的操作步骤表中（`outcome`→系统响应列、`constraint`→异常处理列）。缺失时渲染器输出 `[WARNING]` 占位符——操作手册质量自检会拦截，不能进入 markdown 确认门禁。

**Android 端业务型模块的额外要求**：
- 物理约束必须写明（NFC 感应、GPS 距离、扫码校验等）。
- 离线/在线模式差异必须说明（如支持暂存、断点续做等）。
- 移动端特有的交互必须记录（确认对话框、强制顺序、选项卡本地缓存等）。

### 混合型模块结构

先台账后业务，两段都填：

```json
{
  "title": "模块名称",
  "module_type": "hybrid",
  "evidence": ["页面文件路径"],
  "purpose": "该模块在软件中的用途。",
  "registry": {
    "list": { "columns": [...], "filters": [...], "top_actions": [...], "row_actions": [...] }
  },
  "business_operation": {
    "entry_conditions": ["前置条件"],
    "config_paths": [
      {
        "path_name": "路径名称(如: 双重预防路径)",
        "trigger": "什么开关/选择激活此路径",
        "config_chain": [
          { "step": "步骤名", "fields": [...], "references": "引用哪些模块数据" }
        ],
        "outcome": "走完此路径的结果"
      },
      {
        "path_name": "另一路径",
        "trigger": "...",
        "config_chain": [...],
        "outcome": "..."
      }
    ]
  },
  "screenshot": "截图预留说明"
}
```

**强制要求**：
- 台账面按台账型结构的 `registry` 标准填写，不准省略。
- 业务面的每条配置路径必须完整列出——双重预防路径和包保路径是不同的配置链，必须分别写。
- `references` 字段标注该配置步骤引用了哪个台账模块的数据（NFC、设备等），这是验证"配置链路"正确性的关键。

## 完整性自检

模型填写完 `manual_modules` 后，必须输出 `草稿/模块完整性自检记录.json`，逐模块记录：

```json
{
  "module": "模块名称",
  "module_type": "registry|business|hybrid",
  "source_file_lines": 1800,
  "classification": "台账型|业务型|混合型",
  "completeness": {
    "total_visible_elements_observed": 50,
    "total_steps_documented": 8,
    "has_conditional_branches": true,
    "branches_enumerated": 4,
    "all_columns_enumerated": true,
    "all_filters_enumerated": true,
    "all_row_actions_enumerated": true
  },
  "issues": [
    "条件分支数不足以覆盖代码中所有分支路径"
  ]
}
```

自检门禁规则：
- `all_columns_enumerated`、`all_filters_enumerated`、`all_row_actions_enumerated` 全部为 `true` 的模块才可以进入确认。
- `has_conditional_branches` 为 `true` 但 `branches_enumerated` 少于代码中实际分支数的，标记 WARNING。
- 任何 WARNING 在业务理解确认前必须清零或由模型明确说明原因。
