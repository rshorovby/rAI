"""Источник старта бота: параметр ссылки t.me/<bot>?start=<код>."""

import re
from typing import Optional

# Код в ссылке → подпись в кабинете. Неизвестный код показывается как есть.
SOURCE_LABELS = {
    "minsk_mir": "Минск-Мир",
    "web": "Сайт",
    "web_ios": "Сайт · iOS",
    "web_en": "Сайт · EN",
    "web_ios_en": "Сайт · iOS EN",
}

IOS_WAITLIST_CODES = frozenset({"web_ios", "web_ios_en"})

EVENT_ACQUISITION_START = "acquisition_start"

_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalize_start_code(raw: Optional[str]) -> Optional[str]:
    """Код из /start. Пусто и всё вне алфавита Telegram — не источник."""
    code = (raw or "").strip()
    if not code or not _CODE_RE.fullmatch(code):
        return None
    return code


def source_label(code: Optional[str]) -> str:
    if not code:
        return ""
    return SOURCE_LABELS.get(code, code)


def is_ios_waitlist(code: Optional[str]) -> bool:
    return bool(code and code in IOS_WAITLIST_CODES)
