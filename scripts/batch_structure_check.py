#!/usr/bin/env python3
"""Batch structure templating gate (v2: 风险分级).

v2 变更（方案 v2 决策④）：
  - 确定性检查 = 硬门禁：文件缺失、章节编号错误、文档内精确重复粘贴
  - 相似度检查 = 风险分级：表头归一化指纹（同义词归一）、近似段落（字符 3-gram MinHash）、
    单文档内重复小节/重复表格结构——只出 high/medium/low 风险，不自动阻断
  - 强制格式表（四列步骤表、字段表、术语表、配置要求表、功能清单表等）走白名单，只计背景不判风险

输出：
  status: invalid | blocked（有确定性错误）| risk（有风险，高需人工复核）| pass
  errors: 确定性硬错误（字符串，调用方保持兼容）
  risks: [{pair, level, signal, detail, count}] 结构化风险
  warnings: risks 的字符串形式（兼容旧调用方）

阈值说明：本文件阈值为初值，需用标注样本（真实同构/强制格式/同域自然相似/改词规避）标定后再声称「已修对」。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

from common import read_text

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")

# ── 同义词归一：已知表头别名 → 规范名（消除「改一个词即改指纹」的绕过）──
SYNONYM_MAP = {
    "说明": "说明", "作用": "说明", "描述": "说明",
    "含义": "释义", "释义": "释义", "定义": "释义",
    "最低要求": "最低配置", "最低配置": "最低配置",
    "推荐要求": "推荐配置", "推荐配置": "推荐配置",
    "模块": "功能模块", "子功能": "细分功能",
    "规则说明": "业务规则", "输入限制": "输入边界", "必填": "是否必填",
    "操作内容": "用户操作", "系统反馈": "系统响应", "步骤": "操作步骤",
}

# ── 强制/通用表白名单（归一化后的规范表头元组）──
FORCED_CANON = {
    ("操作步骤", "用户操作", "系统响应", "异常处理"),
    ("术语", "释义"),
    ("字段名称", "字段类型", "是否必填", "输入边界", "业务规则"),
    ("配置项", "最低配置", "推荐配置"),
    ("项目", "最低配置", "推荐配置"),
    ("序号", "功能模块", "细分功能", "说明"),
    ("角色", "使用端", "主要使用内容"),
    ("功能点", "说明"),
    ("异常情况", "处理逻辑"),
    ("字段名称", "字段类型", "是否必填", "业务规则"),
}


def is_separator_row(cells: list[str]) -> bool:
    return all(c in ("---", "---:", ":---", ":---:") or set(c) <= {"-", ":"} for c in cells)


def heading_skeleton(path: Path) -> tuple[list[str], list[str]]:
    """Return (level-tagged heading list, plain heading list).

    编号前缀从 plain 标题中剥离，使 ``1.1 异常功能逻辑`` 与 ``2.1 异常功能逻辑`` 判为同标题。
    """
    tagged: list[str] = []
    plain: list[str] = []
    for line in read_text(path).splitlines():
        m = HEADING_RE.match(line.strip())
        if m:
            level = len(line) - len(line.lstrip("#"))
            text = m.group(1).strip()
            unnumbered = re.sub(r"^\d+(?:\.\d+)*[、.\s]*", "", text)
            tagged.append(f"h{level}:{unnumbered}")
            plain.append(unnumbered)
    return tagged, plain


def heading_numbering_issues(path: Path) -> list[str]:
    """确定性硬检查：章节编号父子不一致（如 ## 4 下挂 ### 3.1）。"""
    issues: list[str] = []
    current: dict[int, tuple[int, ...] | None] = {2: None, 3: None, 4: None}
    for line in read_text(path).splitlines():
        m = re.match(r"^(#{2,4})\s+(\d+(?:\.\d+)*)(?:[、.\s]|$)", line.strip())
        if not m:
            continue
        level = len(m.group(1))
        parts = tuple(int(x) for x in m.group(2).split("."))
        if level == 2:
            current[2] = parts
            current[3] = None
            current[4] = None
        elif level == 3:
            if current[2] is not None:
                if len(parts) == 1:
                    issues.append(f"章节编号错误：`### {m.group(2)}` 应为 `### {current[2][0]}.x` 形式")
                elif parts[0] != current[2][0]:
                    issues.append(f"章节编号错误：`### {m.group(2)}` 与父级章节 {current[2][0]} 不一致")
            current[3] = parts
            current[4] = None
        elif level == 4:
            if current[3] is not None and parts[: len(current[3])] != current[3]:
                issues.append(f"章节编号错误：`#### {m.group(2)}` 与父级 {'.'.join(map(str, current[3]))} 不一致")
            current[4] = parts
    return issues


def table_headers(path: Path) -> list[tuple[str, ...]]:
    """提取每张表的表头行（首行 + 下一行为分隔行）。"""
    headers: list[tuple[str, ...]] = []
    lines = read_text(path).splitlines()
    i = 0
    while i < len(lines) - 1:
        m = TABLE_ROW_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if not cells or not all(cells) or is_separator_row(cells):
            i += 1
            continue
        nm = TABLE_ROW_RE.match(lines[i + 1].strip())
        if nm and is_separator_row([c.strip() for c in nm.group(1).split("|")]):
            headers.append(tuple(cells))
            i += 2
            continue
        i += 1
    return headers


def normalize_header(cells: tuple[str, ...]) -> tuple[str, ...]:
    """确定性归一化：去空白、去括号注释、同义词映射。"""
    out = []
    for c in cells:
        c = re.sub(r"\s+", "", c.strip())
        c = re.sub(r"[（(][^）)]*[)）]", "", c)
        out.append(SYNONYM_MAP.get(c, c))
    return tuple(out)


def _shingles(text: str, n: int = 3) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def _minhash(shingles: set[str], num: int = 64) -> list[int]:
    sig = []
    for i in range(num):
        salt = i * 2654435761
        mn = min((zlib.crc32(s.encode("utf-8")) ^ salt) & 0xFFFFFFFF for s in shingles)
        sig.append(mn)
    return sig


def _jaccard_est(a: list[int], b: list[int]) -> float:
    if not a or not b:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def paragraph_data(path: Path, min_len: int = 40) -> list[dict[str, Any]]:
    """返回正文段落（含 MinHash 签名），跳过标题/表格/代码块/截图预留。"""
    out: list[dict[str, Any]] = []
    in_code = False
    for para in read_text(path).split("\n\n"):
        if para.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        text = " ".join(para.split())
        if len(text) < min_len:
            continue
        if text.startswith(("#", "|", "【", "-", "*", ">", "!")):
            continue
        out.append(
            {
                "text": text,
                "hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
                "sig": _minhash(_shingles(text)),
            }
        )
    return out


def repeated_section_titles(tagged: list[str]) -> list[str]:
    """单文档内重复小节（≥3 次，同一标题）。"""
    plain = [t.split(":", 1)[1] for t in tagged if ":" in t]
    return [title for title, n in Counter(plain).items() if n >= 3]


def grade_pair(heading_ratio: float, shared_tables: int, near_dups: int) -> str:
    """二维信号 → 风险等级（初值，待标注样本标定）。"""
    if heading_ratio >= 0.6 or shared_tables >= 5 or near_dups >= 3:
        return "high"
    if heading_ratio >= 0.4 or shared_tables >= 3 or near_dups >= 1:
        return "medium"
    if heading_ratio >= 0.2 or shared_tables >= 1:
        return "low"
    return ""


def run(manual_paths: list[Path], batch_id: str = "") -> dict[str, Any]:
    hard_errors: list[str] = []
    risks: list[dict[str, Any]] = []
    warnings: list[str] = []

    docs: dict[str, dict[str, Any]] = {}
    for path in manual_paths:
        if not path.exists():
            return {
                "status": "invalid",
                "batch_id": batch_id,
                "documents": [],
                "errors": [f"缺少 {path}"],
                "risks": [],
                "warnings": [],
            }
        tagged, plain = heading_skeleton(path)
        headers = table_headers(path)
        norm_headers = [normalize_header(h) for h in headers]
        paras = paragraph_data(path)
        key = (
            f"{path.parent.parent.name}/{path.name}"
            if path.parent.name == "草稿"
            else f"{path.parent.name}/{path.name}"
        )
        docs[key] = {
            "path": path,
            "tagged": tagged,
            "plain": plain,
            "headers": headers,
            "norm_headers": norm_headers,
            "paras": paras,
            "num_issues": heading_numbering_issues(path),
        }

    # ── 确定性硬检查 ──
    for name, doc in docs.items():
        for issue in doc["num_issues"]:
            hard_errors.append(f"{name}: {issue}")
        # 文档内精确重复粘贴：同一段落原文出现 3 次以上
        text_counts = Counter(p["text"] for p in doc["paras"])
        for text, n in text_counts.items():
            if n >= 3:
                hard_errors.append(f"{name} 存在重复粘贴：同一段落出现 {n} 次（{text[:40]}…）")

    # ── 风险分级 ──
    # 单文档内信号
    for name, doc in docs.items():
        repeats = repeated_section_titles(doc["tagged"])
        if repeats:
            risks.append(
                {
                    "pair": [name],
                    "level": "medium",
                    "signal": "repeated_sections",
                    "detail": f"存在重复小节（≥3 次）：{', '.join(repeats[:8])}",
                    "count": len(repeats),
                }
            )
        # 单文档内重复表格结构（排除强制格式）
        header_counts = Counter(h for h in doc["norm_headers"] if h not in FORCED_CANON)
        repeated_headers = {h: n for h, n in header_counts.items() if n >= 3}
        if repeated_headers:
            top = sorted(repeated_headers.items(), key=lambda kv: -kv[1])[0]
            level = "high" if top[1] >= 5 else "medium"
            risks.append(
                {
                    "pair": [name],
                    "level": level,
                    "signal": "repeated_tables",
                    "detail": f"文档内重复表格结构：{'|'.join(top[0])} 出现 {top[1]} 次（共 {len(repeated_headers)} 种重复表头）",
                    "count": top[1],
                }
            )

    # 跨文档信号
    names = list(docs)
    if len(names) >= 2:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = docs[names[i]], docs[names[j]]
                shared = set(a["plain"]) & set(b["plain"])
                denom = min(len(set(a["plain"])), len(set(b["plain"]))) or 1
                ratio = len(shared) / denom
                # 共享表头（归一化 + 排除强制格式）
                a_h = set(h for h in a["norm_headers"] if h not in FORCED_CANON)
                b_h = set(h for h in b["norm_headers"] if h not in FORCED_CANON)
                shared_tables = len(a_h & b_h)
                # 近似重复段落（MinHash Jaccard ≥ 0.85）
                near_dups = 0
                for pa in a["paras"]:
                    for pb in b["paras"]:
                        if pa["hash"] == pb["hash"] or _jaccard_est(pa["sig"], pb["sig"]) >= 0.85:
                            near_dups += 1
                            break
                level = grade_pair(ratio, shared_tables, near_dups)
                if not level:
                    continue
                detail_parts = []
                if ratio >= 0.2:
                    detail_parts.append(f"标题重合率 {ratio:.0%}（共同 {len(shared)} 个）")
                if shared_tables:
                    detail_parts.append(f"共享表格结构 {shared_tables} 个（排除强制格式）")
                if near_dups:
                    detail_parts.append(f"近似重复段落 {near_dups} 段")
                risks.append(
                    {
                        "pair": [names[i], names[j]],
                        "level": level,
                        "signal": "cross_doc",
                        "detail": "；".join(detail_parts),
                        "count": shared_tables,
                    }
                )

    # 风险 → warnings 字符串（兼容旧调用方）
    for r in risks:
        pair_text = " 与 ".join(r["pair"])
        warnings.append(f"[{r['level']}风险] {pair_text}：{r['detail']}")

    status = "invalid" if not docs else ("blocked" if hard_errors else ("risk" if risks else "pass"))
    return {
        "status": status,
        "batch_id": batch_id,
        "documents": list(docs.keys()),
        "errors": hard_errors,
        "risks": risks,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manuals", nargs="+", required=True, help="Markdown 文档路径（同批次）")
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run([Path(m) for m in args.manuals], batch_id=args.batch_id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"BATCH STRUCTURE {report['status'].upper()}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")
        for r in report["risks"]:
            pair = " 与 ".join(r["pair"])
            print(f"  RISK[{r['level']}]: {pair}: {r['detail']}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
