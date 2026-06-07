#!/usr/bin/env python3
"""Check runtime capabilities at the beginning of the workflow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from common import confirm_params, ensure_dir, resolve_task_dir, resolve_workdir, write_json


def resolve_command(command_name: str) -> str:
    if os.name != "nt":
        return command_name

    lower_name = command_name.lower()
    if lower_name == "dotnet":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet/dotnet.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "dotnet/dotnet.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

    # Generic Windows: try .cmd/.exe extensions for common CLI tools
    if lower_name in ("lark-cli", "npx"):
        for ext in (".cmd", ".exe"):
            candidate = command_name + ext
            try:
                subprocess.run(
                    [candidate, "--version"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=10,
                )
                # resolve_command only returns the name used for invocation; shell=True not needed
                return candidate
            except Exception:
                continue

    return command_name


def command_version(command: list[str]) -> tuple[bool, str]:
    try:
        resolved = [resolve_command(command[0]), *command[1:]]
        completed = subprocess.run(
            resolved,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
        )
        output = (completed.stdout or completed.stderr).strip().splitlines()
        return completed.returncode == 0, output[0] if output else "available"
    except Exception as exc:
        return False, str(exc)


def command_output(command: list[str]) -> tuple[bool, str]:
    try:
        resolved = [resolve_command(command[0]), *command[1:]]
        completed = subprocess.run(
            resolved,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )
        output = (completed.stdout or completed.stderr).strip()
        return completed.returncode == 0, output or "available"
    except Exception as exc:
        return False, str(exc)


def check_lark_user_auth() -> tuple[bool, str]:
    ok, output = command_output(["lark-cli", "auth", "status", "--verify"])
    if not ok:
        return False, output
    try:
        status = json.loads(output)
    except json.JSONDecodeError:
        return False, output
    ready = status.get("identity") == "user" and status.get("tokenStatus") == "valid"
    if ready:
        return True, f"user token valid: {status.get('userName', 'unknown user')}"
    return False, str(status.get("note") or f"identity={status.get('identity')}, tokenStatus={status.get('tokenStatus')}")


def is_feishu_document_target(value: str | None) -> bool:
    target = (value or "").strip()
    if not target:
        return False
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", target):
        return True
    parsed = urlparse(target)
    host = parsed.netloc.lower()
    valid_host = host.endswith(".feishu.cn") or host.endswith(".larksuite.com") or host.endswith(".larkoffice.com")
    valid_path = any(part in parsed.path for part in ("/docx/", "/docs/", "/wiki/"))
    return parsed.scheme in ("http", "https") and valid_host and valid_path


def major_version(version: str) -> int:
    try:
        return int(version.strip().split(".", 1)[0])
    except (ValueError, IndexError):
        return 0


def run_docx_env_windows(skill_dir: Path) -> tuple[bool, str]:
    dotnet_ok, dotnet_version = command_version(["dotnet", "--version"])
    if not dotnet_ok:
        return False, f"dotnet not ready: {dotnet_version}"
    if major_version(dotnet_version) < 8:
        return False, f"dotnet {dotnet_version} found, requires >= 8.0"

    dotnet_dir = skill_dir / "vendor/docx-toolkit/scripts/dotnet"
    cli_project = dotnet_dir / "DocxToolkit.Cli/DocxToolkit.Cli.csproj"
    if not cli_project.exists():
        return False, f"CLI project file not found: {cli_project}"

    built_outputs = [
        dotnet_dir / "DocxToolkit.Cli/bin/Debug/net10.0/DocxToolkit.Cli.dll",
        dotnet_dir / "DocxToolkit.Cli/bin/Debug/net8.0/DocxToolkit.Cli.dll",
    ]
    if any(path.exists() for path in built_outputs):
        return True, f"Windows native check OK: dotnet {dotnet_version}; project built"

    dotnet_command = resolve_command("dotnet")
    restore = subprocess.run(
        [dotnet_command, "restore", str(cli_project), "--verbosity", "quiet"],
        text=True,
        capture_output=True,
        timeout=120,
    )
    if restore.returncode != 0:
        return False, "NuGet restore failed:\n" + (restore.stdout + restore.stderr).strip()

    build = subprocess.run(
        [dotnet_command, "build", str(cli_project), "--verbosity", "quiet", "--no-restore"],
        text=True,
        capture_output=True,
        timeout=120,
    )
    if build.returncode != 0:
        return False, "Build failed:\n" + (build.stdout + build.stderr).strip()

    return True, f"Windows native check OK: dotnet {dotnet_version}; restore/build succeeded"


def run_docx_env(skill_dir: Path) -> tuple[bool, str]:
    if os.name == "nt":
        return run_docx_env_windows(skill_dir)

    env_script = skill_dir / "vendor/docx-toolkit/scripts/env_check.sh"
    if not env_script.exists():
        return False, "vendor/docx-toolkit/scripts/env_check.sh not found"
    try:
        completed = subprocess.run(["bash", str(env_script)], text=True, capture_output=True, timeout=40)
        return completed.returncode == 0, (completed.stdout + completed.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_environment(skill_dir: Path, feishu_doc: str = "", skip_feishu: bool = False) -> dict[str, Any]:
    python_docx = module_available("docx")
    pandoc_ok, pandoc_version = command_version(["pandoc", "--version"])
    dotnet_ok, dotnet_version = command_version(["dotnet", "--version"])
    docx_ready, docx_output = run_docx_env(skill_dir)

    lark_cli_ok, lark_cli_version = command_version(["lark-cli", "--version"])
    lark_user_auth_ok, lark_user_auth_status = (
        (False, "skipped")
        if skip_feishu
        else (check_lark_user_auth() if lark_cli_ok else (False, "lark-cli not installed"))
    )
    whiteboard_cli_ok, whiteboard_cli_version = (
        (False, "skipped")
        if skip_feishu
        else command_version(["npx", "-y", "@larksuite/whiteboard-cli@^0.2.10", "-v"])
    )
    feishu_doc = feishu_doc.strip()
    feishu_doc_ready = is_feishu_document_target(feishu_doc)
    charts_ready = not skip_feishu and lark_cli_ok and lark_user_auth_ok and whiteboard_cli_ok and feishu_doc_ready

    final_docx_mode = "docx-openxml" if docx_ready else ("python-docx" if python_docx else "basic-ooxml")
    action_items: list[str] = []
    if not docx_ready:
        action_items.append("选择安装完整 DOCX 环境，或确认使用基础 DOCX 兜底")
    if not skip_feishu:
        if not lark_cli_ok:
            action_items.append("安装并配置 lark-cli，或明确选择 --skip-feishu")
        elif not lark_user_auth_ok:
            action_items.append("运行 lark-cli auth login --recommend 完成用户授权，或明确选择 --skip-feishu")
        if not whiteboard_cli_ok:
            action_items.append("确认 npx 可调用 @larksuite/whiteboard-cli，或明确选择 --skip-feishu")
        if not feishu_doc_ready:
            action_items.append("用 --feishu-doc 指定可编辑的飞书在线文档 URL/token，或明确选择 --skip-feishu")
    requires_user_input = bool(action_items)
    next_action = "；".join(action_items) if action_items else "环境检查通过，可以进入项目分析。"
    return {
        "output_directory": "项目目录/<年份>年软件著作权申请资料/<软件名称>/",
        "capabilities": {
            "markdown_drafts": True,
            "application_txt": True,
            "basic_docx": python_docx or True,
            "python_docx": python_docx,
            "pandoc_preview": pandoc_ok,
            "docx_openxml_full": docx_ready,
            "dotnet_sdk": dotnet_ok,
            "lark_cli": lark_cli_ok,
            "lark_user_auth": lark_user_auth_ok,
            "whiteboard_cli": whiteboard_cli_ok,
            "feishu_target_document": feishu_doc_ready,
            "feishu_charts": charts_ready,
            "feishu_skipped": skip_feishu,
        },
        "versions": {
            "pandoc": pandoc_version,
            "dotnet": dotnet_version,
            "lark_cli": lark_cli_version,
            "whiteboard_cli": whiteboard_cli_version,
        },
        "feishu": {
            "target_document": feishu_doc or None,
            "target_document_valid": feishu_doc_ready,
            "user_auth_status": lark_user_auth_status,
            "skipped": skip_feishu,
        },
        "final_docx_mode": final_docx_mode,
        "recommendation": (
            "完整 DOCX OpenXML 环境已就绪，建议使用完整 Word 生成和校验流程。"
            if docx_ready
            else "完整 DOCX OpenXML 环境未就绪。可以继续使用兜底 DOCX 生成；如需更规范的 Word 结构和校验，请先安装 .NET SDK 并运行 vendor/docx-toolkit/scripts/setup.sh。"
        ),
        "install_prompt": (
            "是否安装完整 DOCX 环境？安装后文档生成和校验更规范；不安装也可以继续生成 Markdown、TXT 和基础 DOCX。"
            if not docx_ready
            else "无需安装，完整环境可用。"
        ),
        "requires_user_input": requires_user_input,
        "confirmation_stage": "environment" if requires_user_input else None,
        "next_action": next_action,
        "pending_actions": action_items,
        "docx_env_output": docx_output,
    }


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    caps = data["capabilities"]
    lines = [
        "# 软著申请资料生成环境检查",
        "",
        f"- 输出目录：`{data['output_directory']}`",
        f"- 最终 Word 模式：`{data['final_docx_mode']}`",
        "",
        "## 能力状态",
        "",
        f"- Markdown 草稿：{'可用' if caps['markdown_drafts'] else '不可用'}",
        f"- 申请表 TXT：{'可用' if caps['application_txt'] else '不可用'}",
        f"- 基础 DOCX 生成：{'可用' if caps['basic_docx'] else '不可用'}",
        f"- python-docx：{'可用' if caps['python_docx'] else '不可用'}",
        f"- pandoc 预览：{'可用' if caps['pandoc_preview'] else '不可用'}（{data['versions']['pandoc']}）",
        f"- .NET SDK：{'可用' if caps['dotnet_sdk'] else '不可用'}（{data['versions']['dotnet']}）",
        f"- DOCX OpenXML 完整环境：{'可用' if caps['docx_openxml_full'] else '不可用'}",
        "",
        "## 飞书两步检查",
        "",
        "### 第一步：CLI 与用户授权",
        "",
        f"- lark-cli：{'可用' if caps['lark_cli'] else '不可用'}（{data['versions']['lark_cli']}）",
        f"- 用户授权：{'已跳过检查' if caps['feishu_skipped'] else ('有效' if caps['lark_user_auth'] else '无效或未登录')}（{data['feishu']['user_auth_status']}）",
        f"- whiteboard-cli：{'已跳过检查' if caps['feishu_skipped'] else ('可用' if caps['whiteboard_cli'] else '不可用')}（{data['versions']['whiteboard_cli']}）",
        "",
        "### 第二步：目标在线文档",
        "",
        f"- 已指定目标文档：{'是' if caps['feishu_target_document'] else '否'}",
        f"- 目标文档：`{data['feishu']['target_document'] or '未指定'}`",
        f"- 跳过飞书图表：{'是' if caps['feishu_skipped'] else '否'}",
        f"- 飞书画板图表环境：{'可用' if caps['feishu_charts'] else '不可用 — 未显式跳过时需先处理上述缺项'}",
        "",
        "## 建议",
        "",
        data["recommendation"],
        "",
        "## 用户选择",
        "",
        data["install_prompt"],
        "",
        "如果存在待处理项，必须先等待用户选择，并记录 `environment` 门禁后再继续。",
        "",
        "```text" if data.get("requires_user_input") else "",
        "STOP_FOR_USER" if data.get("requires_user_input") else "",
        f"NEXT_ACTION: {data['next_action']}" if data.get("requires_user_input") else "",
        "```" if data.get("requires_user_input") else "",
        "",
        "## DOCX 环境输出摘要",
        "",
        "```text",
        "\n".join(data["docx_env_output"].splitlines()[:40]),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", help="Output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--feishu-doc", default="", help="Editable Feishu document URL or token used to hold whiteboards")
    parser.add_argument("--skip-feishu", action="store_true", help="Explicitly skip Feishu whiteboard diagrams")
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    task_dir = args.task_dir
    if not task_dir:
        found = resolve_task_dir()
        task_dir = str(found) if found else None
    out_dir = Path(args.out_dir) if args.out_dir else (resolve_workdir(task_dir) if task_dir else None)
    if out_dir is None:
        raise SystemExit("找不到任务目录。请用 --task-dir 指定。")
    ensure_dir(out_dir)

    confirm_params(
        {
            "输出目录": str(out_dir),
            "任务目录": str(task_dir or out_dir.parent),
            "飞书目标文档": args.feishu_doc or "未指定",
            "跳过飞书图表": "是" if args.skip_feishu else "否",
        },
        args.confirm,
    )

    data = check_environment(skill_dir, args.feishu_doc, args.skip_feishu)
    write_json(out_dir / "环境检查.json", data)
    write_markdown(out_dir / "环境检查.md", data)
    print(f"OK environment check: {out_dir}")
    print(f"Final DOCX mode: {data['final_docx_mode']}")
    print(data["recommendation"])
    if data.get("requires_user_input"):
        print("STOP_FOR_USER")
        print(f"NEXT_ACTION: {data['next_action']}")


if __name__ == "__main__":
    main()
