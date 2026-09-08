#!/usr/bin/env python3
"""编排求解器（v1.6）：给定选材与模块 evidence，求解抽取顺序使每模块至少一个
完整证据单元落在前30/后30页内；切点对齐文件边界。

算法（装箱构造式）：
1. 每核心模块收集完整证据单元候选（完整文件≤800行，或 line_range 行段）
2. 装箱：front(1500)/back(1500) 两箱，每模块至少一个单元入箱（优先小单元）
3. 剩余文件填充 front 尾部空隙、middle、back 头部空隙
4. 切点取文件边界（front∈[1451,1550]）
5. 无解 → 缺口清单 + 行段声明建议（触发 STOP）
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Layout solver: derive extraction order + front/back cut points from selection."

import argparse
import json
import sys
from pathlib import Path

MAX_UNIT_LINES = 800  # 兼容字段保留；v1.8 起完整文件一律作为单元，不再强制行段声明
FRONT_LO, FRONT_HI = 1451, 1550
CAPACITY = 1500          # 每段容量（30页×50行）
FRONT_POOL = ("primary", "web", "screen")  # 前端池：主前端/Web 管理端/大屏端；其余（backend）为后端池


def load_items(plan: dict) -> list[dict]:
    # evidence_id -> feature_ids 反向映射（features[].code_evidence）
    ev_to_fid: dict[str, list[str]] = {}
    for f in plan.get('features', []):
        for ev_id in (f.get('code_evidence') or []):
            ev_to_fid.setdefault(str(ev_id), []).append(str(f.get('feature_id')))
    items = []
    for e in plan.get('code_evidence', []):
        if not e.get('selected'):
            continue
        lr = e.get('line_range')
        lines = e.get('line_count') or 0
        unit = None
        if isinstance(lr, list) and len(lr) == 2:
            unit = int(lr[1]) - int(lr[0]) + 1
        else:
            # v1.8 完整文件拼装：不截取行段，整个文件作为证据单元
            unit = lines
        fids = ev_to_fid.get(str(e.get('evidence_id')), [])
        fids = fids or [str(x) for x in (e.get('mapped_features') or [])]
        items.append({
            'path': e['path'].replace('\\', '/'),
            'lines': lines,
            'grade': e.get('grade', 'C'),
            'unit': unit,
            'evidence_for': fids,
            'root_id': e.get('root_id', 'primary'),
        })
    return items


def size(it: dict) -> int:
    # 有行段声明时，材料只含行段；否则全文件（v1.8 材料内无文件间分隔行，size=行数）
    if it['unit'] is not None and it['unit'] != it['lines']:
        return it['unit']
    return it['lines']


def solve(items: list[dict], plan: dict) -> dict:
    features = plan.get('features', [])
    core = [m for m in features if m.get('importance') == 'core']
    by_id = {m.get('feature_id'): m for m in features}

    # 每模块的完整单元证据候选
    mod_ev: dict[str, list[dict]] = {}
    for it in items:
        if it['unit']:
            for fid in it['evidence_for']:
                mod_ev.setdefault(fid, []).append(it)

    # 装箱：front/back 各一个箱子，装入「每模块至少一个证据单元」
    front_box: list[dict] = []
    back_box: list[dict] = []
    front_used = 0
    back_used = 0
    placed_ids: set[int] = set()
    gaps: list[str] = []

    for m in core:
        fid = m.get('feature_id')
        cands = sorted(mod_ev.get(fid, []), key=size)
        if not cands:
            gaps.append(f"{m.get('name', fid)} 无任何完整单元证据（evidence 文件缺失）")
            continue
        # 共享满足：若本模块某候选已入箱（为其他模块占位），本模块视为已覆盖，不重复占容量
        if any(id(c) in placed_ids for c in cands):
            continue
        # v1.8 前后端分池：前端(primary/web/screen)可入 front 箱；后端(backend)只能入 back 箱
        # 纯前端选材时（无 backend 候选），前端候选也可入 back 箱（末尾 30 页 = 材料尾部）
        has_backend = any(c.get('root_id') == 'backend' for c in cands)
        front_cands = sorted(
            [c for c in cands if c.get('root_id') in FRONT_POOL],
            key=lambda c: (0 if c.get('root_id') == 'primary' else 1, size(c)),
        )
        back_cands = [c for c in cands if c.get('root_id') == 'backend']
        if not has_backend:
            back_cands = front_cands
        chosen = None
        for c in back_cands + front_cands:
            if id(c) in placed_ids:
                continue
            if c in back_cands and back_used + size(c) <= CAPACITY:
                chosen = ('back', c)
                break
            if c in front_cands and front_used + size(c) <= CAPACITY:
                chosen = ('front', c)
                break
        if chosen is None:
            # 该模块所有候选都放不下：报告缺口（含最小候选大小，供行段建议）
            smallest = cands[0]
            gaps.append(f"{m.get('name', fid)} 无完整单元可放入前30/后30页（最小证据 {size(smallest)} 行，两箱剩余 {CAPACITY-front_used}/{CAPACITY-back_used}）")
            continue
        box_name, c = chosen
        if box_name == 'front':
            front_box.append(c)
            front_used += size(c)
        else:
            back_box.append(c)
        placed_ids.add(id(c))

    # 其余文件填充：front 尾部空隙 → middle → back 头部空隙
    # v1.8 前后端分池：前端文件只填 front 箱，后端文件只填 back 箱
    def fill_key(it: dict) -> tuple:
        g = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(it.get('grade', 'C'), 4)
        root_rank = {'primary': 0, 'web': 1}.get(it.get('root_id'), 2)
        return (root_rank, g, -it['unit'] if it['unit'] else -it['lines'])

    rest = sorted([it for it in items if id(it) not in placed_ids], key=fill_key)
    front_fill = []
    for it in rest:
        if it.get('root_id') not in FRONT_POOL:
            continue
        if front_used + size(it) <= CAPACITY:
            front_fill.append(it)
            front_used += size(it)
    placed_ids |= {id(it) for it in front_fill}
    back_fill = []
    for it in rest:
        if id(it) in placed_ids or it.get('root_id') not in FRONT_POOL + ("backend",):
            continue
        if back_used + size(it) <= CAPACITY:
            back_fill.append(it)
            back_used += size(it)
    placed_ids |= {id(it) for it in back_fill}
    middle = [it for it in items if id(it) not in placed_ids]

    # v1.8 前后端分池输出顺序：front 段在前，back 段在末尾，middle 夹在中间不进入前后 30 页
    # 纯前端选材时 back 段 = 材料尾部（末尾 30 页）
    order = front_box + front_fill + middle + back_fill + back_box

    # 切点：front 在文件边界处截断（上限 CAPACITY=1500，front 必须恰好 30 页）
    total = sum(size(it) for it in order)
    acc = 0
    front_end = FRONT_LO
    for it in order:
        acc += size(it)
        if FRONT_LO <= acc <= CAPACITY:
            front_end = acc
            break
    else:
        front_end = min(acc, CAPACITY)
    back_start = total - CAPACITY + 1
    # back 切点尽量对齐文件边界（在 back 段起始附近）
    acc2 = 0
    for it in reversed(order):
        acc2 += size(it)
        if CAPACITY - 50 <= acc2 <= CAPACITY + 50:
            back_start = total - acc2 + 1
            break

    # 校验：每模块完整单元是否确实落在区间
    zone = set()
    acc = 0
    for it in order:
        s = acc + 1
        e = acc + size(it)
        acc = e
        if it['unit'] and ((s >= 1 and e <= front_end) or (s >= back_start and e <= total)):
            zone.add(it['path'])
    for m in core:
        fid = m.get('feature_id')
        cand_paths = {c['path'] for c in mod_ev.get(fid, [])}
        if cand_paths and not (cand_paths & zone):
            gaps.append(f"{m.get('name', fid)} 证据单元未落入前30/后30页（切点 front={front_end} back={back_start}）")

    suggestions = []
    if gaps:
        for it in items:
            if it['unit'] is None:
                suggestions.append(
                    f"{it['path']}: {it['lines']} 行超 {MAX_UNIT_LINES}，需在计划中声明 line_range（完整函数/类连续区间）")

    # ── v1.6 配比报告（软约束，不阻断）──
    acc = 0
    f_vue = 0
    b_be = 0
    z_total = 0
    for it in order:
        s = acc + 1
        e = acc + size(it)
        acc = e
        in_zone = max(min(e, front_end) - s + 1, 0) + max(min(e, total) - max(s, back_start) + 1, 0)
        if in_zone <= 0:
            continue
        z_total += in_zone
        if it['path'].endswith('.vue'):
            f_vue += in_zone
        elif it['path'].endswith(('.java', '.kt', '.xml')):
            b_be += in_zone
    ratio = {
        'frontend_vue_lines': f_vue,
        'backend_lines': b_be,
        'zone_total_lines': z_total,
        'frontend_ratio': round(f_vue / z_total, 3) if z_total else 0,
        'note': '软约束参考：前端 Vue 占比 >40% 时建议用后端策略/Service/复杂SQL替换部分模板行',
    }
    return {
        'order': [it['path'] for it in order],
        'front_end': front_end,
        'back_start': back_start,
        'total_lines': total,
        'pages': (total + 49) // 50,
        'gaps': sorted(set(gaps)),
        'suggestions': suggestions,
        'front_used': front_used,
        'back_used': back_used,
        'ratio': ratio,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    items = load_items(plan)
    report = solve(items, plan)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"LAYOUT SOLVE: total={report['total_lines']} pages={report['pages']} "
              f"front_end={report['front_end']} back_start={report['back_start']} "
              f"front_used={report['front_used']} back_used={report['back_used']}")
        r = report.get('ratio', {})
        if r:
            print(f"  配比: 前端Vue {r['frontend_vue_lines']} 行 / 后端 {r['backend_lines']} 行 / 区内总 {r['zone_total_lines']} 行 "
                  f"(前端占比 {r['frontend_ratio']:.0%})")
        for g in report['gaps']:
            print(f"  GAP: {g}")
        for s in report['suggestions']:
            print(f"  SUGGEST: {s}")
        if not report['gaps']:
            print('LAYOUT OK: 每核心模块至少一个完整证据单元在前30/后30页内')
    sys.exit(0 if not report['gaps'] else 1)


if __name__ == '__main__':
    main()
