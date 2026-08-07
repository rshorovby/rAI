"""Библиотека упражнений: markdown wiki + таблица drills."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import storage

DRILLS_DIR = Path(__file__).parent / "knowledge" / "wiki" / "drills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Пользовательские строки для RU (wiki frontmatter пока на EN).
DRILL_RU: dict[str, dict[str, str]] = {
    "approach-transition": {
        "title": "Переход к сетке",
        "description": (
            "Удар с подхода, затем один волей — продолжайте движение вперёд."
        ),
    },
    "backhand-height-ladder": {
        "title": "Лестница высоты на бэкхенде",
        "description": (
            "Подачи низко / средне / высоко — подстраивайте высоту контакта."
        ),
    },
    "balance-hold": {
        "title": "Удержание баланса",
        "description": (
            "После каждого теневого удара держите финишную позу 2 секунды."
        ),
    },
    "compact-volley": {
        "title": "Компактный волей",
        "description": ("Волеи с середины корта без замаха, жёсткое запястье."),
    },
    "contact-point-cone": {
        "title": "Конус в точке удара",
        "description": ("Поставьте конус перед передней ногой; контакт — над конусом."),
    },
    "cool-down-shadow": {
        "title": "Заминка тенью",
        "description": ("5 минут медленных теневых ударов только на фокус недели."),
    },
    "count-for-more-time": {
        "title": "Счёт для большего времени",
        "description": (
            "Считайте вслух от отскока (или контакта соперника) до своего удара — "
            "так расширяется ощущение времени на том же полёте мяча."
        ),
    },
    "crosscourt-rally-focus": {
        "title": "Кросс по диагонали",
        "description": (
            "Розыгрыш форхендом по диагонали; ранний unit turn на каждый мяч."
        ),
    },
    "first-step-explosive": {
        "title": "Взрывной первый шаг",
        "description": (
            "Drop-step, затем взрыв к широкому мячу и возврат в готовность."
        ),
    },
    "high-ball-adjust": {
        "title": "Подстройка к высокому мячу",
        "description": ("Подачи выше плеча: мелкие шаги подстройки, контакт впереди."),
    },
    "inside-out-fh": {
        "title": "Форхенд inside-out",
        "description": ("Из угла бэкхенда — форхенд inside-out с полной ротацией."),
    },
    "knee-bend-serve": {
        "title": "Сгиб коленей на подаче",
        "description": ("Усильте сгиб коленей, затем выталкивайтесь вверх к контакту."),
    },
    "late-prep-fix": {
        "title": "Ранняя подготовка",
        "description": ("Начинайте замах на отскоке мяча, а не после отскока."),
    },
    "mini-tennis-contact": {
        "title": "Мини-теннис на контакт",
        "description": (
            "Розыгрыш от линии подачи с ракеткой впереди — "
            "закрепить идеальную точку контакта."
        ),
    },
    "non-hitting-arm": {
        "title": "Свободная рука",
        "description": (
            "Указывайте свободной рукой на мяч, пока не завершится unit turn."
        ),
    },
    "one-hand-extension": {
        "title": "Протяжка на одноручном бэкхенде",
        "description": ("Финиш с длинным выпрямлением руки через линию контакта."),
    },
    "racket-lag-feel": {
        "title": "Ощущение отставания ракетки",
        "description": ("Мягкий хват до зоны контакта, затем уплотните хват."),
    },
    "racket-on-hip": {
        "title": "Ракетка у бедра (ноги подстраиваются)",
        "description": (
            "Ограничьте руки, чтобы подстраиваться к мячу ногами "
            "и входить в ударную зону."
        ),
    },
    "racquet-path-two-hand": {
        "title": "Траектория ракетки двумя руками",
        "description": (
            "Чистый путь через зону контакта: сначала двумя руками, потом одной."
        ),
    },
    "recovery-middle": {
        "title": "Возврат в центр",
        "description": (
            "После каждой подачи возвращайтесь к отмеченной точке "
            "в центре до следующего мяча."
        ),
    },
    "return-split": {
        "title": "Сплит на приёме",
        "description": (
            "Сплит-шаг в верхней точке подброса подачи; блок приёма в глубину."
        ),
    },
    "serve-target-boxes": {
        "title": "Подача по зонам",
        "description": ("10 подач в T, 10 в широкую зону; силу не акцентировать."),
    },
    "short-ball-decision": {
        "title": "Решение на коротком мяче",
        "description": (
            "На коротком мяче рано решайте: подход к сетке или агрессивный форхенд."
        ),
    },
    "slice-cut-the-net": {
        "title": "Слайс «резать сетку»",
        "description": ("Длинное ощущение «срезания сетки» для хватки слайса."),
    },
    "slice-underspin": {
        "title": "Слайс с нижней подкруткой",
        "description": ("Длинная низкая траектория слайса; финиш ниже точки контакта."),
    },
    "split-step-timing": {
        "title": "Тайминг сплит-шага",
        "description": ("Сплит-шаг в момент контакта соперника. 3×10 подач."),
    },
    "toss-consistency": {
        "title": "Стабильный подброс",
        "description": ("20 подач с фокусом только на высоте и месте подброса."),
    },
    "trophy-pause": {
        "title": "Пауза в trophy",
        "description": ("Пауза 1 сек в позиции trophy, затем ускорение вверх."),
    },
    "two-hand-sync": {
        "title": "Синхрон двуручного бэкхенда",
        "description": ("Не доминирующая рука ведёт траекторию; 2 минуты тени."),
    },
    "unit-turn-shadow": {
        "title": "Unit turn тенью",
        "description": ("Теневой unit turn без мяча: сначала плечи, потом бёдра."),
    },
    "weight-transfer-step": {
        "title": "Шаг переноса веса",
        "description": ("Шаг в форхенд передней ногой, когда ракетка опускается."),
    },
    "wide-ball-open-stance": {
        "title": "Открытая стойка на широком мяче",
        "description": (
            "Тренируйте форхенд в открытой стойке только на широких мячах."
        ),
    },
}


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
        # Frontmatter title_ru / description_ru или словарь DRILL_RU
        ru = DRILL_RU.get(drill_id, {})
        title_ru = meta.get("title_ru") or ru.get("title") or title
        description_ru = (
            meta.get("description_ru") or ru.get("description") or description
        )
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        # В БД для RU-продукта храним русские строки; id стабильный для модели.
        storage.upsert_drill(
            drill_id=drill_id,
            title=title_ru,
            description=description_ru,
            tags=list(tags),
            language="ru",
        )
        count += 1
    return count


def localize_drill(drill: dict, lang: str = "ru") -> dict:
    """Возвращает копию drill с title/description на языке UI."""
    out = dict(drill)
    drill_id = out.get("id") or ""
    if lang == "ru":
        ru = DRILL_RU.get(drill_id)
        if ru:
            out["title"] = ru["title"]
            out["description"] = ru["description"]
        return out
    # EN: если в БД уже RU (после sync), подтянем EN из wiki frontmatter map
    en = _DRILL_EN.get(drill_id)
    if en:
        out["title"] = en["title"]
        out["description"] = en["description"]
    return out


# EN из исходных frontmatter (для lang=en после sync с RU в БД)
_DRILL_EN: dict[str, dict[str, str]] = {
    "approach-transition": {
        "title": "Approach transition",
        "description": "Approach shot then one volley; keep moving forward.",
    },
    "backhand-height-ladder": {
        "title": "BH height ladder",
        "description": "Feeds low / medium / high; adjust contact height.",
    },
    "balance-hold": {
        "title": "Balance hold",
        "description": "Hold finish pose 2 seconds after each shadow swing.",
    },
    "compact-volley": {
        "title": "Compact volley punch",
        "description": "No backswing volleys from mid-court, firm wrist.",
    },
    "contact-point-cone": {
        "title": "Contact cone",
        "description": "Place cone ahead of front foot; contact over the cone.",
    },
    "cool-down-shadow": {
        "title": "Cool-down shadow",
        "description": "5 minutes slow shadow of the weekly focus only.",
    },
    "count-for-more-time": {
        "title": "Count for more time",
        "description": (
            "Count aloud bounce-to-hit or opponent-contact-to-hit "
            "to expand time perception."
        ),
    },
    "crosscourt-rally-focus": {
        "title": "Crosscourt focus",
        "description": "Crosscourt FH rally; early unit turn every ball.",
    },
    "first-step-explosive": {
        "title": "Explosive first step",
        "description": "Drop-step then explode to wide ball; reset.",
    },
    "high-ball-adjust": {
        "title": "High ball adjust",
        "description": (
            "Feeds above shoulder; small adjustment steps, contact in front."
        ),
    },
    "inside-out-fh": {
        "title": "Inside-out FH",
        "description": "From BH corner, inside-out FH with full rotation.",
    },
    "knee-bend-serve": {
        "title": "Knee bend serve",
        "description": "Exaggerate knee bend then drive up to contact.",
    },
    "late-prep-fix": {
        "title": "Late prep fix",
        "description": "Start preparation on bounce, not after bounce.",
    },
    "mini-tennis-contact": {
        "title": "Mini tennis contact",
        "description": (
            "Service-line rally with racket forward to groove ideal contact point."
        ),
    },
    "non-hitting-arm": {
        "title": "Non-hitting arm",
        "description": "Point non-hitting arm at ball until unit turn completes.",
    },
    "one-hand-extension": {
        "title": "1HBH extension",
        "description": "Finish with long arm extension through contact line.",
    },
    "racket-lag-feel": {
        "title": "Racket lag feel",
        "description": "Soft grip until contact zone; then firm.",
    },
    "racket-on-hip": {
        "title": "Racket on hip (feet adjust)",
        "description": (
            "Constrain arms so player must adjust to ball with feet into strike zone."
        ),
    },
    "racquet-path-two-hand": {
        "title": "Racquet path two-hand",
        "description": "Clean contact-zone path with two hands then one.",
    },
    "recovery-middle": {
        "title": "Recovery to middle",
        "description": (
            "After each feed, recover to a marked middle spot before next ball."
        ),
    },
    "return-split": {
        "title": "Return split",
        "description": "Split-step on server toss apex; block return deep.",
    },
    "serve-target-boxes": {
        "title": "Serve target boxes",
        "description": "10 serves to T, 10 to wide; ignore power.",
    },
    "short-ball-decision": {
        "title": "Short ball decision",
        "description": "On short ball: decide approach vs aggressive FH early.",
    },
    "slice-cut-the-net": {
        "title": "Slice cut the net",
        "description": "Long cut-the-net feel for slice bite.",
    },
    "slice-underspin": {
        "title": "Slice underspin",
        "description": "Long low slice path; finish below contact.",
    },
    "split-step-timing": {
        "title": "Split-step timing",
        "description": "Practice split-step on opponent contact. 3×10 feeds.",
    },
    "toss-consistency": {
        "title": "Toss consistency",
        "description": "20 serves focusing only on toss height and placement.",
    },
    "trophy-pause": {
        "title": "Trophy pause",
        "description": "Pause 1s in trophy position, then accelerate up.",
    },
    "two-hand-sync": {
        "title": "2HBH sync",
        "description": "Non-dominant hand leads the path; shadow 2 minutes.",
    },
    "unit-turn-shadow": {
        "title": "Unit turn shadow",
        "description": "Shadow unit turn without ball: shoulders first, then hips.",
    },
    "weight-transfer-step": {
        "title": "Weight transfer step",
        "description": "Step into forehand with front foot as racket drops.",
    },
    "wide-ball-open-stance": {
        "title": "Wide open stance",
        "description": "Practice open-stance FH on wide balls only.",
    },
}


def catalog_for_prompt(limit: int = 40) -> str:
    drills_list = storage.list_drills()
    if not drills_list:
        sync_drills_from_wiki()
        drills_list = storage.list_drills()
    lines = []
    for d in drills_list[:limit]:
        tags = ", ".join(d.get("tags") or [])
        # В промпт — id + RU название (модель всё равно выбирает id)
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

    for d in all_drills:
        if d not in picked:
            picked.append(d)
        if len(picked) >= limit:
            break
    return picked


def format_drill_message(drill: dict, lang: str = "ru") -> str:
    localized = localize_drill(drill, lang)
    title = localized.get("title") or localized.get("id")
    desc = localized.get("description") or ""
    if lang == "ru":
        return f"🏋️ Упражнение: *{title}*\n\n{desc}"
    return f"🏋️ Drill: *{title}*\n\n{desc}"
