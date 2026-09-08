#!/usr/bin/env python3
"""实质注释清单（v1.6）：检测 A 级选中文件的算法关键点是否有设计意图注释。

规则（防游戏）：注释只影响"待补清单"，不影响证据等级（grade）。
算法关键点判定：函数定义前 3 行内是否存在含设计语义词的注释
（判定/规则/算法/策略/时间窗/回退/归并/路径/模板/条件/分支/去重/流转/聚合）。
输出: 草稿/待补注释清单.md（人工补充，不改业务逻辑）。
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Detect A-grade files lacking design-intent comments (human follow-up list)."

import argparse
import json
import re
import sys
from pathlib import Path

SEMANTIC = ('判定', '规则', '算法', '策略', '时间窗', '回退', '归并', '路径', '模板',
            '条件', '分支', '去重', '流转', '聚合', '窗口', '责任链', '校验')
FN_RE = re.compile(r'^\s*(public|private|protected)?\s*(static\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\(|^\s*(const|function)\s+([A-Za-z_$][\w$]*)\s*[=(]')


def has_design_comment(lines: list[str], fn_line: int) -> bool:
    for i in range(max(0, fn_line - 3), fn_line):
        s = lines[i].strip()
        if not s.startswith(('//', '/*', '*', '/**')):
            continue
        if any(w in s for w in SEMANTIC):
            return True
    return False


def scan_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    gaps = []
    for i, l in enumerate(lines):
        m = FN_RE.match(l)
        if not m:
            continue
        name = m.group(3) or m.group(5)
        if not name or name[0].isupper():
            continue
        if not has_design_comment(lines, i):
            gaps.append({'line': i + 1, 'fn': name, 'text': l.strip()[:80]})
    return gaps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    roots = {r.get('root_id'): Path(r.get('path')) for r in plan.get('input_roots', [])}
    out_lines = ['# 待补注释清单（实质设计意图注释）', '',
                 '规则：A 级选中文件的算法关键函数前缺少设计意图注释；补充注释不改业务逻辑、不影响证据等级。',
                 '']
    total = 0
    for e in plan.get('code_evidence', []):
        if not e.get('selected') or e.get('grade') not in ('A',):
            continue
        root = roots.get(e.get('root_id'))
        if root is None:
            continue
        p = root / e['path']
        if not p.exists():
            continue
        gaps = scan_file(p)
        if not gaps:
            continue
        out_lines.append(f"## {e['path']}")
        for g in gaps[:8]:
            total += 1
            out_lines.append(f"- 第 {g['line']} 行 `{g['fn']}`：{g['text']}")
        if len(gaps) > 8:
            out_lines.append(f"- …另有 {len(gaps) - 8} 处")
        out_lines.append('')
    out_lines.append(f'共 {total} 处待补（建议优先补核心算法函数，每条注释说明设计意图/判定依据）。')
    out = Path(args.out_dir) / '待补注释清单.md'
    out.write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'OK comment gaps: {total} 处 -> {out}')


if __name__ == '__main__':
    main()
