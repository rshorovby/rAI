import asyncio
import logging
import os

from bot import build_application
from config import load_settings
from error_reporting import init_sentry


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    init_sentry()
    settings = load_settings()
    app = build_application(settings)
    port_raw = os.getenv("HTTP_PORT", "").strip()
    if not port_raw:
        app.run_polling(
            allowed_updates=[
                "message",
                "callback_query",
                "pre_checkout_query",
            ]
        )
        return
    asyncio.run(_run_bot_and_http(app, port_raw))


async def _run_bot_and_http(application, port_raw: str) -> None:
    import uvicorn
    from http_api import create_app, enqueue_ios_job_live

    host = os.getenv("HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(port_raw)
    http_app = create_app(enqueue_ios_job=enqueue_ios_job_live)
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=[
            "message",
            "callback_query",
            "pre_checkout_query",
        ]
    )
    config = uvicorn.Config(http_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    main()
