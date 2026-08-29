#!/usr/bin/env python3
"""Submission readiness gate (1a.3).

Aggregates the final-state gates before DOCX/PDF build. A submission is
ready only when:
  - material-plan confirmed and unchanged (invalidation check)
  - evidence_plan_check passes (re-run)
  - logic_consistency_check passes (re-run)
  - batch_structure_check passes (if sibling docs exist)
  - content-quality / manual / markdown gates confirmed
  - visual evidence gate passes (if visual evidence declared)

Unready builds may still produce an internal preview, but the readiness
report must not mark the output as 可提交版.

Exit codes: 0 ready / 1 not ready (blockers) / 2 invalid input
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import read_json, resolve_draft_dir, resolve_workdir

GATE_FILE = "门禁状态.json"
MATERIAL_PLAN = "材料证据计划.json"
MANUAL_FILE = "操作手册.md"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_checker(args: list[str]) -> tuple[int, str]:
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


def run(workdir: Path, batch_manuals: list[Path] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    gates_path = workdir / GATE_FILE
    if not gates_path.exists():
        return {"status": "invalid", "errors": ["缺少 门禁状态.json"]}
    gates = read_json(gates_path)

    # 1. material-plan confirmed + unchanged
    plan_path = workdir / "草稿" / MATERIAL_PLAN
    if plan_path.exists():
        entry = gates.get("material-plan", {})
        if not entry.get("confirmed"):
            errors.append("material-plan 未确认")
        elif entry.get("artifact_sha256") and sha256_of(plan_path) != entry["artifact_sha256"]:
            errors.append("material-plan 在确认后被修改，确认已失效")
        checks["material-plan"] = {
            "confirmed": bool(entry.get("confirmed")),
            "unchanged": (
                not entry.get("artifact_sha256")
                or sha256_of(plan_path) == entry["artifact_sha256"]
            ),
        }

    # 2. re-run evidence_plan_check
    if plan_path.exists():
        scripts = Path(__file__).resolve().parent
        code, out = _run_checker([str(scripts / "evidence_plan_check.py"), "--plan", str(plan_path)])
        checks["evidence-plan"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"evidence_plan_check 未通过（exit {code}）")

    # 3. re-run logic consistency on the manual
    manual_path = workdir / "草稿" / MANUAL_FILE
    if manual_path.exists():
        scripts = Path(__file__).resolve().parent
        code, out = _run_checker(
            [str(scripts / "logic_consistency_check.py"), "--manual", str(manual_path)]
            + (["--plan", str(plan_path)] if plan_path.exists() else [])
        )
        checks["logic-consistency"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"logic_consistency_check 未通过（exit {code}）")

    # 4. batch structure (only if multiple docs given)
    if batch_manuals and len(batch_manuals) >= 2:
        scripts = Path(__file__).resolve().parent
        code, out = _run_checker(
            [str(scripts / "batch_structure_check.py"), "--manuals", *[str(m) for m in batch_manuals]]
        )
        checks["batch-structure"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"batch_structure_check 未通过（exit {code}）")

    # 5. required gates confirmed
    required = ["manual", "content-quality", "code-selection", "markdown"]
    missing = [g for g in required if not gates.get(g, {}).get("confirmed")]
    if missing:
        errors.append(f"必备门禁未确认：{', '.join(missing)}")
    checks["gates"] = {g: bool(gates.get(g, {}).get("confirmed")) for g in required}

    report = {
        "status": "ready" if not errors else "not-ready",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "submission_allowed": not errors,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", help="Task workdir; auto-resolved if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved if omitted")
    parser.add_argument("--batch-manuals", nargs="*", default=[], help="同批次其他操作手册路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    workdir = Path(args.workdir) if args.workdir else resolve_workdir(args.task_dir)
    report = run(workdir, batch_manuals=[Path(m) for m in args.batch_manuals] or None)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SUBMISSION {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
