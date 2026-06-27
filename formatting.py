import html
import logging
import re

logger = logging.getLogger(__name__)


def markdown_to_html(text: str) -> str:
    """Конвертирует типичный markdown отчёта модели в Telegram HTML."""
    result = html.escape(text)
    result = re.sub(r"^### (.+)$", r"<b>\1</b>", result, flags=re.MULTILINE)
    result = re.sub(r"^## (.+)$", r"<b>\1</b>", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    return result
