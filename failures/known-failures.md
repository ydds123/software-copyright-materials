# 已知失败模式（failures，回归历史）

| # | 失败模式 | 发现 | 防线 |
| --- | --- | --- | --- |
| 1 | 材料过期：抽取后源码变更，7 个文件落后 5~14 天（+14/+180 行）未被发现 | 2026-09-01 双任务审查 | verify_material_currency.py（#1） |
| 2 | 抽取顺序被 propose 重跑重置，TaskCheckNewAct 885 行只露 10 行、报警中心整章被裁出前30/后30页 | 2026-09-01 | verify_coverage_in_pages.py（#2） |
| 3 | 覆盖缺口带空说明通过 code-selection 门禁（"覆盖4核心模块"无原因） | 2026-09-01 | confirm_stage 覆盖硬阻断（#3） |
| 4 | 6 个非 evidence 文件标注 tier=evidence，模块-代码依赖失真 | 2026-09-01 | confirm_stage 标注合规校验（#4） |

对应测试：tests/test_material_currency.py、tests/test_coverage_in_pages.py、tests/test_gate_confirm.py。
