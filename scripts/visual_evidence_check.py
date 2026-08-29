#!/usr/bin/env python3
"""Visual evidence gate (1a.2).

Two tracks per the plan:
  deterministic (local, zero model cost):
    file missing / duplicate sha / size & dimension parse / privacy regex /
    D-grade-masquerading-as-A (dimension+declaration mismatch is model's job;
    here we only check declare-vs-model conflict)
  semantic (DeepSeek flash vision):
    page_type / has_real_data / suspected_design_mockup / status_label_count

Hard blocks (exit 1):
  V1 A/B total == 0
  V2 core-feature visual coverage < threshold (per software type)
  V3 D-grade evidence counted toward core coverage
  V4 capture_source unknown counted
  V5 privacy_scrubbed false in submission-bound evidence
  V6 model assessment conflicts with declaration (goes to manual review,
      evidence NOT counted) — pending items block until resolved
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import read_json, resolve_draft_dir, resolve_screenshot_dir, write_json

from visual_model_adapter import assess_image_sync, load_cache, save_cache

PLAN_FILE = "材料证据计划.json"
REPORT_FILE = "视觉证据门禁报告.json"
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SENSITIVE_RE = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"\d{17}[\dXx]"),
    re.compile(r"(?:身份证|手机号|联系电话|住址|银行卡|密码)"),
]

# Coverage thresholds: {software_type: ratio}. Default UI-dense 0.8, backend 0.5.
COVERAGE_DEFAULT = 0.8
COVERAGE_BACKEND = 0.5


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_image_dimensions(path: Path) -> tuple[int, int] | None:
    """Parse width/height from PNG/JPEG/WebP headers (stdlib only)."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        if 0 < w < 20000 and 0 < h < 20000:
            return w, h
    if data[:2] == b"\xff\xd8":
        # JPEG: walk markers for SOF
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if i + 2 >= len(data):
                break
            seg_len = int.from_bytes(data[i + 2 : i + 4], "big")
            if marker in range(0xC0, 0xC3) or marker in range(0xC5, 0xC7) or marker in range(0xC9, 0xCB) or marker in range(0xCD, 0xCF):
                h, w = int.from_bytes(data[i + 5 : i + 7], "big"), int.from_bytes(data[i + 7 : i + 9], "big")
                if 0 < w < 20000 and 0 < h < 20000:
                    return w, h
            i += 2 + seg_len
    if data[:12] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X" and len(data) >= 30:
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            if 0 < w < 20000 and 0 < h < 20000:
                return w, h
    return None


def privacy_scan(image_path: Path) -> list[str]:
    """Filename-based conservative privacy scan (deterministic track)."""
    hits = [p.pattern for p in SENSITIVE_RE if p.search(image_path.name)]
    return hits


def run(
    plan_path: Path,
    screenshot_dir: Path,
    software_type: str = "ui",
    cache_path: Path | None = None,
    max_retries: int = 0,
) -> dict[str, Any]:
    plan = read_json(plan_path)
    evidence_items = plan.get("visual_evidence") or []
    features = plan.get("features") or []
    code_evidence = plan.get("code_evidence") or []

    errors: list[str] = []
    warnings: list[str] = []
    assessed: list[dict[str, Any]] = []

    cache_path = cache_path or (plan_path.parent / "视觉模型判定缓存.json")

    # ── Deterministic track ──
    seen_hashes: dict[str, str] = {}
    for ev in evidence_items:
        if not isinstance(ev, dict):
            continue
        item = dict(ev)
        file_path = screenshot_dir / item.get("file_path", "")
        item["_resolved_path"] = str(file_path)
        if not file_path.exists():
            errors.append(f"V-DET: 截图文件缺失: {item.get('file_path')}")
            item["_deterministic"] = {"exists": False}
            assessed.append(item)
            continue
        sha = sha256_of(file_path)
        if sha in seen_hashes:
            errors.append(
                f"V-DET: 截图重复（与 {seen_hashes[sha]} 内容相同）: {item.get('file_path')}"
            )
            item["_deterministic"] = {"duplicate": True}
        else:
            seen_hashes[sha] = item.get("file_path", "")
            item["_deterministic"] = {"duplicate": False}
        dims = parse_image_dimensions(file_path)
        if dims and (dims[0] < 400 or dims[1] < 300):
            warnings.append(f"V-WARN: 截图尺寸偏小 {dims[0]}x{dims[1]}: {item.get('file_path')}")
        priv = privacy_scan(file_path)
        if priv:
            errors.append(
                f"V-DET: 截图文件名含敏感信息特征 {priv}: {item.get('file_path')}"
            )
        item["_dimensions"] = list(dims) if dims else None
        item["_sha256"] = sha

        # ── Semantic track: DeepSeek vision ──
        result = assess_image_sync(file_path, cache_path, max_retries=max_retries)
        if result.get("ok"):
            item["_model_assessment"] = result
            decl = {
                "grade": item.get("grade"),
                "capture_source": item.get("capture_source"),
                "data_state": item.get("data_state"),
            }
            model_grade = _model_grade(result)
            item["_cross_check"] = _cross_validate(result, decl, model_grade)
            item["_model_grade"] = model_grade
        else:
            item["_model_assessment"] = result
            item["_cross_check"] = "model_unavailable"
            warnings.append(
                f"V-WARN: 语义判定未执行（{result.get('reason') or result.get('error')}）: {item.get('file_path')}"
            )
        assessed.append(item)

    # ── Hard rules on coverage & grades ──
    required_features = [
        f
        for f in features
        if isinstance(f, dict)
        and f.get("importance") == "core"
        and (f.get("visual_status") or "required") != "not_applicable"
    ]
    if not required_features:
        warnings.append("V-WARN: 没有需要视觉证据的核心功能（或全部 not_applicable）")

    counted: list[dict[str, Any]] = []
    for f in required_features:
        mapped = f.get("visual_evidence") or []
        valid = []
        for vid in mapped:
            ev = next((e for e in assessed if e.get("evidence_id") == vid), None)
            if not ev:
                errors.append(f"V2: 功能 {f.get('feature_id')} 映射的视觉证据 {vid} 不存在于清单")
                continue
            grade = ev.get("grade") or ev.get("_model_grade")
            if ev.get("_cross_check") == "conflict":
                # conflict → not counted, manual review
                errors.append(
                    f"V6: 视觉证据 {vid} 模型判定与申报冲突，当前不计入覆盖，需人工复核"
                )
                continue
            if ev.get("_cross_check") == "model_unavailable":
                continue
            if ev.get("capture_source") == "unknown" or not ev.get("capture_source"):
                errors.append(f"V4: 视觉证据 {vid} capture_source 未确认，不计入覆盖")
                continue
            if grade == "D":
                errors.append(f"V3: D 级视觉证据 {vid} 被用于满足核心功能覆盖要求")
                continue
            if grade in ("A", "B"):
                valid.append(vid)
        if not valid:
            errors.append(
                f"V2: 核心功能 '{f.get('name')}' ({f.get('feature_id')}) 无有效 A/B 级视觉证据"
            )
        else:
            counted.extend(valid)

    ab_total = sum(1 for e in assessed if (e.get("grade") or e.get("_model_grade")) in ("A", "B") and e.get("_cross_check") != "conflict")
    if ab_total == 0:
        errors.append("V1: A/B 级视觉证据总数为 0")

    if required_features:
        coverage = len(set(counted)) / len(required_features)
        threshold = COVERAGE_BACKEND if software_type == "backend" else COVERAGE_DEFAULT
        if coverage < threshold:
            errors.append(
                f"V2: 核心功能视觉证据覆盖率 {coverage:.0%} < 阈值 {threshold:.0%}"
            )
    else:
        coverage = 1.0

    # V5: privacy_scrubbed false in submission-bound evidence
    for ev in assessed:
        if ev.get("privacy_scrubbed") is False and ev.get("acquisition_status") == "acquired":
            errors.append(f"V5: 视觉证据 {ev.get('evidence_id')} 未声明已脱敏")

    report = {
        "schema_version": 1,
        "status": "pass" if not errors else "blocked",
        "software_type": software_type,
        "coverage": round(coverage, 4),
        "ab_total": ab_total,
        "assessed_count": len(assessed),
        "errors": errors,
        "warnings": warnings,
        "cache_file": str(cache_path),
        "model": "deepseek-v4-flash-vision-exp",
    }
    return report


def _model_grade(result: dict[str, Any]) -> str:
    """Infer evidence grade from the model assessment (A/B/C/D)."""
    if result.get("suspected_design_mockup"):
        return "D"
    if result.get("empty_state_detected") or not result.get("has_real_data"):
        return "C"
    return "A" if result.get("has_real_data") else "C"


def _cross_validate(result: dict[str, Any], declaration: dict[str, Any], model_grade: str) -> str:
    """Return 'consistent' | 'conflict' | 'model_unavailable'."""
    declared_grade = declaration.get("grade")
    if declared_grade and declared_grade != model_grade:
        # D (declared) vs A/B (model) is fine (under-promotion OK);
        # A/B declared but model says C/D is a conflict.
        if declared_grade in ("A", "B") and model_grade in ("C", "D"):
            return "conflict"
        return "consistent"
    return "consistent"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", help="Path to 材料证据计划.json; auto-derived if omitted")
    parser.add_argument("--screenshots", help="截图目录; auto-derived if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved if omitted")
    parser.add_argument("--software-type", choices=["ui", "backend"], default="ui")
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan_path = Path(args.plan) if args.plan else resolve_draft_dir(args.task_dir) / PLAN_FILE
    screenshot_dir = (
        Path(args.screenshots)
        if args.screenshots
        else resolve_screenshot_dir(args.task_dir)
    )
    if not plan_path.exists():
        report = {"status": "invalid", "errors": [f"缺少 {plan_path}"]}
        print(json.dumps(report, ensure_ascii=False) if args.json else str(report))
        sys.exit(2)

    try:
        report = run(
            plan_path,
            screenshot_dir,
            software_type=args.software_type,
            max_retries=args.max_retries,
        )
    except Exception as exc:  # noqa: BLE001
        report = {"status": "invalid", "errors": [str(exc)]}
        print(json.dumps(report, ensure_ascii=False) if args.json else str(report))
        sys.exit(2)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"VISUAL EVIDENCE {report['status'].upper()}")
        print(f"覆盖率: {report.get('coverage')} | A/B 证据: {report.get('ab_total')} | 已检查: {report.get('assessed_count')}")
        for e in report.get("errors", []):
            print(f"  ERROR: {e}")
        for w in report.get("warnings", []):
            print(f"  WARNING: {w}")

    sys.exit(1 if report.get("errors") else 0)


if __name__ == "__main__":
    main()
