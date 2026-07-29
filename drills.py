"""Библиотека упражнений: markdown wiki + таблица drills."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import storage

DRILLS_DIR = Path(__file__).parent / "knowledge" / "wiki" / "drills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            meta[key] = [
                p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()
            ]
        else:
            meta[key] = value
    return meta, match.group(2).strip()


def sync_drills_from_wiki() -> int:
    """Читает knowledge/wiki/drills/*.md и upsert в БД. Возвращает число файлов."""
    if not DRILLS_DIR.is_dir():
        return 0
    count = 0
    for path in sorted(DRILLS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if meta.get("type") and meta.get("type") != "drill":
            continue
        drill_id = path.stem
        title = meta.get("title") or drill_id.replace("-", " ").title()
        description = meta.get("description") or body.split("\n\n", 1)[0][:400]
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        storage.upsert_drill(
            drill_id=drill_id,
            title=title,
            description=description,
            tags=list(tags),
            language="en" if "en" in tags else "ru",
        )
        count += 1
    return count


def catalog_for_prompt(limit: int = 40) -> str:
    drills = storage.list_drills()
    if not drills:
        sync_drills_from_wiki()
        drills = storage.list_drills()
    lines = []
    for d in drills[:limit]:
        tags = ", ".join(d.get("tags") or [])
        lines.append(f"- id={d['id']}: {d['title']} [{tags}]")
    return "\n".join(lines)


def pick_drills(
    drill_ids: Optional[list[str]] = None,
    error_tags: Optional[list[str]] = None,
    limit: int = 2,
) -> list[dict]:
    """Выбирает упражнения по id модели или по тегам ошибок."""
    all_drills = storage.list_drills()
    if not all_drills:
        sync_drills_from_wiki()
        all_drills = storage.list_drills()
    by_id = {d["id"]: d for d in all_drills}

    picked: list[dict] = []
    for did in drill_ids or []:
        if did in by_id and by_id[did] not in picked:
            picked.append(by_id[did])
        if len(picked) >= limit:
            return picked

    tags = {t.lower() for t in (error_tags or [])}
    if tags:
        scored = []
        for d in all_drills:
            d_tags = {str(t).lower() for t in (d.get("tags") or [])}
            overlap = len(tags & d_tags)
            if overlap:
                scored.append((overlap, d))
        scored.sort(key=lambda x: -x[0])
        for _, d in scored:
            if d not in picked:
                picked.append(d)
            if len(picked) >= limit:
                return picked

    # фолбэк — первые из каталога
    for d in all_drills:
        if d not in picked:
            picked.append(d)
        if len(picked) >= limit:
            break
    return picked


def format_drill_message(drill: dict, lang: str = "ru") -> str:
    title = drill.get("title") or drill.get("id")
    desc = drill.get("description") or ""
    if lang == "ru":
        return f"🏋️ Упражнение: *{title}*\n\n{desc}"
    return f"🏋️ Drill: *{title}*\n\n{desc}"
