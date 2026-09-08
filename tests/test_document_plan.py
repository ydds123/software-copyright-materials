# -*- coding: utf-8 -*-
"""v1.6 document-material generalization: document plan / style rules / batch structure / screenshot plan / algorithm material."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from batch_structure_check import run as batch_run
from manual_quality import manual_quality_issues
from propose_document_plan import decide, algo_signal_count
from propose_screenshot_plan import module_shots
from propose_algorithm_sections import scan

def _mk_plan(algo_files):
    return {"code_evidence": [
        {"selected": True, "grade": "A", "path": p, "line_range": [1, 10]}
        for p in algo_files
    ] + [
        {"selected": True, "grade": "B", "path": "src/views/a/index.vue"},
    ]}

def _mk_business(biz=0, registry=4):
    return {"manual_modules": [
        {"title": f"模块{i}", "module_type": "business" if i < biz else "registry"}
        for i in range(biz + registry)
    ]}


class DocumentPlanTest(unittest.TestCase):
    def test_algo_heavy_no_biz_picks_design(self):
        plan = _mk_plan(["x/strategy/A.java", "x/chain/B.java", "x/engine/C.java"])
        t, reason, sections = decide(plan, _mk_business(biz=0), set())
        self.assertEqual(t, "design_description")
        self.assertIn("算法密集", reason)

    def test_algo_heavy_with_biz_picks_hybrid(self):
        plan = _mk_plan(["x/strategy/A.java", "x/chain/B.java", "x/engine/C.java"])
        t, _, _ = decide(plan, _mk_business(biz=4), set())
        self.assertEqual(t, "hybrid")

    def test_batch_clash_downgrades_to_user_manual(self):
        plan = _mk_plan(["x/strategy/A.java", "x/engine/B.java", "x/matrix/C.java"])
        t, reason, _ = decide(plan, _mk_business(biz=4), {"hybrid", "design_description"})
        self.assertEqual(t, "user_manual")
        self.assertIn("差异化", reason)

    def test_operational_picks_user_manual(self):
        plan = _mk_plan(["src/views/a/index.vue"])
        t, _, _ = decide(plan, _mk_business(biz=1), set())
        self.assertEqual(t, "user_manual")

    def test_algo_signal_count_only_selected_a(self):
        plan = {"code_evidence": [
            {"selected": True, "grade": "A", "path": "x/strategy/A.java"},
            {"selected": False, "grade": "A", "path": "x/engine/B.java"},
            {"selected": True, "grade": "C", "path": "x/chain/C.java"},
        ]}
        self.assertEqual(algo_signal_count(plan), 1)


class StyleRuleTest(unittest.TestCase):
    def test_dash_density_flagged(self):
        text = "# 手册\n\n" + "流程——完成——进入——下一步——确认——处理——结束——" * 40
        issues = manual_quality_issues(text, [], None, None)
        self.assertTrue(any("破折号密度" in i for i in issues), issues)

    def test_dash_density_ok_when_sparse(self):
        text = "# 手册\n\n" + "这是一个正常的操作说明段落。" * 50
        issues = manual_quality_issues(text, [], None, None)
        self.assertFalse(any("破折号密度" in i for i in issues), issues)

    def test_repeated_section_flagged(self):
        text = "\n\n".join(
            ["# 手册", "## 功能操作", "### 异常功能逻辑", "## 其他", "### 异常功能逻辑", "## 更多", "### 异常功能逻辑"]
        )
        issues = manual_quality_issues(text, [], None, None)
        self.assertTrue(any("重复小节「异常功能逻辑」" in i for i in issues), issues)


class BatchStructureTest(unittest.TestCase):
    def test_same_name_manuals_not_overwritten(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "taskA" / "草稿").mkdir(parents=True)
            (root / "taskB" / "草稿").mkdir(parents=True)
            a = root / "taskA" / "草稿" / "操作手册.md"
            b = root / "taskB" / "草稿" / "操作手册.md"
            a.write_text("# 手册\n\n## 1 系统简介\n\n## 2 系统概述\n\n## 3 功能清单\n", encoding="utf-8")
            b.write_text("# 手册\n\n## 1 系统简介\n\n## 2 系统概述\n\n## 3 功能清单\n", encoding="utf-8")
            rep = batch_run([a, b], batch_id="t")
            # v2 决策④：相同骨架 = 高风险提示（不硬阻断），且两份同名文档都被计入
            self.assertEqual(rep["status"], "risk")
            self.assertEqual(len(rep["documents"]), 2)
            self.assertTrue(any(r["level"] == "high" for r in rep["risks"]), rep["risks"])


class ScreenshotPlanTest(unittest.TestCase):
    def test_business_module_gets_3_shots(self):
        shots = module_shots({"title": "隐患治理", "module_type": "business"})
        self.assertEqual(len(shots), 3)
        self.assertIn("隐患治理", shots[0])

    def test_registry_gets_2_shots(self):
        self.assertEqual(len(module_shots({"title": "字典维护", "module_type": "registry"})), 2)

    def test_screen_gets_2_shots(self):
        self.assertEqual(len(module_shots({"title": "大屏", "module_type": "screen"})), 2)


class AlgorithmMaterialTest(unittest.TestCase):
    def test_vue_assignments_not_methods(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.java"
            p.write_text("public class A {\n  public void real(String x) {\n  }\n  const y = computed(() => 1);\n}\n", encoding="utf-8")
            d = scan(p)
            self.assertEqual([m[1] for m in d["methods"]], ["real"])


if __name__ == "__main__":
    unittest.main()
