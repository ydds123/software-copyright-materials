# -*- coding: utf-8 -*-
"""check_screenshot_scatter 测试：连续截图无文字间隔检测。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from content_quality_check import check_screenshot_scatter


class ScreenshotScatterTest(unittest.TestCase):
    def test_three_stacked_flagged(self):
        lines = [
            '## 模块', '', '文字说明。', '',
            '【截图预留：列表页】',
            '【截图预留：表单页】',
            '【截图预留：结果页】',
        ]
        issues = check_screenshot_scatter(lines)
        self.assertTrue(any('连续 3 张' in i for i in issues), issues)

    def test_two_adjacent_ok(self):
        lines = [
            '## 模块', '', '文字说明。', '',
            '【截图预留：列表页】',
            '【截图预留：表单页】',
            '', '后续文字说明。',
        ]
        issues = check_screenshot_scatter(lines)
        self.assertEqual(issues, [])

    def test_scattered_ok(self):
        lines = [
            '## 模块', '', '列表说明文字。', '',
            '【截图预留：列表页】',
            '', '表单说明文字。', '',
            '【截图预留：表单页】',
            '', '结果说明文字。', '',
            '【截图预留：结果页】',
        ]
        issues = check_screenshot_scatter(lines)
        self.assertEqual(issues, [])

    def test_table_between_counts_as_no_text(self):
        # 表格行不算文字间隔：字段表后连续 3 张截图仍报
        lines = [
            '## 模块', '', '字段表如下：', '',
            '| 字段 | 规则 |', '| --- | --- |',
            '【截图预留：表单页】',
            '【截图预留：结果页】',
            '【截图预留：另一页】',
        ]
        issues = check_screenshot_scatter(lines)
        self.assertTrue(any('连续 3 张' in i for i in issues), issues)


if __name__ == '__main__':
    unittest.main()
