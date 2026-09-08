# -*- coding: utf-8 -*-
"""批次2 回归：死代码清理 + D 级占比可配置阻断（含台账反例）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from extract_code_material import clean_dead_code  # noqa: E402
import evidence_plan_check as epc  # noqa: E402


class DeadCodeCleanTest(unittest.TestCase):
    def test_removes_block_comment_code(self):
        lines = [
            'const a = 1;',
            '/* 注释掉的旧逻辑',
            'const old = compute();',
            '*/',
            'const b = 2;',
        ]
        out, removed = clean_dead_code(lines)
        self.assertEqual(out, ['const a = 1;', 'const b = 2;'])
        self.assertEqual(removed, 3)

    def test_removes_commented_code_lines_and_console(self):
        lines = [
            '// const dead = calculate();',
            'console.log("res", res.data)',
            'const live = 1;',
            '// 这是普通业务注释，保留',
        ]
        out, removed = clean_dead_code(lines)
        self.assertEqual(out, ['const live = 1;', '// 这是普通业务注释，保留'])
        self.assertEqual(removed, 2)

    def test_keeps_normal_code(self):
        lines = ['// 获取列表', 'const x = getList();']
        out, removed = clean_dead_code(lines)
        self.assertEqual(removed, 0)
        self.assertEqual(len(out), 2)


class DGradeBlockTest(unittest.TestCase):
    def _plan(self, grades: list[str], d_ratio_block: bool = False):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            ce = [
                {
                    'evidence_id': f'C-{i:03d}', 'root_id': 'primary', 'path': f'f{i}.java',
                    'line_count': 100, 'sha256': '', 'grade': g,
                    'author_declaration': {'found_author_tags': [], 'categories': [],
                                           'resolution': 'keep', 'resolution_basis': ''},
                    'selected': True, 'source_kind': 'first_party',
                }
                for i, g in enumerate(grades, 1)
            ]
            plan = {
                'schema_version': 3,
                'features': [{'feature_id': 'F-001', 'name': '台账模块', 'importance': 'core',
                              'code_evidence': [c['evidence_id'] for c in ce]}],
                'code_evidence': ce,
            }
            p = d / '计划.json'
            p.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
            errors, warnings, _ = epc.check_plan(p, block_d_grade=d_ratio_block)
            return errors, warnings

    def test_ledger_style_not_blocked(self):
        # 台账型：D 级 30% + B 级 70%（有真实业务逻辑）→ 不应阻断（反例，防误杀）
        errors, warnings = self._plan(['D', 'D', 'D', 'B', 'B', 'B', 'B', 'B', 'B', 'B'], d_ratio_block=True)
        d_grade_msgs = [e for e in errors if 'D 级' in e]
        self.assertEqual(d_grade_msgs, [])

    def test_d_grade_majority_blocked_when_switch_on(self):
        errors, warnings = self._plan(['D'] * 7 + ['B'] * 3, d_ratio_block=True)
        self.assertTrue(any('D 级' in e for e in errors))

    def test_d_grade_majority_warns_when_off(self):
        errors, warnings = self._plan(['D'] * 7 + ['B'] * 3, d_ratio_block=False)
        self.assertTrue(any('D 级' in w for w in warnings))
        self.assertFalse(any('D 级' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
