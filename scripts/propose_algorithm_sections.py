#!/usr/bin/env python3
"""Algorithm section material proposer (v1.6).

Derives 核心算法章节素材 from the *selected* A-grade code evidence in
材料证据计划.json. The model writes the design/manual prose from this
material — the material itself lists real file paths, functions and
design-signal comments, so invented content can be caught by fact checks.

Output: 草稿/算法章节素材.md (reference only, never submitted as-is).
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Ground design-document algorithm chapters in selected A-grade code evidence."

import argparse
import json
import re
import sys
from pathlib import Path

METHOD_RE = re.compile(r'^\s*(public|private|protected)?\s*(static\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*(\{|;)')
VUE_FN_RE = re.compile(r'^\s*(const|function)\s+([A-Za-z_$][\w$]*)\s*(=|\().*=>')
CLASS_RE = re.compile(r'^\s*(public\s+)?(class|interface|enum)\s+([A-Za-z_$][\w$]*)')
DESIGN_RE = re.compile(r'(判定|规则|算法|策略|时间窗|回退|归并|路径|模板|去重|流转|聚合|窗口|责任链|校验|优先级|维度)')


def scan(path: Path) -> dict:
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    classes, methods, notes = [], [], []
    for i, l in enumerate(lines):
        m = CLASS_RE.match(l)
        if m:
            classes.append((i + 1, m.group(3)))
        if '=' in l:
            continue  # Vue 指令/箭头函数/赋值行不是方法定义
        m = METHOD_RE.match(l)
        if m:
            methods.append((i + 1, m.group(3)))
        if '//' in l or '/*' in l or '*' in l[:3]:
            if DESIGN_RE.search(l):
                notes.append((i + 1, l.strip()[:90]))
    return {"lines": len(lines), "classes": classes, "methods": methods, "notes": notes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    roots = {r.get('root_id'): Path(r.get('path')) for r in plan.get('input_roots', [])}

    out = ["# 核心算法章节素材（撰写参考，不直接提交）", "",
           "本文件由 A 级代码证据自动汇总。撰写设计文档/手册时：",
           "- 每段设计描述必须能对应到下列真实文件与函数；",
           "- 不得编造不存在的数据结构、算法或流程；",
           "- 素材中的函数名/类名/行号用于撰写时核对，不写入正文（正文面向用户，不出现代码标识符）。",
           ""]
    for e in plan.get('code_evidence', []):
        if not e.get('selected') or e.get('grade') != 'A':
            continue
        root = roots.get(e.get('root_id'))
        if root is None:
            continue
        p = root / e['path']
        if not p.exists():
            continue
        d = scan(p)
        out.append(f"## {e['path']}（{d['lines']} 行）")
        if d['classes']:
            out.append(f"- 类型: {', '.join(f'{n}@{ln}' for ln, n in d['classes'][:6])}")
        fns = [f"{n}@{ln}" for ln, n in d['methods'][:14]]
        out.append(f"- 关键函数: {', '.join(fns)}{'…' if len(d['methods']) > 14 else ''}")
        for ln, note in d['notes'][:6]:
            out.append(f"- 设计信号(第{ln}行): {note}")
        out.append("")

    out.append("## 写入建议（按文档类型）")
    out.append("- design_description/hybrid：将每组证据转写为「设计依据/数据结构选择/判定条件/边界处理」四段式，禁止照抄注释。")
    out.append("- user_manual：只取用户可感知的行为（条件、时限、反馈），不写内部结构。")
    out_path = Path(args.out_dir) / "算法章节素材.md"
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"OK algorithm material: {out_path}")


if __name__ == "__main__":
    main()
