"""Три прогона одного ролика: старый промпт, новый, новый без wiki.

Не пишет в базу. Живые вызовы только с --yes.

    .venv/bin/python eval_scheme_compare.py --video videos/serve_2.mov --stroke serve --yes
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import prompts
import wiki_context
from analyzer import VideoAnalyzer
from config import load_settings
from pricing import estimate_cost


def _run_one(analyzer, video, stroke, flag, omit_wiki):
    if flag:
        os.environ["STRUCTURED_ANALYSIS_V2"] = "1"
    else:
        os.environ.pop("STRUCTURED_ANALYSIS_V2", None)
    started = time.time()

    def call():
        system = prompts.build_system_prompt("ru", stroke=stroke, experiment_v2=flag)
        result = analyzer.analyze(
            video,
            language_code="ru",
            video_context={"stroke": stroke},
            experiment_v2=flag,
        )
        return system, result

    if omit_wiki:
        with patch.object(wiki_context, "build_knowledge_block", lambda *a, **k: ""):
            system, result = call()
    else:
        system, result = call()
    return system, result, time.time() - started


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Три схемы промпта на одном ролике")
    parser.add_argument("--video", required=True)
    parser.add_argument("--stroke", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    video = Path(args.video).resolve()
    if not video.is_file():
        print(f"Нет файла: {video}")
        return 1
    out = Path(args.out) if args.out else Path("eval_out") / video.stem
    out.mkdir(parents=True, exist_ok=True)

    settings = load_settings()
    model = settings.gemini_model
    variants = [
        ("old", False, False),
        ("new", True, False),
        ("new_no_wiki", True, True),
    ]
    print(f"Модель {model}. Ролик {video.name}, удар {args.stroke}. Прогонов: 3.")
    if not args.yes:
        print("Сухой просмотр. Для вызовов Gemini добавьте --yes.")
        return 0

    analyzer = VideoAnalyzer(settings.gemini_api_key, model)
    summary = []
    for name, flag, omit_wiki in variants:
        print(f"\n=== {name} ===", flush=True)
        try:
            system, result, elapsed = _run_one(
                analyzer, video, args.stroke, flag, omit_wiki
            )
        except Exception as exc:
            print(f"{name}: ошибка {type(exc).__name__}: {exc}", flush=True)
            (out / f"{name}.error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
            )
            summary.append({"name": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        (out / f"{name}.md").write_text(result.text, encoding="utf-8")
        (out / f"{name}.system.txt").write_text(system, encoding="utf-8")
        cost = estimate_cost(
            result.usage.input_tokens,
            result.usage.output_tokens,
            result.usage.thinking_tokens,
            result.model,
        )
        row = {
            "name": name,
            "model": result.model,
            "seconds": round(elapsed, 1),
            "system_chars": len(system),
            "answer_chars": len(result.text),
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "thinking_tokens": result.usage.thinking_tokens,
            "usd": cost,
        }
        summary.append(row)
        print(
            f"{name}: {row['seconds']} с, system {row['system_chars']} симв., "
            f"ответ {row['answer_chars']} симв., "
            f"in {row['input_tokens']} out {row['output_tokens']} "
            f"think {row['thinking_tokens']}",
            flush=True,
        )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nГотово: {out}")
    return 0 if all("error" not in row for row in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
