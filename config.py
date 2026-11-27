import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Дефолты на актуальной линейке Gemini 4 (ноябрь 2026)
DEFAULT_MODEL_PRO = "gemini-4-neon"
DEFAULT_MODEL_FREE = "gemini-4-hydrogen"
DEFAULT_MODEL_CHAT = "gemini-4-hydrogen"

DEFAULT_THINKING_PRO = "low"
DEFAULT_THINKING_FREE = "medium"
DEFAULT_THINKING_CHAT = "low"
_VALID_THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high", "xhigh"})
_VALID_SERVICE_TIERS = frozenset({"flex", "standard", "priority"})


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
    gemini_model_chat: str = DEFAULT_MODEL_CHAT

    def model_for(self, is_pro: bool = False) -> str:
        """Всегда лучшая модель; тариф влияет только на квоты, не на качество."""
        return self.gemini_model_pro

    def chat_model(self) -> str:
        """Модель для последующего текстового диалога по отчёту."""
        return self.gemini_model_chat

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
    gemini_model_chat = os.getenv("GEMINI_MODEL_CHAT", "").strip() or DEFAULT_MODEL_CHAT
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
        gemini_model_chat=gemini_model_chat,
    )


def is_gemini4_model(model: Optional[str]) -> bool:
    """True для моделей семейства Gemini 4 (neon, hydrogen, carbon, argon)."""
    return "gemini-4" in (model or "").strip().lower()


def gemini_thinking_level(
    model: Optional[str], *, for_chat: bool = False
) -> Optional[str]:
    """Уровень thinking для Gemini 4 (или None для 3.x / при явном отключении)."""
    if not is_gemini4_model(model):
        return None
    name = (model or "").strip().lower()
    if for_chat:
        raw = os.getenv("GEMINI_THINKING_CHAT", "").strip().lower()
        default = DEFAULT_THINKING_CHAT
    elif "hydrogen" in name:
        raw = (
            os.getenv("GEMINI_THINKING_FREE", "").strip().lower()
            or os.getenv("GEMINI_THINKING_LEVEL", "").strip().lower()
        )
        default = DEFAULT_THINKING_FREE
    elif "neon" in name:
        raw = (
            os.getenv("GEMINI_THINKING_PRO", "").strip().lower()
            or os.getenv("GEMINI_THINKING_LEVEL", "").strip().lower()
        )
        default = DEFAULT_THINKING_PRO
    else:
        raw = os.getenv("GEMINI_THINKING_LEVEL", "").strip().lower()
        default = "medium"
    chosen = raw or default
    if chosen in ("off", "none", "0", "false"):
        return None
    if chosen in _VALID_THINKING_LEVELS:
        return chosen
    return default


def gemini_service_tier() -> Optional[str]:
    """Нестандартный service tier из GEMINI_SERVICE_TIER (flex / priority) или None."""
    raw = os.getenv("GEMINI_SERVICE_TIER", "").strip().lower()
    if not raw or raw == "standard":
        return None
    if raw in _VALID_SERVICE_TIERS:
        return raw
    return None


def compact_prompt_v3_enabled() -> bool:
    """Компактный персонализированный промпт в structured v2. Включён по умолчанию."""
    raw = os.getenv("COMPACT_PROMPT_V3", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def analysis_temperature() -> float:
    """Температура для лаборатории. Боевой разбор v2 её не читает и всегда шлёт 0.3."""
    raw = os.getenv("ANALYSIS_TEMPERATURE", "0.3").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.3


def focus_evidence_required() -> bool:
    """improved/worse без таймкода в evidence понижается до not_visible."""
    raw = os.getenv("FOCUS_EVIDENCE_REQUIRED", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def pose_prepass_enabled() -> bool:
    """Предварительный поиск ударов (MediaPipe + звук) до Gemini. По умолчанию выкл."""
    raw = os.getenv("POSE_PREPASS", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")
