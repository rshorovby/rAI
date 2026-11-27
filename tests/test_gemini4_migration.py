"""Тесты миграции на Gemini 4 и компактный персонализированный промпт v3."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import drills
from analyzer import (
    GEMINI4_MAX_OUTPUT_TOKENS,
    VideoAnalyzer,
    _build_generate_config,
)
from compact_prompt import (
    build_compact_system_prompt,
    filter_drills_for_strokes,
    issue_tags_for_strokes,
)
from config import (
    DEFAULT_MODEL_CHAT,
    DEFAULT_MODEL_FREE,
    DEFAULT_MODEL_PRO,
    compact_prompt_v3_enabled,
    gemini_service_tier,
    gemini_thinking_level,
    is_gemini4_model,
    load_settings,
)
from issue_tags import issue_tag_slugs
from pricing import Usage, cost_for_usage, estimate_cost, usage_from_response
from prompts import build_system_prompt

FIXTURES = Path(__file__).parent / "fixtures" / "structured"


def test_default_models_are_gemini4(monkeypatch):
    for var in (
        "GEMINI_MODEL",
        "GEMINI_MODEL_PRO",
        "GEMINI_MODEL_FREE",
        "GEMINI_MODEL_CHAT",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    settings = load_settings()
    assert DEFAULT_MODEL_PRO == "gemini-4-neon"
    assert DEFAULT_MODEL_FREE == "gemini-4-hydrogen"
    assert DEFAULT_MODEL_CHAT == "gemini-4-hydrogen"
    assert settings.gemini_model_pro == "gemini-4-neon"
    assert settings.gemini_model_free == "gemini-4-hydrogen"
    assert settings.chat_model() == "gemini-4-hydrogen"
    assert settings.model_for(is_pro=True) == "gemini-4-neon"
    assert settings.model_for(is_pro=False) == "gemini-4-neon"


def test_thinking_level_and_service_tier_rules(monkeypatch):
    for var in (
        "GEMINI_THINKING_PRO",
        "GEMINI_THINKING_FREE",
        "GEMINI_THINKING_CHAT",
        "GEMINI_THINKING_LEVEL",
        "GEMINI_SERVICE_TIER",
    ):
        monkeypatch.delenv(var, raising=False)

    assert is_gemini4_model("gemini-4-neon") is True
    assert is_gemini4_model("gemini-3.1-pro-preview") is False

    assert gemini_thinking_level("gemini-4-neon") == "low"
    assert gemini_thinking_level("gemini-4-hydrogen") == "medium"
    assert gemini_thinking_level("gemini-4-carbon") == "medium"
    assert gemini_thinking_level("gemini-4-hydrogen", for_chat=True) == "low"
    assert gemini_thinking_level("gemini-3.1-pro-preview") is None
    assert gemini_service_tier() is None

    monkeypatch.setenv("GEMINI_THINKING_PRO", "medium")
    assert gemini_thinking_level("gemini-4-neon") == "medium"

    monkeypatch.setenv("GEMINI_THINKING_CHAT", "off")
    assert gemini_thinking_level("gemini-4-hydrogen", for_chat=True) is None

    monkeypatch.setenv("GEMINI_SERVICE_TIER", "flex")
    assert gemini_service_tier() == "flex"


def test_pricing_gemini4_cached_and_flex():
    # Neon: $3/1M in, $15/1M out; 95% скидка на cached input ($0.15/1M)
    full = estimate_cost(20_000, 2_000, 3_000, "gemini-4-neon")
    expected_full = 20_000 / 1e6 * 3.0 + 5_000 / 1e6 * 15.0
    assert abs(full - expected_full) < 1e-9

    cached = estimate_cost(
        20_000, 2_000, 3_000, "gemini-4-neon", cached_input_tokens=10_000
    )
    expected_cached = 10_000 / 1e6 * 3.0 + 10_000 / 1e6 * 0.15 + 5_000 / 1e6 * 15.0
    assert abs(cached - expected_cached) < 1e-9
    assert cached < full

    flex = estimate_cost(20_000, 2_000, 3_000, "gemini-4-neon", service_tier="flex")
    assert abs(flex - full * 0.5) < 1e-9

    # Hydrogen: $1.50 / $7.50
    h_cost = estimate_cost(20_000, 2_000, 3_000, "gemini-4-hydrogen")
    assert abs(h_cost - full * 0.5) < 1e-9

    class Meta:
        prompt_token_count = 20_000
        candidates_token_count = 2_000
        thoughts_token_count = 3_000
        cached_content_token_count = 10_000

    class Resp:
        usage_metadata = Meta()

    usage = usage_from_response(Resp(), "gemini-4-neon")
    assert usage == Usage(20_000, 2_000, 3_000, "gemini-4-neon", 10_000)
    assert abs(cost_for_usage(usage) - expected_cached) < 1e-9


def test_build_generate_config_gemini4_vs_gemini3(monkeypatch):
    from google.genai import types

    monkeypatch.delenv("GEMINI_SERVICE_TIER", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_PRO", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_FREE", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_CHAT", raising=False)

    cfg_neon = _build_generate_config(
        "gemini-4-neon",
        system_instruction="sys",
        legacy_temperature=0.3,
    )
    assert cfg_neon.temperature is None
    assert cfg_neon.max_output_tokens == GEMINI4_MAX_OUTPUT_TOKENS
    assert cfg_neon.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert cfg_neon.service_tier is None

    cfg_hydrogen = _build_generate_config(
        "gemini-4-hydrogen",
        system_instruction="sys",
        legacy_temperature=0.3,
    )
    assert cfg_hydrogen.temperature is None
    assert cfg_hydrogen.thinking_config.thinking_level == types.ThinkingLevel.MEDIUM

    cfg_chat = _build_generate_config(
        "gemini-4-hydrogen",
        system_instruction="sys",
        legacy_temperature=0.5,
        for_chat=True,
    )
    assert cfg_chat.temperature is None
    assert cfg_chat.thinking_config.thinking_level == types.ThinkingLevel.LOW

    cfg_g3 = _build_generate_config(
        "gemini-3.1-pro-preview",
        system_instruction="sys",
        legacy_temperature=0.3,
    )
    assert cfg_g3.temperature == 0.3
    assert cfg_g3.thinking_config is None
    assert cfg_g3.max_output_tokens is None

    monkeypatch.setenv("GEMINI_SERVICE_TIER", "flex")
    cfg_flex = _build_generate_config(
        "gemini-4-neon",
        system_instruction="sys",
        legacy_temperature=0.3,
    )
    assert cfg_flex.service_tier == types.ServiceTier.FLEX


def test_analyzer_structured_and_chat_use_gemini4_config(tmp_path, monkeypatch):
    from google.genai import types

    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    monkeypatch.delenv("GEMINI_SERVICE_TIER", raising=False)
    raw = (FIXTURES / "serve.json").read_text(encoding="utf-8")

    analyzer = VideoAnalyzer(api_key="x", model="gemini-4-neon")
    response = MagicMock()
    response.text = raw

    class Meta:
        prompt_token_count = 15_000
        candidates_token_count = 2_000
        thoughts_token_count = 1_500
        cached_content_token_count = 0

    response.usage_metadata = Meta()

    with (
        patch.object(analyzer, "_generate_with_retry", return_value=response) as gen,
        patch("analyzer.strip_audio_for_upload", return_value=(Path("v.mp4"), None)),
        patch("analyzer.video_duration_sec", return_value=8),
        patch.object(
            analyzer._client.files,
            "upload",
            return_value=MagicMock(uri="u", mime_type="video/mp4", name="f"),
        ),
        patch.object(analyzer, "_wait_until_active", side_effect=lambda item: item),
        patch.object(analyzer, "_safe_delete"),
    ):
        result = analyzer.analyze(
            Path("v.mp4"),
            language_code="ru",
            video_context={"stroke": "serve"},
            player_profile={"hand": "left", "level": "advanced"},
            drills_catalog="- id=toss-spot: точка",
            run_log_dir=tmp_path,
        )

    assert result.model == "gemini-4-neon"
    cfg = gen.call_args.kwargs["config"]
    assert cfg.temperature is None
    assert cfg.max_output_tokens == 65536
    assert cfg.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert "ЛЕВША" in cfg.system_instruction
    assert "## ПОДАЧА" in cfg.system_instruction

    chat_resp = MagicMock()
    chat_resp.text = "Держи подброс чуть ниже."
    chat_resp.usage_metadata = Meta()
    with patch.object(
        analyzer, "_generate_with_retry", return_value=chat_resp
    ) as chat_gen:
        chat_res = analyzer.chat(
            "отчёт",
            [],
            "почему подброс высокий?",
            language_code="ru",
            model="gemini-4-hydrogen",
        )
    assert chat_res.model == "gemini-4-hydrogen"
    chat_cfg = chat_gen.call_args.kwargs["config"]
    assert chat_cfg.temperature is None
    assert chat_cfg.max_output_tokens == 65536
    assert chat_cfg.thinking_config.thinking_level == types.ThinkingLevel.LOW


@pytest.mark.parametrize(
    "stroke,expected_heading,max_chars",
    [
        ("serve", "## ПОДАЧА", 7_500),
        ("forehand", "## ФОРХЕНД", 7_500),
        ("backhand", "## БЭКХЕНД", 7_500),
        ("slice", "## РЕЗАНЫЙ УДАР (slice)", 7_500),
        ("volley", "## СЕТКА (volley)", 7_500),
        ("smash", "## СЕТКА (volley)", 7_500),
        ("footwork", "## НОГИ (footwork)", 7_000),
        ("rally", "## РОЗЫГРЫШ (rally)", 9_500),
        ("general", "## ОБЩИЙ РАЗБОР", 10_000),
    ],
)
def test_compact_prompt_covers_all_segments_cleanly(
    stroke, expected_heading, max_chars
):
    catalog = drills.catalog_for_prompt(50)
    profile = {
        "level": "intermediate",
        "hand": "right",
        "backhand": "two_handed",
        "frequency": "2-3",
        "injuries": "",
    }
    text = build_compact_system_prompt(
        player_profile=profile,
        stroke=stroke,
        drills_catalog=catalog,
    )
    assert expected_heading in text
    assert len(text) < max_chars
    lowered = text.lower()
    assert "поднос" not in lowered
    assert "waiter" not in lowered
    for author in ("николаев", "джумок", "feel tennis"):
        assert author not in lowered
    assert "[[" not in text
    assert "всё понемногу" not in lowered


def test_compact_prompt_personalizes_hand_backhand_injuries_and_junior():
    catalog = drills.catalog_for_prompt(50)

    # Левша + травма на подаче
    serve_left = build_compact_system_prompt(
        player_profile={
            "hand": "left",
            "level": "advanced",
            "injuries": "болит правое колено",
        },
        stroke="serve",
        drills_catalog=catalog,
    )
    assert "ЛЕВША" in serve_left
    assert "справа от корпуса" in serve_left
    assert "ПРИОРИТЕТ №1" in serve_left
    assert "болит правое колено" in serve_left
    assert "forehand" not in serve_left.lower()

    # Бэкхенд 2H vs 1H
    bh_2h = build_compact_system_prompt(
        player_profile={"hand": "right", "backhand": "two_handed"},
        stroke="backhand",
        drills_catalog=catalog,
    )
    assert "Ветка: ДВУРУЧНЫЙ" in bh_2h
    assert "Ветка: ОДНОРУЧНЫЙ" not in bh_2h
    assert "id=two-hand-sync" in bh_2h
    assert "id=one-hand-extension" not in bh_2h

    bh_1h = build_compact_system_prompt(
        player_profile={"hand": "right", "backhand": "one_handed"},
        stroke="backhand",
        drills_catalog=catalog,
    )
    assert "Ветка: ОДНОРУЧНЫЙ" in bh_1h
    assert "Ветка: ДВУРУЧНЫЙ" not in bh_1h
    assert "id=one-hand-extension" in bh_1h
    assert "id=two-hand-sync" not in bh_1h

    # Юниор сохраняет возрастные нормы
    junior = build_compact_system_prompt(
        player_profile={"age_band": "y8_9", "level": "training"},
        stroke="forehand",
        drills_catalog=catalog,
    )
    assert "8–9 лет" in junior
    assert "orange" in junior


def test_compact_prompt_preserves_personal_blocks_and_rollback_flag(monkeypatch):
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    monkeypatch.setenv("COMPACT_PROMPT_V3", "1")
    assert compact_prompt_v3_enabled() is True

    prompt = build_system_prompt(
        "ru",
        player_history=[
            {
                "created_at": "2026-11-20",
                "stroke": "serve",
                "summary": "Низкий подброс",
                "scores": {"footwork": 5, "contact": 6},
            }
        ],
        player_profile={"hand": "left", "level": "advanced"},
        stroke="serve",
        drills_catalog=drills.catalog_for_prompt(50),
        prompt_context={
            "foci": [{"stroke": "serve", "focus": "Сгибать колени в трофее"}],
            "practice": [
                {
                    "post_answer": "yes",
                    "focus_text": "Сгибать колени",
                    "drill_id": "knee-bend-serve",
                }
            ],
        },
    )
    assert "## ПОДАЧА" in prompt
    assert "## ФОРХЕНД" not in prompt
    assert "Сгибать колени в трофее" in prompt
    assert "leg_drive" in prompt
    assert "ЗАМЕТКИ О ИГРОКЕ" in prompt
    assert "ТРЕНИРОВКИ ПОСЛЕ ПРОШЛЫХ РАЗБОРОВ" in prompt

    # Откат на старый v2 через COMPACT_PROMPT_V3=0
    monkeypatch.setenv("COMPACT_PROMPT_V3", "0")
    assert compact_prompt_v3_enabled() is False
    rolled_back = build_system_prompt("ru", stroke="serve")
    assert "## ФОРХЕНД" in rolled_back


def test_all_filtered_issue_tags_belong_to_registry():
    registry = set(issue_tag_slugs())
    for seg in ("serve", "forehand", "backhand", "slice", "volley", "footwork"):
        tags = issue_tags_for_strokes([seg])
        assert tags
        assert set(tags) <= registry
    # Для rally/general возвращается полный реестр
    assert issue_tags_for_strokes([]) == issue_tag_slugs()
    assert issue_tags_for_strokes(["rally"]) == issue_tag_slugs()


def test_filter_drills_keeps_untagged_lines():
    custom = "- id=toss-spot: точка"
    assert filter_drills_for_strokes(custom, ["serve"]) == custom
