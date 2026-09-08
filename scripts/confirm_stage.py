#!/usr/bin/env python3
"""Record explicit user confirmations for gated workflow stages.

All gates are recorded in a single file: <workdir>/门禁状态.json
Previous scattered files (环境确认.json, 项目确认.json, 截图方式确认.json, etc.)
are consolidated into this one file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import confirm_params, read_json, resolve_workdir, write_json

GATE_FILE = "门禁状态.json"
MATERIAL_PLAN_FILE = "材料证据计划.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_gates(workdir: Path) -> dict[str, Any]:
    path = workdir / GATE_FILE
    if not path.exists():
        return {}
    return read_json(path)


def write_gate(workdir: Path, gate: str, note: str, **extra) -> Path:
    gates = load_gates(workdir)
    gates[gate] = {"confirmed": True, "note": note, "confirmed_at": timestamp()}
    gates[gate].update(extra)
    out_path = workdir / GATE_FILE
    write_json(out_path, gates)
    return out_path


def pending_application_fields(md_path: Path) -> list[str]:
    if not md_path.exists():
        return [f"缺少 {md_path}"]
    return [line.strip() for line in md_path.read_text(encoding="utf-8").splitlines() if "待用户确认" in line]


def confirm_environment(workdir: Path, note: str) -> Path:
    return write_gate(workdir, "environment", note)


def confirm_project(workdir: Path, note: str) -> Path:
    return write_gate(workdir, "project", note)


def confirm_business(workdir: Path, note: str) -> Path:
    path = workdir / "草稿/业务理解.json"
    if not path.exists():
        raise SystemExit("Missing 草稿/业务理解.json")
    # v1.8 篇幅规划并入 business 确认：每个 manual_module 必须有配额行
    cp_path = workdir / "草稿/篇幅规划.json"
    if not cp_path.exists():
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 篇幅规划缺失。请先运行 propose_coverage_plan.py 生成三线配额表，"
            "确认每个模块的 importance/材料/手册/截图配额后，与 business 门禁一并确认。"
        )
    try:
        biz = read_json(path)
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        planned = {r.get("module") for r in cp.get("modules", [])}
        titles = {str(m.get("title") or "") for m in biz.get("manual_modules", [])}
        missing = titles - planned
        if missing:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"NEXT_ACTION: 篇幅规划缺少以下模块的配额行：{'、'.join(sorted(missing))}。"
                "请重新运行 propose_coverage_plan.py --confirm 后确认 business 门禁。"
            )
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"STOP_FOR_USER\nNEXT_ACTION: 篇幅规划.json 无法解析：{exc}")
    return write_gate(workdir, "business", note)


def _material_plan_guard(workdir: Path) -> None:
    """v2 guard: when a material evidence plan exists it must be confirmed
    and unchanged since confirmation (invalidation propagation)."""
    plan_path = workdir / "草稿" / MATERIAL_PLAN_FILE
    if not plan_path.exists():
        return  # legacy v1 task without a plan — no guard
    gates = load_gates(workdir)
    entry = gates.get("material-plan", {})
    if not entry.get("confirmed"):
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 检测到材料证据计划，必须先确认 material-plan 门禁。\n"
            "先运行 evidence_plan_check.py 校验，通过后由用户运行：\n"
            "confirm_stage.py --stage material-plan --note \"...\" --confirm"
        )
    recorded = entry.get("artifact_sha256", "")
    if recorded and _sha256(plan_path) != recorded:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 材料证据计划在确认后被修改，原确认已失效。\n"
            "请重新运行 evidence_plan_check.py 并重新确认 material-plan 门禁。"
        )


def gate_switch(workdir: Path, name: str) -> str:
    """Read switches.<name> from 门禁状态.json; default on."""
    gates = load_gates(workdir)
    return str(gates.get('switches', {}).get(name, 'on'))


def confirm_material_plan(workdir: Path, note: str) -> Path:
    """Confirm the material evidence plan after evidence_plan_check passes."""
    plan_path = workdir / "草稿" / MATERIAL_PLAN_FILE
    if not plan_path.exists():
        raise SystemExit("Missing 草稿/材料证据计划.json")
    checker = Path(__file__).resolve().parent / "evidence_plan_check.py"
    cmd = [sys.executable, str(checker), "--plan", str(plan_path)]
    if gate_switch(workdir, "d-grade-block") == "on":
        cmd.append("--block-d-grade")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: evidence_plan_check 未通过（见上方输出）。请修复计划后重新运行。"
        )

    # ── v1.5 接线：视觉证据申报前置（switches.visual-evidence != off 时）──
    if gate_switch(workdir, "visual-evidence") != "off":
        plan = read_json(plan_path)
        visual = plan.get("visual_evidence") or []
        features = plan.get("features") or []
        core = [f for f in features if f.get("importance") == "core"]
        acquired = [v for v in visual if str(v.get("acquisition_status") or "").startswith(("acquired", "exempted"))]
        if core and not visual:
            raise SystemExit(
                "STOP_FOR_USER\n"
                "NEXT_ACTION: 视觉证据尚未申报。请在 材料证据计划.json 的 visual_evidence 中为每个核心功能申报截图"
                "（acquisition_status=acquired/exempted/pending，exempted 必须附 visual_exemption 理由与替代证据）。"
                "如确认暂时跳过截图，需用户明确设置 switches.visual-evidence=off 后重新确认。"
            )
        pending = [v.get("evidence_id") for v in visual if str(v.get("acquisition_status") or "") == "pending"]
        if pending:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"NEXT_ACTION: 视觉证据申报清单尚有 {len(pending)} 项 pending，全部 pending 时不得进入文档生成阶段。"
                "请逐张标记 acquired / exempted 后重新确认。"
            )

    # ── v1.5 接线：申请独立性提示（sibling 计划存在时）──
    plan = read_json(plan_path)
    siblings = plan.get("sibling_application_ids") or []
    if siblings:
        checker = Path(__file__).resolve().parent / "independence_check.py"
        for sib in siblings:
            sib_plan = workdir / sib / "草稿" / MATERIAL_PLAN_FILE
            if sib_plan.exists():
                r = subprocess.run(
                    [sys.executable, str(checker), "--plan-a", str(plan_path), "--plan-b", str(sib_plan)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
                print(r.stdout, end="")
                if r.returncode != 0:
                    raise SystemExit(
                        "STOP_FOR_USER\n"
                        "NEXT_ACTION: 申请独立性检查未通过（见上方输出）。"
                        "请确认两个软件可独立运行、可分别交付，或在计划中填写 independence_declaration。"
                    )
    return write_gate(
        workdir,
        "material-plan",
        note,
        artifact=MATERIAL_PLAN_FILE,
        artifact_sha256=_sha256(plan_path),
        workflow_profile="v2",
    )


def confirm_code_selection(workdir: Path, note: str) -> Path:
    _material_plan_guard(workdir)
    path = workdir / "草稿/代码文件选择.json"
    if not path.exists():
        raise SystemExit("Missing 草稿/代码文件选择.json")
    data = read_json(path)
    files = data.get("files") if isinstance(data, dict) else []
    selected = [item for item in files if isinstance(item, dict) and item.get("selected")]
    if not selected:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 代码文件选择尚未由模型填写。请先选择至少一个源码文件并填写选择理由，再让用户确认。"
        )
    missing_reason = [item.get("path") for item in selected if not str(item.get("model_reason") or "").strip()]
    if data.get("model_selection_required") and missing_reason:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 已选源码缺少模型选择理由，请补全 model_reason 后再确认。\n"
            + "\n".join(f"- {item}" for item in missing_reason[:20])
        )

    # ── 模块代码覆盖验证（硬阻断：缺口必须有说明） ──
    biz_path = workdir / "草稿/业务理解.json"
    if biz_path.exists():
        biz = read_json(biz_path)
        candidate_paths = {
            f.get("path", "").replace("\\", "/")
            for f in files
        }
        selected_paths = {
            f.get("path", "").replace("\\", "/")
            for f in selected
        }

        def _matches_any(ev: str, pool: set[str]) -> bool:
            """evidence 可为绝对路径（含项目根前缀）或相对路径，与池内路径尾缀匹配。"""
            ev = ev.replace("\\", "/")
            if ev in pool:
                return True
            return any(ev.endswith(p) or p.endswith(ev) for p in pool)

        modules = biz.get("manual_modules") or []
        weak_modules: list[str] = []
        for m in modules:
            title = m.get("title", "?")
            evidence = [
                e.replace("\\", "/")
                for e in (m.get("evidence") or [])
            ]
            if not evidence:
                continue
            in_candidates = [e for e in evidence if _matches_any(e, candidate_paths)]
            if not in_candidates:
                weak_modules.append(
                    f"{title} — 所有 evidence 文件均不在候选池中"
                )
            else:
                in_selected = [e for e in evidence if _matches_any(e, selected_paths)]
                if not in_selected:
                    weak_modules.append(
                        f"{title} — evidence 文件在候选池中但未被选中：{', '.join(in_candidates[:3])}"
                    )

        if weak_modules:
            coverage_notes = str(data.get("coverage_notes") or "").strip()
            if not coverage_notes:
                raise SystemExit(
                    "STOP_FOR_USER\n"
                    "NEXT_ACTION: 以下模块在操作手册中有功能描述但无代码覆盖：\n"
                    + "\n".join(f"- {wm}" for wm in weak_modules)
                    + "\n请在 草稿/代码文件选择.json 的 coverage_notes 字段说明无法覆盖的原因，"
                    "或补选对应 evidence 文件后重新确认。"
                )
            print(
                f"WARNING: {len(weak_modules)}/{len(modules)} 个模块无代码覆盖（已有说明）：",
                *[f"  - {wm}" for wm in weak_modules],
                sep="\n",
            )

        # ── 标注合规校验（回归防线 #4） ──
        evidence_all = {
            e.replace("\\", "/").lstrip("./")
            for m in modules
            for e in (m.get("evidence") or [])
        }
        labeling_issues: list[str] = []
        for item in selected:
            item_path = item.get("path", "").replace("\\", "/")
            tier = str(item.get("selection_tier") or "")
            reason = str(item.get("model_reason") or "")
            in_evidence = any(
                item_path == e or item_path.endswith(e) or e.endswith(item_path)
                for e in evidence_all
            )
            if tier == "evidence" and not in_evidence:
                labeling_issues.append(
                    f"{item_path} 标注为 evidence 但不在任何 manual_modules.evidence 中"
                )
            if not in_evidence and tier != "supplement" and not reason.startswith("补充"):
                labeling_issues.append(
                    f"{item_path} 不在 evidence 清单且未标注为补充（tier={tier}, reason 需以「补充」开头）"
                )
        if labeling_issues:
            raise SystemExit(
                "STOP_FOR_USER\n"
                "NEXT_ACTION: 选中文件标注与业务理解 evidence 不一致：\n"
                + "\n".join(f"- {x}" for x in labeling_issues[:20])
                + "\n请修正 selection_tier/evidence/model_reason 后重新确认。"
            )

    # Sync user_confirmed flag in selection JSON
    data["user_confirmed"] = True
    write_json(path, data)

    return write_gate(workdir, "code-selection", note)


def parse_screenshot_method(method: str, note: str) -> str:
    value = (method or note or "").lower()
    if any(key in value for key in ("skip", "no-screenshot", "none", "不截图", "跳过", "暂不", "先不", "不要截图", "无需截图")):
        return "skip"
    if any(key in value for key in ("chrome", "devtools", "mcp")):
        return "chrome-devtools"
    if any(key in value for key in ("computer", "use", "电脑", "桌面")):
        return "computer-use"
    if any(key in value for key in ("user", "manual", "self", "手动", "自己", "用户")):
        return "user-supplied"
    raise SystemExit(
        "STOP_FOR_USER\n"
        "NEXT_ACTION: 请明确截图方式：chrome-devtools、computer-use、user-supplied 或 skip。"
    )


def confirm_screenshot_method(workdir: Path, note: str, method: str) -> Path:
    selected = parse_screenshot_method(method, note)
    return write_gate(workdir, "screenshot-method", note, method=selected)


def confirm_application_fields(workdir: Path, note: str) -> Path:
    pending = pending_application_fields(workdir / "草稿/申请表信息.md")
    if pending:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 申请表信息仍包含[待用户确认]。请先补全字段,再重新确认。\n"
            + "\n".join(f"- {item}" for item in pending[:20])
        )
    return write_gate(workdir, "application-fields", note)


def confirm_content_quality(workdir: Path, note: str) -> Path:
    """Record content-quality gate after running the actual checker.

    The content_quality_check.py script is invoked as a subprocess.  If it
    fails (exit != 0) the gate is NOT recorded — the model must fix issues
    and re-run.
    """
    manual_path = workdir / "草稿/操作手册.md"
    if not manual_path.exists():
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 操作手册草稿不存在，请先生成操作手册后再确认 content-quality 门禁。"
        )

    checker = (
        Path(__file__).resolve().parent / "content_quality_check.py"
    )
    result = subprocess.run(
        [sys.executable, str(checker), "--manual", str(manual_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Print checker output so it's visible in the transcript
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: content_quality_check 未通过（见上方输出）。请修复问题后重新运行。"
        )

    return write_gate(workdir, "content-quality", note)


def confirm_manual(workdir: Path, note: str) -> Path:
    manual_path = workdir / "草稿/操作手册.md"
    if not manual_path.exists():
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 操作手册草稿不存在，请先生成并完成内容质量检查。"
        )
    gates = load_gates(workdir)
    if not gates.get("content-quality", {}).get("confirmed"):
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: 操作手册确认前必须先通过 content-quality 门禁。"
        )

    # v1.6 同批文档结构同构检查（switches.batch-structure != off）
    switches = gates.get("switches", {})
    if switches.get("batch-structure", "on") != "off":
        from batch_structure_check import run as batch_run
        parent = workdir.parent
        sibling_manuals = []
        if parent.exists():
            for d in parent.iterdir():
                if not d.is_dir() or d == workdir:
                    continue
                sm = d / "草稿" / "操作手册.md"
                if sm.exists():
                    sibling_manuals.append(sm)
        if len(sibling_manuals) >= 1:
            report = batch_run([manual_path] + sibling_manuals, batch_id=parent.name)
            my_name = workdir.name
            my_errors = [e for e in report["errors"] if my_name in e]
            sibling_errors = [e for e in report["errors"] if my_name not in e]
            for e in sibling_errors:
                # 仅涉及兄弟任务自身的问题：警示不阻断本任务（与 content_quality_check gate 23 策略一致）
                print(f"  WARNING(兄弟任务): {e}")
            for e in my_errors:
                print(f"  ERROR: {e}")
            # 相似度风险分级（方案 v2 决策④：只提示，不阻断；高风险需人工复核）
            for r in report.get("risks") or []:
                involves_me = any(my_name in p for p in (r.get("pair") or []))
                if involves_me and r.get("level") == "high":
                    print(f"  RISK-HIGH(需人工复核，不阻断): {' 与 '.join(r.get('pair') or [])}: {r.get('detail','')}")
                elif involves_me and r.get("level") == "medium":
                    print(f"  RISK-MEDIUM(建议复核，不阻断): {' 与 '.join(r.get('pair') or [])}: {r.get('detail','')}")
            if my_errors:
                raise SystemExit(
                    "STOP_FOR_USER\n"
                    "NEXT_ACTION: 本任务存在确定性结构错误（文件缺失/章节编号错误/重复粘贴，见上）。"
                    "请修复后重试；相似度风险为提示项，高风险经人工复核确认可辩护后即可继续。"
                )
            if sibling_errors:
                print(f"BATCH STRUCTURE PASS: 本任务与 {len(sibling_manuals)} 个同批任务无确定性错误；兄弟任务之间存在 {len(sibling_errors)} 项确定性错误（警示，建议后续批次差异化处理）")
            else:
                print(f"BATCH STRUCTURE PASS: 与 {len(sibling_manuals)} 个同批任务无同构")

    # v1.7 手册 ↔ 材料三口径覆盖门禁（switches.doc-material-coverage != off）
    if switches.get("doc-material-coverage", "on") != "off":
        cov_checker = Path(__file__).resolve().parent / "verify_doc_material_coverage.py"
        business_path = workdir / "草稿" / "业务理解.json"
        plan_path = workdir / "草稿" / "材料证据计划.json"
        manifest_path = workdir / "草稿" / "代码提取清单.json"
        if business_path.exists() and plan_path.exists() and manifest_path.exists():
            cov = subprocess.run(
                [sys.executable, str(cov_checker),
                 "--business", str(business_path),
                 "--plan", str(plan_path),
                 "--manifest", str(manifest_path),
                 "--manual", str(manual_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            print(cov.stdout, end="")
            if cov.stderr:
                print(cov.stderr, end="", file=sys.stderr)
            if cov.returncode == 1:
                raise SystemExit(
                    "STOP_FOR_USER\n"
                    "NEXT_ACTION: 手册与程序鉴别材料覆盖门禁未通过（核心模块/功能证据缺失，见上）。"
                    "请补全 60 页材料的证据文件或修正手册章节后重试。"
                )

    # v1.7 手册事实断言 ↔ 源码核对（枚举漂移阻断 + 公式清单；switches.manual-facts != off）
    if switches.get("manual-facts", "on") != "off":
        facts_checker = Path(__file__).resolve().parent / "verify_manual_facts.py"
        plan_json = read_json(plan_path) if plan_path.exists() else {}
        src_roots = [r.get("path") for r in plan_json.get("input_roots", []) if r.get("path")]
        if src_roots and all(Path(r).exists() for r in src_roots):
            facts = subprocess.run(
                [sys.executable, str(facts_checker), "--manual", str(manual_path),
                 "--source-roots"] + src_roots,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            print(facts.stdout, end="")
            if facts.stderr:
                print(facts.stderr, end="", file=sys.stderr)
            if facts.returncode == 1:
                raise SystemExit(
                    "STOP_FOR_USER\n"
                    "NEXT_ACTION: 手册事实断言与源码不一致（枚举漂移，见上）。"
                    "请按核对清单修正手册枚举/状态表述后重试。"
                )

    return write_gate(workdir, "manual", note)


def confirm_diagrams(workdir: Path, note: str) -> Path:
    """Verify that the 4 overview + module flow diagram PNGs exist in 截图/."""
    screenshot_dir = workdir / "截图"
    required_overviews = ["系统架构图", "功能模块图", "核心业务流程图", "数据模型关系图"]

    missing = []
    for name in required_overviews:
        png = screenshot_dir / f"{name}.png"
        if not png.exists() or png.stat().st_size == 0:
            missing.append(str(png))

    # Count module flow diagrams (those containing "操作流程")
    if screenshot_dir.exists():
        flow_pngs = list(screenshot_dir.glob("*操作流程*.png"))
        valid_flows = [p for p in flow_pngs if p.stat().st_size > 0]
    else:
        valid_flows = []

    if missing:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 以下总图 PNG 缺失或为空：\n"
            + "\n".join(f"- {m}" for m in missing)
            + f"\n当前流程图数量：{len(valid_flows)}\n"
            "请生成全部 4 张总图并为每个核心功能模块生成操作流程图后重试。"
        )

    if len(valid_flows) < 4:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 模块操作流程图数量不足（当前 {len(valid_flows)}，需 ≥4）。请为每个核心功能模块生成操作流程图后重试。"
        )

    return write_gate(workdir, "diagrams", note,
                       overview_count=len(required_overviews),
                       flow_count=len(valid_flows))


def confirm_markdown(workdir: Path, note: str) -> Path:
    _material_plan_guard(workdir)
    gates = load_gates(workdir)
    gate_names = ["business", "manual", "content-quality", "code-selection", "screenshot-method", "application-fields"]
    gate_labels = {
        "business": "业务理解尚未确认",
        "manual": "操作手册尚未确认",
        "content-quality": "操作手册内容质量尚未通过",
        "code-selection": "代码文件选择尚未确认",
        "screenshot-method": "截图方式尚未确认",
        "application-fields": "申请表字段尚未确认",
    }
    # v2 路径：材料证据计划（schema_version=3）替代 code-selection 门禁
    v2_plan = workdir / "草稿" / "材料证据计划.json"
    is_v2 = False
    if v2_plan.exists():
        try:
            is_v2 = json.loads(v2_plan.read_text(encoding="utf-8")).get("schema_version") == 3
        except Exception:
            pass
    if is_v2:
        gate_names = [("material-plan" if g == "code-selection" else g) for g in gate_names]
        gate_labels["material-plan"] = "材料证据计划尚未确认"
    issues = [gate_labels[g] for g in gate_names if not gates.get(g, {}).get("confirmed")]
    pending = pending_application_fields(workdir / "草稿/申请表信息.md")
    if pending:
        issues.append("申请表信息仍包含[待用户确认]")

    if issues:
        raise SystemExit(
            "STOP_FOR_USER\n"
            "NEXT_ACTION: Markdown 草稿确认前需要先处理以下事项：\n"
            + "\n".join(f"- {item}" for item in issues)
        )

    # ── v1.5 接线：逻辑一致性检查（switches.logic-consistency != off 时）──
    if gate_switch(workdir, "logic-consistency") != "off":
        manual_path = workdir / "草稿/操作手册.md"
        plan_path = workdir / "草稿" / MATERIAL_PLAN_FILE
        if manual_path.exists():
            checker = Path(__file__).resolve().parent / "logic_consistency_check.py"
            cmd = [sys.executable, str(checker), "--manual", str(manual_path)]
            if plan_path.exists():
                cmd += ["--plan", str(plan_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            if result.returncode != 0:
                raise SystemExit(
                    "STOP_FOR_USER\n"
                    "NEXT_ACTION: 逻辑一致性检查未通过（见上方输出）。请修正文档中的矛盾后重新确认。"
                )

    # ── Cooldown check: prevent rapid-fire confirmations ──
    from datetime import datetime, timezone, timedelta
    COOLDOWN_SECONDS = 5
    now = datetime.now(timezone.utc)
    for gate_name, entry in gates.items():
        if gate_name == "markdown":
            continue
        at_str = (entry or {}).get("confirmed_at", "")
        if not at_str:
            continue
        try:
            at = datetime.fromisoformat(at_str)
        except ValueError:
            continue
        # If any recent (non-markdown) gate was confirmed within the cooldown
        # window and its timestamp is close to NOW (not a stale old gate), flag it
        delta = (now - at).total_seconds()
        if 0 < delta < COOLDOWN_SECONDS:
            raise SystemExit(
                "STOP_FOR_USER\n"
                f"NEXT_ACTION: Markdown 门禁冷静期不足（上一门禁 {gate_name} 于 {delta:.0f} 秒前确认）。"
                f"请在实际阅读草稿、检查一致性后再确认 markdown 门禁——不要在同一 turn 连续确认。"
            )

    return write_gate(workdir, "markdown", note)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", help="Task workdir; auto-derived from --task-dir if omitted")
    parser.add_argument("--task-dir", help="Task root dir; auto-resolved from current directory if omitted")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "environment", "project", "business", "code-selection",
            "material-plan",
            "screenshot-method", "application-fields", "markdown",
            "content-quality", "manual", "diagrams",
        ],
    )
    parser.add_argument("--note", default="用户已确认")
    parser.add_argument(
        "--method",
        choices=["chrome-devtools", "computer-use", "user-supplied", "skip"],
        help="Screenshot capture method when --stage screenshot-method",
    )
    parser.add_argument("--confirm", action="store_true", help="Confirmed by user, proceed with execution")
    parser.add_argument("--json", action="store_true", help="Output structured JSON instead of plain text")
    args = parser.parse_args()

    workdir = Path(args.workdir) if args.workdir else resolve_workdir(args.task_dir)

    if not args.confirm:
        raise SystemExit(
            "STOP_FOR_USER\n"
            f"NEXT_ACTION: 用户确认后，重新运行并添加 --confirm 记录 {args.stage} 门禁。"
        )

    confirm_params({"工作目录": str(workdir), "门禁阶段": args.stage, "备注": args.note}, args.confirm)
    if args.stage == "environment":
        path = confirm_environment(workdir, args.note)
    elif args.stage == "project":
        path = confirm_project(workdir, args.note)
    elif args.stage == "business":
        path = confirm_business(workdir, args.note)
    elif args.stage == "material-plan":
        path = confirm_material_plan(workdir, args.note)
    elif args.stage == "code-selection":
        path = confirm_code_selection(workdir, args.note)
    elif args.stage == "screenshot-method":
        path = confirm_screenshot_method(workdir, args.note, args.method or "")
    elif args.stage == "application-fields":
        path = confirm_application_fields(workdir, args.note)
    elif args.stage == "content-quality":
        path = confirm_content_quality(workdir, args.note)
    elif args.stage == "manual":
        path = confirm_manual(workdir, args.note)
    elif args.stage == "diagrams":
        path = confirm_diagrams(workdir, args.note)
    else:
        path = confirm_markdown(workdir, args.note)

    if args.json:
        import json
        result = {
            "stage": args.stage,
            "confirmed": True,
            "path": str(path.resolve()),
            "note": args.note,
        }
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"OK confirmation recorded: {args.stage}")
        print(path)


if __name__ == "__main__":
    main()
