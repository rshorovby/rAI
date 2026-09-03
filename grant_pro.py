#!/usr/bin/env python3
"""Выдать Pro пользователю (админ / SSH).

Пример:
  .venv/bin/python grant_pro.py 123456789
  .venv/bin/python grant_pro.py 123456789 3
"""

from __future__ import annotations

import sys

import billing
import identity
import services


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: grant_pro.py <user_id> [months]", file=sys.stderr)
        sys.exit(1)
    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print("user_id должен быть числом", file=sys.stderr)
        sys.exit(1)
    months = billing.PRO_MONTHS_DEFAULT
    if len(sys.argv) > 2:
        try:
            months = max(1, int(sys.argv[2]))
        except ValueError:
            print("months должен быть числом", file=sys.stderr)
            sys.exit(1)

    player_id = identity.get_or_create_telegram_player(telegram_id)
    sub = services.grant_pro(player_id, months=months, provider=billing.PROVIDER_ADMIN)
    print(
        f"Pro выдан user_id={telegram_id} (player_id={player_id}) на {months} мес. "
        f"expires_at={sub.get('expires_at')} provider={sub.get('provider')}"
    )


if __name__ == "__main__":
    main()
