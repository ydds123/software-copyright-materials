#!/usr/bin/env python3
"""Batch structure templating gate (1a.3).

Compares sibling application documents in the same submission batch:
  - heading skeleton similarity
  - repeated section titles ("异常功能逻辑" 类重复小节)
  - table column-structure fingerprint reuse
  - near-duplicate paragraphs (module-name-only substitution)

Inputs:
  --manuals   path1 path2 ... (Markdown documents of the same batch)
  --batch-id  optional batch identifier (for the report)

Exit codes: 0 pass / 1 structural templating blocked / 2 invalid input
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import read_text

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def heading_skeleton(path: Path) -> tuple[list[str], list[str]]:
    """Return (level-tagged heading list, plain heading list).

    Numbered prefixes are stripped from plain headings so that repeated
    template sections like ``1.1 异常功能逻辑`` / ``2.1 异常功能逻辑`` are
    recognized as the same title.
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


def table_fingerprints(path: Path) -> list[str]:
    """Fingerprint table structures by their header cell sequence."""
    fps: list[str] = []
    for line in read_text(path).splitlines():
        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if all(c in ("---", "---:", ":---", ":---:") or set(c) <= {"-", ":"} for c in cells):
            continue  # separator row
        if cells and all(cells):
            fps.append(hashlib.sha1("|".join(cells).encode("utf-8")).hexdigest()[:12])
    return fps


def paragraph_hashes(path: Path, min_len: int = 30) -> list[tuple[str, str]]:
    """Return (hash, text) for substantive paragraphs."""
    out: list[tuple[str, str]] = []
    for para in read_text(path).split("\n\n"):
        text = " ".join(para.split())
        if len(text) >= min_len and not text.startswith("#") and not text.startswith("```"):
            out.append((hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], text[:60]))
    return out


def repeated_section_titles(tagged: list[str]) -> list[str]:
    """Titles appearing 3+ times within one document (模板化小节)."""
    from collections import Counter

    plain = [t.split(":", 1)[1] for t in tagged if ":" in t]
    return [title for title, n in Counter(plain).items() if n >= 3]


def run(manual_paths: list[Path], batch_id: str = "") -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    docs: dict[str, dict[str, Any]] = {}
    for path in manual_paths:
        if not path.exists():
            return {"status": "invalid", "errors": [f"缺少 {path}"]}
        tagged, plain = heading_skeleton(path)
        fps = table_fingerprints(path)
        paras = paragraph_hashes(path)
        docs[path.name] = {
            "tagged": tagged,
            "plain": plain,
            "table_fps": fps,
            "paras": paras,
        }

    # 1. Repeated section titles inside a single document
    for name, doc in docs.items():
        repeats = repeated_section_titles(doc["tagged"])
        if repeats:
            errors.append(
                f"{name} 存在重复小节（≥3 次）：{', '.join(repeats[:8])}"
            )

    # 2. Cross-document heading skeleton similarity
    names = list(docs)
    if len(names) >= 2:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = docs[names[i]], docs[names[j]]
                shared = set(a["plain"]) & set(b["plain"])
                denom = min(len(set(a["plain"])), len(set(b["plain"]))) or 1
                ratio = len(shared) / denom
                if ratio >= 0.6:
                    errors.append(
                        f"同批文档目录同构：{names[i]} 与 {names[j]} 标题重合率 "
                        f"{ratio:.0%}（共同标题 {len(shared)} 个）"
                    )
                shared_tables = set(a["table_fps"]) & set(b["table_fps"])
                if len(shared_tables) >= 3:
                    errors.append(
                        f"同批文档表格结构同构：{names[i]} 与 {names[j]} 共享 "
                        f"{len(shared_tables)} 个表格结构指纹"
                    )
                para_a = {h for h, _ in a["paras"]}
                para_b = {h for h, _ in b["paras"]}
                shared_paras = para_a & para_b
                if len(shared_paras) >= 3:
                    errors.append(
                        f"同批文档存在重复段落：{names[i]} 与 {names[j]} 共享 "
                        f"{len(shared_paras)} 个相同段落"
                    )

    return {
        "status": "pass" if not errors else "blocked",
        "batch_id": batch_id,
        "documents": names,
        "errors": errors,
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
        for w in report["warnings"]:
            print(f"  WARNING: {w}")
    if report["status"] == "invalid":
        sys.exit(2)
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
