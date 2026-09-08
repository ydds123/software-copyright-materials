#!/usr/bin/env python3
"""Doc-material coverage gate (v1.7): 手册 ↔ 程序鉴别材料 三口径覆盖检查。

通用形态：零硬编码关键词表，全部消费任务自身结构化数据。

口径：
  1. 模块级：业务理解 manual_modules[].evidence 的文件是否出现在 60 页材料
     core 模块缺口 = error；support 模块缺口 = warning
  2. 机制级：材料证据计划 features[].code_evidence 引用的文件是否在 60 页材料
     core feature 缺口 = error；support 缺口 = warning
  3. 反向级：材料每个文件经 mapped_features 反查手册是否描述了对应功能
     全部为 warning（弱信号，不阻断）

Exit codes: 0 pass / 1 blocked (core 缺口) / 2 invalid input
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Doc-material coverage gate wired into confirm_stage manual."

import argparse
import json
import sys
from pathlib import Path


def norm(p: str) -> str:
    return p.replace("\\", "/").lower().rstrip("/")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def material_paths(manifest: dict) -> list[str]:
    files = manifest.get("files") or []
    return [norm(f.get("path", "")) for f in files if f.get("path")]


def match_in_material(evidence_path: str, materials: list[str]) -> bool:
    """evidence（可能为绝对路径）与材料相对路径做后缀匹配。"""
    n = norm(evidence_path)
    return any(n.endswith(m) or m.endswith(n) for m in materials)


def run(business_path: Path, plan_path: Path, manifest_path: Path, manual_path: Path) -> dict:
    if not business_path.exists() or not plan_path.exists():
        return {"status": "invalid", "errors": [f"缺少输入: {business_path} / {plan_path}"]}
    if not manifest_path.exists():
        return {"status": "invalid", "errors": [f"缺少代码提取清单: {manifest_path}"]}

    business = read_json(business_path)
    plan = read_json(plan_path)
    manifest = read_json(manifest_path)
    manual = ""
    if manual_path.exists():
        manual = manual_path.read_text(encoding="utf-8")

    # v1.8 篇幅规划分级：篇幅规划.json 存在时，配额档位优先于 features.importance
    cp_path = business_path.parent / "篇幅规划.json"
    cp_rows: dict[str, dict] = {}
    if cp_path.exists():
        try:
            for r in json.loads(cp_path.read_text(encoding="utf-8")).get("modules", []):
                cp_rows[str(r.get("module") or "")] = r
        except Exception:
            pass

    materials = material_paths(manifest)
    if not materials:
        return {"status": "invalid", "errors": ["代码提取清单无 files 或为空"]}

    errors: list[str] = []
    warnings: list[str] = []
    counts = {"modules": 0, "modules_ok": 0, "mechs": 0, "mechs_ok": 0, "reverse": 0, "reverse_ok": 0}

    # ── 1. 模块级：manual_modules[].evidence → 材料 ──
    core_modules = {f["feature_id"] for f in plan.get("features", []) if f.get("importance") == "core"}
    feature_names = {f["feature_id"]: f.get("name", "") for f in plan.get("features", [])}
    module_feature = {}  # module title -> feature id（按名称匹配）
    for f in plan.get("features", []):
        module_feature[f.get("name", "")] = f["feature_id"]

    for m in business.get("manual_modules", []):
        title = str(m.get("title") or "未命名模块")
        evs = m.get("evidence") or []
        if not evs:
            continue
        counts["modules"] += 1
        hit = any(match_in_material(e, materials) for e in evs if isinstance(e, str))
        cp = cp_rows.get(title, {})
        material_q = str(cp.get("material") or "")
        # v1.8 篇幅规划分级：必进 → error；可进 → warning；不进 → 跳过
        if material_q == "不进":
            counts["modules_ok"] += 1  # 规划明确不进，不算缺口
            continue
        if hit:
            counts["modules_ok"] += 1
        elif material_q == "必进":
            errors.append(f"篇幅规划要求「{title}」代码必进 60 页材料，但证据文件未出现")
        else:
            # 无规划行时按原逻辑：core 判定
            fid = module_feature.get(title, "")
            is_core = fid in core_modules if fid else (str(m.get("module_type")) in ("business", "hybrid"))
            if is_core:
                errors.append(f"核心模块「{title}」的证据文件未出现在 60 页材料中")
            else:
                warnings.append(f"支撑模块「{title}」的证据文件未出现在 60 页材料中")

    # ── 2. 机制级：features[].code_evidence → 材料 ──
    # v1.8 手册配额校验：详写模块手册章节必须存在且有实质内容
    import re as _re
    for m in business.get("manual_modules", []):
        title = str(m.get("title") or "")
        if not title:
            continue
        cp = cp_rows.get(title, {})
        manual_q = str(cp.get("manual") or "")
        if not manual_q:
            continue
        if title not in manual:
            if manual_q == "详写":
                errors.append(f"篇幅规划要求「{title}」手册详写，但手册中无该模块章节")
            else:
                warnings.append(f"篇幅规划要求「{title}」手册顺带，但手册中无该模块描述")
            continue
        if manual_q == "详写":
            idx = manual.find(title)
            body = manual[idx:idx + 1500]
            if len(_re.findall(r'[\u4e00-\u9fff]', body)) < 200:
                errors.append(f"篇幅规划要求「{title}」手册详写，但手册章节内容过薄（<200 字）")

    ev_by_id = {e.get("evidence_id"): e for e in plan.get("code_evidence", [])}
    for f in plan.get("features", []):
        fname = f.get("name", "")
        cids = f.get("code_evidence") or []
        if not cids:
            continue
        counts["mechs"] += 1
        hit = False
        for cid in cids:
            ev = ev_by_id.get(cid, {})
            p = ev.get("path", "")
            if p and match_in_material(p, materials):
                hit = True
                break
        if hit:
            counts["mechs_ok"] += 1
        elif f.get("importance") == "core":
            errors.append(f"核心功能「{fname}」的代码证据未出现在 60 页材料中")
        else:
            warnings.append(f"支撑功能「{fname}」的代码证据未出现在 60 页材料中")

    # ── 3. 反向级：材料文件 → 手册功能描述（弱信号）──
    ev_by_path = {}
    for e in plan.get("code_evidence", []):
        ev_by_path[norm(e.get("path", ""))] = e
    # cid -> feature 名反向索引（mapped_features 缺失时兜底）
    cid_to_feature: dict[str, str] = {}
    for f in plan.get("features", []):
        for cid in f.get("code_evidence") or []:
            cid_to_feature.setdefault(cid, f.get("name", ""))
    for mp in materials:
        ev = ev_by_path.get(mp)
        if not ev:
            # 行段抽取可能改 path 大小写，做一次宽松匹配
            for k, v in ev_by_path.items():
                if k.endswith(mp) or mp.endswith(k):
                    ev = v
                    break
        counts["reverse"] += 1
        if not ev:
            warnings.append(f"材料文件 {mp} 无法映射到计划证据条目")
            continue
        feats = ev.get("mapped_features") or []
        names = [feature_names.get(fid, fid) for fid in feats]
        if not names:
            fallback = cid_to_feature.get(ev.get("evidence_id", ""), "")
            if fallback:
                names = [fallback]
        if not names:
            warnings.append(f"材料文件 {mp} 的计划证据条目未映射功能（mapped_features 缺失），建议补全")
            continue
        if any(n and n in manual for n in names):
            counts["reverse_ok"] += 1
        else:
            warnings.append(
                f"材料文件 {mp} 对应功能「{'/'.join(names)}」未在手册正文中找到描述"
            )

    status = "blocked" if errors else "pass"
    report = {
        "status": status,
        "counts": counts,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="手册 ↔ 程序鉴别材料三口径覆盖门禁")
    parser.add_argument("--business", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manual", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run(Path(args.business), Path(args.plan), Path(args.manifest), Path(args.manual))
    c = report["counts"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"DOC-MATERIAL COVERAGE {report['status'].upper()}: "
            f"模块 {c['modules_ok']}/{c['modules']}, 机制 {c['mechs_ok']}/{c['mechs']}, "
            f"反向 {c['reverse_ok']}/{c['reverse']}"
        )
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for w in report["warnings"]:
            print(f"  WARNING: {w}")

    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
