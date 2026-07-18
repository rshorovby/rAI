"""Tests for wiki_context knowledge loading and prompt injection."""

from pathlib import Path

from prompts import build_follow_up_system_prompt, build_system_prompt
from wiki_context import (
    MAX_KNOWLEDGE_CHARS,
    build_knowledge_block,
    knowledge_slugs_for_tests,
    pages_for_stroke,
)


def test_pages_for_forehand_include_policy_and_stroke():
    pages = pages_for_stroke("forehand")
    assert pages[0] == "policy-modern-defaults.md"
    assert "wiki/strokes/forehand.md" in pages
    assert "wiki/concepts/gradual-acceleration.md" in pages


def test_pages_for_backhand_include_2h():
    pages = pages_for_stroke("backhand")
    assert "wiki/strokes/backhand.md" in pages
    assert "wiki/strokes/backhand-2h.md" in pages


def test_unknown_stroke_falls_back_to_footwork():
    pages = pages_for_stroke("unknown")
    assert "wiki/concepts/footwork.md" in pages
    assert pages[0] == "policy-modern-defaults.md"


def test_knowledge_block_ru_contains_marker():
    block = build_knowledge_block("forehand", "ru")
    assert "БАЗА ЗНАНИЙ" in block
    assert "P1" in block or "gradual" in block.lower()
    assert len(block) <= MAX_KNOWLEDGE_CHARS + 800


def test_knowledge_block_respects_cap(tmp_path: Path):
    (tmp_path / "policy-modern-defaults.md").write_text(
        "---\nstatus: reviewed\n---\n\n# Policy\n\nP1 modern.\n",
        encoding="utf-8",
    )
    strokes = tmp_path / "wiki" / "strokes"
    concepts = tmp_path / "wiki" / "concepts"
    strokes.mkdir(parents=True)
    concepts.mkdir(parents=True)
    (strokes / "forehand.md").write_text(
        "---\nstatus: reviewed\n---\n\n# FH\n\n" + ("x" * 5000),
        encoding="utf-8",
    )
    for name in (
        "contact-point",
        "unit-turn",
        "gradual-acceleration",
        "ground-force",
        "hip-rotation",
    ):
        (concepts / f"{name}.md").write_text(
            "---\nstatus: reviewed\n---\n\n# C\n\n" + ("y" * 3000),
            encoding="utf-8",
        )

    block = build_knowledge_block("forehand", "en", root=tmp_path, max_chars=2500)
    assert "KNOWLEDGE BASE" in block
    assert len(block) <= 2600


def test_missing_file_does_not_raise(tmp_path: Path):
    (tmp_path / "policy-modern-defaults.md").write_text(
        "---\nstatus: reviewed\n---\n\n# Policy only\n",
        encoding="utf-8",
    )
    block = build_knowledge_block("serve", "en", root=tmp_path)
    assert "KNOWLEDGE BASE" in block
    assert "Policy only" in block


def test_unverified_page_skipped(tmp_path: Path):
    (tmp_path / "policy-modern-defaults.md").write_text(
        "---\nstatus: reviewed\n---\n\n# Policy\n",
        encoding="utf-8",
    )
    strokes = tmp_path / "wiki" / "strokes"
    strokes.mkdir(parents=True)
    (strokes / "serve.md").write_text(
        "---\nstatus: unverified\n---\n\n# Secret serve\n",
        encoding="utf-8",
    )
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "grip.md").write_text(
        "---\nstatus: reviewed\n---\n\n# Grip ok\n",
        encoding="utf-8",
    )
    (concepts / "ground-force.md").write_text(
        "---\nstatus: reviewed\n---\n\n# GF ok\n",
        encoding="utf-8",
    )
    block = build_knowledge_block("serve", "en", root=tmp_path)
    assert "Secret serve" not in block
    assert "Grip ok" in block


def test_system_prompt_includes_knowledge():
    system = build_system_prompt("ru", stroke="forehand")
    assert "БАЗА ЗНАНИЙ" in system
    assert "P1" in system or "gradual" in system.lower()


def test_follow_up_prompt_includes_knowledge():
    follow = build_follow_up_system_prompt("en", stroke="backhand")
    assert "KNOWLEDGE BASE" in follow
    assert "backhand" in follow.lower()


def test_knowledge_slugs_helper():
    assert "policy-modern-defaults.md" in knowledge_slugs_for_tests("volley")
