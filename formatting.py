import html
import logging
import re

logger = logging.getLogger(__name__)

_TS = r"\d{1,2}:\d{2}(?:\.\d+)?"
_LABEL_ICONS = {
    "Наблюдение": "👁",
    "Проблема / плюс": "💡",
    "Критичность": "⚠️",
    "Рекомендация": "🎯",
    "Действие": "👉",
    "Зачем": "❓",
}


def markdown_to_html(text: str) -> str:
    """Конвертирует типичный markdown отчёта модели в Telegram HTML."""
    result = html.escape(text)
    result = re.sub(r"^### (.+)$", r"<b>\1</b>", result, flags=re.MULTILINE)
    result = re.sub(r"^## (.+)$", r"<b>\1</b>", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    return result


def cabinet_draft_to_html(text: str) -> str:
    """Telegram HTML для черновика в кабинете тренера: структура для быстрого чтения."""
    result = html.escape(text)
    result = re.sub(
        r"^## (.+)$", r"\n━━━━━━━━━━\n<b>\1</b>", result, flags=re.MULTILINE
    )
    result = re.sub(r"^### (.+)$", r"\n<b>▎\1</b>", result, flags=re.MULTILINE)
    result = re.sub(
        rf"^[-•]\s*({_TS}):?\s+(.+)$",
        r"• <code>\1</code> \2",
        result,
        flags=re.MULTILINE,
    )
    result = re.sub(rf"^({_TS})$", r"\n⏱ <code>\1</code>", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    for label, icon in _LABEL_ICONS.items():
        result = re.sub(
            rf"^<b>{re.escape(label)}:</b>",
            f"{icon} <b>{label}:</b>",
            result,
            flags=re.MULTILINE,
        )
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result
