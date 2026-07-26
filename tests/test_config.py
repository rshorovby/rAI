import pytest

from config import DEFAULT_MODEL_FREE, DEFAULT_MODEL_PRO, load_settings

ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_MODEL_PRO",
    "GEMINI_MODEL_FREE",
    "ADMIN_USER_IDS",
)


@pytest.fixture
def env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    return monkeypatch


def test_defaults_are_current_models(env):
    settings = load_settings()

    assert settings.gemini_model_pro == DEFAULT_MODEL_PRO
    assert settings.gemini_model_free == DEFAULT_MODEL_FREE
    assert "gemini-2.0-flash" not in (
        settings.gemini_model_pro,
        settings.gemini_model_free,
    )


def test_legacy_gemini_model_overrides_both(env):
    env.setenv("GEMINI_MODEL", "gemini-legacy")

    settings = load_settings()

    assert settings.gemini_model_pro == "gemini-legacy"
    assert settings.gemini_model_free == "gemini-legacy"


def test_explicit_models_win_over_legacy(env):
    env.setenv("GEMINI_MODEL", "gemini-legacy")
    env.setenv("GEMINI_MODEL_PRO", "pro-model")
    env.setenv("GEMINI_MODEL_FREE", "free-model")

    settings = load_settings()

    assert settings.gemini_model_pro == "pro-model"
    assert settings.gemini_model_free == "free-model"


def test_model_for_selects_by_plan(env):
    settings = load_settings()

    assert settings.model_for(is_pro=True) == settings.gemini_model_pro
    assert settings.model_for(is_pro=False) == settings.gemini_model_free


def test_admin_ids_parsed(env):
    env.setenv("ADMIN_USER_IDS", " 1, 2 ,3 ")

    assert load_settings().admin_user_ids == (1, 2, 3)


def test_missing_required_vars_raise(env):
    env.delenv("GEMINI_API_KEY")

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        load_settings()
