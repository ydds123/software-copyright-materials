#!/usr/bin/env python3
"""Coverage plan proposer (v1.8): 篇幅规划 —— 三线材料共享的选材蓝图。

在业务理解完成后（business 门禁确认前）运行：
  - 业务重要性（core/support）机器推导 + 人工可调
  - 代表代码质量（A/B/C/D）用 suggest_grade 轻量分级
  - 二维矩阵推导三线配额：代码材料 / 手册篇幅 / 截图

输出：
  - 草稿/篇幅规划.md（人类可读，供用户确认）
  - 草稿/篇幅规划.json（机器可读，business 门禁与覆盖门禁校验）

配额档位：
  material: 必进 / 可进 / 不进
  manual:   详写 / 顺带 / 一笔带过
  screenshot: 必拍 / 选拍 / 不拍
"""
from __future__ import annotations

SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Business-understanding-stage coverage planning; confirmed together with business gate."

import argparse
import json
import re
import sys
from pathlib import Path

from evidence_plan_common import suggest_grade

ALGO_RE = re.compile(r"(strategy|chain|algorithm|engine|solver|matrix|priority|calc|merge|dispatch|rule)", re.I)


def derive_importance(title: str, module_type: str, evidence_paths: list[str]) -> str:
    """业务重要性机器推导：业务型/混合型/App → core；台账型 → support；
    证据含算法路径 → core。"""
    if module_type in ("business", "hybrid", "app", "screen"):
        return "core"
    if any(ALGO_RE.search(p) for p in evidence_paths):
        return "core"
    return "support"


def quota(importance: str, grade: str) -> dict[str, str]:
    """二维矩阵：业务重要性 × 代码质量 → 三线配额。"""
    if importance == "core":
        if grade in ("A", "B", "C"):
            return {"material": "必进", "manual": "详写", "screenshot": "必拍"}
        return {"material": "不进", "manual": "详写", "screenshot": "必拍"}  # D 规避但业务必须讲
    if grade in ("A", "B"):
        return {"material": "可进", "manual": "顺带", "screenshot": "选拍"}
    return {"material": "不进", "manual": "顺带", "screenshot": "选拍"}


def resolve_evidence_files(business: dict) -> dict[str, list[str]]:
    """模块 → 证据文件绝对路径列表（手动补全 visible_elements 时 evidence 已是绝对路径）。"""
    out = {}
    for m in business.get("manual_modules", []):
        title = str(m.get("title") or "")
        out[title] = [str(e) for e in (m.get("evidence") or []) if isinstance(e, str)]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="篇幅规划（业务理解后、手册前）")
    parser.add_argument("--business", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--confirm", action="store_true", help="写入篇幅规划.json/.md")
    args = parser.parse_args()

    business = json.loads(Path(args.business).read_text(encoding="utf-8"))
    modules = business.get("manual_modules", [])
    if not modules:
        raise SystemExit("STOP_FOR_USER: 业务理解缺少 manual_modules")

    rows = []
    for m in modules:
        title = str(m.get("title") or "未命名模块")
        mtype = str(m.get("module_type") or "")
        evs = resolve_evidence_files(business).get(title, [])
        grades = []
        best_grade = "D"
        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        for ev in evs:
            p = Path(ev)
            if not p.exists():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")[:200_000]
            except OSError:
                continue
            g, _ = suggest_grade(p, text)
            grades.append(g)
        if grades:
            best_grade = min(grades, key=lambda g: grade_order.get(g, 4))
        importance = derive_importance(title, mtype, evs)
        q = quota(importance, best_grade)
        rows.append({
            "module": title,
            "importance": importance,
            "grade": best_grade,
            "material": q["material"],
            "manual": q["manual"],
            "screenshot": q["screenshot"],
            "representative_code": evs[0].split("/")[-1] if evs else "（无 evidence）",
            "reason": f"{importance} × {best_grade} → {q['material']}/{q['manual']}/{q['screenshot']}",
        })

    md = ["# 篇幅规划（业务理解确认时一并确认）", "",
          "三线配额：代码材料 60 页 / 手册篇幅 / 截图。理由列给出二维矩阵依据；",
          "确认前请逐行核对 importance 与配额，必要时手工调整（改 JSON 或重跑 --confirm）。", "",
          "| 模块 | 重要性 | 代码等级 | 材料 | 手册 | 截图 | 代表代码 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['module']} | {r['importance']} | {r['grade']} | {r['material']} | {r['manual']} | {r['screenshot']} | {r['representative_code']} |")
    md.append("")
    md.append("## 各模块理由")
    for r in rows:
        md.append(f"- {r['module']}：{r['reason']}")

    out_dir = Path(args.out_dir)
    md_path = out_dir / "篇幅规划.md"
    json_path = out_dir / "篇幅规划.json"
    md_path.write_text("\n".join(md), encoding="utf-8")
    if args.confirm:
        from safe_write import safe_write
        tmp = json_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"modules": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        safe_write(json_path, tmp)
        tmp.unlink(missing_ok=True)
        print(f"OK coverage plan written: {json_path}")
    print(f"篇幅规划: {md_path}")
    for r in rows:
        print(f"  {r['module']}: {r['importance']}/{r['grade']} → 材料{r['material']} 手册{r['manual']} 截图{r['screenshot']}")


if __name__ == "__main__":
    main()
