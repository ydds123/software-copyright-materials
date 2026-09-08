#!/usr/bin/env python3
"""前后30页模块覆盖校验：每个模块的 evidence 在提交页内至少出现 min-lines 行。

Usage:
    verify_coverage_in_pages.py --material 草稿/代码-前后30页.md --business 草稿/业务理解.json \
        [--manifest 草稿/代码提取清单.json] [--min-lines N]

判定（有 manifest 时按行范围交集精确计算，无 manifest 时按 marker 位置）：
- front30 = 行 [1, 1500]；back30 = 行 [back_start, material_line_count]，back_start=(页数-30)*50+1
- 模块覆盖 = 任一 evidence 文件与 front/back 的交集 ≥ min-lines

Exit 0: 全部模块覆盖充分；Exit 1: 存在缺口。
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Front/back 30-page coverage regression gate invoked after extraction."

import argparse
import json
import math
import sys
from pathlib import Path


def _norm(p: str) -> str:
    return str(p).replace('\\', '/')


def check_with_manifest(business: dict, manifest: dict, min_lines: int) -> tuple[list[str], list[str]]:
    total = int(manifest.get('material_line_count') or 0)
    pages = math.ceil(total / 50)
    front_end = 1500
    back_start = (pages - 30) * 50 + 1
    mfiles = {_norm(f.get('path', '')): f for f in manifest.get('files', [])}
    ok: list[str] = []
    problems: list[str] = []
    for m in business.get('manual_modules', []):
        title = str(m.get('title') or '?')
        evidence = [_norm(e) for e in (m.get('evidence') or [])]
        if not evidence:
            continue
        best = 0
        matched = 0
        for e in evidence:
            f = None
            for p, cand in mfiles.items():
                if e == p or p.endswith(e) or e.endswith(p):
                    f = cand
                    break
            if f is None:
                continue
            matched += 1
            s = int(f.get('material_line_start') or 1)
            end = int(f.get('material_line_end') or 0)
            in_front = min(end, front_end) - s + 1
            in_back = min(end, total) - max(s, back_start) + 1
            vis = max(in_front, 0) + max(in_back, 0)
            best = max(best, vis)
        if matched == 0:
            problems.append(f"模块「{title}」的 evidence 文件不在提取清单中")
        elif best < min_lines:
            problems.append(f"模块「{title}」evidence 在提交页内出现不足（最多 {best} 行，要求 ≥{min_lines}）")
        else:
            ok.append(f"{title}: 最多露出 {best} 行")
    return ok, problems


def check_marker(material_text: str, business: dict, min_lines: int) -> tuple[list[str], list[str]]:
    lines = material_text.split('\n')
    markers: dict[str, tuple[int, int]] = {}
    current = None
    start = 0
    for i, line in enumerate(lines):
        if line.startswith('// File: '):
            if current:
                markers[_norm(current)] = (start, i - start)
            current = line[len('// File: '):]
            start = i
    if current:
        markers[_norm(current)] = (start, len(lines) - start)
    marker_paths = set(markers)
    ok: list[str] = []
    problems: list[str] = []
    for m in business.get('manual_modules', []):
        title = str(m.get('title') or '?')
        evidence = [_norm(e) for e in (m.get('evidence') or [])]
        if not evidence:
            continue
        best = 0
        found = 0
        for e in evidence:
            if e in markers:
                found += 1
                best = max(best, markers[e][1] - 1)
                continue
            for mp in marker_paths:
                if mp.endswith(e) or e.endswith(mp):
                    found += 1
                    best = max(best, markers[mp][1] - 1)
                    break
        if found == 0:
            problems.append(f"模块「{title}」的 evidence 文件不在材料页内（可能被前30/后30裁掉）")
        elif best < min_lines:
            problems.append(f"模块「{title}」evidence 在材料中出现过少（最多 {best} 行，要求 ≥{min_lines}）")
        else:
            ok.append(f"{title}: 最多 {best} 行")
    return ok, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--material', required=True)
    parser.add_argument('--business', required=True)
    parser.add_argument('--manifest', default=None)
    parser.add_argument('--min-lines', type=int, default=20,
                        help='模块 evidence 在提交页内出现的最小行数')
    args = parser.parse_args()
    business = json.loads(Path(args.business).read_text(encoding='utf-8'))
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        ok, problems = check_with_manifest(business, manifest, args.min_lines)
    else:
        text = Path(args.material).read_text(encoding='utf-8')
        ok, problems = check_marker(text, business, args.min_lines)
    for o in ok:
        print(f'OK: {o}')
    if problems:
        print('COVERAGE GAP:')
        for p in problems:
            print(f'  - {p}')
        sys.exit(1)
    print('COVERAGE PASS: 全部模块 evidence 在提交页内有足够出现')
    sys.exit(0)


if __name__ == '__main__':
    main()
