"""Реестр блоков ударов для system-промпта structured analysis v2."""

from pathlib import Path
from typing import Optional

BLOCKS_DIR = Path(__file__).resolve().parent / "blocks"
BLOCK_ORDER = ("serve", "forehand", "backhand", "volley", "footwork", "rally")
APPLY_BY_FACT = (
    "Применяй этот раздел по факту: только если на видео виден этот удар. "
    "Выбор игрока это ориентир приоритизации, а не факт о видео."
)


def default_registry() -> dict:
    return {key: BLOCKS_DIR / f"{key}.md" for key in BLOCK_ORDER}


def load_general_rules(path: Optional[Path] = None) -> str:
    source = path or (BLOCKS_DIR / "_general.md")
    return source.read_text(encoding="utf-8").strip()


def load_stroke_blocks(registry: Optional[dict] = None) -> str:
    """Собрать блоки в порядке реестра. Оговорка — первая строка под заголовком."""
    reg = default_registry() if registry is None else registry
    parts = []
    for path in reg.values():
        body = Path(path).read_text(encoding="utf-8").strip()
        lines = body.splitlines()
        if lines and lines[0].startswith("## "):
            body = "\n".join([lines[0], APPLY_BY_FACT, *lines[1:]])
        else:
            body = f"{APPLY_BY_FACT}\n\n{body}"
        parts.append(body)
    return "\n\n".join(parts)
