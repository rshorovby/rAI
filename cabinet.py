"""Уведомления в тренерский кабинет (Forum Topics)."""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Bot
from telegram.error import BadRequest

import identity
import review
import storage

logger = logging.getLogger(__name__)


def _split_text(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip())
    return chunks


def player_label(user_id: int, first_name: str = "", username: str = "") -> str:
    name = (first_name or "").strip()
    if username:
        handle = f"@{username}"
        return f"{name} ({handle})" if name else handle
    return name or f"user {user_id}"


async def ensure_player_topic(
    bot: Bot,
    forum_chat_id: int,
    user_id: int,
    *,
    first_name: str = "",
    username: str = "",
) -> Optional[int]:
    existing = storage.get_player_forum_topic(user_id, forum_chat_id)
    if existing:
        return int(existing["message_thread_id"])

    if not first_name and not username:
        tg_id = identity.telegram_id_for(user_id)
        if tg_id:
            try:
                chat = await bot.get_chat(tg_id)
                first_name = getattr(chat, "first_name", "") or ""
                username = getattr(chat, "username", "") or ""
            except Exception:
                logger.exception(
                    "get_chat failed for topic title telegram_id=%s", tg_id
                )

    title_id = identity.telegram_id_for(user_id) or user_id
    title = review.topic_title(title_id, first_name, username)
    try:
        topic = await bot.create_forum_topic(chat_id=forum_chat_id, name=title)
    except Exception:
        logger.exception(
            "create_forum_topic failed chat_id=%s user_id=%s",
            forum_chat_id,
            user_id,
        )
        return None

    thread_id = int(topic.message_thread_id)
    storage.save_player_forum_topic(user_id, forum_chat_id, thread_id, title)
    return thread_id


async def notify(
    bot: Bot,
    forum_chat_id: Optional[int],
    user_id: int,
    text: str,
    *,
    first_name: str = "",
    username: str = "",
) -> bool:
    """Пишет в тему игрока; при необходимости создаёт тему. False если кабинет недоступен."""
    if not forum_chat_id:
        return False
    body = (text or "").strip()
    if not body:
        return False
    try:
        thread_id = await ensure_player_topic(
            bot,
            int(forum_chat_id),
            user_id,
            first_name=first_name,
            username=username,
        )
    except Exception:
        logger.exception("ensure topic failed user_id=%s", user_id)
        return False
    if thread_id is None:
        return False
    try:
        for chunk in _split_text(body):
            await bot.send_message(
                chat_id=int(forum_chat_id),
                message_thread_id=thread_id,
                text=chunk,
            )
        return True
    except BadRequest:
        logger.exception(
            "cabinet notify BadRequest user_id=%s chat_id=%s",
            user_id,
            forum_chat_id,
        )
        return False
    except Exception:
        logger.exception("cabinet notify failed user_id=%s", user_id)
        return False


def format_start(
    user_id: int,
    *,
    first_name: str = "",
    username: str = "",
    is_new: bool = False,
) -> str:
    label = player_label(user_id, first_name, username)
    if is_new:
        return f"🚀 /start — новый игрок\n{label}\nid: {user_id}"
    return f"▶️ /start — вернулся в бота\n{label}\nid: {user_id}"


def format_onboarding_done(
    user_id: int,
    profile_text: str,
    *,
    skipped: bool = False,
    first_name: str = "",
    username: str = "",
) -> str:
    label = player_label(user_id, first_name, username)
    if skipped:
        return (
            f"⏭ Онбординг пропущен\n{label}\nid: {user_id}\n\n"
            f"{(profile_text or '').strip()}"
        ).strip()
    return (
        f"✅ Онбординг завершён\n{label}\nid: {user_id}\n\n"
        f"{(profile_text or '').strip()}"
    ).strip()


def format_practice_date(
    user_id: int,
    *,
    date_label: str,
    focus: str = "",
    drill: str = "",
    unknown: bool = False,
) -> str:
    focus = (focus or "").strip() or "—"
    drill = (drill or "").strip() or "—"
    date_line = (
        f"дата: не знает точно → ориентир {date_label}"
        if unknown
        else f"дата: {date_label}"
    )
    return (
        f"📅 Следующая тренировка\n"
        f"id: {user_id}\n"
        f"{date_line}\n"
        f"фокус: {focus}\n"
        f"упражнение: {drill}"
    )


def format_reminder(
    user_id: int,
    *,
    kind: str,
    detail: str = "",
) -> str:
    titles = {
        "inactive": "🔔 Напоминание (давненько не было видео)",
        "practice_pre": "🔔 Напоминание перед тренировкой",
        "practice_post": "🔔 Напоминание после тренировки",
    }
    title = titles.get(kind, "🔔 Напоминание отправлено игроку")
    detail = (detail or "").strip()
    if detail:
        return f"{title}\nid: {user_id}\n{detail}"
    return f"{title}\nid: {user_id}"


def format_survey_sent(
    user_id: int,
    *,
    survey_type: str = "no_video",
    source: str = "auto",
    first_name: str = "",
    username: str = "",
) -> str:
    label = player_label(user_id, first_name, username)
    if survey_type == "no_onboarding":
        title = "почему не прошёл онбординг"
        kind = "вручную (тренер)" if source == "manual" else "авто (24ч после /start)"
    else:
        title = "почему нет видео"
        kind = "вручную (тренер)" if source == "manual" else "авто (24ч без видео)"
    return f"📋 Опрос «{title}» отправлен ({kind})\n" f"{label}\nid: {user_id}"


def format_survey_response(
    user_id: int,
    summary: str,
    *,
    survey_type: str = "no_video",
    source: str = "auto",
    first_name: str = "",
    username: str = "",
) -> str:
    label = player_label(user_id, first_name, username)
    if survey_type == "no_onboarding":
        title = "почему не прошёл онбординг"
    else:
        title = "почему нет видео"
    kind = "вручную" if source == "manual" else "авто"
    body = (summary or "").strip() or "—"
    return f"📋 Ответ на опрос «{title}» ({kind})\n" f"{label}\nid: {user_id}\n\n{body}"


def format_video_uploaded(
    user_id: int,
    *,
    duration: int = 0,
    comment: str = "",
) -> str:
    lines = [f"📹 Видео загружено\nid: {user_id}"]
    if duration:
        lines.append(f"длина: {duration} сек")
    comment = (comment or "").strip()
    if comment:
        lines.append(f"подпись: {comment[:300]}")
    lines.append("статус: уточняет удар/акцент")
    return "\n".join(lines)


def format_video_intake_ready(
    user_id: int,
    *,
    stroke: str = "",
    look: str = "",
    duration: int = 0,
    comment: str = "",
) -> str:
    lines = [
        f"🎬 Видео готово к разбору\nid: {user_id}",
        f"удар: {(stroke or '').strip() or 'не указан'}",
        f"акцент: {(look or '').strip() or 'не указан'}",
    ]
    if duration:
        lines.append(f"длина: {duration} сек")
    comment = (comment or "").strip()
    if comment:
        lines.append(f"подпись: {comment[:300]}")
    lines.append("статус: AI ещё готовит черновик — можно смотреть видео")
    return "\n".join(lines)


def format_feedback(user_id: int, *, kind: str) -> str:
    labels = {
        "pos": "👍 Полезно",
        "neg": "👎 Не помогло",
        "clear": "✅ Понятно, что делать на тренировке",
    }
    label = labels.get(kind, kind)
    return f"🗳 Оценка разбора: {label}\nid: {user_id}"


def format_practice_post(
    user_id: int,
    *,
    answer: str,
    focus: str = "",
    drill: str = "",
) -> str:
    labels = {
        "yes": "✅ Сделал упражнение",
        "hard": "😰 Было сложно",
        "skip": "⏭ Не сделал / пропустил",
    }
    label = labels.get(answer, answer or "—")
    focus = (focus or "").strip() or "—"
    drill = (drill or "").strip() or "—"
    return (
        f"🏋️ Check-in после тренировки: {label}\n"
        f"id: {user_id}\n"
        f"фокус: {focus}\n"
        f"упражнение: {drill}"
    )


def format_followup(
    user_id: int,
    *,
    question: str,
    label: str = "",
) -> str:
    q = (question or "").strip()
    if len(q) > 500:
        q = q[:497] + "…"
    head = "💬 Вопрос игрока к боту"
    if label:
        head = f"{head} ({label})"
    return f"{head}\nid: {user_id}\n\n{q}"


def format_analysis_failed(
    user_id: int,
    *,
    error: str = "",
    retry: bool = False,
    simple: bool = False,
) -> str:
    if retry:
        mode = "⚡ повтор на простой модели" if simple else "🔄 повтор анализа"
        return f"{mode}\nid: {user_id}"
    err = (error or "").strip()
    if len(err) > 200:
        err = err[:197] + "…"
    lines = [f"❌ Ошибка анализа\nid: {user_id}"]
    if err:
        lines.append(f"причина: {err}")
    return "\n".join(lines)


def format_same_focus(
    user_id: int,
    *,
    focus: str,
    previous_focus: str = "",
    stroke: str = "",
    analyses_count: int = 0,
) -> str:
    focus = (focus or "").strip() or "—"
    prev = (previous_focus or "").strip()
    stroke = (stroke or "").strip()
    lines = [
        "🔄 Повторное видео по тому же фокусу",
        f"id: {user_id}",
        f"фокус: {focus}",
    ]
    if prev and prev != focus:
        lines.append(f"прошлый фокус: {prev}")
    if stroke:
        lines.append(f"удар: {stroke}")
    if analyses_count:
        lines.append(f"разборов всего: {analyses_count}")
    return "\n".join(lines)


def format_profile_reset(user_id: int) -> str:
    return f"🧹 Сброс профиля\nid: {user_id}\nонбординг начинается заново"


def same_focus(previous: Optional[str], current: Optional[str]) -> bool:
    prev = (previous or "").strip().lower()
    cur = (current or "").strip().lower()
    if not prev or not cur:
        return False
    if prev == cur:
        return True
    if len(prev) >= 12 and prev in cur:
        return True
    if len(cur) >= 12 and cur in prev:
        return True
    return False
