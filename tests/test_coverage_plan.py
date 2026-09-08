# -*- coding: utf-8 -*-
"""篇幅规划：二维矩阵配额 + business 门禁校验 + 覆盖门禁分级。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from propose_coverage_plan import quota, derive_importance
from verify_doc_material_coverage import run


class QuotaMatrixTest(unittest.TestCase):
    def test_core_ab_required(self):
        q = quota('core', 'A')
        self.assertEqual(q, {'material': '必进', 'manual': '详写', 'screenshot': '必拍'})

    def test_core_d_excluded_but_written(self):
        q = quota('core', 'D')
        self.assertEqual(q['material'], '不进')
        self.assertEqual(q['manual'], '详写')

    def test_support_ab_optional(self):
        q = quota('support', 'B')
        self.assertEqual(q['material'], '可进')
        self.assertEqual(q['manual'], '顺带')

    def test_support_cd_skip(self):
        q = quota('support', 'D')
        self.assertEqual(q['material'], '不进')

    def test_importance_business_is_core(self):
        self.assertEqual(derive_importance('隐患治理', 'business', []), 'core')

    def test_importance_registry_is_support(self):
        self.assertEqual(derive_importance('字典维护', 'registry', []), 'support')

    def test_importance_algo_signal_core(self):
        self.assertEqual(
            derive_importance('任务生成', 'registry', ['src/strategy/X.java']), 'core')


class CoveragePlanGateTest(unittest.TestCase):
    def _task(self, tmp: Path, cp_rows):
        (tmp / '草稿').mkdir(parents=True)
        biz = tmp / '草稿' / '业务理解.json'
        biz.write_text(json.dumps({'manual_modules': [
            {'title': '巡检点管理', 'module_type': 'hybrid',
             'evidence': ['E:/proj/src/views/checkpoint/index.vue']},
            {'title': '字典维护', 'module_type': 'registry',
             'evidence': ['E:/proj/src/views/dict/index.vue']},
        ]}, ensure_ascii=False), encoding='utf-8')
        cp = tmp / '草稿' / '篇幅规划.json'
        cp.write_text(json.dumps({'modules': cp_rows}, ensure_ascii=False), encoding='utf-8')
        plan = tmp / '草稿' / '材料证据计划.json'
        plan.write_text(json.dumps({'features': [], 'code_evidence': []}, ensure_ascii=False), encoding='utf-8')
        man = tmp / '草稿' / '代码提取清单.json'
        man.write_text(json.dumps({'files': [
            {'path': 'src/views/checkpoint/index.vue', 'material_line_start': 1},
        ]}, ensure_ascii=False), encoding='utf-8')
        manual = tmp / '草稿' / '操作手册.md'
        manual.write_text('# 手册\n\n巡检点管理\n\n' + '内容' * 100, encoding='utf-8')
        return biz, plan, man, manual

    def test_required_module_missing_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            biz, plan, man, manual = self._task(Path(td), [
                {'module': '巡检点管理', 'importance': 'core', 'material': '必进', 'manual': '详写'},
                {'module': '字典维护', 'importance': 'support', 'material': '不进', 'manual': '顺带'},
            ])
            # 字典维护 evidence 不在材料且 quota=不进 → 跳过；巡检点管理在材料 ✓
            rep = run(biz, plan, man, manual)
            self.assertEqual(rep['status'], 'pass', rep['errors'])

    def test_optional_module_missing_is_warning(self):
        with tempfile.TemporaryDirectory() as td:
            biz, plan, man, manual = self._task(Path(td), [
                {'module': '巡检点管理', 'importance': 'core', 'material': '必进', 'manual': '详写'},
                {'module': '字典维护', 'importance': 'support', 'material': '可进', 'manual': '顺带'},
            ])
            rep = run(biz, plan, man, manual)
            self.assertEqual(rep['status'], 'pass')
            self.assertTrue(any('字典维护' in w for w in rep['warnings']), rep['warnings'])

    def test_detailed_module_thin_manual_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            biz, plan, man, manual = self._task(Path(td), [
                {'module': '巡检点管理', 'importance': 'core', 'material': '必进', 'manual': '详写'},
                {'module': '字典维护', 'importance': 'support', 'material': '不进', 'manual': '顺带'},
            ])
            # 手册中「巡检点管理」内容过薄（<200 字）
            manual.write_text('# 手册\n\n巡检点管理。\n', encoding='utf-8')
            rep = run(biz, plan, man, manual)
            self.assertTrue(any('内容过薄' in e for e in rep['errors']), rep['errors'])


if __name__ == '__main__':
    unittest.main()
