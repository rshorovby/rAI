import logging
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from i18n import DEFAULT_LANG, normalize_language_code, t
from prompts import (
    build_analysis_prompt,
    build_follow_up_system_prompt,
    build_system_prompt,
)
from video_mute import strip_audio_for_upload

MAX_CHAT_TURNS = 10

logger = logging.getLogger(__name__)

PROCESSING_TIMEOUT_SEC = 120
PROCESSING_POLL_INTERVAL_SEC = 2

MAX_GENERATE_RETRIES = 2
RETRY_BACKOFF_SEC = 3
_TRANSIENT_MARKERS = (
    "503",
    "unavailable",
    "overloaded",
    "high demand",
    "500",
    "internal",
)


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


class VideoAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def analyze(
        self,
        video_path: Path,
        user_comment: Optional[str] = None,
        player_history: Optional[list] = None,
        language_code: str = DEFAULT_LANG,
        player_profile: Optional[dict] = None,
        video_context: Optional[dict] = None,
    ) -> str:
        upload_path, mute_tmp = strip_audio_for_upload(video_path)
        uploaded = None
        try:
            uploaded = self._client.files.upload(file=str(upload_path))
            uploaded = self._wait_until_active(uploaded)

            response = self._generate_with_retry(
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded.uri,
                                mime_type=uploaded.mime_type,
                            ),
                            types.Part.from_text(
                                text=build_analysis_prompt(
                                    language_code, user_comment, video_context
                                )
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=build_system_prompt(
                        language_code,
                        player_history,
                        player_profile,
                        stroke=(video_context or {}).get("stroke"),
                    ),
                    temperature=0.4,
                ),
            )
        finally:
            if uploaded is not None:
                self._safe_delete(uploaded.name)
            if mute_tmp is not None:
                try:
                    mute_tmp.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Не удалось удалить локальный mute-файл: %s", mute_tmp
                    )

        return self._extract_text(response)

    def _generate_with_retry(self, **kwargs) -> types.GenerateContentResponse:
        attempt = 0
        while True:
            try:
                return self._client.models.generate_content(model=self._model, **kwargs)
            except Exception as exc:
                if attempt >= MAX_GENERATE_RETRIES or not _is_transient_error(exc):
                    raise
                attempt += 1
                wait = RETRY_BACKOFF_SEC * attempt
                logger.warning(
                    "Временная ошибка Gemini (попытка %s/%s), повтор через %sс: %s",
                    attempt,
                    MAX_GENERATE_RETRIES,
                    wait,
                    exc,
                )
                time.sleep(wait)

    def chat(
        self,
        analysis_report: str,
        history: list[dict[str, str]],
        user_message: str,
        player_history: Optional[list] = None,
        language_code: str = DEFAULT_LANG,
        player_profile: Optional[dict] = None,
        stroke: Optional[str] = None,
    ) -> str:
        ui_lang = "ru" if normalize_language_code(language_code) == "ru" else "en"
        report_intro = (
            "Вот отчёт по видео теннисиста, который мы уже разобрали:\n\n"
            if ui_lang == "ru"
            else "Here is the tennis video analysis report we already reviewed:\n\n"
        )

        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"{report_intro}{analysis_report}")],
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=t(ui_lang, "chat_ack"))],
            ),
        ]

        for turn in history[-MAX_CHAT_TURNS:]:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=turn["user"])],
                )
            )
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=turn["assistant"])],
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            )
        )

        response = self._generate_with_retry(
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=build_follow_up_system_prompt(
                    language_code, player_history, player_profile, stroke=stroke
                ),
                temperature=0.5,
            ),
        )
        return self._extract_text(response)

    def _extract_text(self, response: types.GenerateContentResponse) -> str:
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Модель вернула пустой ответ.")
        return text

    def _wait_until_active(self, uploaded_file: types.File) -> types.File:
        deadline = time.monotonic() + PROCESSING_TIMEOUT_SEC
        current = uploaded_file

        while current.state and current.state.name != "ACTIVE":
            if time.monotonic() > deadline:
                raise TimeoutError(
                    "Превышено время ожидания обработки видео на стороне Gemini."
                )
            if current.state.name == "FAILED":
                raise RuntimeError("Gemini не смог обработать загруженное видео.")

            time.sleep(PROCESSING_POLL_INTERVAL_SEC)
            current = self._client.files.get(name=current.name)

        return current

    def _safe_delete(self, file_name: Optional[str]) -> None:
        if not file_name:
            return
        try:
            self._client.files.delete(name=file_name)
        except Exception:
            logger.warning("Не удалось удалить временный файл в Gemini: %s", file_name)
