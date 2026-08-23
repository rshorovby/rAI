"""Константы событий и форматирование отчёта аналитики."""

EVENT_ONBOARDING_STARTED = "onboarding_started"
EVENT_ONBOARDING_COMPLETED = "onboarding_completed"
EVENT_ONBOARDING_SKIPPED = "onboarding_skipped"
EVENT_VIDEO_SENT = "video_sent"
EVENT_ANALYSIS_SUCCESS = "analysis_success"
EVENT_ANALYSIS_FAILED = "analysis_failed"
EVENT_FEEDBACK_POSITIVE = "feedback_positive"
EVENT_FEEDBACK_NEGATIVE = "feedback_negative"
EVENT_FEEDBACK_CLEAR = "feedback_clear"
EVENT_REMINDER_SENT = "reminder_sent"
EVENT_PROFILE_RESET = "profile_reset"
EVENT_PAYWALL_SHOWN = "paywall_shown"
EVENT_INVOICE_SENT = "invoice_sent"
EVENT_PAYMENT_SUCCESS = "payment_success"
EVENT_SUBSCRIPTION_EXPIRED = "subscription_expired"
EVENT_PRACTICE_DATE_SET = "practice_date_set"
EVENT_PRACTICE_PRE_SENT = "practice_pre_sent"
EVENT_PRACTICE_POST_SENT = "practice_post_sent"
EVENT_PRACTICE_POST_ANSWERED = "practice_post_answered"
EVENT_REVIEW_QUEUED = "review_queued"
EVENT_REVIEW_SENT_COACH = "review_sent_coach"
EVENT_REVIEW_SENT_FALLBACK = "review_sent_fallback"
EVENT_SURVEY_SENT = "survey_sent"
EVENT_SURVEY_COMPLETED = "survey_completed"

ALL_EVENT_TYPES = (
    EVENT_ONBOARDING_STARTED,
    EVENT_ONBOARDING_COMPLETED,
    EVENT_ONBOARDING_SKIPPED,
    EVENT_VIDEO_SENT,
    EVENT_ANALYSIS_SUCCESS,
    EVENT_ANALYSIS_FAILED,
    EVENT_FEEDBACK_POSITIVE,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_CLEAR,
    EVENT_REMINDER_SENT,
    EVENT_PROFILE_RESET,
    EVENT_PAYWALL_SHOWN,
    EVENT_INVOICE_SENT,
    EVENT_PAYMENT_SUCCESS,
    EVENT_SUBSCRIPTION_EXPIRED,
    EVENT_PRACTICE_DATE_SET,
    EVENT_PRACTICE_PRE_SENT,
    EVENT_PRACTICE_POST_SENT,
    EVENT_PRACTICE_POST_ANSWERED,
    EVENT_REVIEW_QUEUED,
    EVENT_REVIEW_SENT_COACH,
    EVENT_REVIEW_SENT_FALLBACK,
    EVENT_SURVEY_SENT,
    EVENT_SURVEY_COMPLETED,
)


def _pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "—"
    return f"{part * 100 // whole}%"


def format_analytics_report(data: dict) -> str:
    users = data["users_total"]
    started = data["events"].get(EVENT_ONBOARDING_STARTED, 0)
    completed = data["events"].get(EVENT_ONBOARDING_COMPLETED, 0)
    skipped = data["events"].get(EVENT_ONBOARDING_SKIPPED, 0)
    videos = data["events"].get(EVENT_VIDEO_SENT, 0)
    success = data["events"].get(EVENT_ANALYSIS_SUCCESS, 0)
    failed = data["events"].get(EVENT_ANALYSIS_FAILED, 0)
    fb_pos = data["events"].get(EVENT_FEEDBACK_POSITIVE, 0)
    fb_neg = data["events"].get(EVENT_FEEDBACK_NEGATIVE, 0)
    fb_clear = data["events"].get(EVENT_FEEDBACK_CLEAR, 0)
    fb_total = fb_pos + fb_neg + fb_clear
    reminders = data["events"].get(EVENT_REMINDER_SENT, 0)
    practice_dates = data["events"].get(EVENT_PRACTICE_DATE_SET, 0)
    practice_pre = data["events"].get(EVENT_PRACTICE_PRE_SENT, 0)
    practice_post = data["events"].get(EVENT_PRACTICE_POST_SENT, 0)
    practice_answers = data["events"].get(EVENT_PRACTICE_POST_ANSWERED, 0)
    paywall = data["events"].get(EVENT_PAYWALL_SHOWN, 0)
    invoices = data["events"].get(EVENT_INVOICE_SENT, 0)
    payments = data["events"].get(EVENT_PAYMENT_SUCCESS, 0)
    expired = data["events"].get(EVENT_SUBSCRIPTION_EXPIRED, 0)
    evals = data.get("coach_evals") or {}

    lines = [
        "📊 RallyAI — статистика",
        "",
        "Пользователи",
        f"• Нажали /start: {users}",
        f"• Профиль заполнен: {data['profiles_complete']}",
        f"• Онбординг пропущен: {data['profiles_skipped']}",
        f"• Отправляли видео: {data['users_with_videos']}",
        f"• Активны за 7 дней: {data['users_active_7d']}",
        "",
        "Воронка",
        f"• Старт онбординга: {started}",
        f"• Завершили: {completed} ({_pct(completed, started)})",
        f"• Пропустили: {skipped} ({_pct(skipped, started)})",
        f"• Видео отправлено: {videos}",
        f"• Разбор успешен: {success} ({_pct(success, videos)})",
        f"• Разбор с ошибкой: {failed} ({_pct(failed, videos)})",
        "",
        "Оплата",
        f"• Paywall показан: {paywall}",
        f"• Инвойс отправлен: {invoices} ({_pct(invoices, paywall)})",
        f"• Оплата успешна: {payments} ({_pct(payments, invoices)})",
        f"• Подписок истекло: {expired}",
        "",
        "Фидбек",
        f"• Всего ответов: {fb_total}",
        f"• 👍 Полезно: {fb_pos} ({_pct(fb_pos, fb_total)})",
        f"• 👎 Не помогло: {fb_neg} ({_pct(fb_neg, fb_total)})",
        f"• ✅ Понятно что делать: {fb_clear} ({_pct(fb_clear, fb_total)})",
        "",
        "Оценка тренера (AI)",
        f"• Всего оценок: {evals.get('total', 0)}",
        f"• ✅ Ок: {evals.get('ok', 0)}",
        f"• ✏️ Дополнил: {evals.get('added', 0)}",
        f"• ❌ Мимо: {evals.get('miss', 0)}",
        f"• С допиской: {evals.get('with_delta', 0)}",
        "",
        "Напоминания",
        f"• Отправлено: {reminders}",
        "",
        "Тренировки (practice)",
        f"• Дата задана: {practice_dates}",
        f"• Pre-nudge: {practice_pre}",
        f"• Post check-in: {practice_post}",
        f"• Ответов на check-in: {practice_answers}",
        "",
        "Разборы",
        f"• Всего: {data['analyses_total']}",
        f"• Уникальных пользователей: {data['users_with_videos']}",
    ]

    usage = data.get("usage") or {}
    if usage:
        lines += [
            "",
            f"API / себестоимость ({usage.get('days', 30)} дн.)",
            f"• Вызовов: {usage.get('calls', 0)} (разборов: {usage.get('analyses', 0)})",
            f"• Токены in/out: {usage.get('input_tokens', 0)} / "
            f"{usage.get('output_tokens', 0) + usage.get('thinking_tokens', 0)}",
            f"• Средние токены / разбор: "
            f"in {usage.get('avg_input_tokens', 0):.0f}, "
            f"out {usage.get('avg_output_tokens', 0):.0f}",
            f"• Cost всего: ${usage.get('cost_usd', 0):.4f}",
            f"• Cost / разбор: ${usage.get('avg_cost_per_analysis', 0):.4f}",
            f"• Cost / активный юзер: ${usage.get('cost_per_active_user', 0):.4f}",
        ]

    retention = data.get("retention") or []
    if retention:
        lines += ["", "Retention (когорты по неделе регистрации)"]
        for c in retention[-6:]:
            lines.append(
                f"• {c['cohort']} n={c['size']}: "
                f"D1 {c['d1_pct']}% · D7 {c['d7_pct']}% · D30 {c['d30_pct']}%"
            )

    recent = data.get("recent_users") or []
    if recent:
        lines += ["", "Последние пользователи"]
        for u in recent:
            name = u.get("display_name") or "—"
            if u.get("username"):
                username = f"@{u['username']}"
            else:
                username = "—"
            lines.append(
                f"• {u['user_id']} {username} {name} — "
                f"видео: {u['videos']}, профиль: {u['profile_status']}"
            )

    return "\n".join(lines)
