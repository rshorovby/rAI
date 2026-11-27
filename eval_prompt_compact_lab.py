"""A/B-тест компактного персонализированного промпта (~3.5-4.5K токенов)
против полного боевого промпта (~16.3K токенов) на gemini-4-neon (thinking_level=low).

Изолированный лабораторный скрипт: боевые prompts.py / analyzer.py не трогает.
Сравнивает:
- serve_rus.mov (профиль: левша, продвинутый любитель)
- forehand_maks.mov (профиль: правша, любитель)

Запуск:
    /tmp/genai-g4-venv/bin/python eval_prompt_compact_lab.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from eval_gemini4_lab import (
    GEMINI4_MAX_OUTPUT_TOKENS,
    HTTP_TIMEOUT_MS,
    RATES_PERMANENT,
    STRUCTURED_VIDEO_FPS,
    _calc_cost,
    _extract_cached_tokens,
    _wait_active,
)

os.environ["STRUCTURED_ANALYSIS_V2"] = "1"

# Реальные профили игроков с тестовых роликов
TEST_CASES = (
    {
        "file": Path("videos/fps-lab/serve_rus.mov"),
        "stroke": "serve",
        "profile": {
            "level": "advanced",
            "hand": "left",
            "backhand": "two_handed",
            "frequency": "2-3",
            "injuries": "",
        },
    },
    {
        "file": Path("videos/fps-lab/forehand_maks.mov"),
        "stroke": "forehand",
        "profile": {
            "level": "intermediate",
            "hand": "right",
            "backhand": "two_handed",
            "frequency": "1-2",
            "injuries": "",
        },
    },
)

LEVEL_TONE_RULES = {
    "beginner": (
        "Подача текста (Начинающий): 1 главный пункт и 1 сильная сторона. "
        "Простые слова, каждый термин объясняй один раз. Без биомеханики. Одно лёгкое упражнение."
    ),
    "intermediate": (
        "Подача текста (Любитель): до 2 пунктов в findings. "
        "Термины можно, кратко. Упражнение с понятной целью на корзину."
    ),
    "advanced": (
        "Подача текста (Продвинутый): до 3 пунктов в findings. "
        "Точные термины без объяснения базы. Допустимы тонкости: тайминг, пронация, глубина падения ракетки, работа опорной руки."
    ),
    "pro": (
        "Подача текста (Pro): до 3 пунктов в findings, точные термины без объяснения базы."
    ),
}

LEVEL_LABELS = {
    "beginner": "Начинающий",
    "intermediate": "Любитель",
    "advanced": "Продвинутый",
    "pro": "Pro",
}

STROKE_ISSUE_TAGS = {
    "serve": (
        "toss-placement",
        "toss-height",
        "trophy-position",
        "knee-bend-drive",
        "contact-height",
        "arm-deceleration",
        "serve-finish-balance",
    ),
    "forehand": (
        "unit-turn",
        "hip-rotation",
        "shoulder-rotation",
        "ground-force",
        "weight-transfer",
        "contact-point",
        "contact-in-front",
        "late-contact",
        "spacing-to-ball",
        "racquet-path",
        "gradual-acceleration",
        "topspin-roll",
        "still-head",
        "grip",
        "no-split-step",
        "small-adjustment-steps",
        "footwork",
        "balance",
        "recovery-position",
    ),
}


def filter_drills_for_stroke(catalog: str, stroke: str) -> str:
    """Оставляет только релевантные выбранному удару и базовые общие дриллы."""
    include_by_stroke = {
        "serve": {"serve", "toss", "balance"},
        "forehand": {"forehand", "contact", "footwork", "balance", "timing", "unit-turn", "weight-transfer", "stance", "preparation", "recovery", "wrist"},
    }
    exclude_by_stroke = {
        "serve": {"forehand", "backhand", "volley", "slice", "1hbh", "2hbh", "return", "rally"},
        "forehand": {"serve", "backhand", "volley", "slice", "1hbh", "2hbh", "return", "transition"},
    }
    inc = include_by_stroke.get(stroke, set())
    exc = exclude_by_stroke.get(stroke, set())
    kept = []
    for line in (catalog or "").splitlines():
        if "[" not in line or "]" not in line:
            continue
        raw_tags = line.rsplit("[", 1)[1].rstrip("]")
        tags = {t.strip().lower() for t in raw_tags.split(",")}
        if tags & exc:
            continue
        if tags & inc:
            kept.append(line)
    return "\n".join(kept)


def _serve_standard_ru(hand: str) -> str:
    if hand == "left":
        hand_note = (
            "Игрок — ЛЕВША: ракетка в левой руке, подброс правой рукой, "
            "приземление в корт на правую ногу, проводка уходит в правую сторону корпуса. "
            "Все стороны в разборе называй строго для левши."
        )
        hit_arm, toss_arm, hit_sh, toss_sh, finish_side = (
            "левая", "правая", "левое плечо", "правое плечо", "справа от корпуса"
        )
    else:
        hand_note = (
            "Игрок — ПРАВША: ракетка в правой руке, подброс левой рукой, "
            "приземление в корт на левую ногу, проводка уходит в левую сторону корпуса."
        )
        hit_arm, toss_arm, hit_sh, toss_sh, finish_side = (
            "правая", "левая", "правое плечо", "левое плечо", "слева от корпуса"
        )

    return f"""\
## СТАНДАРТ РАЗБОРА: ПОДАЧА
{hand_note}

### Жёсткие запреты и ракурсы
- Хватку и ориентацию ракетки (включая «поднос официанта» / waiter's tray) НЕ комментируй: на коротком видео они ненадёжны.
- Пронацию, кисть в контакте и вращение мяча оценивай только если явно видны; иначе молчи.
- Не называй подачу первой или второй, если игрок сам это не указал.
- **Сбоку:** видны вынос подброса вперёд/назад, высота, сгиб коленей, высота контакта, вход в корт. Не виден уход подброса влево/вправо.
- **Сзади / сзади-сбоку:** видны уход подброса влево/вправо, траектория ракетки, баланс приземления. Вынос подброса вперёд и глубину контакта ставь `insufficient`.
- **Одна подача в кадре:** не оценивай стабильность/повторяемость подброса; опиши, где мяч в этой попытке. В `next_video` попроси 4–5 подач подряд с нужного ракурса.

### Принципы школы
- Ускорение нарастает постепенно к контакту; не советуй «жёсткую кисть» и «рывок» как норму.
- Сила идёт по цепи: ноги → таз → корпус → плечо → локоть → предплечье → кисть.

### Внутренний чеклист фаз (пройди мысленно, не печатай списком; в отчёт только подтверждённые видео отклонения по [BASE] и явные ошибки по [STYLE]; невидимые пункты молча пропускай)
1. Стойка [STYLE]: боком к сетке; отмечай только если мешает развороту.
2. Стартовый ритм [BASE]: плавный старт рук и ног без рывков и остановок.
3. Подброс — рука [BASE]: {toss_arm} рука выпрямляется плавно, отпускание на уровне глаз или чуть выше, без кистевого броска.
4. Высота и траектория подброса [BASE]: чуть выше максимального вытяжения ракетки; слишком низкий (спешка) или слишком высокий (пауза ожидания, рвёт ритм) — ошибка.
5. Положение подброса [BASE]: без указания типа подачи просто опиши, где мяч относительно плеч/головы; явная ошибка — далеко за спиной или сильный завал за мячом.
6. Свободная рука после подброса [BASE]: {toss_arm} рука остаётся наверху до начала разгона, затем собирается к корпусу; ранний сброс — ошибка.
7. Сгиб коленей [BASE]: выраженная загрузка ног без складывания корпуса; прямые ноги — ошибка.
8. Положение «трофея» [BASE]: {hit_sh} ниже, чем {toss_sh} (наклон плеч!), бьющий локоть согнут примерно на уровне плеча, головка ракетки вверх, взгляд на мяче. Прямая поднятая рука, горизонтальные плечи или провал локтя — ошибка.
9. Скрутка корпуса [BASE]: плечи и бёдра скручены как пружина; подача одной рукой — ошибка.
10. Толчок ногами [BASE]: активное разгибание вверх-вперёд; отсутствие толчка или рассинхрон с рукой — ошибка.
11. Сброс ракетки за спину [BASE]: расслабленная кисть, локоть высоко; короткий/отсутствующий сброс («толкание») — ошибка.
12. Контакт [BASE]: максимальная высота на почти прямой {hit_arm} руке; низкий контакт с согнутым локтем — ошибка.
13. Ось корпуса на контакте [BASE]: тело вытянуто в линию, голова стабильна; сильный боковой завал или раннее падение головы — ошибка.
14. Проводка [STYLE]: свободный уход вниз-вперёд и {finish_side}; обрыв проводки — ошибка.
15. Приземление и возврат [BASE]: мягкое приземление на переднюю ногу в корт с балансом и быстрым выходом в готовность.

### Оси оценок
`toss`, `preparation` (загрузка, трофей), `leg_drive`, `contact`, `follow_through`. Ось `footwork` для подачи НЕ ставь. Невидимые оси = `null`."""


def _forehand_standard_ru(hand: str) -> str:
    if hand == "left":
        hand_note = "Игрок — ЛЕВША (бьющая рука — левая, свободная — правая)."
        hit_arm, free_arm, opp_sh = "левая", "правая", "правому плечу"
    else:
        hand_note = "Игрок — ПРАВША (бьющая рука — правая, свободная — левая)."
        hit_arm, free_arm, opp_sh = "правая", "левая", "левому плечу"

    return f"""\
## СТАНДАРТ РАЗБОРА: ФОРХЕНД
{hand_note}

### Принципы школы и ракурсы
- Ускорение нарастает постепенно: кисть расслаблена в замахе и собирается к контакту. Не советуй «рывок кистью» и постоянную жёсткость кисти.
- Стойки: открытая, полуоткрытая и закрытая допустимы, если есть баланс и работа ног. Не пиши «открытая стойка только для защиты».
- Рабочий хват (Eastern / Semi-Western) не ломай без причины; хват оценивай только если он явно различим.
- **Сбоку:** видны глубина контакта перед корпусом, дистанция, перенос веса, проводка, баланс, стабильность головы. Хуже виден разворот плеч.
- **Спереди / сзади:** видны разворот плеч и таза, дистанция сбоку, работа ног, траектория и завершение проводки. Глубину контакта вперёд от корпуса оценивай осторожно (`likely`/`insufficient`).
- Сплит-степ оценивай только если виден момент удара соперника/наброса (иначе пропускай или помечай как гипотезу). По одному удару стабильность не оценивай.

### Внутренний чеклист фаз (пройди мысленно, не печатай списком; в отчёт только подтверждённые видео отклонения по [BASE] и явные ошибки по [STYLE]; невидимые пункты молча пропускай)
1. Готовая позиция [BASE]: стопы шире плеч, колени согнуты, вес на передней части стопы, ракетка перед корпусом.
2. Подход к мячу [BASE]: мелкие подстроечные шаги, комфортная дистанция до мяча; опоздание, «прилипание» к мячу или один длинный выпад — ошибка.
3. Разворот корпуса (unit turn) [BASE]: плечи и таз разворачиваются вместе до отскока мяча, {free_arm} рука сопровождает ракетку и указывает к мячу. Отвод одной {hit_arm} рукой при фронтальной груди — критическая ошибка.
4. Замах [STYLE]: петля или прямой замах допустимы; ошибка — чрезмерно длинный или поздний замах.
5. Загрузка ног [BASE]: когда есть время — сгиб коленей, опора и скрутка корпуса (на быстром мяче короткая подготовка допустима).
6. Старт вперёд и цепь [BASE]: опускание ракетки под мяч и последовательный разгон (ноги → таз → корпус → плечо → предплечье). Старт рукой раньше корпуса — ошибка.
7. Контакт [BASE]: перед корпусом на комфортной дистанции сбоку, рука почти выпрямлена (не зажата у бедра), голова стабильна, взгляд на мяче.
8. Проводка [STYLE]: свободное движение ракетки вперёд и вверх к {opp_sh}, разворот корпуса к сетке. Обрыв проводки у груди или слишком низкое завершение — ошибка.
9. Баланс и возврат [BASE]: устойчивая опора (в т.ч. стопорящий шаг внешней ногой на широком мяче) без завала по инерции и быстрый возврат в позицию.

### Оси оценок
`preparation`, `leg_drive`, `contact`, `follow_through`, `footwork`, `balance`. Только то, что видно, остальное `null`."""


def build_compact_system_prompt(
    *,
    stroke: str,
    profile: dict,
    drills_catalog: str,
) -> str:
    hand = profile.get("hand") or "right"
    level = profile.get("level") or "intermediate"
    injuries = (profile.get("injuries") or "").strip()

    parts = [
        """\
Ты AI-ассистент по технике тенниса. Главный — штатный тренер-человек; ты готовишь технический черновик, который тренер проверит или отредактирует. Никогда не пиши от лица тренера («как твой тренер», «на моей тренировке»). Пиши по-русски, конкретно и без воды.""",
    ]

    # Профиль игрока (компактный, без лишних правил)
    prof_lines = [
        "## ПРОФИЛЬ ИГРОКА",
        f"- Уровень: {LEVEL_LABELS.get(level, level)}",
        f"- Ведущая рука: {'левша' if hand == 'left' else 'правша'}",
    ]
    if profile.get("frequency"):
        prof_lines.append(f"- Частота игры: {profile['frequency']} раз/нед")
    if injuries:
        prof_lines.append(
            f"- ⚠️ ТРАВМЫ/ОГРАНИЧЕНИЯ: {injuries}. ПРИОРИТЕТ №1: проверь безопасность движения и НЕ давай упражнения, которые могут усугубить эту травму!"
        )
    prof_lines.append(LEVEL_TONE_RULES.get(level, LEVEL_TONE_RULES["intermediate"]))
    prof_lines.append(
        "Если видео явно противоречит профилю (например, рука или уровень) — доверяй видео и тактично отметь расхождение."
    )
    parts.append("\n".join(prof_lines))

    # Общие правила (сжатые, без дублей)
    parts.append(
        """\
## ОБЩИЕ ПРАВИЛА
- Сначала опиши фазы движения по факту (`observations`), потом делай выводы.
- Таймкоды строго `mm:ss.mmm` с шагом 0.125 с (видео 8 fps, например `00:03.625`). В `remarks.t` указывай окно `mm:ss.mmm-mm:ss.mmm` (1–4 с), чтобы в замедленный фрагмент попали и причина, и результат.
- Каждое замечание помечай: `seen` (видно прямо), `likely` (вероятная гипотеза), `insufficient` (с этого ракурса не оценить — без суждения).
- `findings`: от 1 до 3 самых влиятельных видимых проблем (если видна одна — пиши одну, не выдумывай). Сильную сторону называй конкретно.
- Абсолютная шкала оценок 0–10: 2–3 базовые ошибки; 4–5 рабочий удар с системной ошибкой; 6–7 уверенный сильный любитель с точечными недочётами; 8–9 почти без ошибок; 10 уровень профи. Невидимые оси = `null`.
- Проверка выбора игрока: игрок указал удар ниже. Сначала проверь по кадрам, что на видео именно он. Если явно другой удар — поставь `mismatch_with_player_choice: true` и разбери фактический удар. Если тенниса нет — `visible_content: "not_tennis"`, `primary_segment: "none"`, пустые массивы, вежливое объяснение в `summary`.
- В тексте для игрока запрещены английские служебные слаги, названия источников/авторов и внутренние метки."""
    )

    # Стандарт ТОЛЬКО выбранного удара
    if stroke == "serve":
        parts.append(_serve_standard_ru(hand))
    elif stroke == "forehand":
        parts.append(_forehand_standard_ru(hand))
    else:
        raise ValueError(f"Unsupported stroke in pilot: {stroke}")

    # Фильтрованные дриллы и теги
    filtered_drills = filter_drills_for_stroke(drills_catalog, stroke)
    parts.append(
        "## ДОСТУПНЫЕ УПРАЖНЕНИЯ (выбери 0–2 id для поля drills)\n" + filtered_drills
    )
    tags = STROKE_ISSUE_TAGS.get(stroke, ())
    parts.append(
        "## ТЕГИ ПРОБЛЕМ (выбери 0–3 slug, видимых на видео)\n" + ", ".join(tags)
    )

    return "\n\n".join(parts)


def main() -> int:
    from google import genai
    from google.genai import types

    import drills
    from analysis_schema import build_response_schema, drill_ids_from_catalog, to_sdk_schema
    from config import load_settings
    from eval_fps_lab import video_context_for
    from pricing import usage_from_response
    from prompts import build_analysis_prompt
    from structured_pipeline import run_structured, video_duration_sec
    from video_mute import strip_audio_for_upload

    settings = load_settings()
    catalog = drills.catalog_for_prompt()
    drill_ids = drill_ids_from_catalog(catalog)
    schema = build_response_schema(drill_ids)
    sdk_schema = to_sdk_schema(schema)

    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=HTTP_TIMEOUT_MS),
    )

    out_root = Path("eval_out/gemini4-compact-ab")
    out_root.mkdir(parents=True, exist_ok=True)
    model = "gemini-4-neon"

    for case in TEST_CASES:
        video_path: Path = case["file"]
        stroke: str = case["stroke"]
        profile: dict = case["profile"]
        context = video_context_for(stroke)

        system_prompt = build_compact_system_prompt(
            stroke=stroke,
            profile=profile,
            drills_catalog=catalog,
        )
        user_prompt = build_analysis_prompt("ru", video_context=context)

        print(
            f"\n=== {video_path.name} ({stroke}) | compact prompt={len(system_prompt)} chars ===",
            flush=True,
        )

        upload_path, mute_tmp = strip_audio_for_upload(video_path)
        duration = video_duration_sec(video_path)
        uploaded = None
        try:
            uploaded = _wait_active(client, client.files.upload(file=str(upload_path)))
            part = types.Part.from_uri(
                file_uri=uploaded.uri, mime_type=uploaded.mime_type
            )
            part.video_metadata = types.VideoMetadata(fps=STRUCTURED_VIDEO_FPS)
            part.media_resolution = types.PartMediaResolution(
                level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
            )
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=sdk_schema,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
                max_output_tokens=GEMINI4_MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.LOW
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            )
            cached_total = 0
            started = time.perf_counter()

            def generate():
                nonlocal cached_total
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[part, types.Part.from_text(text=user_prompt)],
                        )
                    ],
                    config=gen_config,
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("Пустой ответ.")
                cached_total += _extract_cached_tokens(response)
                return text, usage_from_response(response, model)

            outcome = run_structured(
                generate,
                schema=schema,
                drill_ids=drill_ids,
                duration_sec=duration,
                downgrade_missing_evidence=True,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                player_id=None,
            )
            latency = round(time.perf_counter() - started, 3)
            tok = dict(outcome["run_log"]["tokens"])
            tok["cached_input"] = cached_total
            cost = round(
                _calc_cost(
                    model,
                    tok["input"],
                    cached_total,
                    tok["output"],
                    tok["thinking"],
                    rates_table=RATES_PERMANENT,
                ),
                5,
            )

            dest = out_root / video_path.stem / "g4-neon-low-compact"
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "report.md").write_text(outcome["text"], encoding="utf-8")
            (dest / "raw.json").write_text(
                json.dumps(outcome["raw_json"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (dest / "system_prompt.txt").write_text(system_prompt, encoding="utf-8")
            meta = {
                "config": "g4-neon-low-compact",
                "model": model,
                "stroke": stroke,
                "profile": profile,
                "prompt_chars": len(system_prompt),
                "duration_sec": round(duration, 2) if duration else None,
                "latency_sec": latency,
                "tokens": tok,
                "cost_usd": cost,
                "retries": outcome["run_log"]["retries"],
                "checks": outcome["run_log"]["checks"],
            }
            (dest / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"OK: {latency}s | in={tok['input']} (cached={cached_total}) | "
                f"out={tok['output']} think={tok['thinking']} | ${cost:.4f} | "
                f"retries={meta['retries']} checks={len(meta['checks'])}",
                flush=True,
            )
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass
            if mute_tmp is not None:
                mute_tmp.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
