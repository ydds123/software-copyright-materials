# -*- coding: utf-8 -*-
"""「先列表后详情表单」顺序检查测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manual_quality import list_before_detail_issues


def _modules():
    return [{"feature": "设备管理", "module_type": "registry"}]


class ListBeforeDetailTest(unittest.TestCase):
    def test_list_first_ok(self):
        text = """# 手册

### 4.1 设备管理

列表页展示设备编码、设备名称、设备状态，支持按名称模糊查询。

新增/修改界面：填写设备编码、名称、类型后保存。
"""
        self.assertEqual(list_before_detail_issues(text, _modules()), [])

    def test_detail_before_list_flagged(self):
        text = """# 手册

### 4.1 设备管理

新增/修改界面：填写设备编码、名称、类型后保存。

列表页展示设备编码、设备名称、设备状态。
"""
        issues = list_before_detail_issues(text, _modules())
        self.assertTrue(any('顺序颠倒' in i for i in issues), issues)

    def test_list_only_no_issue(self):
        text = """# 手册

### 4.1 设备管理

列表页展示设备编码，支持筛选。
"""
        self.assertEqual(list_before_detail_issues(text, _modules()), [])

    def test_detail_only_no_issue(self):
        text = """# 手册

### 4.1 设备管理

查看详情展示设备的检查项清单。
"""
        self.assertEqual(list_before_detail_issues(text, _modules()), [])


if __name__ == '__main__':
    unittest.main()
