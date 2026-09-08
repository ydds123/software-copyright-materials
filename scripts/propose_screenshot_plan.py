#!/usr/bin/env python3
"""Screenshot acquisition plan (v1.6): derive the per-module screenshot checklist.

Background doc priority #1: screenshots are the strongest "real software" evidence.
The checklist is surfaced at material-plan stage (early trigger), before any
document prose is written. Humans take the shots; this tool only enumerates
what each module needs, so the manual author knows exactly what to ask for.

Output: 草稿/截图拍摄清单.md
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Early screenshot checklist derivation at material-plan stage."

import argparse
import json
import sys
from pathlib import Path

OVERVIEW_SHOTS = ["系统架构图", "功能模块图", "核心业务流程图", "数据模型关系图"]

def module_shots(m: dict) -> list[str]:
    t = m.get("module_type", "registry")
    name = m.get("title") or m.get("module_name") or m.get("name") or "未命名模块"
    if t == "business":
        return [
            f"{name}：发起/待办列表页（真实数据）",
            f"{name}：处理表单页（含真实字段与必填项）",
            f"{name}：流转结果/详情页（状态已变更）",
        ]
    if t == "hybrid":
        return [
            f"{name}：配置维护列表页（真实数据）",
            f"{name}：配置表单页（含输入边界）",
            f"{name}：配置生效后的下游效果页",
        ]
    if t == "app":
        return [
            f"{name}：APP 首页/列表页（真实设备截图）",
            f"{name}：APP 关键交互页（拍照/NFC/GPS 等交互）",
            f"{name}：APP 操作结果/失败提示页",
        ]
    if t == "screen":
        return [
            f"{name}：大屏整体布局页（真实数据）",
            f"{name}：大屏局部刷新/联动效果页",
        ]
    return [
        f"{name}：列表页（真实数据）",
        f"{name}：新增/修改表单页（含字段与必填项）",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    business = json.loads(Path(args.business).read_text(encoding="utf-8"))
    modules = business.get("manual_modules", [])
    out = ["# 截图拍摄清单", "",
           "用途：文档鉴别材料中的真实界面截图（驳回原因 4 的直接修复项）。",
           "拍摄要求：真实环境 + 真实业务数据（禁止空状态凑数）；涉及企业名称/姓名/手机号打码；",
           "关键操作用红框+序号标注；截图下方配图注（如“图 6-1 巡检点管理列表界面”）。",
           ""]
    out.append("## 总图（4 张，流程类）")
    for s in OVERVIEW_SHOTS:
        out.append(f"- [ ] {s}")
    out.append("")
    out.append("## 各模块截图")
    total = 0
    for m in modules:
        shots = module_shots(m)
        total += len(shots)
        out.append(f"### {m.get('title') or m.get('module_name') or '未命名模块'}")
        for s in shots:
            out.append(f"- [ ] {s}")
    out.append("")
    out.append(f"合计建议：总图 4 张 + 模块图 {total} 张。按背景文档建议量级（25-35 张）执行，无法截图的模块（后台任务/推送等）在证据计划中声明豁免并附日志截图。")
    out_path = Path(args.out_dir) / "截图拍摄清单.md"
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"OK screenshot plan: {out_path}（总图 4 + 模块 {total} 张）")


if __name__ == "__main__":
    main()
