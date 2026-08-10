from i18n import DEFAULT_LANG, t


def is_model_overloaded(exc: Exception) -> bool:
    """Временные сбои модели/квоты времени — имеет смысл ретрай / запасная модель."""
    message = str(exc)
    lower = message.lower()
    name = type(exc).__name__.lower()
    return (
        isinstance(exc, TimeoutError)
        or "503" in message
        or "504" in message
        or "unavailable" in lower
        or "overloaded" in lower
        or "high demand" in lower
        or "deadline_exceeded" in lower
        or "deadline expired" in lower
        or "timeout" in name
        or "timed out" in lower
        or "timeout" in lower
    )


def format_analysis_error(exc: Exception, lang: str = DEFAULT_LANG) -> str:
    message = str(exc)

    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        return t(lang, "error_quota")

    if is_model_overloaded(exc):
        return t(lang, "error_overloaded")

    if "500" in message or "INTERNAL" in message:
        return t(lang, "error_internal")

    if "location is not supported" in message.lower():
        return t(lang, "error_region")

    if "API key" in message or "PERMISSION_DENIED" in message or "401" in message:
        return t(lang, "error_api_key")

    return t(lang, "error_generic")
