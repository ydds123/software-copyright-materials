#!/usr/bin/env python3
"""Cross-material consistency gate (补漏 4 / plan §6.1 gate 8).

Verifies that software name / version / features are consistent across:
  - material evidence plan (features, software_scope)
  - operation manual (草稿/操作手册.md)
  - application form (草稿/申请表信息.md, optional)
  - code extraction manifest (草稿/代码提取清单.json, optional)

Deterministic checks only; semantic mismatches go to human review.

Exit codes: 0 pass / 1 inconsistency / 2 invalid input
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import read_json, read_text


def plan_features(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in plan.get("features") or [] if isinstance(f, dict)]


def check_name_version(plan: dict[str, Any], manual_text: str) -> list[str]:
    errors: list[str] = []
    scope = plan.get("software_scope") or {}
    name = str(scope.get("name") or "").strip()
    version = str(scope.get("version") or "").strip()
    if name and name not in manual_text:
        errors.append(f"手册中找不到软件名称 '{name}'")
    if version and version not in manual_text:
        errors.append(f"手册中找不到版本号 '{version}'")
    return errors


def check_feature_coverage(plan: dict[str, Any], manual_text: str) -> list[str]:
    errors: list[str] = []
    for f in plan_features(plan):
        name = str(f.get("name") or "").strip()
        if not name:
            continue
        if f.get("importance") == "core" and name not in manual_text:
            errors.append(
                f"核心功能 '{name}'（{f.get('feature_id')}）在手册正文中未出现"
            )
    return errors


def check_document_sections(plan: dict[str, Any], manual_text: str) -> list[str]:
    """Verify plan-declared document_sections exist in the manual."""
    errors: list[str] = []
    for f in plan_features(plan):
        sections = f.get("document_sections") or []
        for sec in sections:
            if str(sec).strip() and str(sec).strip() not in manual_text:
                errors.append(
                    f"功能 {f.get('feature_id')} 声明的文档章节 '{sec}' 在手册中不存在"
                )
    return errors


def check_application_consistency(plan: dict[str, Any], app_text: str) -> list[str]:
    errors: list[str] = []
    scope = plan.get("software_scope") or {}
    name = str(scope.get("name") or "").strip()
    version = str(scope.get("version") or "").strip()
    if name and name not in app_text:
        errors.append(f"申请表中找不到软件名称 '{name}'")
    if version and version not in app_text:
        errors.append(f"申请表中找不到版本号 '{version}'")
    # 功能名主干匹配：去掉常见描述修饰词（配置/编排/维护/跟踪/模块），
    # 申请表自然语言描述（如「巡检点配置管理」）应对应计划功能「巡检点管理」
    import re as _re
    def _compact(s: str) -> str:
        return s.replace(' ', '').replace('\u3000', '')
    app_c = _compact(app_text)
    for f in plan_features(plan):
        if f.get("importance") == "core":
            fname = str(f.get("name") or "").strip()
            if not fname:
                continue
            fname_c = _compact(fname)
            if fname_c in app_c:
                continue
            stem = fname
            for mod in ('配置管理', '编排与管理', '维护管理', '跟踪管理', '管理'):
                if stem.endswith(mod):
                    stem = stem[:-len(mod)]
                    break
            stem_c = _compact(stem)
            if stem_c and stem_c not in app_c:
                errors.append(f"申请表主要功能描述中找不到核心功能 '{fname}'（主干 '{stem}' 也未出现）")
    return errors


def check_code_manifest(plan: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    plan_paths = {
        str(e.get("path", "")).replace("\\", "/")
        for e in plan.get("code_evidence") or []
        if isinstance(e, dict) and e.get("selected")
    }
    manifest_files = manifest.get("files") or []
    manifest_paths = {
        str(f.get("path", "")).replace("\\", "/") for f in manifest_files
    }
    outside = manifest_paths - plan_paths
    if outside:
        errors.append(
            f"代码提取清单中有 {len(outside)} 个文件不在已确认计划的选中项中："
            f"{'; '.join(sorted(outside)[:5])}"
        )
    return errors


def run(
    plan_path: Path,
    manual_path: Path | None = None,
    application_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    if not plan_path.exists():
        return {"status": "invalid", "errors": [f"缺少 {plan_path}"]}
    plan = read_json(plan_path)
    errors: list[str] = []
    checks: dict[str, Any] = {}

    if manual_path and manual_path.exists():
        manual_text = read_text(manual_path)
        e = (
            check_name_version(plan, manual_text)
            + check_feature_coverage(plan, manual_text)
            + check_document_sections(plan, manual_text)
        )
        errors.extend(e)
        checks["manual"] = {"path": str(manual_path), "errors": len(e)}

    if application_path and application_path.exists():
        e = check_application_consistency(plan, read_text(application_path))
        errors.extend(e)
        checks["application"] = {"path": str(application_path), "errors": len(e)}

    if manifest_path and manifest_path.exists():
        e = check_code_manifest(plan, read_json(manifest_path))
        errors.extend(e)
        checks["code_manifest"] = {"path": str(manifest_path), "errors": len(e)}

    errors = list(dict.fromkeys(errors))
    return {
        "status": "pass" if not errors else "blocked",
        "errors": errors,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="材料证据计划.json")
    parser.add_argument("--manual", help="草稿/操作手册.md")
    parser.add_argument("--application", help="草稿/申请表信息.md")
    parser.add_argument("--code-manifest", help="草稿/代码提取清单.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run(
        Path(args.plan),
        Path(args.manual) if args.manual else None,
        Path(args.application) if args.application else None,
        Path(args.code_manifest) if args.code_manifest else None,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"CROSS MATERIAL {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
