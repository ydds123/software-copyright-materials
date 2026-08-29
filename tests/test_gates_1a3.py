"""1a.3 逻辑一致性、批次结构模板化、提交就绪测试。

回归样本直接取自补正报告的真实缺陷模式：
- 章节编号跳跃（6.8 之后直接 6.10）
- 操作步骤编号从 4 开始
- 说 6 种策略只列 4 条
- X 轴与 Z 轴取值完全相同
- 两份文档目录树同构 + 重复"异常功能逻辑"小节
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import batch_structure_check as bsc  # noqa: E402
import logic_consistency_check as lcc  # noqa: E402
import submission_readiness_check as src  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class SectionNumberingTest(unittest.TestCase):
    def test_skipped_section(self):
        text = "# 手册\n\n## 6.8 异常处理\n\n内容\n\n## 6.10 部署\n\n内容\n"
        errors = lcc.check_section_numbering(text.splitlines())
        self.assertTrue(any("跳跃" in e and "6.8" in e for e in errors))

    def test_clean_numbering(self):
        text = "# 手册\n\n## 1 引言\n\n## 2 总体\n\n### 2.1 架构\n\n### 2.2 模块\n"
        errors = lcc.check_section_numbering(text.splitlines())
        self.assertEqual(errors, [])

    def test_not_starting_at_one(self):
        text = "# 手册\n\n## 4 功能清单\n\n## 5 部署\n"
        errors = lcc.check_section_numbering(text.splitlines())
        self.assertTrue(any("未从 1 开始" in e for e in errors))


class StepNumberingTest(unittest.TestCase):
    def test_steps_start_at_four(self):
        text = (
            "# 手册\n\n## 1 使用\n\n| 步骤 | 操作 |\n| --- | --- |\n"
            "| 4 | 打开页面 |\n| 5 | 点击新增 |\n| 6 | 保存 |\n"
        )
        errors = lcc.check_step_numbering(text.splitlines())
        self.assertTrue(any("从 4 开始" in e for e in errors))

    def test_steps_clean(self):
        text = (
            "# 手册\n\n| 步骤 | 操作 |\n| --- | --- |\n"
            "| 1 | 打开 |\n| 2 | 填写 |\n| 3 | 保存 |\n"
        )
        errors = lcc.check_step_numbering(text.splitlines())
        self.assertEqual(errors, [])

    def test_steps_skip(self):
        text = (
            "# 手册\n\n| 步骤 | 操作 |\n| --- | --- |\n"
            "| 1 | 打开 |\n| 2 | 填写 |\n| 4 | 保存 |\n"
        )
        errors = lcc.check_step_numbering(text.splitlines())
        self.assertTrue(any("跳跃" in e for e in errors))


class CountClaimTest(unittest.TestCase):
    def test_six_kinds_four_items_conflict(self):
        text = (
            "本系统提供 6 种任务生成策略，如下表所示，共列出 4 条策略。\n\n"
            "| 策略 | 说明 |\n| --- | --- |\n| 策略1 | A |\n| 策略2 | B |\n"
        )
        errors = lcc.check_count_claims(text)
        self.assertTrue(any("6" in e and "4" in e for e in errors))

    def test_consistent_counts_pass(self):
        text = "本系统提供 3 种查询方式，共列出 3 条说明。\n"
        errors = lcc.check_count_claims(text)
        self.assertEqual(errors, [])


class EnumOverlapTest(unittest.TestCase):
    def test_xyz_axes_identical_values(self):
        plan = {
            "fact_assertions": [
                {"fact_id": "T-001", "subject": "X轴", "type": "enum", "value": ["一级", "二级", "三级"]},
                {"fact_id": "T-002", "subject": "Z轴", "type": "enum", "value": ["一级", "二级", "三级"]},
            ]
        }
        errors = lcc.check_enum_overlap(plan)
        self.assertTrue(any("重复" in e and "T-002" in e for e in errors))

    def test_distinct_values_pass(self):
        plan = {
            "fact_assertions": [
                {"fact_id": "T-001", "subject": "X轴", "type": "enum", "value": ["一级", "二级", "三级"]},
                {"fact_id": "T-002", "subject": "Z轴", "type": "enum", "value": ["高级", "中级", "低级"]},
            ]
        }
        errors = lcc.check_enum_overlap(plan)
        self.assertEqual(errors, [])


class BatchStructureTest(unittest.TestCase):
    def _two_identical_docs(self, d: Path):
        doc = (
            "# 用户使用说明书\n\n## 1 引言\n\n## 2 功能清单\n\n"
            "## 3 巡检点管理\n\n## 3.1 异常功能逻辑\n\n## 3.2 异常功能逻辑\n\n"
            "## 3.3 异常功能逻辑\n\n"
            "| 功能 | 说明 | 操作 |\n| --- | --- | --- |\n| 查询 | 按条件 | 点击 |\n"
        )
        return _write(d / "巡检系统手册.md", doc), _write(d / "报警系统手册.md", doc)

    def test_identical_skeletons_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = self._two_identical_docs(Path(td))
            report = bsc.run([a, b])
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(any("目录同构" in e for e in report["errors"]))

    def test_repeated_section_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            doc = (
                "# 手册\n\n## 1 功能A\n\n## 1.1 异常功能逻辑\n\n## 2 功能B\n\n"
                "## 2.1 异常功能逻辑\n\n## 3 功能C\n\n## 3.1 异常功能逻辑\n"
            )
            a = _write(d / "single.md", doc)
            report = bsc.run([a])
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(any("重复小节" in e for e in report["errors"]))

    def test_distinct_docs_pass(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            a = _write(d / "a.md", "# 软件设计说明书\n\n## 1 引言\n\n## 2 总体设计\n\n## 2.1 架构\n")
            b = _write(d / "b.md", "# 用户操作手册\n\n## 1 登录\n\n## 2 首页\n\n## 2.1 待办\n")
            report = bsc.run([a, b])
            self.assertEqual(report["status"], "pass", report["errors"])


class SubmissionReadinessTest(unittest.TestCase):
    def test_missing_gates_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "门禁状态.json").write_text(
                json.dumps({"material-plan": {"confirmed": True}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (d / "草稿").mkdir(exist_ok=True)
            report = src.run(d)
            self.assertEqual(report["status"], "not-ready")
            self.assertTrue(any("必备门禁未确认" in e for e in report["errors"]))

    def test_plan_changed_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            draft = d / "草稿"
            draft.mkdir(exist_ok=True)
            plan = draft / "材料证据计划.json"
            plan.write_text("{}", encoding="utf-8")
            (d / "门禁状态.json").write_text(
                json.dumps(
                    {"material-plan": {"confirmed": True, "artifact_sha256": "oldhash"}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = src.run(d)
            self.assertTrue(any("修改" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
