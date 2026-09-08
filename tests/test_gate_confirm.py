# -*- coding: utf-8 -*-
"""回归防线 #3/#4：code-selection 门禁的覆盖硬阻断与标注合规校验。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import confirm_stage  # noqa: E402


def make_workdir(files: list[dict], modules: list[dict], coverage_notes: str = '') -> str:
    tmp = tempfile.mkdtemp(prefix='gate_test_')
    wd = Path(tmp)
    (wd / '草稿').mkdir()
    sel = {
        'selection_required': True,
        'model_selection_required': True,
        'user_confirmed': False,
        'coverage_notes': coverage_notes,
        'files': files,
    }
    (wd / '草稿' / '代码文件选择.json').write_text(
        json.dumps(sel, ensure_ascii=False), encoding='utf-8')
    (wd / '草稿' / '业务理解.json').write_text(
        json.dumps({'manual_modules': modules}, ensure_ascii=False), encoding='utf-8')
    return tmp


def base_file(path: str, tier: str = 'evidence', reason: str = '核心页面代码') -> dict:
    return {
        'path': path, 'selected': True, 'line_count': 100,
        'selection_tier': tier, 'evidence': 'x', 'model_reason': reason,
    }


class GateHardBlockTest(unittest.TestCase):
    def test_weak_module_without_notes_blocks(self):
        tmp = make_workdir(
            files=[base_file('src/views/a/index.vue')],
            modules=[
                {'title': '模块A', 'evidence': ['src/views/a/index.vue']},
                {'title': '模块B', 'evidence': ['src/views/b/index.vue']},
            ],
        )
        with self.assertRaises(SystemExit) as ctx:
            confirm_stage.confirm_code_selection(Path(tmp), '测试')
        self.assertIn('无代码覆盖', str(ctx.exception))

    def test_weak_module_with_notes_passes(self):
        tmp = make_workdir(
            files=[base_file('src/views/a/index.vue')],
            modules=[
                {'title': '模块A', 'evidence': ['src/views/a/index.vue']},
                {'title': '模块B', 'evidence': ['src/views/b/index.vue']},
            ],
            coverage_notes='模块B的evidence文件在候选池中不存在，已确认该模块不单独申报代码',
        )
        path = confirm_stage.confirm_code_selection(Path(tmp), '测试')
        self.assertTrue((Path(tmp) / '门禁状态.json').exists())

    def test_evidence_labeling_fraud_blocks(self):
        # 文件不在任何模块 evidence 里，却标注 tier=evidence → 阻断
        tmp = make_workdir(
            files=[base_file('src/views/other/index.vue', tier='evidence', reason='核心页面代码')],
            modules=[{'title': '模块A', 'evidence': ['src/views/a/index.vue']}],
            coverage_notes='模块A证据不存在，说明原因',
        )
        with self.assertRaises(SystemExit) as ctx:
            confirm_stage.confirm_code_selection(Path(tmp), '测试')
        self.assertIn('标注与业务理解 evidence 不一致', str(ctx.exception))

    def test_supplement_labeling_passes(self):
        # 补充文件正确标注 supplement + 「补充」前缀理由 → 通过
        tmp = make_workdir(
            files=[
                base_file('src/views/a/index.vue'),
                base_file('src/views/other/index.vue', tier='supplement', reason='补充——不属特定模块：入口文件'),
            ],
            modules=[{'title': '模块A', 'evidence': ['src/views/a/index.vue']}],
        )
        path = confirm_stage.confirm_code_selection(Path(tmp), '测试')
        self.assertTrue((Path(tmp) / '门禁状态.json').exists())


if __name__ == '__main__':
    unittest.main()
