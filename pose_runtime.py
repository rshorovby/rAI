"""Контакты удара перед разбором. Нет модели или MediaPipe — разбор идёт без измерений."""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "lite"
MAX_CONTACTS = 12


def measure(path: Path, stroke: str, hand: str = "") -> dict:
    """{"contacts": [{"t", "source"}], "metrics": optional, "error": optional}.

    hand — «left» или «right» из профиля. Пустая рука: в промпт идут только контакты.
    """
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
    measured = {"contacts": contacts}
    kind = "serve" if stroke == "serve" else ""
    track = report.get("track")
    if hand in ("left", "right") and track is not None and contacts:
        scale = pose_lab.body_scale(track)
        if scale:
            raw = pose_lab.measure_contacts(
                track, [item["t"] for item in contacts], hand, scale, kind
            )
            measured["metrics"] = metrics_for_prompt(raw, kind)
    return measured


def metrics_for_prompt(metrics: dict, stroke: str) -> dict:
    """Оставляет числа, которые можно отдать модели.

    На подаче локоть, высота контакта, подброс и подписи коленей уходят,
    если кисть из профиля ниже другой: слева и справа на скелете перепутаны.
    Стойка и глубина приседа от подписи стороны не зависят.
    """
    rows = []
    for row in (metrics or {}).get("contacts") or []:
        if not isinstance(row, dict) or "t" not in row:
            continue
        trust_arm = True
        arm_skipped = False
        if stroke == "serve":
            own = row.get("contact_above_head")
            other = row.get("other_above_head")
            trust_arm = own is not None and other is not None and own > other
            arm_skipped = own is not None and other is not None and own < other
        kept = {"t": row["t"]}
        if row.get("stance") is not None:
            kept["stance"] = row["stance"]
        if stroke == "serve" and row.get("knee_load") is not None:
            kept["knee_load"] = row["knee_load"]
        if trust_arm:
            for key in (
                "elbow",
                "knee_left",
                "knee_right",
                "contact_above_head",
                "toss_above_head",
            ):
                if row.get(key) is not None:
                    kept[key] = row[key]
        else:
            kept["arm_skipped"] = arm_skipped
        rows.append(kept)
    spread = {}
    for key in (
        "elbow",
        "knee_left",
        "knee_right",
        "stance",
        "contact_above_head",
        "toss_above_head",
        "knee_load",
    ):
        values = [row[key] for row in rows if row.get(key) is not None]
        if len(values) >= 2:
            spread[key] = round(max(values) - min(values), 2)
    return {
        "hand": (metrics or {}).get("hand") or "",
        "contacts": rows,
        "spread": spread,
    }


def prompt_text(measured: dict, language_code: str) -> str:
    """Блок для промпта. Пустая строка, если контактов нет."""
    contacts = (measured or {}).get("contacts") or []
    if not contacts:
        return ""
    ru = str(language_code or "").lower().startswith("ru")
    moments = ", ".join(_moment(item, ru) for item in contacts)
    if ru:
        text = (
            "ИЗМЕРЕНИЯ ДО РАЗБОРА\n"
            "Контакты посчитаны по скорости кисти и щелчку струны, не на глаз.\n"
            f"Число ударов: {len(contacts)}.\n"
            f"Контакты: {moments}.\n"
            "В наблюдениях ставь таймкод ближайшего контакта из этого списка. "
            "Не выдумывай другой момент удара.\n"
            "Если по кадру ударов больше или меньше — напиши это одной фразой."
        )
    else:
        text = (
            "MEASUREMENTS BEFORE THE REVIEW\n"
            "Contacts come from wrist speed and the string impact, not from a glance.\n"
            f"Stroke count: {len(contacts)}.\n"
            f"Contacts: {moments}.\n"
            "In observations, use the nearest contact from this list. "
            "Do not invent a different impact moment.\n"
            "If the frame shows more or fewer strokes, say so in one sentence."
        )
    extra = _metrics_block(measured.get("metrics") or {}, ru)
    return text if not extra else text + "\n" + extra


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


_HAND_RU = {"right": "правой", "left": "левой"}
_HAND_EN = {"right": "right", "left": "left"}
_ANGLE_KEYS = ("elbow", "knee_left", "knee_right", "knee_load")


def _metrics_block(metrics: dict, ru: bool) -> str:
    rows = metrics.get("contacts") or []
    hand = metrics.get("hand") or ""
    lines = []
    for row in rows:
        line = _attempt_line(row, hand, ru)
        if line:
            lines.append(line)
    spread = _spread_line(metrics.get("spread") or {}, ru)
    if spread:
        lines.append(spread)
    if not lines:
        return ""
    lines.append(_legend(ru))
    return "\n".join(lines)


def _attempt_line(row: dict, hand: str, ru: bool) -> str:
    parts = []
    elbow = row.get("elbow")
    if elbow is not None and hand in _HAND_RU:
        if ru:
            parts.append(f"локоть {_HAND_RU[hand]} руки {_deg(elbow, ru)}")
        else:
            parts.append(f"{_HAND_EN[hand]} elbow {_deg(elbow, ru)}")
    knees = _knee_phrase(row, ru)
    if knees:
        parts.append(knees)
    height = row.get("contact_above_head")
    if height is not None:
        parts.append(_height_phrase(height, ru, "кисть", "wrist"))
    toss = row.get("toss_above_head")
    if toss is not None:
        parts.append(_height_phrase(toss, ru, "подброс", "toss"))
    load = row.get("knee_load")
    if load is not None:
        parts.append(
            f"колено в загрузке {_deg(load, ru)}"
            if ru
            else f"knee load {_deg(load, ru)}"
        )
    stance = row.get("stance")
    if stance is not None:
        parts.append(
            f"стойка {_torso(stance, ru)} торса"
            if ru
            else f"stance {_torso(stance, ru)} torso"
        )
    if row.get("arm_skipped"):
        if ru:
            note = (
                "локоть, высоту контакта и подброс здесь не измеряли: "
                "кисть из профиля ниже другой"
            )
        else:
            note = (
                "elbow, contact height and toss were not measured here: "
                "the profile wrist is lower than the other one"
            )
        parts.append(note)
    if not parts:
        return ""
    moment = _seconds(row["t"], ru)
    prefix = f"Попытка {moment} с: " if ru else f"Attempt {moment} s: "
    return prefix + ", ".join(parts) + "."


def _knee_phrase(row: dict, ru: bool) -> str:
    left = row.get("knee_left")
    right = row.get("knee_right")
    bits = []
    if left is not None:
        bits.append(
            f"левое колено {_deg(left, ru)}" if ru else f"left knee {_deg(left, ru)}"
        )
    if right is not None:
        bits.append(
            f"правое колено {_deg(right, ru)}"
            if ru
            else f"right knee {_deg(right, ru)}"
        )
    return ", ".join(bits)


def _height_phrase(value: float, ru: bool, ru_name: str, en_name: str) -> str:
    amount = _torso(abs(value), ru)
    if abs(value) < 0.005:
        return f"{ru_name} на уровне носа" if ru else f"{en_name} level with the nose"
    if value > 0:
        return (
            f"{ru_name} на {amount} торса выше носа"
            if ru
            else f"{en_name} {amount} torso above the nose"
        )
    return (
        f"{ru_name} на {amount} торса ниже носа"
        if ru
        else f"{en_name} {amount} torso below the nose"
    )


def _spread_line(spread: dict, ru: bool) -> str:
    names_ru = {
        "elbow": "локоть",
        "knee_left": "левое колено",
        "knee_right": "правое колено",
        "stance": "стойка",
        "contact_above_head": "высота контакта",
        "toss_above_head": "подброс",
        "knee_load": "загрузка",
    }
    names_en = {
        "elbow": "elbow",
        "knee_left": "left knee",
        "knee_right": "right knee",
        "stance": "stance",
        "contact_above_head": "contact height",
        "toss_above_head": "toss",
        "knee_load": "knee load",
    }
    names = names_ru if ru else names_en
    parts = []
    for key, title in names.items():
        value = spread.get(key)
        if value is None:
            continue
        if key in _ANGLE_KEYS:
            parts.append(f"{title} {_deg(value, ru)}")
        else:
            unit = "торса" if ru else "torso"
            parts.append(f"{title} {_torso(value, ru)} {unit}")
    if not parts:
        return ""
    head = "Разброс: " if ru else "Spread: "
    return head + ", ".join(parts) + "."


def _legend(ru: bool) -> str:
    if ru:
        return (
            "180° — прямая конечность. Высоты и стойка — в длинах торса, не в сантиметрах. "
            "Опирайся на эти числа. Не заменяй их оценкой на глаз."
        )
    return (
        "180° is a straight limb. Heights and stance are in torso lengths, not centimetres. "
        "Use these numbers. Do not replace them with a visual guess."
    )


def _deg(value: float, ru: bool) -> str:
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 1e-6:
        text = str(int(round(rounded)))
    else:
        text = f"{rounded:.1f}"
        if ru:
            text = text.replace(".", ",")
    return text + "°"


def _torso(value: float, ru: bool) -> str:
    text = f"{float(value):.2f}"
    return text.replace(".", ",") if ru else text
