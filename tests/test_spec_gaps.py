# -*- coding: utf-8 -*-
"""Q-I05 章节职责互斥 + Q-T02 操作路径端点一致性 测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manual_quality import section_duplication_issues, operation_path_issues

DUP_TEXT = """# 手册

### 6.6 异常上报管理

这是第一处说明段落，描述了不合格项从 App 端上报到 Web 端查看的完整链路。

| 操作步骤 | 用户操作 |
| --- | --- |
| 1 | 标记不合格 |
| 2 | 进入隐患治理 |
| 3 | 制定方案 |

### 6.7 异常上报管理二

这是第一处说明段落，描述了不合格项从 App 端上报到 Web 端查看的完整链路。

| 操作步骤 | 用户操作 |
| --- | --- |
| 1 | 标记不合格 |
| 2 | 进入隐患治理 |
| 3 | 制定方案 |
"""


class SectionDuplicationTest(unittest.TestCase):
    def test_duplicated_paragraph_and_table_flagged(self):
        issues = section_duplication_issues(DUP_TEXT)
        self.assertTrue(any('相同段落' in i for i in issues), issues)
        self.assertTrue(any('相同表格行' in i for i in issues), issues)

    def test_distinct_chapters_clean(self):
        text = """# 手册

### 6.1 模块一

模块一的说明段落，内容与其他章节完全不同，讲述第一个模块的操作方式。

### 6.2 模块二

模块二的说明段落，内容与其他章节完全不同，讲述第二个模块的操作方式。
"""
        self.assertEqual(section_duplication_issues(text), [])

    def test_shared_single_table_row_not_flagged(self):
        # 表格 1 行相同不算重复（表头常见）
        text = """# 手册

### 6.1 模块一

| 字段 | 说明 |
| --- | --- |
| 名称 | 标识 |

### 6.2 模块二

| 字段 | 说明 |
| --- | --- |
| 名称 | 标识 |
| 状态 | 当前状态 |
"""
        self.assertEqual(section_duplication_issues(text), [])


class OperationPathTest(unittest.TestCase):
    def _business(self, endpoint, title="隐患治理"):
        return {"manual_modules": [{"title": title, "client_endpoint": endpoint}]}

    def test_web_module_with_app_path_flagged(self):
        text = """# 手册

### 4.1.6 隐患治理

操作路径：App首页 → 隐患治理（App端）。

隐患治理说明文字。
"""
        issues = operation_path_issues(text, self._business('web'))
        self.assertTrue(any('App 入口' in i for i in issues), issues)

    def test_app_module_with_menu_path_flagged(self):
        text = """# 手册

### 4.2 App 端巡检任务执行

操作路径：从系统菜单进入巡检任务页面。

App 说明文字。
"""
        issues = operation_path_issues(text, self._business('app', 'App 端巡检任务执行'))
        self.assertTrue(any('菜单/Web 入口' in i for i in issues), issues)

    def test_mixed_path_warns(self):
        text = """# 手册

### 4.1.6 隐患治理

操作路径：APP主页→隐患治理（APP端）；隐患排查治理→隐患上报审批（web端）。

隐患治理说明文字。
"""
        issues = operation_path_issues(text, self._business('web'))
        self.assertTrue(any('混合两端' in i for i in issues), issues)

    def test_clean_path_ok(self):
        text = """# 手册

### 4.1.6 隐患治理

操作路径：隐患排查治理 → 待处理隐患。

隐患治理说明文字。
"""
        self.assertEqual(operation_path_issues(text, self._business('web')), [])


if __name__ == '__main__':
    unittest.main()
