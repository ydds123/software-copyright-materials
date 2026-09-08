# -*- coding: utf-8 -*-
"""回归防线 #2：前后30页模块覆盖校验（防抽取顺序重置裁掉核心模块）。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_coverage_in_pages import check_marker as check  # noqa: E402
from verify_coverage_in_pages import check_with_manifest  # noqa: E402


def make_manifest(files: dict[str, tuple[int, int]], total: int) -> dict:
    """files: {path: (material_start, material_end)}; total = material_line_count."""
    return {
        'material_line_count': total,
        'files': [
            {'path': p, 'material_line_start': s, 'material_line_end': e}
            for p, (s, e) in files.items()
        ],
    }


class ManifestCoverageTest(unittest.TestCase):
    def test_all_inside_front30(self):
        # 总 4825 行 97 页 → front=[1,1500], back=[3351,4825]
        mf = make_manifest({'src/views/a/index.vue': (1, 703)}, 4825)
        biz = {'manual_modules': [{'title': '模块A', 'evidence': ['src/views/a/index.vue']}]}
        ok, problems = check_with_manifest(biz, mf, min_lines=20)
        self.assertEqual(problems, [])
        self.assertIn('703', ok[0])

    def test_cut_at_back_boundary_detected(self):
        # 文件 A 横跨 back 边界露出 100 行 → OK；文件 B 全在 middle → GAP
        mf = make_manifest({
            'src/views/a/index.vue': (3251, 3950),   # back 内 600 行
            'src/views/b/index.vue': (2000, 2500),   # 全 middle
        }, 4825)
        biz = {'manual_modules': [
            {'title': '模块A', 'evidence': ['src/views/a/index.vue']},
            {'title': '模块B', 'evidence': ['src/views/b/index.vue']},
        ]}
        ok, problems = check_with_manifest(biz, mf, min_lines=20)
        self.assertEqual(len(problems), 1)
        self.assertIn('模块B', problems[0])
        self.assertTrue(any('模块A' in o for o in ok))


def material_text(files: dict[str, str]) -> str:
    out = ['# 代码材料（前30页）', '', '软件名称：测试', '版本号：V1.0', '']
    for path, content in files.items():
        out.append(f'// File: {path}')
        out.extend(content.split('\n'))
        out.append('')
    return '\n'.join(out)


class CoverageInPagesTest(unittest.TestCase):
    def _business(self, modules: list[dict]) -> dict:
        return {'manual_modules': modules}

    def test_all_covered(self):
        text = material_text({
            'src/views/a/index.vue': 'x\n' * 30,
            'src/api/a/index.ts': 'y\n' * 25,
        })
        biz = self._business([{'title': '模块A', 'evidence': ['src/views/a/index.vue']}])
        ok, problems = check(text, biz, min_lines=20)
        self.assertEqual(problems, [])
        self.assertTrue(ok)

    def test_module_cut_out(self):
        # 材料只包含文件 b（模块 A 的 evidence 被裁出前30/后30页）
        text = material_text({'src/views/b/index.vue': 'z\n' * 40})
        biz = self._business([{'title': '模块A', 'evidence': ['src/views/a/index.vue']}])
        ok, problems = check(text, biz, min_lines=20)
        self.assertEqual(len(problems), 1)
        self.assertIn('模块A', problems[0])
        self.assertIn('不在材料页内', problems[0])

    def test_module_too_short(self):
        # TaskCheckNewAct 只露 10 行的场景
        text = material_text({'src/app/task.kt': 'k\n' * 10})
        biz = self._business([{'title': 'App执行', 'evidence': ['src/app/task.kt']}])
        ok, problems = check(text, biz, min_lines=20)
        self.assertEqual(len(problems), 1)
        self.assertIn('出现过少', problems[0])


if __name__ == '__main__':
    unittest.main()
