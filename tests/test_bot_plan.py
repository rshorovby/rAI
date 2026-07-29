import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import billing
import storage
from bot import plan_command
from i18n import t


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_plan_strings_format():
    text = t(
        "ru",
        "plan_status",
        plan="Free",
        used=1,
        limit=2,
        left=1,
        reset="2026-08-01",
        expires="—",
    )
    assert "Free" in text
    assert "1/2" in text


def test_plan_command_free(tmp_path):
    with _tmp_db(tmp_path):
        update = MagicMock()
        update.message = MagicMock()
        update.message.from_user.id = 77
        update.message.from_user.language_code = "ru"
        update.effective_user = update.message.from_user
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.user_data = {}

        async def _run():
            with (
                patch("bot._touch_user", new=AsyncMock()),
                patch("bot._lang_from_update", return_value="ru"),
            ):
                await plan_command(update, context)

        asyncio.run(_run())
        assert update.message.reply_text.await_count == 1
        assert billing.get_plan(77).plan == billing.PLAN_FREE
