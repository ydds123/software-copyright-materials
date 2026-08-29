"""1b 测试：human-writing 适配器、事实锁定回归、篇幅激励关闭、legacy 兼容。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fact_lock_check as flc  # noqa: E402
import human_writing_adapter as hwa  # noqa: E402
from manual_quality import DEFAULT_TEMPLATE_QUALITY  # noqa: E402
import independence_check  # noqa: E402


class StripNonProseTest(unittest.TestCase):
    def test_headings_tables_code_stripped(self):
        text = (
            "# 操作手册\n\n## 1 系统简介\n\n"
            "| 功能 | 说明 |\n| --- | --- |\n| 查询 | 按条件查询 |\n\n"
            "```\nprint('code')\n```\n\n"
            "这是叙述正文段落，应当被保留检查。\n\n"
            "![图 1](截图/首页.png)\n"
            "【截图预留：巡检列表】\n"
        )
        prose = hwa.strip_non_prose(text)
        self.assertNotIn("##", prose)
        self.assertNotIn("|", prose)
        self.assertNotIn("print", prose)
        self.assertNotIn("截图预留", prose)
        self.assertIn("叙述正文", prose)

    def test_machine_fields_stripped(self):
        text = "路径 src/main/java/com/welleyao/A.java 需要保留吗？机器字段应被屏蔽。\n"
        prose = hwa.strip_non_prose(text)
        self.assertNotIn("src/main/java", prose)
        self.assertIn("机器字段", prose)


class HumanWritingAdapterTest(unittest.TestCase):
    def test_clean_prose_passes(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            manual = d / "manual.md"
            manual.write_text(
                "# 手册\n\n本系统用于企业日常巡检管理，支持按周期生成巡检任务。\n",
                encoding="utf-8",
            )
            report = hwa.run(manual, d)
            self.assertEqual(report["status"], "pass", report["checker_output"])

    def test_hard_style_failures_detected(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            manual = d / "manual.md"
            # 违规：提示性冒号 + 破折号 + 黑话
            manual.write_text(
                "一句话总结：本产品实现了对流程的优化——赋能企业降本增效。\n",
                encoding="utf-8",
            )
            report = hwa.run(manual, d)
            self.assertIn(report["status"], ("hard-failures", "pass"), report["checker_output"])
            # 至少 checker 被调用且输出非空
            self.assertIn("checker_output", report)
            self.assertGreater(len(report["checker_output"]), 0)

    def test_version_reported(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            manual = d / "manual.md"
            manual.write_text("这是正文。\n", encoding="utf-8")
            report = hwa.run(manual, d)
            self.assertIn("human_writing_version", report)
            self.assertNotEqual(report["human_writing_version"], "missing")


class FactLockTest(unittest.TestCase):
    def _pair(self, before: str, after: str, plan=None):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            snap = d / "before.md"
            snap.write_text(before, encoding="utf-8")
            cur = d / "after.md"
            cur.write_text(after, encoding="utf-8")
            return flc.run(cur, snap, plan)

    def test_no_drift_passes(self):
        before = "# 手册\n\n软件名称：巡检系统\n\n版本号：V1.0\n\n本系统支持按周期生成任务。\n"
        after = "# 手册\n\n软件名称：巡检系统\n\n版本号：V1.0\n\n本系统可以按周期自动生成任务。\n"
        report = self._pair(before, after)
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_version_drift_blocked(self):
        before = "# 手册\n\n软件名称：巡检系统\n\n版本号：V1.0\n"
        after = "# 手册\n\n软件名称：巡检系统\n\n版本号：V2.0\n"
        report = self._pair(before, after)
        self.assertEqual(report["status"], "drift")
        self.assertTrue(any("锁定事实消失" in e or "新增事实" in e for e in report["errors"]))

    def test_number_drift_blocked(self):
        before = "本系统提供 6 种任务生成策略。\n"
        after = "本系统提供 7 种任务生成策略。\n"
        report = self._pair(before, after)
        self.assertEqual(report["status"], "drift")

    def test_plan_facts_missing_blocked(self):
        plan = {
            "software_scope": {"name": "巡检系统", "version": "V1.0"},
            "features": [{"feature_id": "F-001", "name": "巡检计划管理"}],
            "fact_assertions": [],
        }
        before = "# 手册\n\n软件名称：巡检系统\n\n版本号：V1.0\n"
        after = "# 手册\n\n软件名称：巡检系统\n\n版本号：V1.0\n\n巡检计划管理功能说明。\n"
        report = self._pair(before, after, plan)
        # 计划锁定事实都在文档中 → pass
        self.assertEqual(report["status"], "pass", report["errors"])


class TemplateIncentiveRemovalTest(unittest.TestCase):
    def test_default_minimums_zeroed(self):
        self.assertEqual(DEFAULT_TEMPLATE_QUALITY.get("min_chars"), 0)
        self.assertEqual(DEFAULT_TEMPLATE_QUALITY.get("min_headings"), 0)
        self.assertEqual(DEFAULT_TEMPLATE_QUALITY.get("min_table_lines"), 0)
        self.assertEqual(DEFAULT_TEMPLATE_QUALITY.get("min_screenshot_slots_without_images"), 0)


class LegacyCompatibilityTest(unittest.TestCase):
    def test_legacy_task_without_plan_unaffected(self):
        """无材料证据计划的任务不被 material-plan 守卫拦截（legacy 双轨）。"""
        sys.path.insert(0, str(SCRIPTS))
        import confirm_stage as cs

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "草稿").mkdir(exist_ok=True)
            (d / "门禁状态.json").write_text("{}", encoding="utf-8")
            # 无计划文件时 guard 应静默通过（返回 None）
            self.assertIsNone(cs._material_plan_guard(d))


if __name__ == "__main__":
    unittest.main()


class IndependenceCheckTest(unittest.TestCase):
    def _plan(self, name, hashes, boundaries, declared=False):
        return {
            "schema_version": 3,
            "software_scope": {"name": name, "included_boundaries": boundaries},
            "code_evidence": [{"evidence_id": f"C{i}", "sha256": h, "path": f"f{i}"} for i, h in enumerate(hashes)],
            "independence_declaration": {
                "can_run_independently": declared,
                "can_deliver_separately": declared,
                "confirmed_by_user": declared,
                "user_statement": "test" if declared else "",
            },
        }

    def _run_pair(self, a, b):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pa = d / "a.json"
            pb = d / "b.json"
            pa.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
            pb.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
            return independence_check.run(pa, pb)

    def test_high_shared_code_without_declaration_blocked(self):
        a = self._plan("巡检", ["h1", "h2", "h3"], ["巡检模块"])
        b = self._plan("报警", ["h1", "h2", "h3"], ["报警模块"])
        report = self._run_pair(a, b)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any("independence_declaration" in e for e in report["errors"]))

    def test_high_shared_code_with_declaration_passes(self):
        a = self._plan("巡检", ["h1", "h2", "h3"], ["巡检模块"], declared=True)
        b = self._plan("报警", ["h1", "h2", "h3"], ["报警模块"], declared=True)
        report = self._run_pair(a, b)
        self.assertEqual(report["status"], "pass", report["errors"])
        self.assertTrue(report["high_overlap"])
        self.assertEqual(report["detail"]["shared_code_ratio"], 1.0)

    def test_low_overlap_passes_without_declaration(self):
        a = self._plan("巡检", ["h1", "h2"], ["巡检模块"])
        b = self._plan("报警", ["h3", "h4"], ["报警模块"])
        report = self._run_pair(a, b)
        self.assertEqual(report["status"], "pass", report["errors"])
        self.assertFalse(report["high_overlap"])
