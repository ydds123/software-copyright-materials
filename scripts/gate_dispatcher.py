#!/usr/bin/env python3
"""Gate dispatcher — invoked by PreToolUse hook.

ONLY intercepts:
- Bash commands calling build_docx_from_md.py / extract_code_material.py (gate-protected scripts)
- Write/Edit targeting 门禁状态.json (the single source of gate truth)

Everything else passes through immediately.
"""

import json
import re
import sys
from pathlib import Path

# Only these specific scripts are gate-protected
STEP_GATES: dict[str, list[str]] = {
    "extract_code_material.py": ["code-selection"],
    "build_docx_from_md.py": ["markdown", "diagrams"],
}

GATE_FILE = "门禁状态.json"


def find_gate_json(start: Path) -> Path | None:
    for anchor in [start, *start.parents]:
        p = anchor / GATE_FILE
        if p.exists():
            return p
        p = anchor / "软件著作权申请资料" / GATE_FILE
        if p.exists():
            return p
    return None


def load_gate_state(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    cwd = hook_input.get("cwd", "")

    # ── Bash: only intercept gate-protected scripts ──
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        for script, prereqs in STEP_GATES.items():
            if script not in command:
                continue
            # This is a gate-protected script — find workdir and check gates
            m = re.search(r'--workdir\s+"?([^"\s]+)"?', command)
            start = Path(m.group(1)) if m else Path(cwd)
            gate_path = find_gate_json(start)
            if gate_path is None:
                sys.exit(0)  # No gate file — not in a skill task

            state = load_gate_state(gate_path)
            missing = [g for g in prereqs if not state.get(g, {}).get("confirmed")]
            if missing:
                gate_list = ", ".join(missing)
                print(
                    f"\n[GATE BLOCKED] {script} 依赖以下门禁但尚未确认：{gate_list}",
                    file=sys.stderr,
                )
                print("请先完成对应门禁的用户确认后重试。", file=sys.stderr)
                sys.exit(2)
            break  # One script match is enough

        # ── Block python3 -c / python -c that writes to 门禁状态.json ──
        if GATE_FILE in command and any(
            kw in command for kw in ("python3 -c", "python -c", "python3 -c", "import json")
        ):
            # Only block if the command targets a real gate file
            gate_dir = find_gate_json(Path(cwd))
            if gate_dir is not None:
                print(
                    f"\n[GATE BLOCKED] 禁止通过脚本直接修改门禁状态文件：{GATE_FILE}",
                    file=sys.stderr,
                )
                print("门禁状态应通过 confirm_stage.py 修改。", file=sys.stderr)
                sys.exit(2)

        sys.exit(0)

    # ── Write/Edit: only block 门禁状态.json (single source of truth) ──
    if tool_name in ("Write", "Edit", "MultiEdit"):
        file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)

        if re.search(r"门禁状态\.json", file_path):
            print(
                f"\n[GATE BLOCKED] 禁止直接编辑门禁状态文件：{file_path}",
                file=sys.stderr,
            )
            print("门禁状态应通过 confirm_stage.py 修改。", file=sys.stderr)
            sys.exit(2)

        sys.exit(0)

    # ── Other tools: allow ──
    sys.exit(0)


if __name__ == "__main__":
    main()
