# -*- coding: utf-8 -*-
"""台账深度 / 角色路径 / FAQ 下限 / 测试数据证据 测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manual_quality import (
    registry_depth_issues,
    role_path_issues,
    faq_count_issues,
    test_data_evidence_issues,
)


class RegistryDepthTest(unittest.TestCase):
    def test_full_registry_passes(self):
        text = """# 手册

### 4.1 设备管理

列表页支持按名称模糊查询和按类别筛选。删除已被巡检点引用的设备时系统阻止删除。巡检点关联该设备后自动带入检查项。
"""
        issues = registry_depth_issues(text, [{"feature": "设备管理", "module_type": "registry"}])
        self.assertEqual(issues, [])

    def test_missing_depth_flagged(self):
        text = """# 手册

### 4.1 设备管理

设备管理维护全厂的设备档案。
"""
        issues = registry_depth_issues(text, [{"feature": "设备管理", "module_type": "registry"}])
        self.assertTrue(any('列表筛选条件' in i for i in issues), issues)

    def test_business_module_skipped(self):
        text = """# 手册

### 4.2 任务管理

任务由计划自动生成。
"""
        issues = registry_depth_issues(text, [{"feature": "任务管理", "module_type": "business"}])
        self.assertEqual(issues, [])


class RolePathTest(unittest.TestCase):
    def test_role_missing_in_operations_flagged(self):
        text = """# 手册

## 1 引言

读者包括部门负责人。

## 4 按角色的功能操作

### 4.1 安全管理员

安全管理员创建巡检点。
"""
        biz = {"target_users": [{"role": "安全管理员"}, {"role": "部门负责人"}]}
        issues = role_path_issues(text, biz)
        self.assertTrue(any('部门负责人' in i for i in issues), issues)

    def test_all_roles_present_ok(self):
        text = """# 手册

## 4 按角色的功能操作

### 4.1 安全管理员

安全管理员创建巡检点。

### 4.2 部门负责人

部门负责人查看完成率。
"""
        biz = {"target_users": [{"role": "安全管理员"}, {"role": "部门负责人"}]}
        self.assertEqual(role_path_issues(text, biz), [])


class FaqCountTest(unittest.TestCase):
    def test_too_few_flagged(self):
        text = """# 手册

## 5 故障排查

**问题一**

回答一。

**问题二**

回答二。
"""
        issues = faq_count_issues(text)
        self.assertTrue(any('少于 8 个' in i for i in issues), issues)

    def test_enough_ok(self):
        lines = ['# 手册', '', '## 5 故障排查', '']
        for i in range(9):
            lines += [f'**问题{i}**', '', f'回答{i}。', '']
        self.assertEqual(faq_count_issues('\n'.join(lines)), [])


class TestDataEvidenceTest(unittest.TestCase):
    def test_test_data_flagged(self):
        issues = test_data_evidence_issues('列表页展示测试数据用于演示。')
        self.assertTrue(any('测试数据' in i for i in issues), issues)

    def test_clean_ok(self):
        self.assertEqual(test_data_evidence_issues('列表页展示真实巡检记录。'), [])


if __name__ == '__main__':
    unittest.main()
