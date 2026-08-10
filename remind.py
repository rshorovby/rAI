#!/usr/bin/env python3
"""Рассылка напоминаний, practice pre/post и недельных дайджестов."""

import asyncio
import logging
import sys

from telegram import Bot

import cabinet
import practice
import review
import storage
from analytics import (
    EVENT_PRACTICE_POST_SENT,
    EVENT_PRACTICE_PRE_SENT,
    EVENT_REMINDER_SENT,
)
from config import load_settings
from i18n import normalize_language_code, t
from practice import keyboard_post_checkin, keyboard_pre_nudge

logger = logging.getLogger(__name__)


def _ui_lang(language_code: str) -> str:
    return "ru" if normalize_language_code(language_code or "") == "ru" else "en"


def _focus_drill(row: dict) -> tuple[str, str]:
    focus = (row.get("focus_text") or "").strip() or "—"
    drill = (row.get("drill_text") or "").strip() or "—"
    return focus, drill


async def run_reminders(days: int = 7) -> int:
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    users = storage.get_users_for_reminder(days=days)
    sent = 0
    for row in users:
        user_id = row["user_id"]
        lang = _ui_lang(row.get("language_code") or "")
        task = (row.get("next_video") or "").strip()
        if task:
            text = t(lang, "reminder_with_task", task=task)
        else:
            text = t(lang, "reminder_generic")
        try:
            await bot.send_message(chat_id=user_id, text=text)
            storage.mark_reminder_sent(user_id)
            storage.log_event(user_id, EVENT_REMINDER_SENT)
            await cabinet.notify(
                bot,
                settings.coach_forum_chat_id,
                int(user_id),
                cabinet.format_reminder(
                    int(user_id),
                    kind="inactive",
                    detail=f"задача: {task}" if task else "",
                ),
            )
            sent += 1
            logger.info("Напоминание отправлено user_id=%s", user_id)
        except Exception:
            logger.exception("Не удалось отправить напоминание user_id=%s", user_id)
    return sent


async def run_digests() -> int:
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    users = storage.get_users_for_digest()
    sent = 0
    for row in users:
        user_id = int(row["user_id"])
        lang = _ui_lang(row.get("language_code") or "")
        focus_row = storage.get_player_focus(user_id)
        focus = (focus_row or {}).get("focus") or "—"
        analyses = int(row.get("analyses_week") or 0)
        streak = int(row.get("streak_weeks") or 0)
        text = t(
            lang,
            "digest_weekly",
            focus=focus,
            streak=streak + (1 if analyses else 0),
            analyses=analyses,
        )
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
            storage.mark_digest_sent(user_id, had_analysis=analyses > 0)
            sent += 1
            logger.info("Дайджест отправлен user_id=%s", user_id)
        except Exception:
            logger.exception("Не удалось отправить дайджест user_id=%s", user_id)
    return sent


async def run_practice_nudges() -> tuple[int, int]:
    """Отправляет due pre/post по московскому времени. Возвращает (pre, post)."""
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    today = practice.today_msk().isoformat()
    storage.auto_schedule_stale_practice_plans(today)
    pre_sent = 0
    post_sent = 0

    if practice.should_send_pre_now():
        for row in storage.list_due_practice_pre(today):
            user_id = int(row["user_id"])
            lang = _ui_lang(row.get("language_code") or "")
            focus, drill = _focus_drill(row)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=t(lang, "practice_pre", focus=focus, drill=drill),
                    parse_mode="Markdown",
                    reply_markup=keyboard_pre_nudge(lang),
                )
                storage.mark_practice_pre_sent(int(row["id"]))
                storage.log_event(user_id, EVENT_PRACTICE_PRE_SENT)
                await cabinet.notify(
                    bot,
                    settings.coach_forum_chat_id,
                    user_id,
                    cabinet.format_reminder(
                        user_id,
                        kind="practice_pre",
                        detail=f"фокус: {focus}\nупражнение: {drill}",
                    ),
                )
                pre_sent += 1
                logger.info("Practice pre отправлен user_id=%s", user_id)
            except Exception:
                logger.exception(
                    "Не удалось отправить practice pre user_id=%s", user_id
                )

    if practice.should_send_post_now():
        for row in storage.list_due_practice_post(today):
            user_id = int(row["user_id"])
            lang = _ui_lang(row.get("language_code") or "")
            focus, drill = _focus_drill(row)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=t(lang, "practice_post", drill=drill),
                    reply_markup=keyboard_post_checkin(lang),
                )
                storage.mark_practice_post_sent(int(row["id"]))
                storage.log_event(user_id, EVENT_PRACTICE_POST_SENT)
                await cabinet.notify(
                    bot,
                    settings.coach_forum_chat_id,
                    user_id,
                    cabinet.format_reminder(
                        user_id,
                        kind="practice_post",
                        detail=f"фокус: {focus}\nупражнение: {drill}",
                    ),
                )
                post_sent += 1
                logger.info("Practice post отправлен user_id=%s", user_id)
            except Exception:
                logger.exception(
                    "Не удалось отправить practice post user_id=%s", user_id
                )

    return pre_sent, post_sent


async def run_review_fallbacks(hours: int = 24) -> int:
    """Через N часов без ревью тренера — отправить AI с пометкой."""
    from bot import _deliver_review_to_player

    settings = load_settings()
    bot = Bot(settings.telegram_token)

    class _Ctx:
        def __init__(self):
            self.bot = bot
            self.user_data = {}
            self.application = type("App", (), {"bot_data": {"settings": settings}})()

    ctx = _Ctx()
    sent = 0
    for job in storage.list_review_jobs_for_fallback(hours=hours):
        lang = _ui_lang(job.get("language_code") or "")
        final_text = review.compose_final_report(
            job.get("draft_text") or "",
            fallback=True,
            lang=lang,
        )
        try:
            await _deliver_review_to_player(
                ctx,
                job,
                final_text=final_text,
                status=review.STATUS_SENT_FALLBACK,
            )
            sent += 1
            logger.info("Review fallback отправлен job_id=%s", job["id"])
            if job.get("forum_chat_id") and job.get("message_thread_id"):
                try:
                    await bot.send_message(
                        chat_id=int(job["forum_chat_id"]),
                        message_thread_id=int(job["message_thread_id"]),
                        text=(
                            f"⏰ Fallback: AI-отчёт ушёл игроку без ревью "
                            f"(job #{job['id']})."
                        ),
                    )
                except Exception:
                    logger.exception("Не удалось написать в тему о fallback")
        except Exception:
            logger.exception("Review fallback failed job_id=%s", job.get("id"))
    return sent


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    mode = "remind"
    days = 7
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "digest":
            mode = "digest"
        elif arg == "practice":
            mode = "practice"
        elif arg == "review":
            mode = "review"
        else:
            days = int(arg)
    if mode == "digest":
        count = asyncio.run(run_digests())
        print(f"Отправлено дайджестов: {count}")
    elif mode == "practice":
        pre, post = asyncio.run(run_practice_nudges())
        print(f"Practice nudges: pre={pre}, post={post}")
    elif mode == "review":
        count = asyncio.run(run_review_fallbacks(24))
        print(f"Review fallbacks: {count}")
    else:
        count = asyncio.run(run_reminders(days))
        print(f"Отправлено напоминаний: {count}")


if __name__ == "__main__":
    main()
