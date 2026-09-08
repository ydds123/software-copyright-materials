#!/usr/bin/env python3
"""材料-源码时效校验：比对代码提取清单与当前源码，报告过期文件。

Usage:
    verify_material_currency.py --manifest 草稿/代码提取清单.json [--project <根>]
Exit 0: 材料与当前源码一致；Exit 1: 有文件过期（或清单损坏）。

这是回归防线 #1：防止"抽取后源码变更导致材料过期"。
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Material-currency regression gate invoked before final artifact build."

import argparse
import sys
from pathlib import Path


def load_manifest(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding='utf-8'))


def check(manifest: dict, roots: dict | None = None) -> tuple[list[dict], list[str]]:
    changed: list[dict] = []
    errors: list[str] = []
    project = Path(manifest.get('project_root', '.'))
    # v2 多根：优先按文件自身的 root_id 解析，其次依次尝试各根，最后回落 project
    for item in manifest.get('files', []):
        rel = item.get('path', '')
        p = None
        rid = item.get('root_id', '')
        if roots and rid and rid in roots:
            cand = Path(roots[rid]) / rel
            if cand.exists():
                p = cand
        if p is None:
            p = project / rel
            if not p.exists() and roots:
                for rid2, rpath in roots.items():
                    cand = Path(rpath) / rel
                    if cand.exists():
                        p = cand
                        break
        if not p.exists():
            errors.append(f"源文件不存在: {rel}")
            continue
        current = p.read_text(encoding='utf-8', errors='replace').splitlines()
        recorded = int(item.get('source_line_count') or 0)
        sel_end = int(item.get('selected_line_end') or 0)
        if len(current) != recorded:
            changed.append({
                'path': item.get('path'),
                'recorded_lines': recorded,
                'current_lines': len(current),
            })
        elif sel_end > len(current):
            changed.append({
                'path': item.get('path'),
                'recorded_lines': recorded,
                'current_lines': len(current),
                'note': 'selected_line_end 超出当前文件行数',
            })
    return changed, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--plan', default=None, help='v2 材料证据计划.json（提供 input_roots 多根解析）')
    args = parser.parse_args()
    manifest = load_manifest(Path(args.manifest))
    roots = None
    if args.plan:
        import json as _json
        plan = _json.loads(Path(args.plan).read_text(encoding='utf-8'))
        roots = {r.get('root_id'): r.get('path') for r in plan.get('input_roots', [])}
    changed, errors = check(manifest, roots)
    for e in errors:
        print(f'ERROR: {e}')
    if changed:
        print(f'MATERIAL OUTDATED: {len(changed)} 个文件与当前源码不一致：')
        for c in changed:
            print(f"  - {c['path']}: 清单 {c['recorded_lines']} 行, 当前 {c['current_lines']} 行")
        sys.exit(1)
    print(f'MATERIAL CURRENT: {manifest.get("file_count", len(manifest.get("files", [])))} 个文件与当前源码一致')
    sys.exit(0 if not errors else 1)


if __name__ == '__main__':
    main()
