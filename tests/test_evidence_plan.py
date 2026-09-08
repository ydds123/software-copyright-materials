"""1a.1 证据计划与选材测试。

覆盖验收标准：
1. 署名三分法标签库命中（framework / ai_tool）
2. 等级信号启发式（CRUD 六件套 → D，责任链/动态 SQL → A）
3. evidence_plan_check 硬规则（R2 核心映射 / R3 A-B 存在 / R4 框架署名禁 replace / R5 哈希校验）
4. 行段抽取保持连续区间与原始行号
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
BOILERPLATE = FIXTURES / "boilerplate_case"

sys.path.insert(0, str(SCRIPTS))

import evidence_plan_check as epc  # noqa: E402
from evidence_plan_common import (  # noqa: E402
    classify_author,
    crud_method_hits,
    is_crud_six_piece,
    is_pure_api_wrapper,
    is_pure_pojo,
    suggest_grade,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_fixture(rel: str) -> str:
    return (BOILERPLATE / rel).read_text(encoding="utf-8")


class OwnershipLibraryTest(unittest.TestCase):
    def test_framework_authors(self):
        self.assertEqual(classify_author("Lion Li"), "framework")
        self.assertEqual(classify_author("lion li"), "framework")

    def test_ai_tool_authors(self):
        self.assertEqual(classify_author("claude"), "ai_tool")
        self.assertEqual(classify_author("Cursor"), "ai_tool")

    def test_team_member_not_classified(self):
        self.assertIsNone(classify_author("stzy"))
        self.assertIsNone(classify_author("Xin Hai Ye"))


class GradeSignalTest(unittest.TestCase):
    def test_crud_controller_is_d(self):
        text = read_fixture("backend/InsAbnormalReportController.java")
        self.assertTrue(is_crud_six_piece(text))
        grade, signals = suggest_grade(Path("InsAbnormalReportController.java"), text)
        self.assertEqual(grade, "D")
        self.assertIn("crud_six_piece", signals)

    def test_pojo_is_d(self):
        text = read_fixture("backend/MwAlarmRecord.java")
        self.assertTrue(is_pure_pojo(text))

    def test_api_wrapper_is_d(self):
        text = read_fixture("frontend/api/ticketAlarm/index.ts")
        self.assertTrue(is_pure_api_wrapper(text))

    def test_chain_handler_is_a(self):
        text = read_fixture("backend/ImmediatePushAndAssignHandler.java")
        grade, signals = suggest_grade(Path("ImmediatePushAndAssignHandler.java"), text)
        self.assertEqual(grade, "A")
        self.assertTrue(any("handler" in s or "strategy" in s for s in signals))

    def test_dynamic_sql_is_a(self):
        text = read_fixture("backend/mapper/AlarmMapper.xml")
        grade, signals = suggest_grade(Path("AlarmMapper.xml"), text)
        self.assertEqual(grade, "A")
        self.assertIn("dynamic_sql", signals)


class PlanCheckHardRulesTest(unittest.TestCase):
    def _make_plan(self, evidence, features):
        return {
            "schema_version": 3,
            "input_roots": [{"root_id": "primary", "path": str(BOILERPLATE)}],
            "software_scope": {"name": "t", "version": "v1"},
            "code_evidence": evidence,
            "features": features,
            "fact_assertions": [],
            "blockers": [],
            "warnings": [],
        }

    def _write(self, plan):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "材料证据计划.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return path

    def _evidence(self, eid, path, grade="B", selected=True, resolution="", categories=None, sha=None):
        real = BOILERPLATE / path
        return {
            "evidence_id": eid,
            "root_id": "primary",
            "path": path.replace("\\", "/"),
            "line_range": None,
            "sha256": sha or sha256_bytes(real.read_bytes()),
            "source_kind": "first_party",
            "grade": grade,
            "author_declaration": {
                "found_author_tags": [],
                "categories": categories or [],
                "resolution": resolution,
                "resolution_basis": "",
            },
            "mapped_features": [],
            "selection_reason": "test",
            "selected": selected,
        }

    def test_pass_with_core_mapped_and_ab(self):
        plan = self._make_plan(
            evidence=[
                self._evidence("C-001", "backend/ImmediatePushAndAssignHandler.java", grade="A"),
            ],
            features=[
                {
                    "feature_id": "F-001",
                    "name": "即时推送",
                    "importance": "core",
                    "code_evidence": ["C-001"],
                    "verification": "needs_review",
                }
            ],
        )
        path = self._write(plan)
        errors, warnings, report = epc.check_plan(path)
        self.assertEqual(errors, [])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["ab_evidence_count"], 1)

    def test_r2_core_feature_without_selected_evidence_blocked(self):
        plan = self._make_plan(
            evidence=[self._evidence("C-001", "backend/ImmediatePushAndAssignHandler.java", selected=False)],
            features=[
                {
                    "feature_id": "F-001",
                    "name": "即时推送",
                    "importance": "core",
                    "code_evidence": ["C-001"],
                    "verification": "needs_review",
                }
            ],
        )
        path = self._write(plan)
        errors, _, report = epc.check_plan(path)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(e.startswith("R2") for e in errors))

    def test_r3_no_ab_evidence_blocked(self):
        plan = self._make_plan(
            evidence=[self._evidence("C-001", "backend/InsAbnormalReportController.java", grade="D")],
            features=[],
        )
        path = self._write(plan)
        errors, _, _ = epc.check_plan(path)
        self.assertTrue(any(e.startswith("R3") for e in errors))

    def test_r4_framework_replace_blocked(self):
        plan = self._make_plan(
            evidence=[
                self._evidence(
                    "C-001",
                    "backend/InsAbnormalReportController.java",
                    grade="B",
                    resolution="replace",
                    categories=[{"author": "Lion Li", "category": "framework"}],
                )
            ],
            features=[],
        )
        path = self._write(plan)
        errors, _, _ = epc.check_plan(path)
        self.assertTrue(any(e.startswith("R4") for e in errors))

    def test_r4_framework_exclude_allowed(self):
        plan = self._make_plan(
            evidence=[
                self._evidence(
                    "C-001",
                    "backend/ImmediatePushAndAssignHandler.java",
                    grade="A",
                    resolution="exclude",
                    categories=[{"author": "Lion Li", "category": "framework"}],
                )
            ],
            features=[],
        )
        path = self._write(plan)
        errors, _, _ = epc.check_plan(path)
        self.assertFalse(any(e.startswith("R4") for e in errors))

    def test_r5_hash_mismatch_blocked(self):
        plan = self._make_plan(
            evidence=[self._evidence("C-001", "backend/ImmediatePushAndAssignHandler.java", sha="deadbeef")],
            features=[],
        )
        path = self._write(plan)
        errors, _, _ = epc.check_plan(path)
        self.assertTrue(any(e.startswith("R5") for e in errors))

    def test_warning_for_ai_tool_selected_without_resolution(self):
        plan = self._make_plan(
            evidence=[
                self._evidence(
                    "C-001",
                    "backend/ImmediatePushAndAssignHandler.java",
                    categories=[{"author": "claude", "category": "ai_tool"}],
                )
            ],
            features=[],
        )
        path = self._write(plan)
        errors, warnings, _ = epc.check_plan(path)
        self.assertEqual(errors, [])
        self.assertTrue(any(w.startswith("W-002") for w in warnings))


class LineRangeExtractionTest(unittest.TestCase):
    def test_line_range_respected(self):
        from extract_code_material import collect_code_lines, load_selected_files

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        src = root / "app.py"
        lines = [f"line {i}" for i in range(1, 21)]
        src.write_text("\n".join(lines), encoding="utf-8")

        draft = root / "草稿"
        draft.mkdir(parents=True)
        selection = draft / "材料证据计划.json"
        selection.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "input_roots": [{"root_id": "primary", "path": str(root)}],
                    "code_evidence": [
                        {
                            "evidence_id": "C-001",
                            "root_id": "primary",
                            "path": "app.py",
                            "line_range": [5, 10],
                            "sha256": sha256_bytes(src.read_bytes()),
                            "selected": True,
                            "grade": "A",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        gate = root / "门禁状态.json"
        gate.write_text(
            json.dumps({"material-plan": {"confirmed": True, "artifact_sha256": "x"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        all_lines, manifest, _layout = collect_code_lines(root, selection)
        body = [l for l in all_lines if l.startswith("line ")]
        self.assertEqual(body, [f"line {i}" for i in range(5, 11)])
        self.assertEqual(manifest[0]["selected_line_start"], 5)
        self.assertEqual(manifest[0]["selected_line_end"], 10)

    def test_line_range_out_of_bounds_blocked(self):
        from extract_code_material import collect_code_lines

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        src = root / "app.py"
        src.write_text("a\nb\nc", encoding="utf-8")
        draft = root / "草稿"
        draft.mkdir(parents=True)
        selection = draft / "材料证据计划.json"
        selection.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "input_roots": [{"root_id": "primary", "path": str(root)}],
                    "code_evidence": [
                        {
                            "evidence_id": "C-001",
                            "root_id": "primary",
                            "path": "app.py",
                            "line_range": [1, 99],
                            "sha256": sha256_bytes(src.read_bytes()),
                            "selected": True,
                            "grade": "A",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        gate = root / "门禁状态.json"
        gate.write_text(
            json.dumps({"material-plan": {"confirmed": True}}, ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit) as ctx:
            collect_code_lines(root, selection)
        self.assertIn("行段超出文件范围", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
