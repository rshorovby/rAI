import logging
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from prompts import FOLLOW_UP_SYSTEM_PROMPT, SYSTEM_PROMPT, build_analysis_prompt

MAX_CHAT_TURNS = 10

logger = logging.getLogger(__name__)

PROCESSING_TIMEOUT_SEC = 120
PROCESSING_POLL_INTERVAL_SEC = 2


class VideoAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def analyze(self, video_path: Path, user_comment: Optional[str] = None) -> str:
        uploaded = self._client.files.upload(file=str(video_path))
        uploaded = self._wait_until_active(uploaded)

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded.uri,
                                mime_type=uploaded.mime_type,
                            ),
                            types.Part.from_text(
                                text=build_analysis_prompt(user_comment)
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.4,
                ),
            )
        finally:
            self._safe_delete(uploaded.name)

        return self._extract_text(response)

    def chat(
        self,
        analysis_report: str,
        history: list[dict[str, str]],
        user_message: str,
    ) -> str:
        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=(
                            "Вот отчёт по видео теннисиста, который мы уже разобрали:\n\n"
                            f"{analysis_report}"
                        )
                    )
                ],
            ),
            types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text="Понял. Готов ответить на вопросы и уточнения по этому разбору."
                    )
                ],
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

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=FOLLOW_UP_SYSTEM_PROMPT,
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
