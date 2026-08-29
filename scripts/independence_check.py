#!/usr/bin/env python3
"""Application independence check (1b) — 同批次申请独立性。

Compares two material evidence plans from the same submission batch:
  - functional boundary overlap ratio
  - shared code ratio (identical sha256 across plans)

Blocks downstream flow when the independence declaration is missing;
high overlap triggers warning + mandatory declaration (not a hard block,
per plan §6.4).

Exit codes: 0 ok (declaration present if required) / 1 declaration missing
or invalid / 2 invalid input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import read_json


def plan_code_hashes(plan: dict[str, Any]) -> set[str]:
    hashes: set[str] = set()
    for ev in plan.get("code_evidence") or []:
        if isinstance(ev, dict) and ev.get("sha256"):
            hashes.add(ev["sha256"])
    return hashes


def plan_boundaries(plan: dict[str, Any]) -> set[str]:
    scope = plan.get("software_scope") or {}
    return set(scope.get("included_boundaries") or [])


def compute_overlap(
    plan_a: dict[str, Any], plan_b: dict[str, Any]
) -> tuple[float, float, dict[str, Any]]:
    a_hashes = plan_code_hashes(plan_a)
    b_hashes = plan_code_hashes(plan_b)
    shared = a_hashes & b_hashes
    denom = min(len(a_hashes), len(b_hashes)) or 1
    shared_ratio = len(shared) / denom

    a_bound = plan_boundaries(plan_a)
    b_bound = plan_boundaries(plan_b)
    bound_shared = a_bound & b_bound
    bound_denom = min(len(a_bound), len(b_bound)) or 1
    boundary_overlap = len(bound_shared) / bound_denom if a_bound and b_bound else 0.0

    return shared_ratio, boundary_overlap, {
        "shared_code_count": len(shared),
        "shared_code_ratio": round(shared_ratio, 4),
        "boundary_overlap_ratio": round(boundary_overlap, 4),
        "plan_a_code_total": len(a_hashes),
        "plan_b_code_total": len(b_hashes),
        "plan_a_boundaries": sorted(a_bound),
        "plan_b_boundaries": sorted(b_bound),
        "shared_boundaries": sorted(bound_shared),
    }


def run(plan_a_path: Path, plan_b_path: Path, threshold: float = 0.5) -> dict[str, Any]:
    if not plan_a_path.exists() or not plan_b_path.exists():
        return {"status": "invalid", "errors": [f"缺少计划文件 {plan_a_path} / {plan_b_path}"]}
    plan_a = read_json(plan_a_path)
    plan_b = read_json(plan_b_path)

    shared_ratio, boundary_overlap, detail = compute_overlap(plan_a, plan_b)

    errors: list[str] = []
    warnings: list[str] = []
    high_overlap = shared_ratio >= threshold or boundary_overlap >= threshold
    if high_overlap:
        warnings.append(
            f"共享代码占比 {shared_ratio:.0%}，功能边界重叠 {boundary_overlap:.0%}，"
            "请确认两个软件可独立运行、可分别交付；若实为同一软件的两个模块，建议合并申请"
        )
        decl_a = plan_a.get("independence_declaration") or {}
        decl_b = plan_b.get("independence_declaration") or {}
        if not decl_a.get("confirmed_by_user") or not decl_b.get("confirmed_by_user"):
            errors.append(
                "检测到高重叠（共享代码/边界重叠超阈值）但 independence_declaration "
                "未由用户确认，禁止进入下游"
            )

    return {
        "status": "pass" if not errors else "blocked",
        "high_overlap": high_overlap,
        "detail": detail,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-a", required=True)
    parser.add_argument("--plan-b", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run(Path(args.plan_a), Path(args.plan_b), threshold=args.threshold)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"INDEPENDENCE {report['status'].upper()}")
        if report.get("detail"):
            d = report["detail"]
            print(f"  共享代码: {d['shared_code_ratio']:.0%} ({d['shared_code_count']}/{min(d['plan_a_code_total'], d['plan_b_code_total'])})")
            print(f"  边界重叠: {d['boundary_overlap_ratio']:.0%}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
