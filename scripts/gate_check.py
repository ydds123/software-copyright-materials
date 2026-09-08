#!/usr/bin/env python3
"""Gate pre-check — blocks downstream execution when prerequisite gates are unconfirmed."""

import json
import sys
from pathlib import Path

GATE_CHAIN: dict[str, list[str]] = {
    "project":            [],
    "business":           [],
    "application-fields": ["code-selection"],
    "manual-draft":       ["business"],
    "content-quality":    ["business"],
    "manual":             ["content-quality"],
    "code-selection":     ["manual"],
    "extract-code":       ["code-selection"],
    "application-info":   ["code-selection"],
    "screenshot-method":  ["manual"],
    "diagrams":           ["manual"],
    "markdown":           ["application-fields", "code-selection", "screenshot-method", "content-quality", "manual"],
    "build-final":        ["markdown"],
}


def resolve_workdir(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for anchor in [cur, *cur.parents]:
        if (anchor / "门禁状态.json").exists():
            return anchor
        if (anchor / "软件著作权申请资料" / "门禁状态.json").exists():
            return anchor / "软件著作权申请资料"
    return None


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Gate pre-check")
    p.add_argument("--workdir", help="Path to 软件著作权申请资料 (auto-detected if omitted)")
    p.add_argument("--before", required=True, help="Step name to check (see GATE_CHAIN keys)")
    p.add_argument("--confirm", action="store_true", help="Suppress dry-run prompt")
    args = p.parse_args()

    wd = Path(args.workdir) if args.workdir else resolve_workdir()
    if wd is None:
        print("GATE ERROR: 找不到 门禁状态.json，无法确定当前工作目录。请用 --workdir 指定。")
        sys.exit(1)

    try:
        with open(wd / "门禁状态.json", "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    # v2 路径：存在材料证据计划（schema_version=3）时，code-selection 门禁由 material-plan 替代
    v2_plan = wd / "草稿" / "材料证据计划.json"
    is_v2 = False
    if v2_plan.exists():
        try:
            with open(v2_plan, "r", encoding="utf-8") as f:
                is_v2 = json.load(f).get("schema_version") == 3
        except Exception:
            pass

    prerequisites = GATE_CHAIN.get(args.before)
    if prerequisites is None:
        print(f"GATE UNKNOWN: step '{args.before}' is not in GATE_CHAIN. Allowed: {list(GATE_CHAIN)}")
        sys.exit(2)

    if is_v2 and "code-selection" in prerequisites:
        prerequisites = [("material-plan" if g == "code-selection" else g) for g in prerequisites]
    # extract-code/application-info 的 v1 前置 code-selection 在 v2 下同样由 material-plan 承担
    if is_v2 and args.before in ("extract-code", "application-info") and "code-selection" in prerequisites:
        prerequisites = ["material-plan" if g == "code-selection" else g for g in prerequisites]

    missing = []
    for gate_name in prerequisites:
        entry = state.get(gate_name, {})
        if not entry.get("confirmed"):
            missing.append(gate_name)

    if not missing:
        print(f"GATE OK: all prerequisites for '{args.before}' confirmed ({prerequisites})")
        sys.exit(0)

    gate_list = ", ".join(missing)
    print(f"GATE BLOCKED: 步骤 '{args.before}' 依赖以下门禁但尚未确认：{gate_list}")
    print(f"请先完成对应门禁的用户确认：python3 confirm_stage.py --stage <门禁名> --note \"...\" --confirm")
    sys.exit(1)


if __name__ == "__main__":
    main()
