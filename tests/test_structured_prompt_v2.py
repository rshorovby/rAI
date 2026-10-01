"""Сборка промпта structured analysis v2. Флаг по умолчанию выключен."""

from pathlib import Path

import pytest

from prompts import (
    build_analysis_prompt,
    build_follow_up_system_prompt,
    build_system_prompt,
)
from stroke_blocks import APPLY_BY_FACT, BLOCKS_DIR, load_stroke_blocks
from wiki_context import (
    build_knowledge_block,
    issue_tag_slugs,
    lint_sanitized_wiki,
    lint_wiki_authors,
    sanitize_wiki,
)

pytestmark = pytest.mark.usefixtures("_v2_on")


@pytest.fixture
def _v2_on(monkeypatch):
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")


def _joined(stroke="serve", **kwargs):
    system = build_system_prompt("ru", stroke=stroke, **kwargs)
    user = build_analysis_prompt(
        "ru",
        "вторая подача, снимал сбоку",
        {"stroke": stroke, "look": "technique"},
    )
    return system + "\n\n" + user


def test_serve_prompt_scopes_out_grip_without_trigger_phrases():
    text = _joined().lower()
    assert "хватку и ориентацию ракетки" in text
    assert "поднос" not in text
    assert "waiter" not in text
    assert "grip cues if visible" not in text
    assert "формат ответа" not in text


def test_english_stays_on_the_old_path():
    system = build_system_prompt("en", stroke="serve")
    assert "waiter's tray" in system
    assert "ОБЩИЕ ПРАВИЛА" not in system
    follow = build_follow_up_system_prompt("ru", stroke="serve")
    assert "ОБЩИЕ ПРАВИЛА" not in follow


def test_flag_off_keeps_the_old_prompt(monkeypatch):
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2")
    system = build_system_prompt("ru", stroke="serve", experiment_v2=True)
    assert "поднос официанта" in system
    assert "## ПОДАЧА" not in system


def test_flag_on_uses_structured_prompt_not_hybrid():
    system = build_system_prompt("ru", stroke="serve")
    user = build_analysis_prompt("ru", None, {"stroke": "serve", "look": "technique"})
    assert "## ПОДАЧА" in system
    assert "Формат ответа" not in user
    assert "```json" not in user


def test_experiment_keeps_legacy_user_prompt():
    system = build_system_prompt("ru", stroke="serve", experiment_v2=True)
    user = build_analysis_prompt(
        "ru",
        None,
        {"stroke": "serve", "look": "technique"},
        experiment_v2=True,
    )
    assert "## ПОДАЧА" in system
    assert "Формат ответа" in user


def test_block_order_is_fixed_when_player_picks_forehand():
    system = build_system_prompt("ru", stroke="forehand", experiment_v2=True)
    markers = [
        "## ОБЩИЕ ПРАВИЛА",
        "## ПОДАЧА",
        "## ФОРХЕНД",
        "## БЭКХЕНД",
        "## СЕТКА (volley)",
        "## НОГИ (footwork)",
        "## РОЗЫГРЫШ (rally)",
        "БАЗА ЗНАНИЙ",
    ]
    positions = [system.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert system.count(APPLY_BY_FACT) == 6
    profile = build_system_prompt(
        "ru",
        stroke="forehand",
        player_profile={"injuries": "МеткаПрофиляV2"},
        experiment_v2=True,
    )
    assert profile.index("БАЗА ЗНАНИЙ") < profile.index("МеткаПрофиляV2")


def test_registry_accepts_an_extra_block_without_assembler_edits(tmp_path: Path):
    extra = tmp_path / "dropshot.md"
    extra.write_text("## ДРОП\n\nКороткий блок.\n", encoding="utf-8")
    registry = {
        "serve": BLOCKS_DIR / "serve.md",
        "dropshot": extra,
    }
    text = load_stroke_blocks(registry)
    assert text.index("## ПОДАЧА") < text.index("## ДРОП")
    assert text.count(APPLY_BY_FACT) == 2


def test_caveat_is_not_stored_in_block_files():
    for path in BLOCKS_DIR.glob("*.md"):
        assert "Применяй этот раздел по факту" not in path.read_text(encoding="utf-8")


def test_caveat_is_the_first_line_under_each_heading():
    text = load_stroke_blocks()
    for heading in (
        "## ПОДАЧА",
        "## ФОРХЕНД",
        "## БЭКХЕНД",
        "## СЕТКА (volley)",
        "## НОГИ (footwork)",
        "## РОЗЫГРЫШ (rally)",
    ):
        lines = text[text.index(heading) :].splitlines()
        assert lines[1] == APPLY_BY_FACT


def test_blocks_have_no_service_notes():
    for path in BLOCKS_DIR.glob("*.md"):
        assert "добавить в словарь" not in path.read_text(encoding="utf-8")


def test_general_rules_do_not_list_forbidden_tokens():
    body = (BLOCKS_DIR / "_general.md").read_text(encoding="utf-8")
    lowered = body.lower()
    assert "поднос" not in lowered
    assert "waiter" not in lowered
    assert "[[" not in body
    assert "p1" not in lowered


def test_reference_section_stays_only_for_serve_and_rally():
    kept = {"serve.md", "rally.md"}
    for path in BLOCKS_DIR.glob("*.md"):
        body = path.read_text(encoding="utf-8")
        if path.name in kept:
            assert "### Справка" in body
        elif path.name != "_general.md":
            assert "### Справка" not in body


def test_serve_wiki_page_is_omitted_and_sanitized():
    block = build_knowledge_block("serve", "ru", sanitize=True, omit_serve_page=True)
    assert "рюмка" not in block
    assert "[[" not in block
    assert "unverified" not in block.lower()
    assert "feel tennis" not in block.lower()
    forehand = build_knowledge_block(
        "forehand", "ru", sanitize=True, omit_serve_page=True
    )
    assert "[[" not in forehand
    assert "unverified" not in forehand.lower()
    assert "feel tennis" not in forehand.lower()


def test_sanitize_wiki_translates_known_slugs_and_drops_unknown():
    raw = (
        "Смотри [[unit-turn|разворот]] и [[serve#toss]] и [[no-such-slug]].\n"
        "## P1 — Ускорение и кисть (GS) · RESOLVED → modern\n"
        "## 8 steps (Feel Tennis, unverified)\n"
        "(-contact-point-ideal)\n"
        "| A | |\n"
        "Николаев оставил заметку. поднос официанта. waiter."
    )
    cleaned = sanitize_wiki(raw)
    assert "разворот корпуса" in cleaned
    assert "подача" in cleaned
    assert "no-such-slug" not in cleaned
    assert "contact-point-ideal" not in cleaned
    assert "| A |" not in cleaned
    assert lint_sanitized_wiki(cleaned) == []
    assert "Николаев" in cleaned
    assert "поднос" not in cleaned.lower()
    assert "waiter" not in cleaned.lower()


def test_lint_sanitized_wiki_flags_leftover_markup():
    dirty = "## — хвост\n(-toss-height)\n| A | |\n[[serve]]\n()"
    assert lint_sanitized_wiki(dirty)


def test_issue_tag_list_matches_schema_enum():
    import json

    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schema" / "response-schema.json"
        ).read_text()
    )
    top = schema["properties"]["issue_tags"]["items"]["enum"]
    findings = schema["properties"]["findings"]["items"]["properties"]["issue_tags"][
        "items"
    ]["enum"]
    assert issue_tag_slugs() == top == findings
    system = build_system_prompt("ru", stroke="serve", experiment_v2=True)
    for slug in ("toss-placement", "unit-turn"):
        assert slug in system


def test_author_lint_reports_names_without_editing_pages():
    hits = lint_wiki_authors()
    assert any("Николаев" in hit for hit in hits)
    assert any("Джумок" in hit for hit in hits)
