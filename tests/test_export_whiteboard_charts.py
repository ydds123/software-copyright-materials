# -*- coding: utf-8 -*-
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_docx_from_md import _fit_image_size, resolve_manual_image
from content_quality_check import check_login_and_homepage
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
        self.assertIn("../截图/系统架构图.svg | ../截图/系统架构图.png", result)
        self.assertIn("../截图/区域管理操作流程.svg | ../截图/区域管理操作流程.png", result)
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
        self.assertIn("![系统架构图](../截图/系统架构图.png)", result)
        self.assertIn("![区域管理操作流程](../截图/区域管理操作流程.png)", result)

    def test_manual_image_resolves_from_markdown_directory(self):
        with tempfile.TemporaryDirectory() as td:
            task = Path(td)
            draft = task / "草稿"
            shots = task / "截图"
            draft.mkdir()
            shots.mkdir()
            image = shots / "系统架构图.png"
            image.write_bytes(b"png")
            self.assertEqual(resolve_manual_image(draft, "../截图/系统架构图.png"), image.resolve())

    def test_manual_image_keeps_legacy_task_root_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            task = Path(td)
            draft = task / "草稿"
            shots = task / "截图"
            draft.mkdir()
            shots.mkdir()
            image = shots / "系统架构图.png"
            image.write_bytes(b"png")
            self.assertEqual(resolve_manual_image(draft, "截图/系统架构图.png"), image.resolve())

    def test_fit_image_size_caps_height_for_tall_flowchart(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "tall.png"
            Image.new("RGB", (666, 3200), "white").save(png)
            w, h = _fit_image_size(png)
            self.assertLessEqual(round(h, 2), 8.5)
            self.assertAlmostEqual(round(w / h, 2), 0.21, places=1)

    def test_fit_image_size_uses_full_width_for_wide(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "wide.png"
            Image.new("RGB", (2400, 607), "white").save(png)
            w, h = _fit_image_size(png)
            self.assertAlmostEqual(round(w, 2), 5.8, places=1)
            self.assertAlmostEqual(round(w / h, 2), 3.95, places=1)

    def test_login_check_accepts_sibling_user_screenshot(self):
        text = "## 1 系统登录\n\n![系统登录界面](../用户截图/登录页面.png)\n"
        ok, message = check_login_and_homepage(text)
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()
