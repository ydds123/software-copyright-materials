#!/usr/bin/env python3
"""软件边界说明生成（方案 v2 阶段 3，决策②落地）。

按独立软件申请：每项申请生成「软件边界说明」——入口、代码来源、选中文件、与同批任务的共享/独有范围。
只记录备案，不裁定是否合并。

用法：
  python code_boundary_report.py --workspace "<年份>年软件著作权申请资料目录" [--out <输出目录>]

输出：
  - 软件边界报告.md（整批视角：两两共享率 + 每任务边界说明）
  - 软件边界报告.json
  - 每个任务的 软件边界说明.md（写入该任务草稿目录，供登记备案）
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

TASK_FILE = "任务登记.json"
CODE_FILE_RE = re.compile(r"//\s*File:\s*(\S+)")
EXCLUDE_PATTERNS = ("~$", "新版模板式", "(1)", "copy", "副本")
REPOS = ("welleyao-hse-web", "screen", "welleyao-hse-plus", "welleyao-hse-app")


def path_key(p: str) -> str:
    """跨任务比对键：去掉项目根前缀，保留「仓库名/相对路径」。"""
    p = p.replace("\\", "/")
    for repo in REPOS:
        idx = p.find("/" + repo + "/")
        if idx >= 0:
            return p[idx + 1:]
    return p


def resolve_to_abs(p: str, project_root: str) -> str:
    """相对路径 → 绝对路径：先按 project_root，再逐个仓库试存在性。"""
    p = p.replace("\\", "/")
    if ":" in p or p.startswith("/"):
        return p
    if project_root:
        cand = f"{project_root}/{p}"
        if Path(cand).exists():
            return cand
    for repo in REPOS:
        cand = f"{project_root}/{repo}/{p}"
        if Path(cand).exists():
            return cand
    return p


def load_manifests(workspace: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in sorted(workspace.iterdir()):
        if not d.is_dir():
            continue
        # project_root：优先任务登记，其次清单
        project_root = ""
        reg = d / TASK_FILE
        if reg.exists():
            try:
                project_root = (json.loads(reg.read_text(encoding="utf-8")).get("project_root") or "").replace("\\", "/")
            except Exception:
                pass
        mf = d / "草稿" / "代码提取清单.json"
        data: dict[str, Any] = {}
        if mf.exists():
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if not project_root:
            project_root = (data.get("project_root") or "").replace("\\", "/")
        paths: list[str] = []
        files = data.get("files") or []
        if files:
            # 相对路径 → 绝对路径（不同任务 project_root 不同，绝对化后才能跨任务比对）
            for f in files:
                p = (f.get("path") or "").replace("\\", "/")
                if not p:
                    continue
                paths.append(resolve_to_abs(p, project_root))
        else:
            # 用户素材（as_is）结构：sources[].file
            for s in data.get("sources") or []:
                p = (s.get("file") or "").replace("\\", "/")
                if p:
                    paths.append(p)
        # 无清单但有正式代码 docx：从「// File: ...」标记提取代码来源
        if not paths:
            from batch_risk_report import extract_docx_text
            formal_dir = d / "正式资料"
            if formal_dir.is_dir():
                for c in sorted(formal_dir.glob("*.docx")):
                    if any(pat in c.name for pat in EXCLUDE_PATTERNS):
                        continue
                    text = extract_docx_text(c)
                    for m in CODE_FILE_RE.finditer(text):
                        p = resolve_to_abs(m.group(1), project_root)
                        if p not in paths:
                            paths.append(p)
        if not paths:
            continue
        out[d.name] = {
            "software_name": data.get("software_name") or d.name,
            "project_root": data.get("project_root") or project_root or "",
            "file_count": len(paths),
            "source_line_count": data.get("selected_source_line_count")
            or data.get("source_line_count")
            or data.get("material_line_count")
            or 0,
            "paths": paths,
        }
    return out


def run(workspace: Path) -> dict[str, Any]:
    manifests = load_manifests(workspace)
    names = sorted(manifests)

    # 两两共享（按 path_key 归一化，跨不同 project_root 也能比对同一文件）
    pairs: list[dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            sa = {path_key(p) for p in manifests[a]["paths"]}
            sb = {path_key(p) for p in manifests[b]["paths"]}
            shared = sa & sb
            union = sa | sb
            if not union or not shared:
                continue
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "shared": sorted(shared),
                    "shared_count": len(shared),
                    "shared_ratio": round(len(shared) / min(len(sa), len(sb)), 3) if min(len(sa), len(sb)) else 0,
                    "union_ratio": round(len(shared) / len(union), 3),
                }
            )
    pairs.sort(key=lambda p: -p["shared_count"])

    # 每任务边界
    per_task: list[dict[str, Any]] = []
    for n in names:
        m = manifests[n]
        own = {path_key(p) for p in m["paths"]}
        shared_with: list[dict[str, Any]] = []
        for other in names:
            if other == n:
                continue
            s = own & {path_key(p) for p in manifests[other]["paths"]}
            if s:
                shared_with.append(
                    {
                        "task": other,
                        "count": len(s),
                        "ratio": round(len(s) / len(own), 3),
                        "files": sorted(s),
                    }
                )
        shared_with.sort(key=lambda x: -x["count"])
        unique = sorted(own - {f for sw in shared_with for f in sw["files"]})
        per_task.append(
            {
                "task": n,
                "software_name": m["software_name"],
                "project_root": m["project_root"],
                "file_count": m["file_count"],
                "source_line_count": m["source_line_count"],
                "unique_files": unique,
                "shared_with": shared_with,
                "shared_ratio_total": round(1 - len(unique) / len(own), 3) if own else 0,
            }
        )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task_count": len(manifests),
        "pairs": pairs,
        "per_task": per_task,
    }


def write_reports(report: dict[str, Any], out_dir: Path, workspace: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "软件边界报告.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 软件边界报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 有代码提取清单的任务：{report['task_count']} 个",
        "",
        "## 两两代码共享（按共享文件数排序）",
        "",
        "| 任务 A | 任务 B | 共享文件数 | 共享率（相对较小集） | 并集占比 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for p in report["pairs"]:
        lines.append(
            f"| {p['a']} | {p['b']} | {p['shared_count']} | {p['shared_ratio']:.0%} | {p['union_ratio']:.0%} |"
        )
    lines.extend(["", "## 各任务软件边界说明", ""])
    for t in report["per_task"]:
        lines.append(f"### {t['task']}（{t['software_name']}）")
        lines.append("")
        lines.append(
            f"- 代码来源：`{t['project_root']}`；选中 {t['file_count']} 个文件，约 {t['source_line_count']} 行"
        )
        lines.append(f"- 独有文件 {len(t['unique_files'])} 个；共享率 {t['shared_ratio_total']:.0%}")
        if t["shared_with"]:
            lines.append("- 与其他任务共享：")
            for sw in t["shared_with"]:
                lines.append(f"  - {sw['task']}：共享 {sw['count']} 个文件（{sw['ratio']:.0%}）")
        else:
            lines.append("- 与其他任务无共享文件")
        lines.append("")
    (out_dir / "软件边界报告.md").write_text("\n".join(lines), encoding="utf-8")

    # 每任务 软件边界说明.md（备案到各自草稿目录）
    for t in report["per_task"]:
        task_dir = workspace / t["task"]
        if not task_dir.is_dir():
            continue
        draft = task_dir / "草稿"
        if not draft.is_dir():
            continue
        tl = [f"# 软件边界说明", ""]
        tl.append(f"- 软件全称：{t['software_name']}")
        tl.append(f"- 代码来源：{t['project_root']}")
        tl.append(f"- 程序鉴别材料：{t['file_count']} 个文件、约 {t['source_line_count']} 行")
        tl.append(f"- 独有文件 {len(t['unique_files'])} 个（{1 - t['shared_ratio_total']:.0%}）")
        tl.append("")
        if t["shared_with"]:
            tl.append("## 与同批任务共享范围（按独立软件申请，记录备案）")
            tl.append("")
            for sw in t["shared_with"]:
                tl.append(f"- {sw['task']}：共享 {sw['count']} 个文件")
                for f in sw["files"][:10]:
                    tl.append(f"  - `{f}`")
        tl.append("")
        (draft / "软件边界说明.md").write_text("\n".join(tl), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="<年份>年软件著作权申请资料 目录")
    parser.add_argument("--out", help="报告输出目录（默认工作区下的 软件边界报告/）")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        raise SystemExit(f"workspace 不存在: {workspace}")
    report = run(workspace)
    out_dir = Path(args.out) if args.out else workspace / "软件边界报告"
    write_reports(report, out_dir, workspace)

    print(f"CODE BOUNDARY REPORT（任务 {report['task_count']} 个）")
    for p in report["pairs"]:
        flag = " ⚠️" if p["shared_ratio"] >= 0.5 else ""
        print(f"  {p['a']} ↔ {p['b']}: 共享 {p['shared_count']} 个（{p['shared_ratio']:.0%}）{flag}")
    print(f"报告已写入: {out_dir}")


if __name__ == "__main__":
    main()
