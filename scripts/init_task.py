#!/usr/bin/env python3
"""Initialize a task directory for a new copyright application.

Creates the standard directory structure under a year-prefixed workspace:

    <project>/<year>年软件著作权申请资料/<software-name>/
    ├── 任务登记.json
    ├── analysis/
    ├── 草稿/
    ├── 正式资料/
    ├── 截图/
    └── 用户截图/

If called without --confirm, prints the proposed path and exits with
STOP_FOR_USER so the model must ask the user before creating anything.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ensure_dir, proposed_task_path, write_json


TASK_FILE = "任务登记.json"
SUBDIRS = ["analysis", "草稿", "正式资料", "截图", "用户截图"]


def init_task(task_dir: Path, software_name: str, project_root: str) -> dict[str, Any]:
    dirs = [task_dir / name for name in SUBDIRS]
    for d in dirs:
        ensure_dir(d)

    meta = {
        "software_name": software_name,
        "project_root": str(Path(project_root).resolve()),
        "task_dir": str(task_dir.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "init",
        "directories": {d.name: str(d.resolve()) for d in dirs},
    }
    write_json(task_dir / TASK_FILE, meta)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a copyright task directory")
    parser.add_argument("--project", required=True, help="Project root (where source code lives)")
    parser.add_argument("--software-name", required=True, help="Software full name for this copyright")
    parser.add_argument("--year", type=int, help="Year for workspace prefix (defaults to current year)")
    parser.add_argument("--task-dir", help="Explicit task directory (overrides --project/--year/--software-name)")
    parser.add_argument("--confirm", action="store_true", help="User has approved the proposed path")
    args = parser.parse_args()

    project = Path(args.project)
    if args.task_dir:
        task_dir = Path(args.task_dir)
    else:
        task_dir = proposed_task_path(project, args.software_name, args.year)

    if not args.confirm:
        print(f"项目目录：{project.resolve()}")
        print(f"建议输出路径：{task_dir.resolve()}")
        print(f"内部结构：{'/'.join(SUBDIRS[:3])}/...")
        if task_dir.exists():
            print(f"⚠️  路径已存在，将继续使用现有目录")
        print()
        print("STOP_FOR_USER")
        print("NEXT_ACTION: 请确认以上路径是否正确。确认后加 --confirm 重新运行。")
        raise SystemExit(0)

    meta = init_task(task_dir, args.software_name, str(project.resolve()))
    print(f"OK task init: {task_dir}")
    print(f"Software: {meta['software_name']}")
    print(f"Project: {meta['project_root']}")
    for name, path in meta["directories"].items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
