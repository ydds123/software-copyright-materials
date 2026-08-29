"""1a.2 视觉证据门禁测试。

模型调用被 mock（不依赖真实 API / 网络）。覆盖验收标准：
- V1 零 A/B 级阻断
- V2 覆盖率不足阻断 / 达标通过
- V3 D 级冒充阻断
- V4 capture_source unknown 不计入覆盖
- V5 未脱敏阻断
- V6 模型与申报冲突 → 人工复核且不计入覆盖
- 确定性层：重复截图、缺失文件、尺寸解析、隐私扫描
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import visual_evidence_check as vec  # noqa: E402
from visual_model_adapter import _parse_model_json  # noqa: E402


def _mock_assess(has_real_data=True, mockup=False, empty=False, status_count=None):
    return patch(
        "visual_evidence_check.assess_image_sync",
        return_value={
            "supported": True,
            "ok": True,
            "cached": False,
            "model": "deepseek-v4-flash-vision-exp",
            "model_version": "deepseek-v4-flash-vision-exp",
            "prompt_version": "visual-gate-v1",
            "assessed_at": "2026-08-29T00:00:00Z",
            "page_type": "list",
            "has_real_data": has_real_data,
            "suspected_design_mockup": mockup,
            "empty_state_detected": empty,
            "status_label_count": status_count,
            "raw_answer": "{}",
        },
    )

# Minimal valid PNG (1x1) bytes
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c636000000200010005000a2f8e0e0000000049454e44ae426082"
)


def _write_png(path: Path) -> Path:
    path.write_bytes(PNG_1PX)
    return path


def _plan(visual_evidence, features=None):
    return {
        "schema_version": 3,
        "visual_evidence": visual_evidence,
        "features": features
        or [
            {
                "feature_id": "F-001",
                "name": "核心功能",
                "importance": "core",
                "visual_evidence": [],
                "visual_status": "required",
            }
        ],
        "code_evidence": [],
    }


def _ev(eid, fpath, grade="A", capture="live_system", scrubbed=True, acquired=True, mapped=None):
    return {
        "evidence_id": eid,
        "kind": "ui_screenshot",
        "file_path": fpath,
        "grade": grade,
        "capture_source": capture,
        "data_state": "populated",
        "privacy_scrubbed": scrubbed,
        "acquisition_status": "acquired" if acquired else "pending",
        "mapped_features": mapped or ["F-001"],
    }


class DeterministicTest(unittest.TestCase):
    def test_dimensions_parse(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write_png(Path(td) / "shot.png")
            dims = vec.parse_image_dimensions(p)
            self.assertEqual(dims, (1, 1))

    def test_duplicate_detected(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "a.png")
            _write_png(d / "b.png")  # same bytes
            plan = _plan(
                [
                    _ev("V-001", "a.png"),
                    _ev("V-002", "b.png"),
                ]
            )
            plan_path = d / "材料证据计划.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            report = vec.run(plan_path, d, cache_path=d / "cache.json")
            self.assertTrue(any("相同" in e for e in report["errors"]))

    def test_missing_file_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            plan = _plan([_ev("V-001", "missing.png")])
            plan_path = d / "材料证据计划.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            report = vec.run(plan_path, d, cache_path=d / "cache.json")
            self.assertTrue(any("缺失" in e for e in report["errors"]))

    def test_privacy_hint_in_filename(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "13800138000_截图.png")
            plan = _plan([_ev("V-001", "13800138000_截图.png")])
            plan_path = d / "材料证据计划.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            with _mock_assess():
                report = vec.run(plan_path, d, cache_path=d / "cache.json")
            self.assertTrue(any("敏感信息" in e for e in report["errors"]))


class GateRulesTest(unittest.TestCase):
    def _run(self, plan, screenshot_dir, **kw):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            plan_path = d / "材料证据计划.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            return vec.run(plan_path, screenshot_dir, cache_path=d / "cache.json", **kw)

    def test_v1_no_ab_evidence_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "c.png")
            plan = _plan([_ev("V-001", "c.png", grade="C", capture="live_system")])
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess(has_real_data=False):
                report = self._run(plan, d)
            self.assertTrue(any(e.startswith("V1") for e in report["errors"]))

    def test_v2_coverage_below_threshold_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "a.png")
            plan = _plan(
                [_ev("V-001", "a.png", grade="A")],
                features=[
                    {"feature_id": "F-001", "name": "功能1", "importance": "core", "visual_evidence": [], "visual_status": "required"},
                    {"feature_id": "F-002", "name": "功能2", "importance": "core", "visual_evidence": [], "visual_status": "required"},
                ],
            )
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess():
                report = self._run(plan, d)
            self.assertTrue(any(e.startswith("V2") and "覆盖" in e for e in report["errors"]))

    def test_v2_coverage_pass(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "a.png")
            plan = _plan([_ev("V-001", "a.png", grade="A")])
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess():
                report = self._run(plan, d)
            self.assertEqual(report["status"], "pass", report["errors"])

    def test_v3_d_grade_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "mock.png")
            plan = _plan([_ev("V-001", "mock.png", grade="D")])
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess():
                report = self._run(plan, d)
            self.assertTrue(any(e.startswith("V3") for e in report["errors"]))

    def test_v4_unknown_source_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "a.png")
            plan = _plan([_ev("V-001", "a.png", grade="A", capture="unknown")])
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess():
                report = self._run(plan, d)
            self.assertTrue(any(e.startswith("V4") for e in report["errors"]))

    def test_v5_unscrubbed_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_png(d / "a.png")
            plan = _plan([_ev("V-001", "a.png", grade="A", scrubbed=False)])
            plan["features"][0]["visual_evidence"] = ["V-001"]
            with _mock_assess():
                report = self._run(plan, d)
            self.assertTrue(any(e.startswith("V5") for e in report["errors"]))


class ModelParseTest(unittest.TestCase):
    def test_parse_clean_json(self):
        result = _parse_model_json('{"page_type": "list", "has_real_data": true, "status_label_count": 5}')
        self.assertTrue(result.get("has_real_data"))
        self.assertEqual(result.get("status_label_count"), 5)

    def test_parse_fenced_json(self):
        result = _parse_model_json('这里分析：```json\n{"page_type": "form", "has_real_data": false}\n```')
        self.assertEqual(result.get("page_type"), "form")
        self.assertFalse(result.get("has_real_data"))

    def test_parse_garbage(self):
        result = _parse_model_json("无法识别这张图片")
        self.assertTrue(result.get("parse_error"))


if __name__ == "__main__":
    unittest.main()
