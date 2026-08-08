import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# gemini-2.0-flash отключён Google 01.06.2026 — дефолты держим на актуальных моделях
DEFAULT_MODEL_PRO = "gemini-3.1-pro-preview"
DEFAULT_MODEL_FREE = "gemini-3.5-flash"


def _parse_id_list(env_name: str) -> tuple[int, ...]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return ()
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return tuple(ids)


def _parse_admin_user_ids() -> tuple[int, ...]:
    return _parse_id_list("ADMIN_USER_IDS")


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    gemini_api_key: str
    gemini_model_pro: str
    gemini_model_free: str
    admin_user_ids: tuple[int, ...]
    coach_user_ids: tuple[int, ...]
    coach_forum_chat_id: Optional[int]

    def model_for(self, is_pro: bool = False) -> str:
        """Всегда лучшая модель; тариф влияет только на квоты, не на качество."""
        return self.gemini_model_pro

    @property
    def gemini_model(self) -> str:
        return self.gemini_model_pro

    def is_coach(self, user_id: int) -> bool:
        """Кнопки кабинета: COACH_USER_IDS, иначе fallback на ADMIN_USER_IDS."""
        if self.coach_user_ids:
            return user_id in self.coach_user_ids
        return user_id in self.admin_user_ids


def load_settings() -> Settings:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    legacy_model = os.getenv("GEMINI_MODEL", "").strip()
    gemini_model_pro = (
        os.getenv("GEMINI_MODEL_PRO", "").strip() or legacy_model or DEFAULT_MODEL_PRO
    )
    # Запасная модель для fallback при 503 — не берём legacy GEMINI_MODEL
    # (часто это тот же pro).
    gemini_model_free = os.getenv("GEMINI_MODEL_FREE", "").strip() or DEFAULT_MODEL_FREE
    admin_user_ids = _parse_admin_user_ids()
    coach_user_ids = _parse_id_list("COACH_USER_IDS")
    forum_raw = os.getenv("COACH_FORUM_CHAT_ID", "").strip()
    coach_forum_chat_id: Optional[int] = int(forum_raw) if forum_raw else None

    missing = []
    if not telegram_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not gemini_api_key:
        missing.append("GEMINI_API_KEY")

    if missing:
        raise RuntimeError(
            f"Не заданы переменные окружения: {', '.join(missing)}. "
            "Скопируйте .env.example в .env и заполните значения."
        )

    return Settings(
        telegram_token=telegram_token,
        gemini_api_key=gemini_api_key,
        gemini_model_pro=gemini_model_pro,
        gemini_model_free=gemini_model_free,
        admin_user_ids=admin_user_ids,
        coach_user_ids=coach_user_ids,
        coach_forum_chat_id=coach_forum_chat_id,
    )
