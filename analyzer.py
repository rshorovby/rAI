import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from analysis_schema import build_response_schema, drill_ids_from_catalog, to_sdk_schema
from config import (
    focus_evidence_required,
    gemini_service_tier,
    gemini_thinking_level,
    is_gemini4_model,
)
from i18n import DEFAULT_LANG, normalize_language_code, t
from pricing import Usage, usage_from_response
from prompts import (
    build_analysis_prompt,
    build_follow_up_system_prompt,
    build_system_prompt,
    use_structured_analysis_v2,
)
from structured_pipeline import run_structured, video_duration_sec, write_run_log
from video_mute import strip_audio_for_upload

MAX_CHAT_TURNS = 10

logger = logging.getLogger(__name__)

PROCESSING_TIMEOUT_SEC = 120
PROCESSING_POLL_INTERVAL_SEC = 2
# HTTP-таймаут generate/upload (мс). Без него generate_content может висеть минутами.
HTTP_TIMEOUT_MS = 180_000
FLEX_HTTP_TIMEOUT_MS = 600_000

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

_NO_AFC = types.AutomaticFunctionCallingConfig(disable=True)


STRUCTURED_VIDEO_FPS = 8.0
STRUCTURED_TEMPERATURE = 0.3
GEMINI4_MAX_OUTPUT_TOKENS = 65536


def _thinking_config(
    model: str, *, for_chat: bool = False
) -> Optional[types.ThinkingConfig]:
    level_name = gemini_thinking_level(model, for_chat=for_chat)
    if not level_name:
        return None
    enum_cls = getattr(types, "ThinkingLevel", None)
    if enum_cls is None:
        return None
    level = getattr(enum_cls, level_name.upper(), None)
    if level is None:
        return None
    return types.ThinkingConfig(thinking_level=level)


def _service_tier_value():
    tier_name = gemini_service_tier()
    if not tier_name:
        return None
    enum_cls = getattr(types, "ServiceTier", None)
    if enum_cls is not None:
        resolved = getattr(enum_cls, tier_name.upper(), None)
        if resolved is not None:
            return resolved
    return tier_name


def _build_generate_config(
    model: str,
    *,
    system_instruction: str,
    legacy_temperature: float,
    for_chat: bool = False,
    response_mime_type: Optional[str] = None,
    response_schema=None,
    media_resolution=None,
) -> types.GenerateContentConfig:
    kwargs = {
        "system_instruction": system_instruction,
        "automatic_function_calling": _NO_AFC,
    }
    if is_gemini4_model(model):
        # Gemini 4: temperature не передавать; явно задаём thinking_level и max_output_tokens.
        kwargs["max_output_tokens"] = GEMINI4_MAX_OUTPUT_TOKENS
        thinking = _thinking_config(model, for_chat=for_chat)
        if thinking is not None:
            kwargs["thinking_config"] = thinking
    else:
        kwargs["temperature"] = legacy_temperature
    tier = _service_tier_value()
    if tier is not None:
        kwargs["service_tier"] = tier
    if response_mime_type is not None:
        kwargs["response_mime_type"] = response_mime_type
    if response_schema is not None:
        kwargs["response_schema"] = response_schema
    if media_resolution is not None:
        kwargs["media_resolution"] = media_resolution
    return types.GenerateContentConfig(**kwargs)


def _prepare_structured_video(part) -> None:
    """Разбор v2 всегда смотрит 8 кадров/с в высоком разрешении."""
    if "fps" not in getattr(types.VideoMetadata, "model_fields", {}):
        raise RuntimeError("Нужен google-genai с VideoMetadata.fps.")
    part.video_metadata = types.VideoMetadata(fps=STRUCTURED_VIDEO_FPS)
    part.media_resolution = types.PartMediaResolution(
        level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
    )


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


RUN_LOG_DIR = Path(__file__).resolve().parent / "logs" / "analysis-runs"


@dataclass(frozen=True)
class AnalysisResult:
    text: str
    usage: Usage
    model: str
    raw_json: Optional[dict] = None
    run_log: Optional[dict] = None


class VideoAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        timeout = (
            FLEX_HTTP_TIMEOUT_MS if gemini_service_tier() == "flex" else HTTP_TIMEOUT_MS
        )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout),
        )
        self._model = model

    def analyze(
        self,
        video_path: Path,
        user_comment: Optional[str] = None,
        player_history: Optional[list] = None,
        language_code: str = DEFAULT_LANG,
        player_profile: Optional[dict] = None,
        video_context: Optional[dict] = None,
        model: Optional[str] = None,
        active_focus: Optional[str] = None,
        drills_catalog: Optional[str] = None,
        coach_corrections: Optional[list] = None,
        prompt_context: Optional[dict] = None,
        experiment_v2: bool = False,
        player_id: Optional[int] = None,
        run_log_dir: Optional[Path] = RUN_LOG_DIR,
    ) -> AnalysisResult:
        use_model = model or self._model
        upload_path, mute_tmp = strip_audio_for_upload(video_path)
        uploaded = None
        try:
            logger.info(
                "Gemini upload start model=%s file=%s", use_model, upload_path.name
            )
            uploaded = self._client.files.upload(file=str(upload_path))
            uploaded = self._wait_until_active(uploaded)
            logger.info("Gemini generate start model=%s", use_model)
            system_prompt = build_system_prompt(
                language_code,
                player_history,
                player_profile,
                stroke=(video_context or {}).get("stroke"),
                active_focus=active_focus,
                drills_catalog=drills_catalog,
                coach_corrections=coach_corrections,
                strokes=(video_context or {}).get("strokes"),
                prompt_context=prompt_context,
                experiment_v2=experiment_v2,
            )
            user_prompt = build_analysis_prompt(
                language_code,
                user_comment,
                video_context,
                experiment_v2=experiment_v2,
            )
            video_part = types.Part.from_uri(
                file_uri=uploaded.uri,
                mime_type=uploaded.mime_type,
            )
            structured = use_structured_analysis_v2(language_code) and not experiment_v2
            if structured:
                _prepare_structured_video(video_part)
                drill_ids = drill_ids_from_catalog(drills_catalog)
                schema = build_response_schema(drill_ids)
                sdk_schema = to_sdk_schema(schema)
                started = time.perf_counter()

                def generate():
                    response = self._generate_with_retry(
                        model=use_model,
                        contents=[
                            types.Content(
                                role="user",
                                parts=[
                                    video_part,
                                    types.Part.from_text(text=user_prompt),
                                ],
                            )
                        ],
                        config=_build_generate_config(
                            use_model,
                            system_instruction=system_prompt,
                            legacy_temperature=STRUCTURED_TEMPERATURE,
                            response_mime_type="application/json",
                            response_schema=sdk_schema,
                            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
                        ),
                    )
                    return (
                        self._extract_text(response),
                        usage_from_response(response, use_model),
                    )

                outcome = run_structured(
                    generate,
                    schema=schema,
                    drill_ids=drill_ids,
                    duration_sec=video_duration_sec(video_path),
                    downgrade_missing_evidence=focus_evidence_required(),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=use_model,
                    player_id=player_id,
                )
                outcome["run_log"]["latency_sec"] = round(
                    time.perf_counter() - started, 3
                )
                if run_log_dir is not None:
                    write_run_log(run_log_dir, outcome["run_log"])
                return AnalysisResult(
                    text=outcome["text"],
                    usage=outcome["usage"],
                    model=use_model,
                    raw_json=outcome["raw_json"],
                    run_log=outcome["run_log"],
                )

            response = self._generate_with_retry(
                model=use_model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            video_part,
                            types.Part.from_text(text=user_prompt),
                        ],
                    )
                ],
                config=_build_generate_config(
                    use_model,
                    system_instruction=system_prompt,
                    legacy_temperature=0.4,
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

        text = self._extract_text(response)
        usage = usage_from_response(response, use_model)
        logger.info(
            "Gemini generate done model=%s chars=%s in=%s out=%s",
            use_model,
            len(text),
            usage.input_tokens,
            usage.output_tokens,
        )
        return AnalysisResult(text=text, usage=usage, model=use_model)

    def _generate_with_retry(
        self, model: Optional[str] = None, **kwargs
    ) -> types.GenerateContentResponse:
        attempt = 0
        while True:
            try:
                return self._client.models.generate_content(
                    model=model or self._model, **kwargs
                )
            except Exception as exc:
                # HTTP timeout — не ретраим бесконечно: пользователю нужен retry UI.
                name = type(exc).__name__.lower()
                msg = str(exc).lower()
                if "timeout" in name or "timed out" in msg:
                    raise TimeoutError(
                        "Превышено время ожидания ответа Gemini."
                    ) from exc
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
        model: Optional[str] = None,
        coach_corrections: Optional[list] = None,
        prompt_context: Optional[dict] = None,
        scoped: bool = False,
    ) -> AnalysisResult:
        use_model = model or self._model
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
            model=use_model,
            contents=contents,
            config=_build_generate_config(
                use_model,
                system_instruction=build_follow_up_system_prompt(
                    language_code,
                    player_history,
                    player_profile,
                    stroke=stroke,
                    coach_corrections=coach_corrections,
                    prompt_context=prompt_context,
                    scoped=scoped,
                ),
                legacy_temperature=0.5,
                for_chat=True,
            ),
        )
        text = self._extract_text(response)
        usage = usage_from_response(response, use_model)
        return AnalysisResult(text=text, usage=usage, model=use_model)

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
