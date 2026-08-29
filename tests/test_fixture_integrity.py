"""里程碑 0 最小自检测试。

验证：
1. 回归期望标签文件格式合法。
2. 每个被标记的 fixture 文件真实存在。
3. 视觉缺陷场景清单格式合法。
4. 回归期望覆盖所有 fixture 文件（防遗漏）。

后续各里程碑的门禁测试在此基础上扩展；本测试只做结构完整性校验，
不判定任何业务规则（判定逻辑在 1a.x 各阶段实现）。
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
REGRESSION = ROOT / "regression" / "expected_patterns.json"
VISUAL = FIXTURES / "visual" / "defect_cases.json"


class FixtureIntegrityTest(unittest.TestCase):
    """fixture 完整性与标签格式。"""

    @classmethod
    def setUpClass(cls):
        with open(REGRESSION, encoding="utf-8") as f:
            cls.regression = json.load(f)
        with open(VISUAL, encoding="utf-8") as f:
            cls.visual = json.load(f)

    def test_regression_schema(self):
        self.assertEqual(self.regression.get("schema_version"), 1)
        self.assertIn("cases", self.regression)
        self.assertGreater(len(self.regression["cases"]), 0)

    def test_regression_cases_wellformed(self):
        for case in self.regression["cases"]:
            with self.subTest(case=case.get("file")):
                self.assertIn("file", case)
                self.assertIn("expected_grade", case)
                self.assertIn("expected_signals", case)
                self.assertIsInstance(case["expected_signals"], list)

    def test_every_regression_fixture_exists(self):
        for case in self.regression["cases"]:
            file = case.get("file", "")
            if file.startswith("fixtures/") and file.endswith(".json") and file.endswith("defect_cases.json"):
                continue  # 清单自身不要求存在为图片
            with self.subTest(file=file):
                self.assertTrue((ROOT / file).exists(), f"缺失 fixture: {file}")

    def test_every_fixture_file_has_regression_entry(self):
        declared = set()
        for case in self.regression["cases"]:
            if case["file"].startswith("fixtures/") and not case["file"].endswith("defect_cases.json"):
                declared.add(case["file"])
        actual = set()
        for p in FIXTURES.rglob("*"):
            if p.is_file() and p.name != "defect_cases.json":
                actual.add(str(p.relative_to(ROOT)).replace("\\", "/"))
        self.assertEqual(actual, declared, "fixture 文件与回归标签不一致")

    def test_visual_scenarios_wellformed(self):
        self.assertEqual(self.visual.get("schema_version"), 1)
        self.assertIn("scenarios", self.visual)
        for s in self.visual["scenarios"]:
            with self.subTest(scenario=s.get("id")):
                for key in ("id", "name", "defect", "expected", "rule_ref"):
                    self.assertIn(key, s)


if __name__ == "__main__":
    unittest.main()
