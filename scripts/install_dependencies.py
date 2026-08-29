#!/usr/bin/env python3
"""Dependency detection and installation (external deps for this skill).

Checks the two optional external dependencies:
  1. human-writing skill (style checker) — installable from GitHub
  2. DeepSeek vision model key — configuration only, never downloaded

Modes:
  --check     report status only (exit 0 = all optional deps satisfied,
              1 = at least one missing, 2 = invalid usage)
  --install   install missing human-writing via git clone (requires git)
  --force     reinstall human-writing even if present

Portability note: nothing here is bound to a specific agent harness.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HUMAN_WRITING_REPO = "https://github.com/KKKKhazix/human-writing.git"


def human_writing_dir() -> Path:
    env = os.environ.get("HUMAN_WRITING_SKILL_DIR")
    if env:
        return Path(env)
    return Path.home() / ".agents" / "skills" / "human-writing"


def human_writing_installed() -> bool:
    d = human_writing_dir()
    return (d / "SKILL.md").exists() and (d / "scripts" / "check_prose.py").exists()


def deepseek_key_available() -> bool:
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return True
    for candidate in (
        Path.home() / ".pi" / "agent" / "models.json",
        Path.home() / ".deepseek" / "secrets" / "secrets.json",
    ):
        if candidate.exists():
            try:
                import json

                data = json.loads(candidate.read_text(encoding="utf-8"))
                if data.get("providers", {}).get("deepseek", {}).get("apiKey"):
                    return True
                if data.get("entries", {}).get("deepseek"):
                    return True
            except Exception:
                continue
    return False


def install_human_writing(force: bool = False) -> tuple[bool, str]:
    target = human_writing_dir()
    if target.exists() and not force:
        return True, f"已存在，跳过: {target}"
    if target.exists() and force:
        import shutil

        shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", HUMAN_WRITING_REPO, str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return False, f"git clone 失败: {(result.stderr or '').strip()[:400]}"
    # human-writing repo nests the skill under ./human-writing — move up if needed
    nested = target / "human-writing"
    if (nested / "SKILL.md").exists() and not (target / "SKILL.md").exists():
        import shutil

        tmp = target.parent / f".hw-move-{target.name}"
        shutil.move(str(nested), str(tmp))
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(tmp), str(target))
    if not human_writing_installed():
        return False, f"安装后校验失败: {target}（仓库结构异常，请手动安装）"
    return True, f"已安装: {target}"


def check_report() -> dict:
    hw_ok = human_writing_installed()
    key_ok = deepseek_key_available()
    report = {
        "human_writing": {"installed": hw_ok, "path": str(human_writing_dir())},
        "deepseek_vision_key": {"available": key_ok},
        "missing": [],
    }
    if not hw_ok:
        report["missing"].append("human-writing")
    if not key_ok:
        report["missing"].append("deepseek_vision_key")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查不安装")
    parser.add_argument("--install", action="store_true", help="自动安装缺失依赖")
    parser.add_argument("--force", action="store_true", help="强制重装 human-writing")
    args = parser.parse_args()

    report = check_report()

    print("依赖检查:")
    hw = report["human_writing"]
    print(f"  human-writing: {'已安装' if hw['installed'] else '缺失'} ({hw['path']})")
    print(f"  DeepSeek 视觉 key: {'可用' if report['deepseek_vision_key']['available'] else '未配置'}")

    if not report["missing"]:
        print("\n全部可选依赖就绪。")
        sys.exit(0)

    print("\n缺失依赖：")
    if "human-writing" in report["missing"]:
        print(f"  - human-writing（文风检查）：{HUMAN_WRITING_REPO}")
    if "deepseek_vision_key" in report["missing"]:
        print("  - DeepSeek 视觉 key（视觉语义判定）：设置环境变量 DEEPSEEK_API_KEY")
    print("\n说明：两项均为可选依赖。缺失时相关门禁降级为确定性检查 + 人工提示，不会静默放行。")

    if args.check:
        sys.exit(1)

    if args.install:
        if "human-writing" in report["missing"] or args.force:
            ok, msg = install_human_writing(force=args.force)
            print(f"\nhuman-writing 安装: {'OK' if ok else 'FAILED'}\n{msg}")
            if not ok:
                sys.exit(1)
        if "deepseek_vision_key" in report["missing"]:
            print("\nDeepSeek key 无法自动安装（需用户提供），请设置 DEEPSEEK_API_KEY。")
            sys.exit(1)
        print("\n依赖安装完成。")
        sys.exit(0)

    print("\nNEXT_ACTION: 运行 `--install` 自动安装，或手动安装后重试。")
    sys.exit(1)


if __name__ == "__main__":
    main()
