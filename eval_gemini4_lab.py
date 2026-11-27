"""A/B-лаборатория Gemini 4 (Hydrogen, Neon, Carbon) против baseline Gemini 3.1 Pro.

Изолированный скрипт: не меняет боевые analyzer.py / prompts.py / pricing.py.
Для моделей Gemini 4 применяет 4 рекомендации:
1. Не передаёт temperature / top_p / top_k.
2. Явно задаёт thinking_level (medium / high).
3. Явно задаёт max_output_tokens = 65536.
4. Собирает system_instruction в cache-friendly порядке (весь статический префикс
   в начале, переменный knowledge_ctx по удару в конце) + логирует cached_input.

Запуск (через venv с google-genai >= 2.27):
    /tmp/genai-g4-venv/bin/python eval_gemini4_lab.py --dir videos/Genimi4Test
    /tmp/genai-g4-venv/bin/python eval_gemini4_lab.py --dir videos/Genimi4Test --yes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from eval_fps_lab import VIDEO_SUFFIXES, list_videos, stroke_of, video_context_for

STRUCTURED_VIDEO_FPS = 8.0
BASELINE_TEMPERATURE = 0.3
GEMINI4_MAX_OUTPUT_TOKENS = 65536
HTTP_TIMEOUT_MS = 600_000
MAX_TRANSIENT_RETRIES = 2
TRANSIENT_BACKOFF_SEC = 5
_TRANSIENT_MARKERS = (
    "503",
    "unavailable",
    "overloaded",
    "high demand",
    "500",
    "internal",
    "429",
    "resource_exhausted",
)

# Тарифы USD за 1M токенов: (input, cached_input, output_incl_thinking)
# Постоянные ставки (с 1 декабря 2026 для Carbon/Argon).
RATES_PERMANENT: dict[str, tuple[float, float, float]] = {
    "gemini-3.1-pro-preview": (2.00, 0.20, 12.00),
    "gemini-4-hydrogen": (1.50, 0.075, 7.50),
    "gemini-4-neon": (3.00, 0.15, 15.00),
    "gemini-4-carbon": (4.00, 0.20, 20.00),
    "gemini-4-argon": (4.00, 0.20, 20.00),
}

# Текущие ноябрьские ставки (до 30 ноября 2026 включительно).
RATES_NOV_2026: dict[str, tuple[float, float, float]] = {
    **RATES_PERMANENT,
    "gemini-4-carbon": (2.00, 0.10, 10.00),
    "gemini-4-argon": (2.00, 0.10, 10.00),
}


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model: str
    is_gemini4: bool
    thinking: str = ""
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    cache_friendly_prompt: bool = False


CONFIGS: tuple[ModelConfig, ...] = (
    ModelConfig(
        name="baseline-3.1-pro",
        model="gemini-3.1-pro-preview",
        is_gemini4=False,
        thinking="",
        temperature=BASELINE_TEMPERATURE,
        max_output_tokens=None,
        cache_friendly_prompt=False,
    ),
    ModelConfig(
        name="g4-hydrogen-medium",
        model="gemini-4-hydrogen",
        is_gemini4=True,
        thinking="medium",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
    ModelConfig(
        name="g4-hydrogen-high",
        model="gemini-4-hydrogen",
        is_gemini4=True,
        thinking="high",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
    ModelConfig(
        name="g4-neon-low",
        model="gemini-4-neon",
        is_gemini4=True,
        thinking="low",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
    ModelConfig(
        name="g4-neon-medium",
        model="gemini-4-neon",
        is_gemini4=True,
        thinking="medium",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
    ModelConfig(
        name="g4-neon-high",
        model="gemini-4-neon",
        is_gemini4=True,
        thinking="high",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
    ModelConfig(
        name="g4-carbon-medium",
        model="gemini-4-carbon",
        is_gemini4=True,
        thinking="medium",
        temperature=None,
        max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
        cache_friendly_prompt=True,
    ),
)


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def _calc_cost(
    model: str,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    *,
    rates_table: dict[str, tuple[float, float, float]],
) -> float:
    in_rate, cache_rate, out_rate = rates_table.get(model, (2.00, 0.20, 12.00))
    cached = min(max(0, cached_tokens), max(0, input_tokens))
    uncached = max(0, input_tokens - cached)
    billable_out = max(0, output_tokens) + max(0, thinking_tokens)
    return (
        uncached / 1_000_000 * in_rate
        + cached / 1_000_000 * cache_rate
        + billable_out / 1_000_000 * out_rate
    )


def build_cache_friendly_system_prompt_v2(
    language_code: str,
    *,
    stroke: Optional[str],
    strokes: Optional[list],
    drills_catalog: Optional[str],
) -> str:
    """То же содержимое, что _build_system_prompt_v2, но весь общий статический
    префикс вынесен в начало, чтобы Gemini 4 Implicit Caching срабатывал между
    всеми роликами и ударами."""
    import prompts
    from i18n import language_instruction
    from stroke_blocks import load_general_rules, load_stroke_blocks
    from wiki_context import build_knowledge_block

    parts = [
        prompts.SYSTEM_PROMPT_V2.strip(),
        language_instruction(language_code),
        load_general_rules(),
        load_stroke_blocks(),
    ]
    if drills_catalog:
        parts.append(
            "Available drills (pick 0–2 ids for the metadata JSON):\n" + drills_catalog
        )
    tag_line = prompts._issue_tag_line()
    if tag_line:
        parts.append(tag_line)
    prompts._append_forehand_checklist(parts)
    prompts._append_backhand_checklist(parts)
    prompts._append_slice_checklist(parts)
    prompts._append_serve_checklist(parts)

    # Переменная часть (зависит от выбранного удара) — строго в конце.
    knowledge_ctx = build_knowledge_block(
        stroke,
        language_code,
        strokes=strokes,
        chronic_tags=None,
        sanitize=True,
        omit_serve_page=True,
    )
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    return "\n\n".join(parts)


def _catalog() -> str:
    db = Path(__file__).resolve().parent / "data" / "rally.db"
    if not db.is_file():
        return ""
    import drills

    return drills.catalog_for_prompt()


def _wait_active(client, uploaded):
    deadline = time.monotonic() + 300
    current = uploaded
    while current.state and current.state.name != "ACTIVE":
        if time.monotonic() > deadline:
            raise TimeoutError("Gemini не успел принять файл.")
        if current.state.name == "FAILED":
            raise RuntimeError("Gemini не смог обработать файл.")
        time.sleep(2)
        current = client.files.get(name=current.name)
    return current


def _extract_cached_tokens(response) -> int:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0
    val = getattr(meta, "cached_content_token_count", None)
    if val is None and isinstance(meta, dict):
        val = meta.get("cached_content_token_count")
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _run_one(
    client,
    uploaded,
    cfg: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    drill_ids: list,
    duration: Optional[float],
) -> tuple[dict, int]:
    from google.genai import types

    from analysis_schema import to_sdk_schema
    from pricing import usage_from_response
    from structured_pipeline import run_structured

    part = types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)
    part.video_metadata = types.VideoMetadata(fps=STRUCTURED_VIDEO_FPS)
    part.media_resolution = types.PartMediaResolution(
        level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
    )

    config_kwargs: dict = {
        "system_instruction": system_prompt,
        "response_mime_type": "application/json",
        "response_schema": to_sdk_schema(schema),
        "media_resolution": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    }
    if cfg.temperature is not None:
        config_kwargs["temperature"] = cfg.temperature
    if cfg.max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = cfg.max_output_tokens
    if cfg.thinking:
        level = types.ThinkingLevel[cfg.thinking.upper()]
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=level)

    gen_config = types.GenerateContentConfig(**config_kwargs)
    cached_tokens_total = 0
    started = time.perf_counter()

    def generate():
        nonlocal cached_tokens_total
        last_exc: Optional[Exception] = None
        response = None
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=cfg.model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[part, types.Part.from_text(text=user_prompt)],
                        )
                    ],
                    config=gen_config,
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_TRANSIENT_RETRIES and _is_transient(exc):
                    wait = TRANSIENT_BACKOFF_SEC * (attempt + 1)
                    print(f"  transient error ({exc}), retry in {wait}s...", flush=True)
                    time.sleep(wait)
                    continue
                raise
        if response is None:
            raise last_exc or RuntimeError("Нет ответа от Gemini.")
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Модель вернула пустой ответ.")
        cached_tokens_total += _extract_cached_tokens(response)
        return text, usage_from_response(response, cfg.model)

    outcome = run_structured(
        generate,
        schema=schema,
        drill_ids=drill_ids,
        duration_sec=duration,
        downgrade_missing_evidence=True,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=cfg.model,
        player_id=None,
    )
    outcome["run_log"]["latency_sec"] = round(time.perf_counter() - started, 3)
    return outcome, cached_tokens_total


def _build_meta(
    outcome: dict,
    cached_tokens: int,
    cfg: ModelConfig,
    stroke: str,
    sdk: str,
    audio_stripped: bool,
    duration: Optional[float],
) -> dict:
    log = outcome["run_log"]
    tokens = dict(log.get("tokens") or {})
    in_tok = int(tokens.get("input") or 0)
    out_tok = int(tokens.get("output") or 0)
    think_tok = int(tokens.get("thinking") or 0)
    tokens["cached_input"] = cached_tokens
    cache_pct = round(cached_tokens / in_tok * 100, 1) if in_tok else 0.0

    cost_perm = round(
        _calc_cost(
            cfg.model, in_tok, cached_tokens, out_tok, think_tok,
            rates_table=RATES_PERMANENT,
        ),
        5,
    )
    cost_now = round(
        _calc_cost(
            cfg.model, in_tok, cached_tokens, out_tok, think_tok,
            rates_table=RATES_NOV_2026,
        ),
        5,
    )
    return {
        "config": cfg.name,
        "model": cfg.model,
        "is_gemini4": cfg.is_gemini4,
        "stroke": stroke,
        "duration_sec": round(duration, 2) if duration else None,
        "fps": STRUCTURED_VIDEO_FPS,
        "media_resolution": "high",
        "thinking": cfg.thinking or "default",
        "temperature": cfg.temperature,
        "max_output_tokens": cfg.max_output_tokens,
        "cache_friendly_prompt": cfg.cache_friendly_prompt,
        "sdk": sdk,
        "latency_sec": log.get("latency_sec"),
        "tokens": tokens,
        "cache_hit_pct": cache_pct,
        "cost_usd_dec": cost_perm,
        "cost_usd_now": cost_now,
        "retries": log.get("retries"),
        "checks": log.get("checks") or [],
        "phrase_incident": bool(log.get("phrase_incident")),
        "slug_leak": log.get("slug_leak") or [],
        "author_leak": log.get("author_leak") or [],
        "audio_stripped": audio_stripped,
    }


def _short(text: str, limit: int = 160) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def _format_scores(raw: dict) -> str:
    items = raw.get("scores") or []
    parts = []
    for item in items:
        if isinstance(item, dict) and item.get("value") is not None:
            parts.append(f"{item.get('axis')}={item.get('value')}")
    return ", ".join(parts) if parts else "—"


def generate_comparison_md(
    out_root: Path,
    videos: list[Path],
    configs: tuple[ModelConfig, ...],
) -> str:
    lines: list[str] = [
        "# A/B-тест Gemini 4 vs Gemini 3.1 Pro — `Genimi4Test`",
        "",
        f"Видео: {len(videos)} шт. | FPS: {STRUCTURED_VIDEO_FPS} | Resolution: HIGH | Звук: вырезан (как в проде)",
        "",
        "## 1. Сводная таблица по конфигам",
        "",
        "| Конфиг | Успешно | Средн. время | Сумм. время | Средн. in | Средн. cached (%) | Средн. out | Средн. think | Ретраи | Замечания checks | Итого $ (дек) | Средн. $/видео (дек) | Итого $ (ноя) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for cfg in configs:
        ok_metas = []
        errors = 0
        for v in videos:
            mpath = out_root / v.stem / cfg.name / "meta.json"
            epath = out_root / v.stem / cfg.name / "error.txt"
            if mpath.is_file():
                ok_metas.append(json.loads(mpath.read_text(encoding="utf-8")))
            elif epath.is_file():
                errors += 1
        n = len(ok_metas)
        if not n:
            lines.append(
                f"| `{cfg.name}` | 0/{len(videos)} (err {errors}) | — | — | — | — | — | — | — | — | — | — | — |"
            )
            continue
        sum_lat = sum(m.get("latency_sec") or 0 for m in ok_metas)
        avg_lat = sum_lat / n
        sum_in = sum((m.get("tokens") or {}).get("input") or 0 for m in ok_metas)
        sum_cached = sum((m.get("tokens") or {}).get("cached_input") or 0 for m in ok_metas)
        sum_out = sum((m.get("tokens") or {}).get("output") or 0 for m in ok_metas)
        sum_think = sum((m.get("tokens") or {}).get("thinking") or 0 for m in ok_metas)
        cache_pct = (sum_cached / sum_in * 100) if sum_in else 0.0
        retries = sum(m.get("retries") or 0 for m in ok_metas)
        checks_cnt = sum(len(m.get("checks") or []) for m in ok_metas)
        cost_dec = sum(m.get("cost_usd_dec") or 0 for m in ok_metas)
        cost_now = sum(m.get("cost_usd_now") or 0 for m in ok_metas)
        lines.append(
            f"| `{cfg.name}` | {n}/{len(videos)} | {avg_lat:.1f} с | {sum_lat:.1f} с | "
            f"{sum_in // n:,} | {sum_cached // n:,} ({cache_pct:.0f}%) | "
            f"{sum_out // n:,} | {sum_think // n:,} | {retries} | {checks_cnt} | "
            f"${cost_dec:.3f} | ${cost_dec / n:.4f} | ${cost_now:.3f} |"
        )

    lines.extend(["", "## 2. Детальное сравнение по каждому видео", ""])

    for v in videos:
        stroke = stroke_of(v)
        lines.append(f"### `{v.name}` (сегмент на входе: `{stroke}`)")
        lines.append("")
        lines.append(
            "| Конфиг | Время | in / cached (%) | out / think | $ (дек) | retries / checks | Видит модель (`primary` / `segments` / `reps` / `level`) |"
        )
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")

        per_cfg_raw: list[tuple[ModelConfig, Optional[dict], Optional[dict], Optional[str]]] = []
        for cfg in configs:
            d = out_root / v.stem / cfg.name
            mpath = d / "meta.json"
            rpath = d / "raw.json"
            epath = d / "error.txt"
            if mpath.is_file() and rpath.is_file():
                meta = json.loads(mpath.read_text(encoding="utf-8"))
                raw = json.loads(rpath.read_text(encoding="utf-8"))
                per_cfg_raw.append((cfg, meta, raw, None))
                tok = meta.get("tokens") or {}
                vid = raw.get("video") or {}
                seen = (
                    f"`{raw.get('primary_segment')}` / "
                    f"{raw.get('detected_segments')} / "
                    f"reps={vid.get('stroke_repetitions')} / "
                    f"{vid.get('level_estimate')}"
                )
                lines.append(
                    f"| `{cfg.name}` | {meta.get('latency_sec')} с | "
                    f"{tok.get('input', 0):,} / {tok.get('cached_input', 0):,} ({meta.get('cache_hit_pct', 0):.0f}%) | "
                    f"{tok.get('output', 0):,} / {tok.get('thinking', 0):,} | "
                    f"${meta.get('cost_usd_dec', 0):.4f} | "
                    f"{meta.get('retries', 0)} / {len(meta.get('checks') or [])} | {seen} |"
                )
            else:
                err = epath.read_text(encoding="utf-8").strip() if epath.is_file() else "нет данных"
                per_cfg_raw.append((cfg, None, None, err))
                lines.append(f"| `{cfg.name}` | ERR | — | — | — | — | {_short(err, 90)} |")

        lines.append("")
        for cfg, meta, raw, err in per_cfg_raw:
            if raw is None:
                lines.append(f"- **`{cfg.name}`**: ОШИБКА — `{_short(err or '', 200)}`")
                continue
            vid = raw.get("video") or {}
            checks = (meta or {}).get("checks") or []
            findings = raw.get("findings") or []
            f_strs = []
            for idx, f in enumerate(findings[:3], 1):
                if isinstance(f, dict):
                    ts = f.get("timecodes") or f.get("t") or ""
                    if isinstance(ts, list):
                        ts = ", ".join(str(x) for x in ts)
                    ts_part = f" [{ts}]" if ts else ""
                    f_strs.append(
                        f"#{idx} ({f.get('severity', '')}){ts_part}: {_short(f.get('problem') or '', 120)}"
                    )
            lines.append(f"- **`{cfg.name}`**:")
            lines.append(f"  - **Фокус:** {_short(raw.get('focus') or '', 220)}")
            lines.append(f"  - **Оценки:** {_format_scores(raw)} | **Теги:** `{raw.get('issue_tags')}` | **Дриллы:** `{raw.get('drills')}`")
            if vid.get("mismatch_with_player_choice"):
                lines.append(f"  - **Mismatch:** {_short(vid.get('mismatch_note') or '', 200)}")
            if f_strs:
                lines.append("  - **Findings:** " + " ; ".join(f_strs))
            if checks:
                lines.append(f"  - **Автопроверки (`checks`):** {checks}")
            if (meta or {}).get("phrase_incident") or (meta or {}).get("slug_leak") or (meta or {}).get("author_leak"):
                lines.append(
                    f"  - **Инциденты:** phrase={meta.get('phrase_incident')}, "
                    f"slug={meta.get('slug_leak')}, author={meta.get('author_leak')}"
                )
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="A/B-тест Gemini 4 vs Gemini 3.1 Pro")
    parser.add_argument("--dir", default="videos/Genimi4Test", help="Папка с видео")
    parser.add_argument("--out", default="eval_out/gemini4-test", help="Папка результатов")
    parser.add_argument("--only", default="", help="Ограничить именами роликов (stem через запятую)")
    parser.add_argument("--configs", default="", help="Ограничить именами конфигов (через запятую)")
    parser.add_argument("--yes", action="store_true", help="Реально вызвать Gemini API")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"Нет папки: {directory}")
        return 1

    videos = list_videos(directory)
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        by_stem = {p.stem: p for p in videos}
        missing = [x for x in wanted if x not in by_stem]
        if missing:
            print("Нет роликов: " + ", ".join(missing))
            return 1
        videos = [by_stem[x] for x in wanted]

    configs = CONFIGS
    if args.configs:
        wanted_c = [x.strip() for x in args.configs.split(",") if x.strip()]
        by_name = {c.name: c for c in CONFIGS}
        missing_c = [x for x in wanted_c if x not in by_name]
        if missing_c:
            print("Нет конфигов: " + ", ".join(missing_c))
            return 1
        configs = tuple(by_name[x] for x in wanted_c)

    print(
        f"Роликов: {len(videos)}. Конфигов: {len(configs)}. Всего вызовов: {len(videos) * len(configs)}."
    )
    for v in videos:
        print(f"  {v.name}  →  {stroke_of(v)}")
    print("Конфиги: " + ", ".join(c.name for c in configs))
    if not args.yes:
        print("Сухой просмотр. Добавьте --yes для запуска.")
        return 0

    import google.genai
    from google import genai
    from google.genai import types

    sdk = google.genai.__version__
    if "fps" not in getattr(types.VideoMetadata, "model_fields", {}):
        raise SystemExit(f"google-genai {sdk} не поддерживает VideoMetadata.fps")

    os.environ["STRUCTURED_ANALYSIS_V2"] = "1"
    from analysis_schema import build_response_schema, drill_ids_from_catalog
    from config import load_settings
    from prompts import build_analysis_prompt, build_system_prompt
    from structured_pipeline import video_duration_sec
    from video_mute import strip_audio_for_upload

    settings = load_settings()
    catalog = _catalog()
    drill_ids = drill_ids_from_catalog(catalog)
    schema = build_response_schema(drill_ids)
    use_v1beta = any("preview" in c.model for c in configs)
    http_opts = (
        types.HttpOptions(timeout=HTTP_TIMEOUT_MS, api_version="v1beta")
        if use_v1beta
        else types.HttpOptions(timeout=HTTP_TIMEOUT_MS)
    )
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=http_opts,
    )

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    # Проверяем, какие вызовы ещё не выполнены
    pending: set[tuple[str, str]] = set()
    for cfg in configs:
        for v in videos:
            d = out_root / v.stem / cfg.name
            if not ((d / "report.md").is_file() and (d / "meta.json").is_file()):
                pending.add((cfg.name, v.stem))

    needed_videos = {stem for _, stem in pending}
    uploaded_map: dict[str, tuple[object, Optional[Path], bool, Optional[float]]] = {}

    try:
        # 1. Однократно загружаем только те видео, которые нужны для невыполненных вызовов
        for v in videos:
            if v.stem not in needed_videos:
                continue
            print(f"[upload] {v.name}...", flush=True)
            upload_path, mute_tmp = strip_audio_for_upload(v)
            audio_stripped = mute_tmp is not None
            duration = video_duration_sec(v)
            uploaded = _wait_active(client, client.files.upload(file=str(upload_path)))
            uploaded_map[v.stem] = (uploaded, mute_tmp, audio_stripped, duration)
            print(f"[upload] {v.name} ACTIVE (dur={duration:.2f}s, muted={audio_stripped})", flush=True)

        # 2. Идём по конфигам (внутри — все 5 видео подряд для прогрева Implicit Cache!)
        for cfg in configs:
            print(f"\n================ {cfg.name} ({cfg.model}) ================", flush=True)
            for v in videos:
                dest = out_root / v.stem / cfg.name
                dest.mkdir(parents=True, exist_ok=True)
                if (cfg.name, v.stem) not in pending:
                    print(f"[skip] {v.name} / {cfg.name} (уже готов)", flush=True)
                    continue

                stroke = stroke_of(v)
                context = video_context_for(stroke)
                if cfg.cache_friendly_prompt:
                    system_prompt = build_cache_friendly_system_prompt_v2(
                        "ru",
                        stroke=None if stroke == "general" else stroke,
                        strokes=context["strokes"],
                        drills_catalog=catalog or None,
                    )
                else:
                    system_prompt = build_system_prompt(
                        "ru",
                        stroke=None if stroke == "general" else stroke,
                        strokes=context["strokes"],
                        drills_catalog=catalog or None,
                    )
                user_prompt = build_analysis_prompt("ru", video_context=context)
                uploaded, _, audio_stripped, duration = uploaded_map[v.stem]

                print(f"\n--- {v.name} ({stroke}) / {cfg.name} ---", flush=True)
                try:
                    outcome, cached_tokens = _run_one(
                        client,
                        uploaded,
                        cfg,
                        system_prompt,
                        user_prompt,
                        schema,
                        drill_ids,
                        duration,
                    )
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    print(f"ERROR: {message}", flush=True)
                    (dest / "error.txt").write_text(message + "\n", encoding="utf-8")
                    continue

                (dest / "report.md").write_text(outcome["text"], encoding="utf-8")
                (dest / "raw.json").write_text(
                    json.dumps(outcome["raw_json"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                meta = _build_meta(
                    outcome, cached_tokens, cfg, stroke, sdk, audio_stripped, duration
                )
                (dest / "meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tok = meta["tokens"]
                print(
                    f"OK: {meta['latency_sec']}s | in={tok['input']} (cached={tok['cached_input']}, {meta['cache_hit_pct']}%) | "
                    f"out={tok['output']} think={tok['thinking']} | "
                    f"dec=${meta['cost_usd_dec']:.4f} | retries={meta['retries']} checks={len(meta['checks'])}",
                    flush=True,
                )
    finally:
        for stem, (uploaded, mute_tmp, _, _) in uploaded_map.items():
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                print(f"[cleanup] Не удалось удалить в Gemini: {stem}", flush=True)
            if mute_tmp is not None:
                mute_tmp.unlink(missing_ok=True)

    # 3. Собираем summary.json и comparison.md из всех готовых результатов
    summary = []
    for cfg in configs:
        for v in videos:
            d = out_root / v.stem / cfg.name
            mpath = d / "meta.json"
            epath = d / "error.txt"
            if mpath.is_file():
                meta = json.loads(mpath.read_text(encoding="utf-8"))
                summary.append({"file": v.name, **meta})
            elif epath.is_file():
                summary.append(
                    {
                        "file": v.name,
                        "config": cfg.name,
                        "error": epath.read_text(encoding="utf-8").strip(),
                    }
                )
    (out_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    comp_md = generate_comparison_md(out_root, videos, configs)
    (out_root / "comparison.md").write_text(comp_md, encoding="utf-8")
    print(f"\nГотово! Результаты: {out_root / 'comparison.md'}", flush=True)
    return 0 if all("error" not in row for row in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
