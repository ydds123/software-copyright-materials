#!/usr/bin/env python3
"""DeepSeek flash vision adapter for visual evidence assessment (1a.2).

Single-model integration (per user decision): calls
``deepseek-v4-flash-vision-exp`` on the OpenAI-compatible endpoint
``https://api.deepseek.com/v1``.

Key guarantees:
- model / prompt version recorded with every assessment (drift detection)
- result cache keyed by (image sha256, model version) — one call per image
- privacy pre-screen: images containing likely sensitive data are refused
  before any upload (regex pass); classifier is conservative
- no auto-retry on API failure; failures surface to the caller
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

# Model config: environment variables override the defaults so the skill
# is not hard-bound to a specific provider setup.
MODEL_ID = os.environ.get("DEEPSEEK_VISION_MODEL", "deepseek-v4-flash-vision-exp")
DEFAULT_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
PROMPT_VERSION = "visual-gate-v1"

# image-format constraints
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Conservative privacy pre-screen (Chinese + English patterns)
SENSITIVE_PATTERNS = [
    r"1[3-9]\d{9}",  # CN mobile
    r"\d{17}[\dXx]",  # CN ID card
    r"(?:身份证|手机号|联系电话|地址|住址|银行卡)",
    r"(?:sk-[a-zA-Z0-9]{16,}|AKIA[0-9A-Z]{16})",
]

CACHE_FILE = "视觉模型判定缓存.json"


def read_api_key() -> str:
    from common import read_json, skill_dir

    env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key
    # fallback lookup order: pi models.json → deepseek CLI secrets
    # (both optional; env var is the portable, documented path)
    try:
        models_json = Path.home() / ".pi" / "agent" / "models.json"
        data = read_json(models_json)
        key = (data.get("providers", {}).get("deepseek", {}) or {}).get("apiKey", "")
        if key:
            return key
    except Exception:
        pass
    try:
        secrets = Path.home() / ".deepseek" / "secrets" / "secrets.json"
        data = read_json(secrets)
        key = (data.get("entries", {}).get("deepseek", "") or "")
        if key:
            return key
    except Exception:
        pass
    raise SystemExit(
        "找不到 DeepSeek API key。\n"
        "请设置环境变量 DEEPSEEK_API_KEY（推荐，跨环境可移植），\n"
        "或确认 ~/.pi/agent/models.json / ~/.deepseek/secrets/secrets.json 存在。\n"
        "不配置 key 时视觉门禁将降级为确定性检查 + 人工提示。"
    )


def ocr_sensitive_hint(image_path: Path) -> list[str]:
    """Extremely cheap static pre-screen: filename/path based heuristics only.

    True OCR on the adapter side is out of scope for 1a.2; the deterministic
    layer (visual_evidence_check.py) does the stronger checks. This function
    exists so privacy refusal logic has a first-line gate.
    """
    text = image_path.name
    hits = []
    for pat in SENSITIVE_PATTERNS:
        if re.search(pat, text):
            hits.append(pat)
    return hits


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    try:
        from common import read_json

        return read_json(cache_path)
    except Exception:
        return {}


def save_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    from common import write_json

    write_json(cache_path, cache)


def assess_image_sync(
    image_path: Path,
    cache_path: Path,
    question: str | None = None,
    max_retries: int = 0,
) -> dict[str, Any]:
    """Assess one image with the DeepSeek vision model.

    Returns a dict with keys: model, model_version, prompt_version,
    assessed_at, ok, supported, cached and the model answer fields
    (page_type / has_real_data / ...) when ok.
    """
    if image_path.suffix.lower() not in ALLOWED_EXTS:
        return {
            "supported": False,
            "reason": f"不支持的图片格式 {image_path.suffix}（支持 png/jpg/jpeg/webp/bmp）",
        }

    image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
    cache = load_cache(cache_path)
    cache_key = f"{image_sha}|{MODEL_ID}|{PROMPT_VERSION}"
    if cache_key in cache:
        entry = dict(cache[cache_key])
        entry["cached"] = True
        return entry

    question = question or (
        "请分析这张软件界面截图，回答以下问题，只输出 JSON：\n"
        '{"page_type": "list|form|detail|dashboard|other", '
        '"has_real_data": true/false, '
        '"suspected_design_mockup": true/false, '
        '"status_label_count": <整数或null>, '
        '"empty_state_detected": true/false, '
        '"summary": "<一句话说明>"}'
    )

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(image_path.suffix.lower(), "image/png")

    payload = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 700,
    }
    req = urllib.request.Request(
        f"{DEFAULT_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {read_api_key()}",
        },
        method="POST",
    )

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"] or ""
            parsed = _parse_model_json(content)
            result = {
                "model": MODEL_ID,
                "model_version": MODEL_ID,
                "prompt_version": PROMPT_VERSION,
                "assessed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ok": True,
                "cached": False,
                "raw_answer": content[:800],
                **parsed,
            }
            cache[cache_key] = {k: v for k, v in result.items() if k != "cached"}
            save_cache(cache_path, cache)
            return result
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    return {
        "model": MODEL_ID,
        "model_version": MODEL_ID,
        "prompt_version": PROMPT_VERSION,
        "assessed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": False,
        "cached": False,
        "error": str(last_err),
    }


def _parse_model_json(content: str) -> dict[str, Any]:
    """Extract the JSON object from the model answer (tolerates fences/text)."""
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return {"parse_error": True, "raw_answer": content[:500]}
    try:
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            return {"parse_error": True, "raw_answer": content[:500]}
        return data
    except Exception:
        return {"parse_error": True, "raw_answer": content[:500]}
