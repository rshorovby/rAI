"""Проверка identity token Sign in with Apple."""

from typing import Optional


def verify_apple_identity_token(
    identity_token: str, audience: Optional[str] = None
) -> str:
    """Возвращает `sub`. В тестах функция подменяется."""
    import jwt
    from jwt import PyJWKClient

    token = (identity_token or "").strip()
    if not token:
        raise ValueError("empty token")
    client = PyJWKClient("https://appleid.apple.com/auth/keys")
    signing_key = client.get_signing_key_from_jwt(token)
    options = {"verify_aud": bool(audience)}
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer="https://appleid.apple.com",
        options=options,
    )
    sub = payload.get("sub")
    if not sub:
        raise ValueError("no sub")
    return str(sub)
