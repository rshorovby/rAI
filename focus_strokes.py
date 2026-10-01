"""Русские названия ударов в хранилище → ключи схемы."""

import logging

logger = logging.getLogger(__name__)

STROKE_KEYS = (
    "serve",
    "forehand",
    "backhand",
    "volley",
    "footwork",
    "rally",
)

_LABELS = {
    "подача": "serve",
    "serve": "serve",
    "форхенд": "forehand",
    "forehand": "forehand",
    "бэкхенд": "backhand",
    "бекхенд": "backhand",
    "backhand": "backhand",
    "волье": "volley",
    "сетка": "volley",
    "volley": "volley",
    "ноги": "footwork",
    "работа ног": "footwork",
    "footwork": "footwork",
    "розыгрыш": "rally",
    "rally": "rally",
}


def stroke_key(label: str) -> str:
    """Ключ удара. Неизвестное название логируется и возвращает пустую строку."""
    raw = (label or "").strip().lower().replace("ё", "е")
    key = _LABELS.get(raw, "")
    if raw and not key:
        logger.warning("Неизвестное название удара в фокусе: %s", label)
    return key
