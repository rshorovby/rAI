"""Идентичность игрока: внутренний player_id и привязки каналов."""

from typing import Optional

import storage

PROVIDER_TELEGRAM = storage.PROVIDER_TELEGRAM
PROVIDER_APPLE = storage.PROVIDER_APPLE


def get_or_create_telegram_player(telegram_user_id: int) -> int:
    return storage.get_or_create_telegram_player(telegram_user_id)


def player_id_for_telegram(telegram_user_id: int) -> Optional[int]:
    return storage.player_id_for_telegram(telegram_user_id)


def telegram_id_for(player_id: int) -> Optional[int]:
    return storage.telegram_id_for(player_id)
