#!/usr/bin/env python3
"""Extract real source code and create Markdown draft pages."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import COPYRIGHT_CODE_EXTS, FRONTEND_EXTS, confirm_params, ensure_dir, is_known_config_file, iter_project_files, looks_binary, read_json, read_text, rel, resolve_draft_dir, safe_filename, write_json


LINES_PER_PAGE = 50
SPLIT_THRESHOLD_PAGES = 60


def category_weight(path: Path, project: Path) -> tuple[int, str]:
    r = rel(path, project).lower()
    name = path.name.lower()
    priority = 80
    if name in {"main.ts", "main.js", "main.tsx", "main.jsx", "app.vue", "app.tsx"} or r in {
        "src/app/page.tsx",
        "src/app/layout.tsx",
        "app/page.tsx",
        "app/layout.tsx",
    } or r.endswith("/src/app/page.tsx") or r.endswith("/src/app/layout.tsx"):
        priority = 0
    elif path.suffix.lower() in {".css", ".scss", ".sass", ".less"}:
        priority = 90
    elif "/router/" in r or "/routes/" in r or "router." in r or "routes." in r:
        priority = 10
    elif "/pages/" in r or "/views/" in r or "/app/" in r or "/screens/" in r:
        priority = 20
    elif "/api/" in r or "/apis/" in r or "/services/" in r or "request." in r:
        priority = 30
    elif "/store/" in r or "/stores/" in r or "/pinia/" in r or "/redux/" in r:
        priority = 40
    elif "/components/" in r:
        priority = 50
    elif "/utils/" in r or "/lib/" in r or "/hooks/" in r or "/composables/" in r:
        priority = 60
    elif path.suffix.lower() not in FRONTEND_EXTS:
        if any(part in r for part in ("/backend/app/", "/server/", "/api/", "/services/", "/models/", "/schemas/", "/workers/")):
            priority = 70
        elif name in {"docker-compose.yml", "docker-compose.yaml", "pyproject.toml"} or path.suffix.lower() in {".toml", ".yml", ".yaml"}:
            priority = 95
        else:
            priority = 100
    return priority, r


def should_skip_file(path: Path) -> bool:
    if path.suffix.lower() not in COPYRIGHT_CODE_EXTS:
        return True
    if is_known_config_file(path):
        return True
    if looks_binary(path):
        return True
    try:
        size = path.stat().st_size
    except OSError:
        return True
    if size <= 0 or size > 800_000:
        return True
    try:
        sample = read_text(path, limit=20_000)
    except Exception:
        return True
    lines = sample.splitlines()
    if any(len(line) > 3000 for line in lines[:80]):
        return True
    return False


def selected_line_estimate(item: dict[str, Any]) -> int:
    try:
        total = int(item.get("line_count") or 0)
    except (TypeError, ValueError):
        total = 0
    return total + 2 if total > 0 else 0


def available_pages_from_selection(selection_path: Path | None, lines_per_page: int) -> tuple[int, int, int]:
    if selection_path is None or not selection_path.exists():
        return 0, 0, 0
    data = read_json(selection_path)
    items = data.get("files") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return 0, 0, 0
    available_lines = sum(selected_line_estimate(item) for item in items if isinstance(item, dict))
    unselected = sum(1 for item in items if isinstance(item, dict) and not item.get("selected") and selected_line_estimate(item) > 0)
    pages = (available_lines + lines_per_page - 1) // lines_per_page if available_lines else 0
    return available_lines, pages, unselected


def marker_for(path: Path, project: Path) -> str:
    return f"// File: {rel(path, project)}"


def load_selected_files(project: Path, selection_path: Path | None) -> list[dict[str, Any]]:
    if selection_path is None:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 代码抽取必须先使用 propose_code_selection.py 生成并确认 草稿/代码文件选择.json，"
            "或使用 propose_evidence_plan.py 生成并确认 草稿/材料证据计划.json。"
        )

    data = read_json(selection_path)

    # ── v2: material evidence plan drives extraction ──
    if data.get("schema_version") == 3 and isinstance(data.get("code_evidence"), list):
        gate_file = selection_path.parent.parent / "门禁状态.json"
        gate_confirmed = False
        if gate_file.exists():
            try:
                gates = read_json(gate_file)
                gate_confirmed = gates.get("material-plan", {}).get("confirmed", False)
            except Exception:
                pass
        if not gate_confirmed:
            raise SystemExit(
                "STOP_FOR_USER\n"
                "NEXT_ACTION: 材料证据计划尚未确认。请先运行 evidence_plan_check.py 并确认 material-plan 门禁。"
            )
        roots = {r.get("root_id", "primary"): Path(r["path"]) for r in data.get("input_roots") or []}
        selected = []
        for item in data["code_evidence"]:
            if not isinstance(item, dict) or not item.get("selected"):
                continue
            root_id = item.get("root_id", "primary")
            root = roots.get(root_id)
            if root is None:
                raise SystemExit(f"计划中的输入根不存在: {root_id}")
            selected.append(
                {
                    "root_id": root_id,
                    "path": str(item.get("path", "")),
                    "selected": True,
                    "project": root,
                    "line_range": item.get("line_range"),
                    "sha256": item.get("sha256", ""),
                }
            )
        return selected

    # ── legacy v1: 代码文件选择.json ──
    # Check gate: old inline user_confirmed or new 门禁状态.json
    gate_file = selection_path.parent.parent / "门禁状态.json"
    gate_confirmed = False
    if gate_file.exists():
        try:
            gates = read_json(gate_file)
            gate_confirmed = gates.get("code-selection", {}).get("confirmed", False)
        except Exception:
            pass
    confirmed = data.get("user_confirmed") or gate_confirmed
    if isinstance(data, dict) and data.get("selection_required") and not confirmed:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 代码文件选择尚未确认。请先确认或修改 草稿/代码文件选择.json，"
            "再运行 `python3 <SKILL_DIR>/scripts/confirm_stage.py --workdir <任务目录> --stage code-selection --note \"<用户确认内容>\" --confirm`。"
        )
    items = data.get("files") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit(f"Invalid selection file: {selection_path}")

    selected = []
    for item in items:
        if not isinstance(item, dict) or not item.get("selected"):
            continue
        path_value = item.get("path")
        if not path_value:
            continue
        selected.append(
            {
                "path": str(path_value),
                "selected": True,
                "project": project,
                "line_range": item.get("line_range"),
                "sha256": item.get("sha256", ""),
            }
        )
    return selected


def _sha256_of(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_dead_code(lines: list[str]) -> tuple[list[str], int]:
    """v1.6 死代码清理（默认关）：移除注释掉的代码块与 console.log，不动业务逻辑。
    返回 (清理后行列表, 移除行数)。"""
    out: list[str] = []
    removed = 0
    in_block = False
    for line in lines:
        stripped = line.strip()
        if in_block:
            removed += 1
            if '*/' in stripped:
                in_block = False
            continue
        # 整行 /* ... */ 注释
        if stripped.startswith('/*') and stripped.endswith('*/'):
            removed += 1
            continue
        # 行中 /* 开始的块注释（可能跨行）
        if stripped.startswith('/*'):
            in_block = True
            removed += 1
            if '*/' in stripped:
                in_block = False
            continue
        # 注释掉的代码行：// 开头且剩余内容含代码特征（非纯文字注释）
        if stripped.startswith('//'):
            body = stripped[2:].strip()
            code_like = any(tok in body for tok in ('=', ';', '{', '}', '(', ')', '=>', 'return', 'const ', 'let ', 'var ', 'import '))
            if code_like and not body.startswith(('File:', '[')):
                removed += 1
                continue
        # console.log 调试语句（含跨行）
        if re.match(r'^(console\.(log|debug|info)\s*\(|[a-zA-Z_$.]*console\.log\s*\()', stripped):
            removed += 1
            continue
        out.append(line)
    return out, removed


def collect_code_lines(project: Path, selection_path: Path | None) -> tuple[list[str], list[dict[str, Any]]]:
    selected_items = load_selected_files(project, selection_path)
    dead_code_clean = False

    # ── v1.6 编排求解器接入（switches.layout-solver != off 时自动求解顺序）──
    layout_report: dict[str, Any] | None = None
    if selection_path is not None and Path(selection_path).exists():
        sel_data = read_json(Path(selection_path))
        if sel_data.get('schema_version') == 3:
            gate_file = Path(selection_path).parent.parent / '门禁状态.json'
            gates = read_json(gate_file) if gate_file.exists() else {}
            if str(gates.get('switches', {}).get('layout-solver', 'on')) != 'off':
                import layout_solver as _ls
                _items = _ls.load_items(sel_data)
                layout_report = _ls.solve(_items, sel_data)
                if layout_report.get('gaps'):
                    raise SystemExit(
                        'STOP_FOR_USER\n'
                        'NEXT_ACTION: 编排求解无解（每核心模块至少一个完整证据单元入前30/后30页）：\n'
                        + '\n'.join(f'- {g}' for g in layout_report['gaps'])
                        + ('\n建议：\n' + '\n'.join(f'- {s}' for s in layout_report.get('suggestions', [])) if layout_report.get('suggestions') else '')
                    )
                _order_map = {p: i for i, p in enumerate(layout_report.get('order', []))}
                selected_items.sort(key=lambda it: _order_map.get(str(it.get('path', '')).replace('\\', '/'), 9999))
                _gates_file = Path(selection_path).parent.parent / '门禁状态.json'
                _gates = read_json(_gates_file) if _gates_file.exists() else {}
                dead_code_clean = str(_gates.get('switches', {}).get('dead-code-clean', 'off')) == 'on'
                # v1.8 文件标记与 page-annotations 同开关：off 时材料为纯源码，无 File/源行标注
                file_marker_on = str(_gates.get('switches', {}).get('page-annotations', 'on')) != 'off'
    all_lines: list[str] = []
    manifest_files: list[dict[str, Any]] = []

    for item in selected_items:
        item_project = item.get("project") or project
        path = (item_project / item["path"]).resolve()
        try:
            path.relative_to(item_project.resolve())
        except ValueError:
            raise SystemExit(f"Selected file is outside project: {path}")
        if should_skip_file(path):
            continue
        if item.get("sha256") and _sha256_of(path) != item["sha256"]:
            raise SystemExit(
                f"STOP_FOR_USER\n文件哈希与计划不一致（文件已被修改）: {item['path']}\n"
                "请重新生成或确认材料证据计划。"
            )
        text = read_text(path)
        source_lines = text.splitlines()
        line_range = item.get("line_range")
        if isinstance(line_range, list) and len(line_range) == 2:
            start_line, end_line = int(line_range[0]), int(line_range[1])
            if start_line < 1 or end_line > len(source_lines) or start_line > end_line:
                raise SystemExit(f"行段超出文件范围: {item['path']} {line_range}")
            selected_lines = source_lines[start_line - 1 : end_line]
        else:
            start_line, end_line = 1, len(source_lines)
            selected_lines = source_lines
        # v1.6 死代码清理（默认关，开关 on 时材料为清理版）
        cleaned = False
        removed_n = 0
        if dead_code_clean:
            selected_lines, removed_n = clean_dead_code(selected_lines)
            cleaned = True
        start = len(all_lines) + 1
        if file_marker_on:
            marker = marker_for(path, item_project)
            all_lines.append(marker)
        all_lines.extend(selected_lines)
        end = len(all_lines)
        manifest_files.append(
            {
                "root_id": item.get("root_id", "primary"),
                "path": rel(path, item_project),
                "sha256": _sha256_of(path),
                "source_line_count": len(source_lines),
                "selected_line_start": start_line,
                "selected_line_end": end_line,
                "selected_line_count": len(selected_lines),
                "cleaned": cleaned,
                "removed_lines": removed_n,
                "material_line_start": start,
                "material_line_end": end,
            }
        )
    return all_lines, manifest_files, layout_report


def paginate(lines: list[str], lines_per_page: int) -> list[list[str]]:
    return [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]


def paginate_dense(lines: list[str], lines_per_page: int, max_total_per_page: int = 65) -> list[list[str]]:
    """v1.8 纯代码分页：每页必须凑满 lines_per_page 行非空代码；
    总行数（含空行）上限 max_total_per_page 仅防极端溢出（10.5pt×65行=682.5pt < A4 可用 728.5pt）。"""
    pages: list[list[str]] = []
    cur: list[str] = []
    n = 0
    total = 0
    for l in lines:
        cur.append(l)
        total += 1
        if l.strip():
            n += 1
        if n >= lines_per_page:
            pages.append(cur)
            cur = []
            n = 0
            total = 0
        elif total >= max_total_per_page:
            # 总行先到上限：把当前空行截到下一块，优先保证本块凑满 50 行代码
            pages.append(cur)
            cur = []
            n = 0
            total = 0
    if cur:
        pages.append(cur)
    return pages


def page_annotations(files: list[dict[str, Any]], total_lines: int, lines_per_page: int) -> dict[int, str]:
    """v1.6 每页首行标注：// [文件路径 | 本页源行段 S-E | 文件总行 L]（注释形式，可回溯）。"""
    ann: dict[int, str] = {}
    page_count = (total_lines + lines_per_page - 1) // lines_per_page
    for pno in range(1, page_count + 1):
        start = (pno - 1) * lines_per_page + 1
        end = min(pno * lines_per_page, total_lines)
        hit = None
        for f in files:
            fs, fe = int(f['material_line_start']), int(f['material_line_end'])
            if fs <= start <= fe:
                hit = f
                break
        if hit is None:
            ann[pno] = '// [跨文件页]'
            continue
        # 源行偏移：material 行首是 marker，源首行在 material_line_start+1
        off = max(start - int(hit['material_line_start']) - 1, 0)
        s_src = int(hit['selected_line_start']) + off
        e_src = min(s_src + (end - start), int(hit['selected_line_end']))
        ann[pno] = f"// [{hit['path']} | 源行 {s_src}-{e_src} | 总 {hit['source_line_count']}]"
    return ann


def write_pages_md(path: Path, title: str, software_name: str, version: str, pages: list[tuple[int, list[str]]], annotations: dict[int, str] | None = None) -> None:
    chunks = [f"# {title}", "", f"软件名称：{software_name}", f"版本号：{version}", ""]
    for page_no, page_lines in pages:
        chunks.extend([f"## 第 {page_no} 页", "", "```text"])
        if annotations and annotations.get(page_no):
            chunks.append(annotations[page_no])
        chunks.extend(page_lines)
        chunks.extend(["```", ""])
    path.write_text("\n".join(chunks), encoding="utf-8")


def write_pages_md_append(path: Path, title: str, software_name: str, version: str, pages: list[tuple[int, list[str]]], annotations: dict[int, str] | None = None) -> None:
    """Append back-page material to an existing MD file (no duplicate header)."""
    chunks = [f"# {title}", f"软件名称：{software_name}", f"版本号：{version}", ""]
    for page_no, page_lines in pages:
        chunks.extend([f"## 第 {page_no} 页", "", "```text"])
        if annotations and annotations.get(page_no):
            chunks.append(annotations[page_no])
        chunks.extend(page_lines)
        chunks.extend(["```", ""])
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(chunks) + "\n")


def write_manifest_md(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# 代码提取清单",
        "",
        f"- 软件名称：{manifest['software_name']}",
        f"- 版本号：{manifest['version']}",
        f"- 项目目录：{manifest['project_root']}",
        f"- 源码文件数：{manifest['file_count']}",
        f"- 材料代码行数：{manifest['material_line_count']}",
        f"- 每页行数：{manifest['lines_per_page']}",
        f"- 总页数：{manifest['total_pages']}",
        f"- 目标页数：{manifest['target_pages']}",
        f"- 候选源码可生成页数：{manifest['available_candidate_pages']}",
        f"- 补充状态：{manifest['supplement_status']}",
        f"- 输出模式：{manifest['mode']}",
        "",
        "## 文件来源",
        "",
        "| 文件 | 源码行数 | 抽取源码范围 | 抽取行数 | 材料行范围 |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    for item in manifest["files"]:
        lines.append(
            f"| `{item['path']}` | {item['source_line_count']} | "
            f"{item['selected_line_start']}-{item['selected_line_end']} | "
            f"{item['selected_line_count']} | "
            f"{item['material_line_start']}-{item['material_line_end']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract(project: Path, out_dir: Path, software_name: str, version: str, lines_per_page: int, selection_path: Path | None) -> dict[str, Any]:
    ensure_dir(out_dir)
    code_lines, files, layout_report = collect_code_lines(project, selection_path)
    if not code_lines:
        raise SystemExit("No selected frontend source code files found for extraction.")

    pages = paginate(code_lines, lines_per_page)
    total_pages = len(pages)
    available_lines, available_pages, unselected_count = available_pages_from_selection(selection_path, lines_per_page)
    if total_pages < SPLIT_THRESHOLD_PAGES and available_pages >= SPLIT_THRESHOLD_PAGES and unselected_count > 0:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 当前已选代码只有 {total_pages} 页，但候选源码足够补齐到 {SPLIT_THRESHOLD_PAGES} 页。"
            "请在 草稿/代码文件选择.json 中继续选择补充文件，重新记录 code-selection 门禁后再抽取。"
        )
    outputs: list[str] = []

    if total_pages >= SPLIT_THRESHOLD_PAGES:
        # v1.8 前后端分池 + 纯代码分页：前 30 页=前端完整文件（非空代码 50 行/页），后 30 页=后端完整文件；
        # 纯前端选材时后 30 页 = 材料末尾 30 页（尾部）
        front_files = [f for f in files if f.get("root_id") in ("primary", "web", "screen")]
        back_files = [f for f in files if f.get("root_id") == "backend"]

        def lines_of(flist):
            out: list[str] = []
            for f in flist:
                out.extend(code_lines[int(f["material_line_start"]) - 1 : int(f["material_line_end"])])
            return out

        front_pages = paginate_dense(lines_of(front_files), lines_per_page)
        if back_files:
            back_pages = paginate_dense(lines_of(back_files), lines_per_page)[:30]
            front_pages = front_pages[:30]
        else:
            # 纯前端：前 30 页 + 末尾 30 页；末尾不足每页行数的残页舍弃，保证每页满行
            full_pages = front_pages if len(front_pages[-1]) == lines_per_page else front_pages[:-1]
            back_pages = full_pages[-30:] if len(full_pages) > 30 else []
            front_pages = full_pages[:30]
        front = list(enumerate(front_pages[:30], start=1))
        back = list(enumerate(back_pages[:30], start=31))
        combined_path = out_dir / "代码-前后30页.md"
        # v1.6 页首行段标注（switches.page-annotations != off）
        annotations = None
        if selection_path is not None and Path(selection_path).exists():
            _gf = Path(selection_path).parent.parent / '门禁状态.json'
            _g = read_json(_gf) if _gf.exists() else {}
            if str(_g.get('switches', {}).get('page-annotations', 'on')) != 'off':
                annotations = page_annotations(files, len(code_lines), lines_per_page)
        write_pages_md(combined_path, "代码材料（前30页）", software_name, version, front, annotations)
        # Append back 30 pages to same file
        with open(combined_path, "a", encoding="utf-8") as f:
            f.write("\n")
        write_pages_md_append(combined_path, "代码材料（后30页）", software_name, version, back, annotations)
        outputs.append(combined_path.name)
        mode = "front30_back30"
        # v1.8 后置拦截：材料实际页数必须 ≥60，不足则停止要求补选（防 59 页漏网）
        _material_pages = len(front) + len(back)
        if _material_pages < SPLIT_THRESHOLD_PAGES:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"NEXT_ACTION: 代码材料实际仅 {_material_pages} 页（前 {len(front)} + 后 {len(back)}），不足 60 页。"
                "请在 材料证据计划.json 中补选代码文件（或放宽 layout_solver 容量）后重新抽取。"
            )
    else:
        all_path = out_dir / "代码-全部.md"
        all_pages = list(enumerate(pages, start=1))
        write_pages_md(all_path, "代码材料（全部）", software_name, version, all_pages)
        outputs.append(all_path.name)
        mode = "all_under_60_pages"
    supplement_status = (
        "候选源码可达到前30页/后30页要求"
        if available_pages >= SPLIT_THRESHOLD_PAGES
        else "候选源码不足60页，按全部代码材料生成"
    )

    manifest = {
        "software_name": software_name,
        "version": version,
        "project_root": str(project.resolve()),
        "file_count": len(files),
        "material_line_count": len(code_lines),
        "source_line_count": sum(item["source_line_count"] for item in files),
        "selected_source_line_count": sum(item["selected_line_count"] for item in files),
        "lines_per_page": lines_per_page,
        "total_pages": total_pages,
        "target_pages": SPLIT_THRESHOLD_PAGES,
        "available_candidate_line_count": available_lines,
        "available_candidate_pages": available_pages,
        "supplement_status": supplement_status,
        "mode": mode,
        "selection_file": str(selection_path) if selection_path else None,
        "outputs": outputs,
        "files": files,
        "safe_software_filename": safe_filename(software_name),
    }
    if layout_report:
        manifest["order_solution"] = layout_report
    write_json(out_dir / "代码提取清单.json", manifest)
    write_manifest_md(out_dir / "代码提取清单.md", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--analysis", help="Optional project analysis JSON; retained for workflow traceability")
    parser.add_argument("--software-name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out-dir", help="Draft output dir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument("--lines-per-page", type=int, default=LINES_PER_PAGE)
    parser.add_argument("--selection", help="Editable JSON file created by propose_code_selection.py")
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    args = parser.parse_args()

    project = Path(args.project)
    if not project.exists():
        raise SystemExit(f"Project not found: {project}")
    if args.analysis and not Path(args.analysis).exists():
        raise SystemExit(f"Analysis JSON not found: {args.analysis}")

    selection = Path(args.selection) if args.selection else None
    if selection and not selection.exists():
        raise SystemExit(f"Selection JSON not found: {selection}")

    out_dir = Path(args.out_dir) if args.out_dir else resolve_draft_dir(args.task_dir)

    confirm_params({"输出目录": str(out_dir), "软件名称": args.software_name, "版本号": args.version, "项目目录": str(project)}, args.confirm)
    manifest = extract(project, out_dir, args.software_name, args.version, args.lines_per_page, selection)
    print(f"OK code drafts: {out_dir}")
    print(f"Selected files: {manifest['file_count']}")
    print(f"Mode: {manifest['mode']}")
    print(f"Total pages: {manifest['total_pages']}")
    print(f"Outputs: {', '.join(manifest['outputs'])}")


if __name__ == "__main__":
    main()
