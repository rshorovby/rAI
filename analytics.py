"""Константы событий и форматирование отчёта аналитики."""

EVENT_ONBOARDING_STARTED = "onboarding_started"
EVENT_ONBOARDING_COMPLETED = "onboarding_completed"
EVENT_ONBOARDING_SKIPPED = "onboarding_skipped"
EVENT_VIDEO_SENT = "video_sent"
EVENT_ANALYSIS_SUCCESS = "analysis_success"
EVENT_ANALYSIS_FAILED = "analysis_failed"

ALL_EVENT_TYPES = (
    EVENT_ONBOARDING_STARTED,
    EVENT_ONBOARDING_COMPLETED,
    EVENT_ONBOARDING_SKIPPED,
    EVENT_VIDEO_SENT,
    EVENT_ANALYSIS_SUCCESS,
    EVENT_ANALYSIS_FAILED,
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

    lines = [
        "📊 *RallyAI — статистика*",
        "",
        "*Пользователи*",
        f"• Нажали /start: {users}",
        f"• Профиль заполнен: {data['profiles_complete']}",
        f"• Онбординг пропущен: {data['profiles_skipped']}",
        f"• Отправляли видео: {data['users_with_videos']}",
        f"• Активны за 7 дней: {data['users_active_7d']}",
        "",
        "*Воронка*",
        f"• Старт онбординга: {started}",
        f"• Завершили: {completed} ({_pct(completed, started)})",
        f"• Пропустили: {skipped} ({_pct(skipped, started)})",
        f"• Видео отправлено: {videos}",
        f"• Разбор успешен: {success} ({_pct(success, videos)})",
        f"• Разбор с ошибкой: {failed} ({_pct(failed, videos)})",
        "",
        "*Разборы*",
        f"• Всего: {data['analyses_total']}",
        f"• Уникальных пользователей: {data['users_with_videos']}",
    ]

    recent = data.get("recent_users") or []
    if recent:
        lines += ["", "*Последние пользователи*"]
        for u in recent:
            name = u.get("display_name") or "—"
            username = f"@{u['username']}" if u.get("username") else "—"
            lines.append(
                f"• `{u['user_id']}` {username} {name} — "
                f"видео: {u['videos']}, профиль: {u['profile_status']}"
            )

    return "\n".join(lines)
