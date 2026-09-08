# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from export_whiteboard_charts import parse_chart_rows, update_chart_list, update_manual_references


SAMPLE = """## 总图
| # | 图表名称 | 画板链接 | 本地文件 |
|---|---|---|---|
| 1 | 系统架构图 | https://my.feishu.cn/whiteboard/TokenA123 | 截图/系统架构图.jpg |

## 分图
| # | 图表名称 | 对应模块 | 画板链接 | 本地文件 |
|---|---|---|---|---|
| 2 | 区域管理操作流程 | area | https://my.feishu.cn/whiteboard/TokenB456 | 截图/区域管理操作流程.jpg |
"""


class ExportWhiteboardChartsTest(unittest.TestCase):
    def test_parse_chart_rows(self):
        charts = parse_chart_rows(SAMPLE)
        self.assertEqual([(c.name, c.token) for c in charts], [
            ("系统架构图", "TokenA123"),
            ("区域管理操作流程", "TokenB456"),
        ])

    def test_update_chart_list_records_svg_and_png(self):
        charts = parse_chart_rows(SAMPLE)
        result = update_chart_list(SAMPLE, charts)
        self.assertIn("SVG源文件", result)
        self.assertIn("Word图片", result)
        self.assertIn("截图/系统架构图.svg | 截图/系统架构图.png", result)
        self.assertIn("截图/区域管理操作流程.svg | 截图/区域管理操作流程.png", result)
        self.assertNotIn("系统架构图.jpg", result)

    def test_update_chart_list_is_idempotent(self):
        charts = parse_chart_rows(SAMPLE)
        once = update_chart_list(SAMPLE, charts)
        twice = update_chart_list(once, charts)
        self.assertEqual(once, twice)

    def test_update_manual_references_uses_word_png(self):
        charts = parse_chart_rows(SAMPLE)
        manual = "![系统架构图](截图/系统架构图-自适应-白底-2400.png)\n![区域管理操作流程](截图/区域管理操作流程.jpg)\n"
        result = update_manual_references(manual, charts)
        self.assertIn("![系统架构图](截图/系统架构图.png)", result)
        self.assertIn("![区域管理操作流程](截图/区域管理操作流程.png)", result)


if __name__ == "__main__":
    unittest.main()
