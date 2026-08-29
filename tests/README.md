# 测试架构（里程碑 0）

本目录是软著 Skill 优化迭代的测试基线与匿名回归样本。**不包含任何真实项目代码、真实截图或真实申请数据**。

## 目录结构

```
tests/
├── README.md                        # 本文件
├── fixtures/
│   ├── boilerplate_case/            # 模板代码案例（按补正报告模式合成的匿名样本）
│   ├── simple_original_case/        # 简单原创案例（无复杂算法但有领域约束）
│   └── visual/defect_cases.json     # 视觉证据缺陷场景清单（不含真实图片）
├── regression/
│   └── expected_patterns.json       # 回归期望标签：每个 fixture 的预期判定
└── test_fixture_integrity.py        # 最小自检测试：fixture 完整性与标签格式
```

## 运行

```bash
cd C:/Users/rd001/.codex/skills/software-copyright-materials
python -m unittest discover -s tests -p "test_*.py" -v
```

## 约定

1. 每个 fixture 文件必须在 `regression/expected_patterns.json` 中有对应条目，声明预期分级（A/B/C/D）、预期风险信号或预期缺陷类型。
2. 后续各里程碑（1a.1/1a.2/1a.3）的新门禁测试必须引用本目录的样本，不得在测试中内联真实项目内容。
3. 视觉缺陷样本在本阶段以 JSON 场景清单形式存在（无真实图片）；真实截图样本将在 dry-run 阶段由用户素材脱敏后补充。
4. 所有阈值（覆盖率、占比、pHash 距离）在影子统计前不得硬编码进生产逻辑。
