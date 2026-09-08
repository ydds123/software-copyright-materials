# -*- coding: utf-8 -*-
"""human-writing check_prose 规则接线测试：硬禁令 error + 软形状 warning，技术文档冒号不误报。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manual_quality import human_writing_hard_issues, human_writing_soft_notes


class HumanWritingHardTest(unittest.TestCase):
    def test_pivot_sentence_flagged(self):
        issues = human_writing_hard_issues("这个功能不是简单的查询，而是完整的状态流转。")
        self.assertTrue(any("翻案" in i for i in issues), issues)

    def test_hard_jargon_flagged(self):
        issues = human_writing_hard_issues("系统赋能企业实现降本增效。")
        self.assertTrue(any("黑话" in i and "赋能" in i for i in issues), issues)

    def test_hard_stop_flagged(self):
        issues = human_writing_hard_issues("说白了，这个页面就是列表。")
        self.assertTrue(any("硬停词" in i and "说白了" in i for i in issues), issues)

    def test_road_sign_flagged(self):
        issues = human_writing_hard_issues("值得注意的是，这个模块支持离线。")
        self.assertTrue(any("路标" in i for i in issues), issues)

    def test_clean_prose_passes(self):
        issues = human_writing_hard_issues("安全管理员创建巡检点，关联设备设施，配置检查项和检查标准。")
        self.assertEqual(issues, [])

    def test_technical_colon_not_flagged(self):
        # 技术文档冒号（字段说明/表格）合法，不在 hard 检查范围
        issues = human_writing_hard_issues("列表页展示设备编码、设备名称、责任部门。")
        self.assertEqual(issues, [])


class HumanWritingSoftTest(unittest.TestCase):
    def test_nominalization_warned(self):
        notes = human_writing_soft_notes("系统进行了流程的优化。")
        self.assertTrue(any("名词化" in n for n in notes), notes)

    def test_clean_no_notes(self):
        notes = human_writing_soft_notes("管理员创建计划，系统按规则生成任务，人员执行检查。")
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
