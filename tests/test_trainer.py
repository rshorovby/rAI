from pathlib import Path
from unittest.mock import patch

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import practice
import storage
import trainer
from i18n import t


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "test.db")


def test_grant_is_idempotent_and_revoke_keeps_cards(tmp_path):
    with _tmp_db(tmp_path):
        storage.grant_trainer(10)
        storage.grant_trainer(10)
        card = storage.create_trainer_card(10, "Маша")
        assert card is not None
        storage.grant_trainer(10)
        assert storage.is_trainer(10)
        assert storage.trainer_instruction_pending(10)
        storage.mark_trainer_instruction_sent(10)
        assert not storage.trainer_instruction_pending(10)
        assert storage.revoke_trainer(10)
        assert not storage.revoke_trainer(10)
        assert not storage.is_trainer(10)
        assert storage.get_trainer_card_by_player(card["player_id"])["archived"] == 0


def test_card_context_is_separate_and_name_is_unique(tmp_path):
    with _tmp_db(tmp_path):
        storage.grant_trainer(10)
        storage.upsert_user(10, "coach", "Иван", "", "ru")
        first = storage.create_trainer_card(10, "Маша")
        assert storage.create_trainer_card(10, "маша") is None
        second = storage.create_trainer_card(10, "Петя")
        storage.save_player_profile(
            first["player_id"],
            {
                "level": "beginner",
                "hand": "right",
                "backhand": "two_handed",
                "frequency": "1",
                "experience": "under_1",
                "coaching": "individual",
                "focus": "technique",
                "injuries": "",
                "skipped": False,
            },
        )
        storage.mark_profile_skipped(second["player_id"])
        assert storage.get_player_profile(first["player_id"])["level"] == "beginner"
        assert storage.get_player_profile(second["player_id"])["skipped"]
        assert storage.get_active_trainer_card(10)["player_id"] == second["player_id"]
        assert storage.trainer_label(10) == "Иван"
        assert trainer.topic_title("Маша", "Иван") == "Маша · Иван"
        assert storage.rename_trainer_card(10, first["player_id"], "Петя") == "taken"
        assert storage.rename_trainer_card(10, first["player_id"], "Мария") == "ok"
        assert storage.archive_trainer_card(10, second["player_id"])
        assert storage.get_active_trainer_card(10) is None
        reused = storage.create_trainer_card(10, "Петя")
        assert reused["player_id"] != second["player_id"]


def test_name_rules_and_video_block():
    assert trainer.name_problem("") == "tr_name_empty"
    assert trainer.name_problem("Завести") == "tr_name_reserved"
    assert trainer.name_problem("x" * 61) == "tr_name_long"
    assert trainer.name_problem("  Анна  ") is None
    assert trainer.normalize_name("  Анна   Мария ") == "Анна Мария"
    data = {}
    assert not trainer.blocks_video(data)
    trainer.set_wizard(data, "await_name", trainer_id=1)
    assert trainer.blocks_video(data)
    trainer.clear_wizard(data)
    assert not trainer.blocks_video(data)
    assert trainer.is_cancel_text("ru", t("ru", "tr_btn_cancel"))


def test_practice_callback_is_bound_to_card():
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("ok", callback_data="p:pre:ok")]]
    )
    bound = practice.markup_for_player(markup, 77)
    assert bound.inline_keyboard[0][0].callback_data == "pc:77:pre:ok"


def test_topic_title_is_capped():
    title = trainer.topic_title("А" * 100, "Б" * 100)
    assert len(title) == 128
    assert " · " in title
