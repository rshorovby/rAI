import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_user_ids() -> tuple[int, ...]:
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    if not raw:
        return ()
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return tuple(ids)


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    gemini_api_key: str
    gemini_model: str
    admin_user_ids: tuple[int, ...]


def load_settings() -> Settings:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    admin_user_ids = _parse_admin_user_ids()

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
        gemini_model=gemini_model,
        admin_user_ids=admin_user_ids,
    )
