# -*- coding: utf-8 -*-
"""verify_doc_material_coverage 门禁测试：核心缺口阻断、支撑缺口警告、反向弱信号。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_doc_material_coverage import run, match_in_material


def _mk_business(tmp: Path, modules):
    biz = {"manual_modules": modules}
    p = tmp / "业务理解.json"
    p.write_text(json.dumps(biz, ensure_ascii=False), encoding="utf-8")
    return p


def _mk_plan(tmp: Path, features, evidence):
    plan = {"features": features, "code_evidence": evidence}
    p = tmp / "材料证据计划.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return p


def _mk_manifest(tmp: Path, paths):
    man = {"files": [{"path": p, "material_line_start": 1} for p in paths]}
    p = tmp / "代码提取清单.json"
    p.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return p


def _mk_manual(tmp: Path, text):
    p = tmp / "操作手册.md"
    p.write_text(text, encoding="utf-8")
    return p


class CoverageGateTest(unittest.TestCase):
    def test_core_module_missing_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            biz = _mk_business(tmp, [
                {"title": "巡检点管理", "module_type": "hybrid",
                 "evidence": ["E:/proj/src/views/inspection/checkpoint/index.vue"]},
                {"title": "隐患治理", "module_type": "business",
                 "evidence": ["E:/proj/src/views/hazard/index.vue"]},
            ])
            plan = _mk_plan(tmp,
                [{"feature_id": "F-001", "name": "巡检点管理", "importance": "core",
                  "code_evidence": ["C-1"]},
                 {"feature_id": "F-002", "name": "隐患治理", "importance": "core",
                  "code_evidence": ["C-2"]}],
                [{"evidence_id": "C-1", "path": "src/views/inspection/checkpoint/index.vue",
                  "mapped_features": ["F-001"]},
                 {"evidence_id": "C-2", "path": "src/views/hazard/index.vue",
                  "mapped_features": ["F-002"]}])
            man = _mk_manifest(tmp, ["src/views/inspection/checkpoint/index.vue"])
            manual = _mk_manual(tmp, "# 手册\n\n巡检点管理\n\n隐患治理\n")
            rep = run(biz, plan, man, manual)
            self.assertEqual(rep["status"], "blocked")
            self.assertTrue(any("隐患治理" in e for e in rep["errors"]), rep["errors"])

    def test_support_module_missing_only_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            biz = _mk_business(tmp, [
                {"title": "设备管理", "module_type": "registry",
                 "evidence": ["E:/proj/src/views/facility/index.vue"]},
            ])
            plan = _mk_plan(tmp,
                [{"feature_id": "F-007", "name": "设备管理", "importance": "support",
                  "code_evidence": ["C-7"]}],
                [{"evidence_id": "C-7", "path": "src/views/facility/index.vue",
                  "mapped_features": ["F-007"]}])
            man = _mk_manifest(tmp, ["src/views/other/index.vue"])
            manual = _mk_manual(tmp, "# 手册\n\n设备管理\n")
            rep = run(biz, plan, man, manual)
            self.assertEqual(rep["status"], "pass")
            self.assertTrue(any("设备管理" in w for w in rep["warnings"]), rep["warnings"])

    def test_reverse_feature_not_in_manual_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            biz = _mk_business(tmp, [])
            plan = _mk_plan(tmp,
                [{"feature_id": "F-001", "name": "巡检点管理", "importance": "core",
                  "code_evidence": ["C-1"]}],
                [{"evidence_id": "C-1", "path": "src/views/checkpoint/index.vue",
                  "mapped_features": ["F-001"]}])
            man = _mk_manifest(tmp, ["src/views/checkpoint/index.vue"])
            manual = _mk_manual(tmp, "# 手册\n\n只有其他内容\n")
            rep = run(biz, plan, man, manual)
            self.assertEqual(rep["counts"]["reverse_ok"], 0)
            self.assertTrue(any("巡检点管理" in w for w in rep["warnings"]), rep["warnings"])

    def test_match_absolute_relative(self):
        self.assertTrue(match_in_material(
            "E:/proj/src/views/inspection/checkpoint/index.vue",
            ["src/views/inspection/checkpoint/index.vue"]))
        self.assertFalse(match_in_material(
            "E:/proj/src/views/other/index.vue",
            ["src/views/inspection/checkpoint/index.vue"]))

    def test_invalid_input(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rep = run(tmp / "x.json", tmp / "y.json", tmp / "z.json", tmp / "m.md")
            self.assertEqual(rep["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
