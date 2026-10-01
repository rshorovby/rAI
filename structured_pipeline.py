"""Прогон structured output: проверка, повтор, рендер, журнал."""

import hashlib
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from analysis_checks import apply_checks, player_text_issues
from analysis_schema import SCHEMA_PATH, schema_errors
from pricing import Usage, estimate_cost
from render_report import render_report
from stroke_blocks import BLOCKS_DIR

logger = logging.getLogger(__name__)

MAX_SCHEMA_RETRIES = 2


class AnalysisFailed(Exception):
    """Схема или блокирующая проверка не прошли после повторов."""

    def __init__(self, reason: str, raw: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


def video_duration_sec(path: Path) -> Optional[float]:
    """Длительность файла через ffprobe. Нет утилиты — None, сверка таймкода пропускается."""
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        logger.info("ffprobe недоступен, длительность ролика не сверяется")
        return None
    raw = (completed.stdout or "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def content_hashes() -> dict:
    schema = SCHEMA_PATH.read_bytes()
    blocks = b"\n".join(path.read_bytes() for path in sorted(BLOCKS_DIR.glob("*.md")))
    return {
        "schema": hashlib.sha256(schema).hexdigest(),
        "blocks": hashlib.sha256(blocks).hexdigest(),
    }


def run_structured(
    generate,
    *,
    schema: dict,
    drill_ids: list,
    duration_sec: Optional[float],
    downgrade_missing_evidence: bool,
    system_prompt: str,
    user_prompt: str,
    model: str,
    player_id: Optional[int] = None,
) -> dict:
    """generate() -> (text, Usage). До двух повторов на схему, блокировку и «поднос»."""
    retries = 0
    phrase_retry_used = False
    last_text = ""
    usages = []
    while True:
        text, usage = generate()
        last_text = text
        usages.append(usage)
        parsed, errors = _parse(text, schema)
        notes = []
        blocking = list(errors)
        if parsed is not None and not blocking:
            blocking, notes, parsed = apply_checks(
                parsed,
                duration_sec=duration_sec,
                drill_ids=drill_ids,
                downgrade_missing_evidence=downgrade_missing_evidence,
            )
        if blocking:
            if retries < MAX_SCHEMA_RETRIES:
                retries += 1
                logger.warning("Повтор разбора %s: %s", retries, "; ".join(blocking))
                continue
            raise AnalysisFailed("; ".join(blocking), last_text)

        rendered = render_report(parsed)
        issues = player_text_issues(rendered)
        if issues["phrase"] and not phrase_retry_used and retries < MAX_SCHEMA_RETRIES:
            phrase_retry_used = True
            retries += 1
            logger.warning("Повтор разбора %s: поднос/waiter", retries)
            continue
        incident = bool(issues["phrase"])
        if incident:
            logger.error("Инцидент: в тексте игрока остались поднос/waiter")
        if issues["slug_leak"]:
            logger.warning("slug_leak: %s", ", ".join(issues["slug_leak"]))
        if issues["author_leak"]:
            logger.warning("author_leak: %s", ", ".join(issues["author_leak"]))
        total = _sum_usage(usages, model)
        log = {
            "player_id": player_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "hashes": content_hashes(),
            "raw": last_text,
            "checks": notes,
            "retries": retries,
            "phrase_incident": incident,
            "slug_leak": issues["slug_leak"],
            "author_leak": issues["author_leak"],
            "tokens": {
                "input": total.input_tokens,
                "output": total.output_tokens,
                "thinking": total.thinking_tokens,
            },
            "cost_usd": estimate_cost(
                total.input_tokens,
                total.output_tokens,
                total.thinking_tokens,
                model,
            ),
            "model": model,
        }
        return {"text": rendered, "raw_json": parsed, "usage": total, "run_log": log}


def write_run_log(directory: Path, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = directory / f"{stamp}-{uuid.uuid4().hex[:8]}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse(text: str, schema: dict):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, ["ответ не JSON"]
    if not isinstance(data, dict):
        return None, ["ответ не объект"]
    errors = schema_errors(data, schema)
    return data, errors


def _sum_usage(usages: list, model: str) -> Usage:
    return Usage(
        input_tokens=sum(item.input_tokens for item in usages),
        output_tokens=sum(item.output_tokens for item in usages),
        thinking_tokens=sum(item.thinking_tokens for item in usages),
        model=model,
    )
