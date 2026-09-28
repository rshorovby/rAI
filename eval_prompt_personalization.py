"""Проверка, что промпт разбора помнит игрока. Сеть не нужна.

Ролик по желанию, ключ не печатается:

    GEMINI_API_KEY=... .venv/bin/python eval_prompt_personalization.py --video clip.mp4
"""

import argparse
import os
import sys

from prompts import build_system_prompt


def cases():
    """Четыре игрока. must — строки, которые обязаны быть в промпте."""
    repeat_history = [
        {
            "created_at": "2026-09-01 10:00:00",
            "summary": "Поздний unit turn на форхенде.",
            "top3": "1. Разворот до отскока",
            "stroke": "forehand",
            "focus": "разворот до отскока",
            "scores": {"preparation": 4},
            "drill_ids": ["unit-turn-shadow"],
            "issue_tags": ["unit-turn"],
            "focus_checks": [],
        },
        {
            "created_at": "2026-09-10 10:00:00",
            "summary": "Разворот всё ещё после отскока.",
            "top3": "1. Разворот до отскока",
            "stroke": "forehand",
            "focus": "разворот до отскока",
            "scores": {"preparation": 4},
            "drill_ids": ["unit-turn-shadow"],
            "issue_tags": ["unit-turn"],
            "focus_checks": [{"stroke": "forehand", "status": "same"}],
        },
    ]
    return [
        {
            "name": "novice",
            "must": ["Это первое видео игрока."],
            "must_not": ["Хронические проблемы", "чужой секрет"],
            "kwargs": {
                "language_code": "ru",
                "prompt_context": {"session_count": 0, "today": "2026-09-26"},
            },
        },
        {
            "name": "repeat",
            "must": [
                "Поздний unit turn",
                "unit-turn",
                "Хронические проблемы",
                "было трудно",
                "unit-turn-shadow",
            ],
            "must_not": ["чужой секрет"],
            "kwargs": {
                "language_code": "ru",
                "player_history": repeat_history,
                "prompt_context": {
                    "today": "2026-09-26",
                    "session_count": 4,
                    "practice": [
                        {
                            "post_answer": "hard",
                            "focus_text": "разворот до отскока",
                            "drill_id": "unit-turn-shadow",
                        }
                    ],
                    "path": {
                        "session_count": 4,
                        "first_at": "2026-08-01 10:00:00",
                        "stroke_counts": {"forehand": 4},
                        "closed_focuses": 0,
                        "chronic": [
                            {
                                "stroke": "forehand",
                                "tag": "unit-turn",
                                "count": 2,
                                "last_at": "2026-09-10 10:00:00",
                            }
                        ],
                    },
                    "chronic_tags": ["unit-turn"],
                },
            },
        },
        {
            "name": "closed-focus",
            "must": ["разворот до отскока", "прежний текст", "стало лучше"],
            "must_not": ["чужой секрет"],
            "kwargs": {
                "language_code": "ru",
                "player_history": [
                    {
                        "created_at": "2026-09-12 10:00:00",
                        "summary": "Разворот успел.",
                        "top3": "",
                        "stroke": "forehand",
                        "focus": "разворот до отскока",
                        "focus_checks": [{"stroke": "forehand", "status": "improved"}],
                    }
                ],
                "prompt_context": {
                    "today": "2026-09-26",
                    "session_count": 3,
                    "foci": [{"stroke": "forehand", "focus": "разворот до отскока"}],
                },
            },
        },
        {
            "name": "multi",
            "must": [
                "разворот до отскока",
                "подброс в одну точку",
                "форхенд",
                "подача",
                "болит локоть",
            ],
            "must_not": ["чужой секрет", "ЭТАЛОН ТРЕНЕРА", "двуручный бэкхенд"],
            "kwargs": {
                "language_code": "ru",
                "coach_corrections": [
                    {
                        "scope": "player",
                        "draft_text": "черновик",
                        "delta_text": "двуручный бэкхенд, восточная хватка",
                    }
                ],
                "prompt_context": {
                    "today": "2026-09-26",
                    "session_count": 2,
                    "foci": [
                        {"stroke": "forehand", "focus": "разворот до отскока"},
                        {"stroke": "serve", "focus": "подброс в одну точку"},
                    ],
                    "notes": [
                        {
                            "created_at": "2026-09-20 10:00:00",
                            "text": "болит локоть на бэкхенде",
                        }
                    ],
                },
            },
        },
    ]


def system_for(case: dict) -> str:
    kwargs = dict(case["kwargs"])
    language = kwargs.pop("language_code")
    return build_system_prompt(language, **kwargs)


def check(case: dict):
    text = system_for(case)
    missing = [item for item in case["must"] if item not in text]
    forbidden = [item for item in case["must_not"] if item in text]
    return missing, forbidden


def _live_video(path: str) -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Ролик пропущен: нет GEMINI_API_KEY.")
        return 0
    from pathlib import Path

    from analyzer import VideoAnalyzer
    from config import load_settings

    settings = load_settings()
    case = cases()[1]
    analyzer = VideoAnalyzer(key, settings.gemini_model)
    result = analyzer.analyze(
        Path(path),
        player_history=case["kwargs"].get("player_history"),
        language_code="ru",
        prompt_context=case["kwargs"].get("prompt_context"),
        active_focus="разворот до отскока",
    )
    text = result.text
    print(f"Ролик разобран, символов: {len(text)}")
    needles = ("разворот", "unit")
    missed = [item for item in needles if item.lower() not in text.lower()]
    if missed:
        print("В ответе не нашлось: " + ", ".join(missed))
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Проверка персонализации промпта")
    parser.add_argument("--video", help="Локальный ролик. Боевые заявки не читаются.")
    args = parser.parse_args(argv)
    failed = 0
    for case in cases():
        missing, forbidden = check(case)
        if missing or forbidden:
            failed += 1
            print(f"{case['name']}: нет {missing or '—'}; лишнее {forbidden or '—'}")
        else:
            print(f"{case['name']}: ок")
    if args.video:
        failed += _live_video(args.video)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
