#!/usr/bin/env python3
"""Best-effort screenshot helpers for operation manuals."""

from __future__ import annotations

import argparse
import json
import shutil
import re
from pathlib import Path
from urllib.parse import urljoin

from common import confirm_params, ensure_dir, read_json, resolve_screenshot_dir, resolve_task_dir, write_json


def safe_name(path: str) -> str:
    value = path.strip("/") or "home"
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:80] or "page"


def collect_manual_screenshots(input_dir: Path, out_dir: Path) -> dict[str, object]:
    out_dir = ensure_dir(out_dir)
    screenshots = []
    errors = []
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    for index, path in enumerate(sorted(input_dir.iterdir()), start=1):
        if path.suffix.lower() not in allowed or not path.is_file():
            continue
        target = out_dir / f"{index:02d}-{safe_name(path.stem)}{path.suffix.lower()}"
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
        screenshots.append({"route": "", "url": "", "path": str(target), "source": str(path)})
    if not screenshots:
        errors.append({"error": f"no screenshot images found in {input_dir}"})
    manifest = {
        "status": "ok" if screenshots else "empty",
        "method": "user-supplied",
        "screenshots": screenshots,
        "errors": errors,
    }
    write_json(out_dir / "截图清单.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--analysis")
    parser.add_argument("--out-dir", help="Screenshot output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--manual-dir", help="Collect user-supplied screenshots from this directory")
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    args = parser.parse_args()

    task_dir = args.task_dir
    if not task_dir:
        found = resolve_task_dir()
        task_dir = str(found) if found else None
    out_dir = Path(args.out_dir) if args.out_dir else (resolve_screenshot_dir(task_dir) if task_dir else None)
    if out_dir is None:
        raise SystemExit("找不到任务目录。请用 --task-dir 指定。")
    ensure_dir(out_dir)

    confirm_params({"截图输出目录": str(out_dir)}, args.confirm)

    if args.manual_dir:
        manifest = collect_manual_screenshots(Path(args.manual_dir), Path(args.out_dir))
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if not manifest["screenshots"]:
            raise SystemExit(3)
        return

    if not args.base_url or not args.analysis:
        raise SystemExit("Missing --base-url and --analysis unless --manual-dir is provided")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(json.dumps({"status": "error", "reason": f"playwright unavailable: {exc}"}, ensure_ascii=False))
        raise SystemExit(2)

    analysis = read_json(Path(args.analysis))
    paths = analysis.get("routes") or ["/"]
    clean_paths = []
    for path in paths:
        if isinstance(path, str) and path.startswith("/") and path not in clean_paths:
            clean_paths.append(path)
    clean_paths = clean_paths[: args.max_pages] or ["/"]

    out_dir = ensure_dir(Path(args.out_dir))
    screenshots = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for route in clean_paths:
            url = urljoin(args.base_url.rstrip("/") + "/", route.lstrip("/"))
            file_path = out_dir / f"{safe_name(route)}.png"
            try:
                page.goto(url, wait_until="networkidle", timeout=15_000)
                page.screenshot(path=str(file_path), full_page=True)
                screenshots.append({"route": route, "url": url, "path": str(file_path)})
            except Exception as exc:
                errors.append({"route": route, "url": url, "error": str(exc)})
        browser.close()

    manifest = {"status": "ok" if screenshots else "partial", "screenshots": screenshots, "errors": errors}
    write_json(out_dir / "截图清单.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if not screenshots:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
