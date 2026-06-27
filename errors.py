def format_analysis_error(exc: Exception) -> str:
    message = str(exc)

    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        return (
            "⚠️ *Исчерпана квота Gemini API*\n\n"
            "Бесплатный лимит запросов закончился или для вашего ключа квота = 0.\n\n"
            "Что сделать:\n"
            "1. Проверьте лимиты: https://ai.dev/rate-limit\n"
            "2. Создайте новый ключ на https://aistudio.google.com/apikey\n"
            "   (должен начинаться с `AIzaSy...`)\n"
            "3. Подождите до сброса дневного лимита\n"
            "4. Или подключите платный тариф в Google AI Studio"
        )

    if (
        "503" in message
        or "UNAVAILABLE" in message
        or "overloaded" in message.lower()
        or "high demand" in message.lower()
    ):
        return (
            "⚠️ *Gemini сейчас перегружен*\n\n"
            "Это временно: на стороне Google всплеск нагрузки на модель. "
            "С вашим видео и ключом всё в порядке.\n\n"
            "Отправьте видео ещё раз через минуту."
        )

    if "500" in message or "INTERNAL" in message:
        return (
            "⚠️ *Внутренняя ошибка Gemini*\n\n"
            "Временный сбой на стороне Google. Отправьте видео ещё раз через минуту."
        )

    if "location is not supported" in message.lower():
        return (
            "⚠️ *Gemini недоступен в вашем регионе*\n\n"
            "Запустите бота через VPN или на сервере за рубежом (VPS в EU/US)."
        )

    if "API key" in message or "PERMISSION_DENIED" in message or "401" in message:
        return (
            "⚠️ *Неверный API-ключ Gemini*\n\n"
            "Создайте ключ на https://aistudio.google.com/apikey "
            "и вставьте его в файл `.env` как `GEMINI_API_KEY`."
        )

    if isinstance(exc, TimeoutError):
        return (
            "⏱ Не успел обработать видео вовремя. "
            "Попробуйте короче ролик или повторите позже."
        )

    return (
        "❌ Не удалось проанализировать видео.\n\n"
        "Попробуйте ещё раз или отправьте другой ракурс. "
        "Если ошибка повторяется — проверьте ключ Gemini в `.env`."
    )
