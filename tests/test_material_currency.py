# -*- coding: utf-8 -*-
"""回归防线 #1：材料-源码时效校验（防材料过期）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_material_currency import check  # noqa: E402


class MaterialCurrencyTest(unittest.TestCase):
    def _make_manifest(self, tmp: Path, files: dict[str, str]) -> dict:
        for rel, content in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
        items = []
        for rel, content in files.items():
            lines = content.splitlines()
            items.append({
                'path': rel,
                'source_line_count': len(lines),
                'selected_line_start': 1,
                'selected_line_end': len(lines),
            })
        return {'project_root': str(tmp), 'file_count': len(items), 'files': items}

    def test_all_current(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manifest = self._make_manifest(tmp, {'a.vue': 'line1\nline2\n', 'b.ts': 'x\n'})
            changed, errors = check(manifest)
            self.assertEqual(errors, [])
            self.assertEqual(changed, [])

    def test_detects_modified_source(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manifest = self._make_manifest(tmp, {'a.vue': 'line1\nline2\n', 'b.ts': 'x\n'})
            # 抽取后源码被改：b.ts 增加 3 行
            (tmp / 'b.ts').write_text('x\ny\nz\nw\n', encoding='utf-8')
            changed, errors = check(manifest)
            self.assertEqual(errors, [])
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0]['path'], 'b.ts')
            self.assertEqual(changed[0]['recorded_lines'], 1)
            self.assertEqual(changed[0]['current_lines'], 4)

    def test_detects_missing_source(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manifest = self._make_manifest(tmp, {'a.vue': 'line1\n'})
            (tmp / 'a.vue').unlink()
            changed, errors = check(manifest)
            self.assertEqual(len(errors), 1)
            self.assertIn('源文件不存在', errors[0])


if __name__ == '__main__':
    unittest.main()
