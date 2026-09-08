#!/usr/bin/env python3
"""Export Feishu whiteboards as content-fitted SVG and Word-ready white PNG files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


WHITEBOARD_URL_RE = re.compile(r"https?://[^\s|]+/whiteboard/([A-Za-z0-9_-]+)")
IMAGE_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^\)]+)(\))")


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
                cells = [c for c in cells if c not in {"本地文件", "SVG源文件", "Word图片"}]
                cells.extend(["SVG源文件", "Word图片"])
                chart_table_columns = len(cells)
                out.append("| " + " | ".join(cells) + " |")
                continue
            if in_chart_table and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                out.append("| " + " | ".join(["---"] * chart_table_columns) + " |")
                continue
            match = next((WHITEBOARD_URL_RE.search(cell) for cell in cells if "whiteboard/" in cell), None)
            if in_chart_table and match and match.group(1) in chart_map:
                chart = chart_map[match.group(1)]
                # Drop old local-file columns, preserving columns through the whiteboard URL.
                url_idx = next(i for i, c in enumerate(cells) if "whiteboard/" in c)
                cells = cells[: url_idx + 1]
                safe = safe_filename(chart.name)
                cells.extend([f"../截图/{safe}.svg", f"../截图/{safe}.png"])
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


def export_chart(chart: Chart, output_dir: Path, width: int, height: int, identity: str) -> tuple[Path, Path]:
    safe = safe_filename(chart.name)
    svg = output_dir / f"{safe}.svg"
    png = output_dir / f"{safe}.png"
    native = output_dir / f".{safe}.native.png"

    run_checked([
        command("lark-cli"), "whiteboard", "+export",
        "--whiteboard-token", chart.token,
        "--output-type", "svg",
        "--output", f"./{svg.name}",
        "--overwrite", "--as", identity,
    ], output_dir)

    npx = command("npx")
    run_checked([npx, "-y", "sharp-cli", "-i", f"./{svg.name}", "-o", f"./{native.name}", "flatten", "white"], output_dir)
    run_checked([
        npx, "-y", "sharp-cli", "-i", f"./{native.name}", "-o", f"./{png.name}",
        "resize", str(width), str(height), "--fit", "inside",
    ], output_dir)
    native.unlink(missing_ok=True)
    return svg, png


def main() -> int:
    parser = argparse.ArgumentParser(description="飞书画板 SVG 自适应导出与 Word 白底 PNG 转换")
    parser.add_argument("--chart-list", required=True, help="草稿/技术图表清单.md")
    parser.add_argument("--output-dir", required=True, help="截图目录")
    parser.add_argument("--manual", help="操作手册.md；提供后自动切换图表引用到 PNG")
    parser.add_argument("--width", type=int, default=2400, help="Word PNG 最大宽度，默认 2400")
    parser.add_argument("--height", type=int, default=3200, help="Word PNG 最大高度，默认 3200")
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
        svg, png = export_chart(chart, output_dir, args.width, args.height, args.identity)
        results.append({"name": chart.name, "token": chart.token, "svg": str(svg), "png": str(png)})
        print(f"OK {chart.name}: {svg.name} + {png.name}")

    chart_list.write_text(update_chart_list(text, charts), encoding="utf-8")
    if args.manual:
        manual = Path(args.manual).resolve()
        manual.write_text(update_manual_references(manual.read_text(encoding="utf-8"), charts), encoding="utf-8")

    report = output_dir / "技术图表SVG导出报告.json"
    report.write_text(json.dumps({
        "mode": "svg-adaptive",
        "png_background": "white",
        "png_max_width": args.width,
        "png_max_height": args.height,
        "png_fit": "inside",
        "charts": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"导出完成: {len(results)} 张；报告: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
