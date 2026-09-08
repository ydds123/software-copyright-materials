#!/usr/bin/env python3
"""事实断言表候选生成：从业务理解 manual_modules 提取数量/枚举候选，模型确认后并入计划。

Usage:
    propose_fact_assertions.py --business 草稿/业务理解.json --out-dir 草稿
输出: 草稿/事实断言表.json（候选，含 source 与依据文本，待模型确认/修正 value）
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Draft fact-assertion candidates from business context for logic-consistency gate."

import argparse
import json
import re
import sys
from pathlib import Path

PATTERNS = [
    (re.compile(r'(四|五|六|七|八|九|十|\d+)\s*(种|类|个|级|项|步|道|条)'), 'count'),
    (re.compile(r'(四|五|六|七|八|九|十|\d+)\s*(状态|阶段|角色|视图|场景|方式)'), 'count'),
]
CN_NUM = {'四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def to_num(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    return CN_NUM.get(s)


def extract(text: str, kind: str) -> list[str]:
    hits = []
    for pat, k in PATTERNS:
        for m in pat.finditer(text):
            n = to_num(m.group(1))
            if n is not None and 1 <= n <= 60:
                seg = text[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ')
                hits.append(f'{m.group(1)}{m.group(2)}（{kind}，上下文: …{seg}…）')
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--business', required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    biz = json.loads(Path(args.business).read_text(encoding='utf-8'))
    out: list[dict] = []
    fid = 0
    for m in biz.get('manual_modules', []):
        title = str(m.get('title') or '?')
        blobs = []
        for k, v in m.items():
            if k in ('evidence', 'title'):
                continue
            if isinstance(v, str):
                blobs.append(v)
        text = '\n'.join(blobs)
        for kind in ('模块',):
            for hit in extract(text, title):
                fid += 1
                out.append({
                    'fact_id': f'T-{fid:03d}',
                    'subject': title,
                    'predicate': '数量',
                    'value': None,
                    'source': 'business_context',
                    'source_ref': hit,
                    'document_locations': [],
                    'type': 'count',
                    'status': 'candidate',
                })
    result = {
        'schema_version': '1.0',
        'note': '候选断言由脚本从业务理解中提取数量表述，value 为空表示待模型确认；'
                '无来源的断言不得进入材料证据计划。确认后合并入 材料证据计划.json 的 fact_assertions。',
        'assertions': out,
    }
    out_path = Path(args.out_dir) / '事实断言表.json'
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'OK fact assertions: {len(out)} 条候选 -> {out_path}')
    for a in out[:12]:
        print(f"  {a['fact_id']} [{a['subject']}] {a['source_ref'][:70]}")


if __name__ == '__main__':
    main()
