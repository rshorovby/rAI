"""Лабораторный прогон роликов с разной частотой кадров.

Тот же промпт и та же схема, что боевой structured-разбор. В базу не пишет.
Нужен интерпретатор, у которого в google-genai у VideoMetadata есть поле fps
(проверено на 1.47.0). Боевое окружение 1.10.0 для этого скрипта не подходит.

Без --yes только печатает план.

    /tmp/genai-fps-venv/bin/python eval_fps_lab.py --dir videos/fps-lab
    /tmp/genai-fps-venv/bin/python eval_fps_lab.py --dir videos/fps-lab --yes

Имя файла задаёт удар: первое слово до «__» или «_», если это известный сегмент.
Иначе разбор общий.
    serve__двор.mp4, backhand_nik.mov, просто.mp4
Допустимые префиксы: forehand, backhand, serve, volley, footwork, rally, general.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}
STROKES = ("forehand", "backhand", "serve", "volley", "footwork", "rally", "general")


@dataclass(frozen=True)
class Variant:
    name: str
    fps: float
    high_resolution: bool = False
    thinking: str = ""
    prompt: str = ""
    temperature: float = 0.0


DEFAULT_VARIANTS = (
    Variant("fps1", 1),
    Variant("fps4", 4),
    Variant("fps8", 8),
)
HIGH_VARIANT = Variant("fps8-high", 8, high_resolution=True)


_STROKE_ALIASES = {"forhand": "forehand"}


def stroke_of(path: Path) -> str:
    stem = path.stem.lower()
    for separator in ("__", "_"):
        prefix = stem.split(separator, 1)[0]
        mapped = _STROKE_ALIASES.get(prefix, prefix)
        if mapped in STROKES:
            return mapped
    return "general"


def video_context_for(stroke: str) -> dict:
    if stroke == "general":
        return {"stroke": "general", "strokes": []}
    return {"stroke": stroke, "strokes": [stroke]}


def list_videos(directory: Path) -> list:
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.name.lower())


def variants_for(high: bool) -> tuple:
    if high:
        return DEFAULT_VARIANTS + (HIGH_VARIANT,)
    return DEFAULT_VARIANTS


def natali_matrix() -> tuple:
    """fps 4 и 8 × разрешение кадра × thinking low/high. Имена не затирают fps1/8/16."""
    found = []
    for fps in (4, 8):
        for high in (False, True):
            for level in ("low", "high"):
                res = "high" if high else "default"
                found.append(
                    Variant(
                        f"fps{fps}-res-{res}-think-{level}",
                        fps,
                        high_resolution=high,
                        thinking=level,
                    )
                )
    return tuple(found)


def prompt_matrix() -> tuple:
    """Старый и новый промпт при fps 1/4/8, высоком разрешении и thinking high."""
    found = []
    for fps in (1, 4, 8):
        for prompt in ("old", "new"):
            found.append(
                Variant(
                    f"{prompt}-fps{fps}-res-high-think-high",
                    fps,
                    high_resolution=True,
                    thinking="high",
                    prompt=prompt,
                )
            )
    return tuple(found)


def temperature_matrix() -> tuple:
    """Новый промпт, fps 8, температура 0.3 и 1. Имена не затирают папку fps8."""
    return (
        Variant("fps8-temp-0.3", 8, temperature=0.3),
        Variant("fps8-temp-1", 8, temperature=1.0),
    )


def variants_from_fps(raw: str) -> tuple:
    found = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        value = float(text)
        if not 0 < value <= 24:
            raise SystemExit(f"fps вне диапазона (0, 24]: {text}")
        label = str(int(value)) if value == int(value) else str(value)
        found.append(Variant(f"fps{label}", value))
    if not found:
        raise SystemExit("Пустой список --fps")
    return tuple(found)


def _require_fps_sdk():
    import google.genai
    from google.genai import types

    fields = getattr(types.VideoMetadata, "model_fields", {})
    if "fps" not in fields:
        raise SystemExit(
            "У этого google-genai нет VideoMetadata.fps. "
            "Запускайте скрипт интерпретатором с пакетом 1.47 или новее, "
            "не боевым .venv (там 1.10.0)."
        )
    return google.genai.__version__


def _catalog() -> str:
    db = Path(__file__).resolve().parent / "data" / "rally.db"
    if not db.is_file():
        return ""
    import drills

    return drills.catalog_for_prompt()


def _run_one(client, uploaded, variant, system_prompt, user_prompt, schema, drill_ids, duration, model):
    from google.genai import types

    from analysis_schema import to_sdk_schema
    from config import analysis_temperature
    from pricing import usage_from_response
    from structured_pipeline import run_structured

    part = types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)
    part.video_metadata = types.VideoMetadata(fps=variant.fps)
    if variant.high_resolution:
        part.media_resolution = types.PartMediaResolution(
            level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
        )
    legacy = variant.prompt == "old"
    if variant.temperature:
        temperature = variant.temperature
    elif legacy:
        temperature = 0.4
    else:
        temperature = analysis_temperature()
    config_kwargs = {
        "system_instruction": system_prompt,
        "temperature": temperature,
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
    }
    if not legacy:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = to_sdk_schema(schema)
    config = types.GenerateContentConfig(**config_kwargs)
    if variant.high_resolution:
        config.media_resolution = types.MediaResolution.MEDIA_RESOLUTION_HIGH
    if variant.thinking:
        level = types.ThinkingLevel[variant.thinking.upper()]
        config.thinking_config = types.ThinkingConfig(thinking_level=level)

    started = time.perf_counter()

    def generate():
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[part, types.Part.from_text(text=user_prompt)],
                )
            ],
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Модель вернула пустой ответ.")
        return text, usage_from_response(response, model)

    if legacy:
        text, usage = generate()
        from pricing import estimate_cost

        return {
            "text": text,
            "raw_json": None,
            "run_log": {
                "model": model,
                "latency_sec": round(time.perf_counter() - started, 3),
                "tokens": {
                    "input": usage.input_tokens,
                    "output": usage.output_tokens,
                    "thinking": usage.thinking_tokens,
                },
                "cost_usd": estimate_cost(
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.thinking_tokens,
                    model,
                ),
                "retries": 0,
                "checks": [],
                "phrase_incident": False,
            },
        }

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
    outcome["run_log"]["latency_sec"] = round(time.perf_counter() - started, 3)
    return outcome


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


def _meta(outcome, variant, stroke, sdk, audio_stripped) -> dict:
    log = outcome["run_log"]
    return {
        "stroke": stroke,
        "config": variant.name,
        "fps": variant.fps,
        "media_resolution": "high" if variant.high_resolution else "default",
        "thinking": variant.thinking or "default",
        "prompt": variant.prompt or "new",
        "temperature": variant.temperature or None,
        "sdk": sdk,
        "model": log.get("model"),
        "latency_sec": log.get("latency_sec"),
        "tokens": log.get("tokens"),
        "cost_usd": log.get("cost_usd"),
        "retries": log.get("retries"),
        "checks": log.get("checks"),
        "phrase_incident": log.get("phrase_incident"),
        "audio_stripped": audio_stripped,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Прогон роликов с разным fps")
    parser.add_argument("--dir", required=True, help="Папка с роликами")
    parser.add_argument("--out", default="eval_out/fps-lab")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--high", action="store_true", help="Добавить вариант fps8 и high resolution")
    parser.add_argument("--fps", default="", help="Список частот через запятую, например 1,8,16")
    parser.add_argument(
        "--matrix",
        default="",
        help="natali, resolution, prompt или temp (новый промпт, fps 8, температура 0.3 и 1)",
    )
    parser.add_argument("--only", default="", help="Только ролик с этим именем, без расширения")
    parser.add_argument("--yes", action="store_true", help="Реально вызвать Gemini")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"Нет папки: {directory}")
        return 1
    if args.repeats < 1:
        print("--repeats должен быть больше нуля")
        return 1

    videos = list_videos(directory)
    if args.matrix in ("prompt", "temp") and not args.only:
        print(f"Для --matrix {args.matrix} укажите --only: иначе прогон пойдёт по всей папке.")
        return 1
    if args.matrix == "prompt":
        plan = prompt_matrix()
    elif args.matrix == "temp":
        plan = temperature_matrix()
    elif args.matrix in ("natali", "resolution"):
        plan = natali_matrix()
    elif args.fps:
        plan = variants_from_fps(args.fps)
    else:
        plan = variants_for(args.high)
    if args.only:
        order = [part.strip() for part in args.only.split(",") if part.strip()]
        by_stem = {path.stem: path for path in videos}
        missing = [name for name in order if name not in by_stem]
        if missing:
            print("Нет ролика: " + ", ".join(missing))
            return 1
        videos = [by_stem[name] for name in order]
    elif args.matrix == "natali":
        videos = [path for path in videos if path.stem == "serve_natali"]
    calls = len(videos) * len(plan) * args.repeats
    print(f"Роликов: {len(videos)}. Вариантов: {len(plan)}. Повторов: {args.repeats}. Вызовов: {calls}.")
    if not videos:
        print("Положите в папку mp4, mov или webm. Удар — префикс имени, например serve_rus.mov.")
        return 1
    for path in videos:
        print(f"  {path.name}  →  {stroke_of(path)}")
    print("Варианты: " + ", ".join(item.name for item in plan))
    if not args.yes:
        print("Сухой просмотр. Деньги не списываются. Для прогона добавьте --yes.")
        return 0

    sdk = _require_fps_sdk()
    os.environ["STRUCTURED_ANALYSIS_V2"] = "1"

    from google import genai
    from google.genai import types

    from analysis_schema import build_response_schema, drill_ids_from_catalog
    from config import load_settings
    from prompts import build_analysis_prompt, build_system_prompt
    from structured_pipeline import video_duration_sec
    from video_mute import strip_audio_for_upload

    settings = load_settings()
    model = settings.gemini_model
    catalog = _catalog()
    drill_ids = drill_ids_from_catalog(catalog)
    schema = build_response_schema(drill_ids)
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=300_000),
    )
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    summary = []

    for path in videos:
        stroke = stroke_of(path)
        context = video_context_for(stroke)
        def prompts_for(variant):
            if variant.prompt == "old":
                os.environ.pop("STRUCTURED_ANALYSIS_V2", None)
            else:
                os.environ["STRUCTURED_ANALYSIS_V2"] = "1"
            system_prompt = build_system_prompt(
                "ru",
                stroke=None if stroke == "general" else stroke,
                strokes=context["strokes"],
                drills_catalog=catalog or None,
            )
            user_prompt = build_analysis_prompt("ru", video_context=context)
            os.environ["STRUCTURED_ANALYSIS_V2"] = "1"
            return system_prompt, user_prompt

        upload_path, mute_tmp = strip_audio_for_upload(path)
        audio_stripped = mute_tmp is not None
        duration = video_duration_sec(path)
        uploaded = None
        try:
            uploaded = _wait_active(client, client.files.upload(file=str(upload_path)))
            for variant in plan:
                for repeat in range(1, args.repeats + 1):
                    label = variant.name if args.repeats == 1 else f"{variant.name}-r{repeat}"
                    dest = out_root / path.stem / label
                    dest.mkdir(parents=True, exist_ok=True)
                    if (dest / "report.md").is_file():
                        print(f"пропуск {label}: отчёт уже есть", flush=True)
                        continue
                    print(f"\n=== {path.name} / {label} ===", flush=True)
                    system_prompt, user_prompt = prompts_for(variant)
                    try:
                        outcome = _run_one(
                            client,
                            uploaded,
                            variant,
                            system_prompt,
                            user_prompt,
                            schema,
                            drill_ids,
                            duration,
                            model,
                        )
                    except Exception as exc:
                        message = f"{type(exc).__name__}: {exc}"
                        print(message, flush=True)
                        (dest / "error.txt").write_text(message + "\n", encoding="utf-8")
                        summary.append({"file": path.name, "config": label, "error": message})
                        continue
                    (dest / "report.md").write_text(outcome["text"], encoding="utf-8")
                    (dest / "raw.json").write_text(
                        json.dumps(outcome["raw_json"], ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    meta = _meta(outcome, variant, stroke, sdk, audio_stripped)
                    meta["repeat"] = repeat
                    (dest / "meta.json").write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    summary.append({"file": path.name, **meta})
                    tokens = meta["tokens"] or {}
                    print(
                        f"{label}: {meta['latency_sec']} с, "
                        f"in {tokens.get('input')} out {tokens.get('output')} "
                        f"think {tokens.get('thinking')}, ${meta['cost_usd']}",
                        flush=True,
                    )
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    print(f"Не удалось удалить файл в Gemini: {path.name}", flush=True)
            if mute_tmp is not None:
                mute_tmp.unlink(missing_ok=True)

    (out_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nГотово: {out_root}")
    return 0 if all("error" not in row for row in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
