"""Проверка Gemini API без Telegram. Запуск: python test_gemini.py [путь_к_видео.mp4]"""

import sys
from pathlib import Path

from analyzer import VideoAnalyzer
from config import load_settings


def main() -> None:
    settings = load_settings()
    print(f"Модель: {settings.gemini_model}")
    print(f"Ключ: {settings.gemini_api_key[:8]}...")

    client = VideoAnalyzer(settings.gemini_api_key, settings.gemini_model)

    if len(sys.argv) > 1:
        video_path = Path(sys.argv[1])
        if not video_path.exists():
            print(f"Файл не найден: {video_path}")
            sys.exit(1)
        print(f"Анализ видео: {video_path}")
        report = client.analyze(video_path)
    else:
        from google import genai

        api = genai.Client(api_key=settings.gemini_api_key)
        print("Тест текстового запроса (без видео)...")
        r = api.models.generate_content(
            model=settings.gemini_model,
            contents="Ответь одним словом: работает",
        )
        report = r.text or ""

    print("\n--- РЕЗУЛЬТАТ ---\n")
    print(report[:2000])


if __name__ == "__main__":
    main()
