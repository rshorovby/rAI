"""Контакты удара перед разбором. Нет модели или MediaPipe — разбор идёт без измерений."""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "lite"
MAX_CONTACTS = 12


def measure(path: Path, stroke: str) -> dict:
    """{"contacts": [{"t", "source"}], "error": optional}."""
    os.environ.setdefault("GLOG_minloglevel", "2")
    try:
        import pose_lab
    except ImportError:
        logger.info("pose: mediapipe не установлен")
        return {"contacts": [], "error": "import"}
    model = pose_lab.MODELS_DIR / f"pose_landmarker_{MODEL_NAME}.task"
    if not model.is_file():
        logger.info("pose: нет модели %s", model)
        return {"contacts": [], "error": "model"}
    try:
        report = pose_lab.analyze(
            Path(path),
            model=MODEL_NAME,
            stroke="serve" if stroke == "serve" else "",
        )
    except Exception:
        logger.exception("pose: измерение не удалось")
        return {"contacts": [], "error": "failed"}
    contacts = []
    for item in (report.get("contacts") or [])[:MAX_CONTACTS]:
        if not isinstance(item, dict) or "t" not in item:
            continue
        contacts.append(
            {"t": float(item["t"]), "source": item.get("source") or "wrist"}
        )
    return {"contacts": contacts}


def prompt_text(measured: dict, language_code: str) -> str:
    """Блок для промпта. Пустая строка, если контактов нет."""
    contacts = (measured or {}).get("contacts") or []
    if not contacts:
        return ""
    ru = str(language_code or "").lower().startswith("ru")
    moments = ", ".join(_moment(item, ru) for item in contacts)
    if ru:
        return (
            "ИЗМЕРЕНИЯ ДО РАЗБОРА\n"
            "Контакты посчитаны по скорости кисти и щелчку струны, не на глаз.\n"
            f"Число ударов: {len(contacts)}.\n"
            f"Контакты: {moments}.\n"
            "В наблюдениях ставь таймкод ближайшего контакта из этого списка. "
            "Не выдумывай другой момент удара.\n"
            "Если по кадру ударов больше или меньше — напиши это одной фразой."
        )
    return (
        "MEASUREMENTS BEFORE THE REVIEW\n"
        "Contacts come from wrist speed and the string impact, not from a glance.\n"
        f"Stroke count: {len(contacts)}.\n"
        f"Contacts: {moments}.\n"
        "In observations, use the nearest contact from this list. "
        "Do not invent a different impact moment.\n"
        "If the frame shows more or fewer strokes, say so in one sentence."
    )


def player_line(measured: dict, lang: str) -> Optional[str]:
    """Строка статуса. None, если измерение не запускалось."""
    from i18n import t

    if (measured or {}).get("error"):
        return None
    contacts = (measured or {}).get("contacts") or []
    if not contacts:
        return t(lang, "pose_none")
    ru = lang == "ru"
    times = ", ".join(_seconds(item["t"], ru) for item in contacts)
    return t(lang, "pose_found", n=len(contacts), times=times)


def _moment(item: dict, ru: bool) -> str:
    source = "звук" if item.get("source") == "audio" else "кисть"
    if not ru:
        source = "audio" if item.get("source") == "audio" else "wrist"
    return (
        f"{_seconds(item['t'], ru)} с ({source})"
        if ru
        else f"{_seconds(item['t'], ru)} s ({source})"
    )


def _seconds(value: float, ru: bool) -> str:
    text = f"{value:.2f}"
    return text.replace(".", ",") if ru else text
