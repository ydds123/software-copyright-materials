#!/usr/bin/env python3
"""Record explicit user confirmations for gated workflow stages.

All gates are recorded in a single file: <workdir>/门禁状态.json
Previous scattered files (环境确认.json, 项目确认.json, 截图方式确认.json, etc.)
are consolidated into this one file.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import confirm_params, read_json, resolve_workdir, write_json

GATE_FILE = "门禁状态.json"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_gates(workdir: Path) -> dict[str, Any]:
    path = workdir / GATE_FILE
    if not path.exists():
        return {}
    return read_json(path)


def write_gate(workdir: Path, gate: str, note: str, **extra) -> Path:
    gates = load_gates(workdir)
    gates[gate] = {"confirmed": True, "note": note, "confirmed_at": timestamp()}
    gates[gate].update(extra)
    out_path = workdir / GATE_FILE
    write_json(out_path, gates)
    return out_path


def pending_application_fields(md_path: Path) -> list[str]:
    if not md_path.exists():
        return [f"缺少 {md_path}"]
    return [line.strip() for line in md_path.read_text(encoding="utf-8").splitlines() if "待用户确认" in line]


def confirm_environment(workdir: Path, note: str) -> Path:
    return write_gate(workdir, "environment", note)


def confirm_project(workdir: Path, note: str) -> Path:
    return write_gate(workdir, "project", note)


def confirm_business(workdir: Path, note: str) -> Path:
    path = workdir / "草稿/业务理解.json"
    if not path.exists():
        raise SystemExit("Missing 草稿/业务理解.json")
    return write_gate(workdir, "business", note)


def confirm_code_selection(workdir: Path, note: str) -> Path:
    path = workdir / "草稿/代码文件选择.json"
    if not path.exists():
        raise SystemExit("Missing 草稿/代码文件选择.json")
    data = read_json(path)
    files = data.get("files") if isinstance(data, dict) else []
    selected = [item for item in files if isinstance(item, dict) and item.get("selected")]
    if not selected:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 代码文件选择尚未由模型填写。请先选择至少一个源码文件并填写选择理由，再让用户确认。"
        )
    missing_reason = [item.get("path") for item in selected if not str(item.get("model_reason") or "").strip()]
    if data.get("model_selection_required") and missing_reason:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 已选源码缺少模型选择理由，请补全 model_reason 后再确认。\n"
            + "\n".join(f"- {item}" for item in missing_reason[:20])
        )

    # ── 模块代码覆盖验证 ──
    biz_path = workdir / "草稿/业务理解.json"
    if biz_path.exists():
        biz = read_json(biz_path)
        candidate_paths = {
            f.get("path", "").replace("\\", "/")
            for f in files
        }
        selected_paths = {
            f.get("path", "").replace("\\", "/")
            for f in selected
        }
        modules = biz.get("manual_modules") or []
        weak_modules: list[str] = []
        for m in modules:
            title = m.get("title", "?")
            evidence = [
                e.replace("\\", "/")
                for e in (m.get("evidence") or [])
            ]
            if not evidence:
                continue
            in_candidates = [e for e in evidence if e in candidate_paths]
            if not in_candidates:
                weak_modules.append(
                    f"{title} — 所有 evidence 文件均不在候选池中"
                )
            else:
                in_selected = [e for e in evidence if e in selected_paths]
                if not in_selected:
                    weak_modules.append(
                        f"{title} — evidence 文件在候选池中但未被选中：{', '.join(in_candidates[:3])}"
                    )

        if weak_modules and not data.get("module_code_coverage"):
            print(
                f"WARNING: {len(weak_modules)}/{len(modules)} 个模块无代码覆盖：",
                *[f"  - {wm}" for wm in weak_modules],
                sep="\n",
            )
            print(
                "HINT: 这些模块在操作手册中有功能描述但无对应代码材料，可能触发补正。"
            )

    return write_gate(workdir, "code-selection", note)


def parse_screenshot_method(method: str, note: str) -> str:
    value = (method or note or "").lower()
    if any(key in value for key in ("skip", "no-screenshot", "none", "不截图", "跳过", "暂不", "先不", "不要截图", "无需截图")):
        return "skip"
    if any(key in value for key in ("chrome", "devtools", "mcp")):
        return "chrome-devtools"
    if any(key in value for key in ("computer", "use", "电脑", "桌面")):
        return "computer-use"
    if any(key in value for key in ("user", "manual", "self", "手动", "自己", "用户")):
        return "user-supplied"
    raise SystemExit(
        "STOP_FOR_USER\n"
        "NEXT_ACTION: 请明确截图方式：chrome-devtools、computer-use、user-supplied 或 skip。"
    )


def confirm_screenshot_method(workdir: Path, note: str, method: str) -> Path:
    selected = parse_screenshot_method(method, note)
    return write_gate(workdir, "screenshot-method", note, method=selected)


def confirm_application_fields(workdir: Path, note: str) -> Path:
    pending = pending_application_fields(workdir / "草稿/申请表信息.md")
    if pending:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 申请表信息仍包含[待用户确认]。请先补全字段,再重新确认。\n"
            + "\n".join(f"- {item}" for item in pending[:20])
        )
    return write_gate(workdir, "application-fields", note)


def confirm_content_quality(workdir: Path, note: str) -> Path:
    """Record content-quality gate after running the actual checker.

    The content_quality_check.py script is invoked as a subprocess.  If it
    fails (exit != 0) the gate is NOT recorded — the model must fix issues
    and re-run.
    """
    manual_path = workdir / "草稿/操作手册.md"
    if not manual_path.exists():
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 操作手册草稿不存在，请先生成操作手册后再确认 content-quality 门禁。"
        )

    checker = (
        Path(__file__).resolve().parent / "content_quality_check.py"
    )
    result = subprocess.run(
        [sys.executable, str(checker), "--manual", str(manual_path)],
        capture_output=True,
        text=True,
    )
    # Print checker output so it's visible in the transcript
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: content_quality_check 未通过（见上方输出）。请修复问题后重新运行。"
        )

    return write_gate(workdir, "content-quality", note)


def confirm_diagrams(workdir: Path, note: str) -> Path:
    """Verify that the 4 overview + module flow diagram PNGs exist in 截图/."""
    screenshot_dir = workdir / "截图"
    required_overviews = ["系统架构图", "功能模块图", "核心业务流程图", "数据模型关系图"]

    missing = []
    for name in required_overviews:
        png = screenshot_dir / f"{name}.png"
        if not png.exists() or png.stat().st_size == 0:
            missing.append(str(png))

    # Count module flow diagrams (those containing "操作流程")
    if screenshot_dir.exists():
        flow_pngs = list(screenshot_dir.glob("*操作流程*.png"))
        valid_flows = [p for p in flow_pngs if p.stat().st_size > 0]
    else:
        valid_flows = []

    if missing:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 以下总图 PNG 缺失或为空：\n"
            + "\n".join(f"- {m}" for m in missing)
            + f"\n当前流程图数量：{len(valid_flows)}\n"
            "请生成全部 4 张总图并为每个核心功能模块生成操作流程图后重试。"
        )

    if len(valid_flows) < 4:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 模块操作流程图数量不足（当前 {len(valid_flows)}，需 ≥4）。请为每个核心功能模块生成操作流程图后重试。"
        )

    return write_gate(workdir, "diagrams", note,
                       overview_count=len(required_overviews),
                       flow_count=len(valid_flows))


def confirm_markdown(workdir: Path, note: str) -> Path:
    gates = load_gates(workdir)
    gate_names = ["business", "code-selection", "screenshot-method", "application-fields", "diagrams"]
    gate_labels = {
        "business": "业务理解尚未确认",
        "code-selection": "代码文件选择尚未确认",
        "screenshot-method": "截图方式尚未确认",
        "application-fields": "申请表字段尚未确认",
        "diagrams": "技术图表尚未生成",
    }
    issues = [gate_labels[g] for g in gate_names if not gates.get(g, {}).get("confirmed")]
    pending = pending_application_fields(workdir / "草稿/申请表信息.md")
    if pending:
        issues.append("申请表信息仍包含[待用户确认]")

    if issues:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: Markdown 草稿确认前需要先处理以下事项：\n"
            + "\n".join(f"- {item}" for item in issues)
        )

    # ── Cooldown check: prevent rapid-fire confirmations ──
    from datetime import datetime, timezone, timedelta
    COOLDOWN_SECONDS = 5
    now = datetime.now(timezone.utc)
    for gate_name, entry in gates.items():
        if gate_name == "markdown":
            continue
        at_str = (entry or {}).get("confirmed_at", "")
        if not at_str:
            continue
        try:
            at = datetime.fromisoformat(at_str)
        except ValueError:
            continue
        # If any recent (non-markdown) gate was confirmed within the cooldown
        # window and its timestamp is close to NOW (not a stale old gate), flag it
        delta = (now - at).total_seconds()
        if 0 < delta < COOLDOWN_SECONDS:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"NEXT_ACTION: Markdown 门禁冷静期不足（上一门禁 {gate_name} 于 {delta:.0f} 秒前确认）。"
                f"请在实际阅读草稿、检查一致性后再确认 markdown 门禁——不要在同一 turn 连续确认。"
            )

    return write_gate(workdir, "markdown", note)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", help="Task workdir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "environment", "project", "business", "code-selection",
            "screenshot-method", "application-fields", "markdown",
            "content-quality", "diagrams",
        ],
    )
    parser.add_argument("--note", default="用户已确认")
    parser.add_argument(
        "--method",
        choices=["chrome-devtools", "computer-use", "user-supplied", "skip"],
        help="Screenshot capture method when --stage screenshot-method",
    )
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    parser.add_argument("--json", action="store_true", help="Output structured JSON instead of plain text")
    args = parser.parse_args()

    workdir = Path(args.workdir) if args.workdir else resolve_workdir(args.task_dir)

    confirm_params({"工作目录": str(workdir), "门禁阶段": args.stage, "备注": args.note}, args.confirm)
    if args.stage == "environment":
        path = confirm_environment(workdir, args.note)
    elif args.stage == "project":
        path = confirm_project(workdir, args.note)
    elif args.stage == "business":
        path = confirm_business(workdir, args.note)
    elif args.stage == "code-selection":
        path = confirm_code_selection(workdir, args.note)
    elif args.stage == "screenshot-method":
        path = confirm_screenshot_method(workdir, args.note, args.method or "")
    elif args.stage == "application-fields":
        path = confirm_application_fields(workdir, args.note)
    elif args.stage == "content-quality":
        path = confirm_content_quality(workdir, args.note)
    elif args.stage == "diagrams":
        path = confirm_diagrams(workdir, args.note)
    else:
        path = confirm_markdown(workdir, args.note)

    if args.json:
        import json
        result = {
            "stage": args.stage,
            "confirmed": True,
            "path": str(path.resolve()),
            "note": args.note,
        }
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"OK confirmation recorded: {args.stage}")
        print(path)


if __name__ == "__main__":
    main()
