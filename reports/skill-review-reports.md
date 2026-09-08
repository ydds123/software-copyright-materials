# yao-meta-skill 对 software-copyright-materials 的质量评估报告

- 评估对象：`C:\Users\rd001\.agents\skills\software-copyright-materials`（v1.3，实际指向 `.codex\skills\` 的符号链接）
- 评估工具：`C:\Users\rd001\.claude\skills\yao-meta-skill`（skill 工程评估体系）
- 评估日期：2026-09-01
- 输出产物：`E:\HSE\tmp\ruanzhu-review\{conformance_generic,trust_check}.{json,md}`

## 一、自动化检查结果

| 检查 | 结果 | 关键发现 |
| --- | --- | --- |
| lint_skill.py | ✅ ok | 1 警告：SKILL.md 过长，建议内容移入 references/ |
| validate_skill.py | ❌ fail | **缺 `agents/interface.yaml`** |
| run_conformance_suite.py (generic) | ❌ fail (0/24 通过) | 缺 manifest（name/version/owner/status/maturity_tier/review_cadence）、缺 interface（display_name/short_description/default_prompt）、缺 Skill IR、缺 activation mode / execution context / execution shell / trust source tier / degradation note |
| trust_check.py | ❌ fail (1) | `remote_inline_execution` 未声明 forbid；无依赖/lock 文件；7 个内部模块缺 SCRIPT_INTERFACE 声明；**file_write / subprocess 权限未经审批**（无 security/permission_policy.json）；安全面良好：0 密钥泄露、网络脚本极少（仅 github clone 安装脚本 + deepseek API 调用） |
| governance_check.py | ⚠️ **20/100** | 评级 **draft**（最低档）；metadata_integrity=0、ownership_and_review=0、boundary_and_eval=5、operational_assets=10、maintenance_evidence=5 |
| resource_boundary_check.py | ❌ fail | **初始加载 10019 tokens > 1000 预算**（SKILL.md 约 9993 tokens）；延迟资源 130224 tokens > 120000 阈值（scripts/ 114K tokens）；quality_density=3.5 |

## 二、QA Ladder 对照

| 级别 | 适用条件 | 达标情况 |
| --- | --- | --- |
| Basic（disposable/exploratory） | 一次性、低风险 | ✅ 结构合理、命名一致、边界清晰 |
| Standard（reused） | 复用、references/scripts 可能漂移 | ❌ validate_skill 不过（缺 interface.yaml）、资源边界 FAIL、无 trigger 回归 |
| Advanced（shared infrastructure） | 打包/路由错误代价高、需要长期健康证据 | ❌ 无治理元数据、无回归历史、无 eval 套件 |

**该 skill 的实际使用强度是 production/library 级**（多任务复用、产出申报材料、含 36 个脚本的工程），但结构停留在 scaffold 级。

## 三、定性评估（结合本会话完整通读 + 实战）

### 方法论层面（真正的价值，评分体系未覆盖的部分）

| 优点 | 说明 |
| --- | --- |
| 分阶段门禁流水线 | 模型做业务判断、脚本只做证据/校验/机械生成；每 turn 一个门禁，STOP_FOR_USER 协议防越权 |
| 三层门禁防线 | confirm_stage 内置校验（模块覆盖软警告、申请表待确认检查、markdown 冷静期）→ gate_check 前置链 → PreToolUse hook 拦截 |
| 证据可追溯 | 代码提取清单记录每文件行段、`// File:` 标记、material_line_start/end 全链路可回溯 |
| 安全写机制 | safe_write 原子替换 + 防空文件覆盖 + IDE Local History 兜底 |
| 法规落地准确 | 前后各30页、每页50行、页眉软件全称+版本号+页码域，符合《计算机软件著作权登记办法》第十条 |

### 缺陷（yao-meta 体系的标准分类）

1. **无机器可验证的防回归**：本会话实战踩的 4 个坑——材料过期（无 sha256）、propose 重跑重置 files 顺序导致前后30页核心模块被裁、补充文件标注造假、覆盖缺口带空说明过门禁——全是"没有回归测试/eval"的直接后果。skill 无 tests/ 目录，36 个脚本 0 个测试。
2. **SKILL.md 严重超重**：9993 tokens（建议 1000），1188 行；大量细则（STOP 格式、门禁卡片、图表演示流程）应下沉到 references/——违反"Keep SKILL.md lean"原则。
3. **治理元数据全缺**：无 manifest.json（无 owner、无 review_cadence、无 maturity_tier、无 lifecycle_stage）；无 agents/interface.yaml；无 Skill IR。共享给团队/多任务复用时无法判断"该信谁、多久审一次、能不能升级"。
4. **安全治理声明缺失**：15 个脚本写文件、6 个脚本跑子进程，但无 permission_policy.json 审批记录；trust 元数据（source_tier 等）为空。
5. **v1/v2 双路径并存未收敛**：legacy（代码文件选择.json，无哈希）与 v2（材料证据计划，sha256 锁定）两套逻辑同时存在，SKILL.md 与 references/code_selection_rules.md 对"是否支持行段抽取"表述互相矛盾，脚本以"检测到 schema_version==3"来分叉——分叉逻辑是隐式的，没有明确的路径选择决策表。
6. **依赖声明缺失**：python-docx、pdfplumber 等运行时依赖无声明/锁定（trust_check 的 dependency_files 为空），环境检查只查能力不查版本。

## 四、治理评分解读（20/100 = draft）

| 维度 | 得分 | 差距 |
| --- | --- | --- |
| metadata_integrity | 0 | 无 manifest.json |
| ownership_and_review | 0 | 无 owner、无 review_cadence |
| boundary_and_eval | 5 | 无 trigger 回归、无边界测试 |
| operational_assets | 10 | 有 scripts 但无治理证据 |
| maintenance_evidence | 5 | 无回归历史、无 eval 结果记录 |

## 五、结论

**一句话**：方法论一流的工程级 skill，包装和治理零分。

- 它对"软著材料生成"这个业务域的抽象（门禁、证据链、法规分页）设计水平很高，实战跑通了两个完整任务
- 但按 yao-meta-skill 的标准，它是一个 **draft 级包装的 production 级使用强度的 skill**：validate/conformance/trust/resource-boundary 四项 FAIL，治理 20 分
- 如果继续作为团队共享资产使用，应补上：manifest.json、agents/interface.yaml、SKILL.md 瘦身（细则下沉 references/）、permission_policy 审批、针对 4 个实战坑的回归测试（材料时效性、抽取顺序、标注合规、覆盖门禁硬阻断）

## 六、改进优先级建议

| 优先级 | 动作 | 解决 |
| --- | --- | --- |
| P0 | SKILL.md 瘦身（细则→references/，正文留路由+门禁卡片） | 初始加载 10K→预算内 |
| P0 | 补 manifest.json（owner/review_cadence/maturity_tier=production） | governance 20→80+ |
| P1 | 补 agents/interface.yaml + 声明 SCRIPT_INTERFACE（7 个内部模块） | validate/conformance 通过 |
| P1 | 补 security/permission_policy.json（file_write/subprocess 审批） | trust 通过 |
| P1 | 回归测试：抽取顺序不变式、材料-源码时效检查、module_coverage 硬阻断 | 防止本会话 4 个坑复发 |
| P2 | 统一 v1/v2 路径决策表（何时用哪条路径，写进 SKILL.md） | 消除双路径矛盾 |
| P2 | 依赖声明（requirements.txt 或环境检查内置版本探测） | 可复现性 |
