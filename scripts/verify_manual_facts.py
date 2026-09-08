#!/usr/bin/env python3
"""Manual fact checks (v1.7): 手册枚举/公式断言 ↔ 源码事实核对。

补丁 1+4 落地：回答手册"写得对不对"（层次 1 事实正确性）。

机制：
  1. 枚举漂移：从手册表格/列举中提取中文枚举集合，扫描后端 enum 类的
     description 字符串集合做包含比对。
       ⊆ 源码 → ✓；交集≥2 但非包含 → ✗ error（漂移）；无交集 → ? 人工确认
  2. 公式/口径：从手册提取"按 X 计算/除以/百分比"句式，定位源码候选公式
     位置，列入人工确认清单（不自动判定）。

输出：草稿/事实断言核对清单.md + exit code（0 通过 / 1 有枚举漂移 / 2 无效）
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Manual-vs-source fact drift gate; runs before manual gate confirmation."

import argparse
import json
import re
import sys
from pathlib import Path

# 手册枚举候选：表格首列连续块 + 顿号列举（逐项提取）
ENUM_TABLE_CELL = re.compile(r'^\|\s*([\u4e00-\u9fffA-Za-z（）、\-]{2,16})\s*\|')
ENUM_ITEMS = re.compile(r'(?:^|[^\u4e00-\u9fff])([\u4e00-\u9fff]{2,6}(?:、[\u4e00-\u9fff]{2,6}){2,})')
FIELD_SUFFIXES = ('编号', '名称', '部门', '方式', '开关', '时间', '时段', '类型', '间隔', '单位', '日期',
                 '期限', '状态', '原因', '记录', '配置', '规则', '路径', '入口', '人员', '范围', '描述', '内容',
                 '推送', '机制', '点', '措施', '等级', '天数', '班组', '编码', '类别', '管控', '治理', '按钮', '管理', '计划', '任务')
FORMULA_SENTENCE = re.compile(r'[^。\n]*(?:按[^。\n]{0,20}(?:计算|除以|累加|取)|百分比|保留一位小数|\d+(?:\.\d+)?%)[^。\n]*。')

STOP_WORDS = {'字段', '配置项', '组成', '步骤', '读者', '角色', '模块', '职责', '状态', '含义', '进入条件', '后续去向',
              '表格', '项目', '说明', '版本', '日期', '修订人', '修订内容', '术语'}


def _is_sep(cell: str) -> bool:
    return not cell or all(ch in '-: ' for ch in cell)


def extract_manual_enums(manual: str) -> list[tuple[str, list[str]]]:
    """提取手册中疑似枚举集合（表格首列连续块或顿号列举）。"""
    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    lines = manual.splitlines()
    # 表格首列连续块
    i = 0
    while i < len(lines):
        m = ENUM_TABLE_CELL.match(lines[i].strip())
        cell = m.group(1) if m else ''
        if not m or _is_sep(cell) or cell in STOP_WORDS or cell.endswith(FIELD_SUFFIXES):
            i += 1
            continue
        block = []
        j = i
        while j < len(lines) and j - i < 20:
            m2 = ENUM_TABLE_CELL.match(lines[j].strip())
            if not m2 or _is_sep(m2.group(1)):
                break
            block.append(m2.group(1))
            j += 1
        if len(block) >= 3:
            key = '|'.join(sorted(set(block)))
            if key not in seen:
                seen.add(key)
                out.append((f'表格: {block[0]}…', block))
        i = j if j > i else i + 1
    # 顿号列举（3 项以上，逐项提取；过滤字段列举与正文粘连）
    for m in ENUM_ITEMS.finditer(manual):
        seg = m.group(1)
        items = [x for x in re.split(r'[、，]', seg) if len(x) >= 2]
        # 去掉粘连正文的项（含 的/是/和/与/或/等/及）
        items = [x for x in items if not any(c in x for c in ('的', '是', '和', '与', '或', '等', '及'))]
        if len(items) < 3:
            continue
        # 字段列举（≥50% 项含字段尾词）跳过
        if sum(1 for x in items if x.endswith(FIELD_SUFFIXES)) * 2 >= len(items):
            continue
        key = '|'.join(sorted(set(items)))
        if key not in seen:
            seen.add(key)
            out.append((f'列举: {seg[:30]}', items))
    return out


def extract_source_enums(roots: list[Path]) -> dict[str, set[str]]:
    """扫描源码 enum 类（os.walk，排除 .worktrees/target），提取中文 description 集合。"""
    import os
    src_enums: dict[str, set[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if 'target' in dirpath or '.worktrees' in dirpath or '.git' in dirpath:
                continue
            for fn in filenames:
                if not fn.endswith('.java'):
                    continue
                # 枚举类不都带 Enum 后缀（如 HazardStatus.java），按文件名关键字+内容双重判定
                if not any(k in fn for k in ('Enum', 'Status', 'State', 'Type')):
                    continue
                p = Path(dirpath) / fn
                try:
                    text = p.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                if 'enum ' not in text[:4000]:
                    continue
                descs = set(re.findall(r'"([\u4e00-\u9fff（）]{2,12})"', text))
                if descs:
                    src_enums[fn] = descs
    return src_enums


def find_source_formulas(roots: list[Path]) -> list[str]:
    """定位源码中的计算表达式（百分比/除法/汇总），供人工核对。"""
    import os
    hits = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if 'target' in dirpath or '.worktrees' in dirpath or '.git' in dirpath:
                continue
            for fn in filenames:
                if not fn.endswith('.java'):
                    continue
                p = Path(dirpath) / fn
                try:
                    text = p.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                for pat in (r'\* 100\.0 /', r'\* 100 /', r'/ total', r'/ totalNum', r'completionRate', r'\.0f%%'):
                    if re.search(pat, text):
                        line_no = 1
                        for i, l in enumerate(text.splitlines(), 1):
                            if re.search(pat, l):
                                line_no = i
                                break
                        hits.append(f'{p.as_posix()}:{line_no} {text.splitlines()[line_no-1].strip()[:80]}')
                        break  # 每文件最多一处
    return hits[:12]


def run(manual_path: Path, source_roots: list[str]) -> dict:
    if not manual_path.exists():
        return {"status": "invalid", "errors": [f"缺少手册: {manual_path}"]}
    manual = manual_path.read_text(encoding='utf-8')
    roots = [Path(r) for r in source_roots]

    manual_enums = extract_manual_enums(manual)
    src_enums = extract_source_enums(roots)
    all_src = set()
    for sset in src_enums.values():
        all_src |= sset

    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    for label, items in manual_enums:
        # 字段表/字段列举过滤：≥50% 项含字段尾词；步骤表（长词/含与和）跳过
        if sum(1 for x in items if x.endswith(FIELD_SUFFIXES)) * 2 >= len(items):
            continue
        if any('与' in x or '和' in x or len(x) > 6 for x in items[:4]):
            continue
        is_table = label.startswith('表格')
        # denoise：只保留出现在源码枚举中的项，去正文粘连
        clean = [x for x in items if x in all_src]
        if len(clean) < 3:
            # 状态特征块（漂移后大部分词不在源码）→ 人工确认提示
            stateish = [x for x in items if re.search(r'(待|已|中$|完成|超时|逾期|认领|巡检|关闭|验收|处理)', x)]
            if len(stateish) * 2 >= len(items):
                warnings.append(f"疑似枚举漂移需人工确认：手册「{label[:40]}」({len(items)} 项)与源码枚举交集不足 2 项")
                checks.append({"manual": label[:50], "status": "unknown",
                               "note": f"{len(items)} 项与源码枚举交集 <2，疑为状态枚举漂移，需人工确认"})
            continue
        mset = set(clean)
        matched_src = None
        for fname, sset in src_enums.items():
            inter = mset & sset
            if inter and len(inter) / max(len(mset), 1) >= 0.8 and len(inter) >= len(sset) * 0.8:
                matched_src = fname
                break
        if matched_src:
            checks.append({"manual": label[:50], "status": "pass", "note": f"与 {matched_src} 枚举一致（{len(items)} 项）"})
            continue
        # 有交集但覆盖不足 → 漂移嫌疑
        best = None
        for fname, sset in src_enums.items():
            inter = mset & sset
            if len(inter) >= 2:
                if best is None or len(inter) > best[1]:
                    best = (fname, len(inter), len(sset), sorted(mset - sset), sorted(sset - mset))
        if best:
            fname, inter_n, src_n, only_manual, only_src = best
            msg = (
                f"枚举漂移：手册「{label[:40]}」与源码 {fname} 不一致——"
                f"共同 {inter_n} 项，手册多出 {only_manual[:5]}，源码有 {src_n} 项"
                + (f"（手册未列 {only_src[:5]}）" if only_src else "")
            )
            if is_table:
                errors.append(msg)
            else:
                warnings.append(msg + "（正文列举，允许分组引用，请人工确认）")
            checks.append({"manual": label[:50], "status": "fail" if is_table else "unknown",
                           "note": f"与 {fname} 共同 {inter_n} 项，手册多 {only_manual[:5]}，源码多 {only_src[:5]}"})
            continue
        # 交集 <2：状态特征词块提示人工确认（4 状态 vs 10 状态类漂移交集可能只有 1 项）
        stateish = [x for x in mset if re.search(r'(待|已|中$|完成|超时|逾期|认领|巡检|关闭|验收|处理)', x)]
        if len(stateish) * 2 >= len(mset):
            warnings.append(f"疑似枚举漂移需人工确认：手册「{label[:40]}」({len(mset)} 项)与源码枚举交集不足 2 项")
            checks.append({"manual": label[:50], "status": "unknown",
                           "note": f"{len(mset)} 项与源码枚举交集 <2，疑为状态枚举漂移，需人工确认"})
        # 交集 <2 或无交集：静默（字段表/普通列举不报）

    formulas = re.findall(FORMULA_SENTENCE, manual)
    src_formulas = find_source_formulas(roots)
    if formulas:
        warnings.append(f"公式/口径句 {len(formulas)} 处，源码候选公式 {len(src_formulas)} 处，见核对清单")

    # 写核对清单
    out_lines = ['# 事实断言核对清单（v1.7 自动生成）', '',
                 '本清单由 verify_manual_facts.py 生成：枚举集合与源码 enum 自动比对，公式/口径需人工确认。', '']
    out_lines.append('## 枚举比对')
    for c in checks:
        mark = {'pass': '✓', 'fail': '✗', 'unknown': '?'}[c['status']]
        out_lines.append(f"- {mark} {c['manual']} —— {c['note']}")
    out_lines.append('')
    out_lines.append('## 公式/口径句（人工确认）')
    for f in formulas:
        out_lines.append(f"- 手册: {f.strip()[:80]}")
    out_lines.append('')
    out_lines.append('## 源码候选公式位置')
    for s in src_formulas:
        out_lines.append(f"- {s}")

    report = {
        "status": "blocked" if errors else "pass",
        "manual": str(manual_path),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "formula_sentences": len(formulas),
        "source_formula_hits": len(src_formulas),
    }
    out_path = manual_path.parent / '事实断言核对清单.md'
    out_path.write_text('\n'.join(out_lines), encoding='utf-8')
    report["output"] = str(out_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description='手册事实断言 ↔ 源码核对（枚举漂移 + 公式清单）')
    parser.add_argument('--manual', required=True)
    parser.add_argument('--source-roots', nargs='+', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    report = run(Path(args.manual), args.source_roots)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MANUAL FACTS {report['status'].upper()}: 枚举检查 {len(report['checks'])} 组，公式句 {report['formula_sentences']} 处")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
        print(f"清单输出: {report.get('output')}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == '__main__':
    main()
