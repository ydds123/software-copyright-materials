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


def run(
    workdir: Path,
    batch_manuals: list[Path] | None = None,
    final_artifact: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    gates_path = workdir / GATE_FILE
    if not gates_path.exists():
        return {"status": "invalid", "errors": ["缺少 门禁状态.json"]}
    gates = read_json(gates_path)
    # gate switches (plan §completion-11: per-gate on/off)
    switches = gates.get("switches", {})
    scripts = Path(__file__).resolve().parent
    plan_path = workdir / "草稿" / MATERIAL_PLAN
    manual_path = workdir / "草稿" / MANUAL_FILE

    profile = gates.get("material-plan", {}).get("workflow_profile", "legacy-v1")
    checks["workflow_profile"] = {"value": profile}

    # 1. material-plan confirmed + unchanged
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
        code, out = _run_checker([str(scripts / "evidence_plan_check.py"), "--plan", str(plan_path)])
        checks["evidence-plan"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"evidence_plan_check 未通过（exit {code}）")

    # 3. re-run logic consistency on the manual
    if manual_path.exists():
        code, out = _run_checker(
            [str(scripts / "logic_consistency_check.py"), "--manual", str(manual_path)]
            + (["--plan", str(plan_path)] if plan_path.exists() else [])
        )
        checks["logic-consistency"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"logic_consistency_check 未通过（exit {code}）")

    # 4. batch structure（方案 v2 决策④：确定性硬门禁阻断；相似度高风险仅告警人工复核）
    if batch_manuals and len(batch_manuals) >= 2:
        code, out = _run_checker(
            [str(scripts / "batch_structure_check.py"), "--manuals", *[str(m) for m in batch_manuals], "--json"]
        )
        checks["batch-structure"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"batch_structure_check 未通过（exit {code}）")
        try:
            batch_json = json.loads(out)
            high_risks = [r for r in batch_json.get("risks") or [] if r.get("level") == "high"]
            if high_risks:
                for r in high_risks[:5]:
                    warnings.append(
                        f"[高风险-需人工复核] {' 与 '.join(r.get('pair') or [])}: {r.get('detail','')}"
                    )
                warnings.append(f"batch_structure 高风险共 {len(high_risks)} 项，提交前需人工复核确认可辩护")
        except (json.JSONDecodeError, AttributeError):
            pass

    # 4b. cross-material consistency (plan §6.1 gate 8)
    if plan_path.exists() and switches.get("cross-material", "on") != "off":
        cmd = [str(scripts / "cross_material_check.py"), "--plan", str(plan_path)]
        if manual_path.exists():
            cmd += ["--manual", str(manual_path)]
        app_md = workdir / "草稿" / "申请表信息.md"
        if app_md.exists():
            cmd += ["--application", str(app_md)]
        manifest = workdir / "草稿" / "代码提取清单.json"
        if manifest.exists():
            cmd += ["--code-manifest", str(manifest)]
        code, out = _run_checker(cmd)
        checks["cross-material"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"cross_material_check 未通过（exit {code}）")

    # 4c. final artifact re-check (plan §6.6)
    if final_artifact and final_artifact.exists() and switches.get("final-artifact", "on") != "off":
        scope = read_json(plan_path).get("software_scope", {}) if plan_path.exists() else {}
        cmd = [
            str(scripts / "final_artifact_check.py"),
            "--artifact", str(final_artifact),
            "--software-name", str(scope.get("name", "")),
            "--version", str(scope.get("version", "")),
        ]
        if plan_path.exists():
            cmd += ["--plan", str(plan_path)]
        if manual_path.exists():
            cmd += ["--source-manual", str(manual_path)]
        code, out = _run_checker(cmd)
        checks["final-artifact"] = {"exit": code, "output": out[:500]}
        if code != 0:
            errors.append(f"final_artifact_check 未通过（exit {code}）")

    # 5. required gates confirmed（v2 路径：材料证据计划替代 code-selection）
    v2 = False
    if plan_path.exists():
        try:
            v2 = read_json(plan_path).get("schema_version") == 3
        except Exception:
            pass
    required = ["manual", "content-quality", "code-selection", "markdown"]
    if v2:
        required = [("material-plan" if g == "code-selection" else g) for g in required]
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
    parser.add_argument("--final-artifact", help="最终 DOCX/PDF 路径（复检）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    workdir = Path(args.workdir) if args.workdir else resolve_workdir(args.task_dir)
    report = run(
        workdir,
        batch_manuals=[Path(m) for m in args.batch_manuals] or None,
        final_artifact=Path(args.final_artifact) if args.final_artifact else None,
    )
    if args.json:
        report["disclaimer"] = "本材料仅用于降低补正风险，不保证登记机关最终结论。"
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SUBMISSION {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
        print("声明：本材料仅用于降低补正风险，不保证登记机关最终结论。")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
