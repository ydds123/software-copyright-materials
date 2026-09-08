#!/usr/bin/env python3
"""Export Feishu whiteboards as Word-ready PNG files.

导出策略：飞书画板导出为 preview 完整快照，再按内容包围盒裁剪。
飞书 SVG 导出的 viewBox 只覆盖「画板视口」，非中心布局的画板（如带分支的纵向流程图）
内容会超出 viewBox 而被裁剪，因此 SVG 路径不可靠，统一使用 preview + 内容裁剪。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

WHITEBOARD_URL_RE = re.compile(r"https?://[^\s|]+/whiteboard/([A-Za-z0-9_-]+)")
IMAGE_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^\)]+)(\))")
MARGIN = 24


@dataclass(frozen=True)
class Chart:
    name: str
    token: str


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")
    return cleaned or "chart"


def parse_chart_rows(text: str) -> list[Chart]:
    charts: list[Chart] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        match = next((WHITEBOARD_URL_RE.search(cell) for cell in cells if "whiteboard/" in cell), None)
        if not match:
            continue
        token = match.group(1)
        name = cells[1] if cells[0].isdigit() and len(cells) > 1 else cells[0]
        if token not in seen:
            charts.append(Chart(name=name, token=token))
            seen.add(token)
    return charts


def update_manual_references(text: str, charts: list[Chart]) -> str:
    names = {chart.name: safe_filename(chart.name) for chart in charts}

    def replace(match: re.Match[str]) -> str:
        prefix, path, suffix = match.groups()
        stem = Path(path.replace("\\", "/")).stem
        for name, safe in names.items():
            if stem == name or stem.startswith(name + "-"):
                return f"{prefix}../截图/{safe}.png{suffix}"
        return match.group(0)

    return IMAGE_REF_RE.sub(replace, text)


def update_chart_list(text: str, charts: list[Chart]) -> str:
    chart_map = {chart.token: chart for chart in charts}
    lines = text.splitlines()
    out: list[str] = []
    in_chart_table = False
    chart_table_columns = 0
    for line in lines:
        if line.lstrip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if "图表名称" in cells and "画板链接" in cells:
                in_chart_table = True
                cells = [c for c in cells if c not in {"本地文件", "SVG源文件", "Word图片", "SVG源文件｜Word图片"}]
                if "本地文件" not in cells:
                    cells.append("本地文件")
                chart_table_columns = len(cells)
                out.append("| " + " | ".join(cells) + " |")
                continue
            if in_chart_table and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                out.append("| " + " | ".join(["---"] * chart_table_columns) + " |")
                continue
            match = next((WHITEBOARD_URL_RE.search(cell) for cell in cells if "whiteboard/" in cell), None)
            if in_chart_table and match and match.group(1) in chart_map:
                chart = chart_map[match.group(1)]
                url_idx = next(i for i, c in enumerate(cells) if "whiteboard/" in c)
                cells = cells[: url_idx + 1]
                safe = safe_filename(chart.name)
                cells.append(f"../截图/{safe}.png")
                out.append("| " + " | ".join(cells) + " |")
                continue
        else:
            in_chart_table = False
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def command(name: str) -> str:
    found = shutil.which(name) or shutil.which(name + ".cmd") or shutil.which(name + ".exe")
    if not found:
        raise RuntimeError(f"命令不可用: {name}")
    return found


def run_checked(args: list[str], cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"命令失败 ({result.returncode}): {' '.join(args[:4])}\n{detail[:1000]}")


def crop_to_content(image: Image.Image, margin: int = MARGIN) -> Image.Image:
    """按非白内容包围盒裁剪，保留 margin 边距。"""
    arr = np.asarray(image.convert("RGB"))
    nonwhite = np.any(arr < 240, axis=2)
    rows = np.where(nonwhite.any(axis=1))[0]
    cols = np.where(nonwhite.any(axis=0))[0]
    if not rows.any():
        raise RuntimeError("图片内容全白")
    y0 = max(0, int(rows[0]) - margin)
    y1 = min(image.height - 1, int(rows[-1]) + margin)
    x0 = max(0, int(cols[0]) - margin)
    x1 = min(image.width - 1, int(cols[-1]) + margin)
    return image.crop((x0, y0, x1 + 1, y1 + 1))


def export_chart(chart: Chart, output_dir: Path, identity: str) -> tuple[Path, Path]:
    """导出 preview 完整快照并按内容裁剪，返回 (png 路径, 源快照信息)。"""
    safe = safe_filename(chart.name)
    png = output_dir / f"{safe}.png"
    tmp = output_dir / f".preview_{chart.token}.jpg"

    run_checked([
        command("lark-cli"), "whiteboard", "+export",
        "--whiteboard-token", chart.token,
        "--output-type", "preview",
        "--output", f"./{tmp.name}",
        "--overwrite", "--as", identity,
    ], output_dir)

    im = Image.open(tmp)
    cropped = crop_to_content(im)
    cropped.save(png, quality=92)
    tmp.unlink(missing_ok=True)
    return png, cropped.size


def main() -> int:
    parser = argparse.ArgumentParser(description="飞书画板 preview 完整快照导出与 Word 白底 PNG（内容包围盒裁剪）")
    parser.add_argument("--chart-list", required=True, help="草稿/技术图表清单.md")
    parser.add_argument("--output-dir", required=True, help="截图目录")
    parser.add_argument("--manual", help="操作手册.md；提供后自动切换图表引用到 PNG")
    parser.add_argument("--as", dest="identity", choices=["user", "bot"], default="user")
    args = parser.parse_args()

    chart_list = Path(args.chart_list).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    text = chart_list.read_text(encoding="utf-8")
    charts = parse_chart_rows(text)
    if not charts:
        raise SystemExit("未在技术图表清单中找到飞书画板链接")

    results = []
    for chart in charts:
        png, size = export_chart(chart, output_dir, args.identity)
        results.append({"name": chart.name, "token": chart.token, "png": str(png), "size": list(size)})
        print(f"OK {chart.name}: {size[0]}x{size[1]} -> {png.name}")

    chart_list.write_text(update_chart_list(text, charts), encoding="utf-8")
    if args.manual:
        manual = Path(args.manual).resolve()
        manual.write_text(update_manual_references(manual.read_text(encoding="utf-8"), charts), encoding="utf-8")

    report = output_dir / "技术图表SVG导出报告.json"
    report.write_text(json.dumps({
        "mode": "preview-crop",
        "note": "飞书 SVG 导出的 viewBox 只覆盖画板视口，非中心布局画板内容会被裁剪；统一使用 preview 完整快照 + 内容包围盒裁剪（margin 24px）",
        "charts": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"导出完成: {len(results)} 张；报告: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
