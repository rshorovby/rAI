import logging

from bot import build_application
from config import load_settings


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    settings = load_settings()
    app = build_application(settings)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
