import sqlite3
from pathlib import Path
from unittest.mock import patch

import prompts
import storage
from eval_prompt_ablation import (
    apply_variant,
    build_prompts,
    context_for_job,
    jobs_from_videos,
    main,
    metrics,
    pick_jobs,
    strip_example,
    stroke_from_name,
    trim_to_moment,
    variant_patches,
    video_context_for,
)

OLD = "2026-09-01 10:00:00"
JOB_AT = "2026-09-20 10:00:00"
NEW = "2026-09-21 10:00:00"
PLAYER = 7
REPORT = (
    "## Краткое резюме\nПоздний разворот.\n\n## Топ-3 приоритета для тренировки\n1. x\n"
)


def _snapshot(tmp_path: Path) -> tuple:
    db = tmp_path / "snap.db"
    with patch.object(storage, "DB_PATH", db):
        storage.save_session(PLAYER, REPORT, "ru", stroke="forehand")
        storage.save_session(PLAYER, REPORT, "ru", stroke="forehand")
        old_job = storage.create_review_job(
            PLAYER,
            video_file_id="tg-old",
            draft_text="старый черновик",
            stroke="forehand",
        )
        job = storage.create_review_job(
            PLAYER, video_file_id="tg-target", draft_text="черновик", stroke="forehand"
        )
        later_job = storage.create_review_job(
            PLAYER, video_file_id="ios:/tmp/x.mp4", draft_text="позже", stroke="serve"
        )
        storage.upsert_coach_evaluation(
            old_job, player_id=PLAYER, coach_user_id=1, delta_text="старая правка"
        )
        storage.upsert_coach_evaluation(
            later_job, player_id=PLAYER, coach_user_id=1, delta_text="будущая правка"
        )
        storage.add_player_note(PLAYER, "старая заметка")
        storage.add_player_note(PLAYER, "будущая заметка")
        storage.set_player_focus(PLAYER, "будущий фокус", "forehand")
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE player_sessions SET created_at = ? WHERE id = (SELECT MIN(id) FROM player_sessions)",
        (OLD,),
    )
    conn.execute(
        "UPDATE player_sessions SET created_at = ? WHERE id = (SELECT MAX(id) FROM player_sessions)",
        (NEW,),
    )
    conn.execute("UPDATE review_jobs SET created_at = ?", (JOB_AT,))
    conn.execute(
        "UPDATE coach_evaluations SET updated_at = ? WHERE job_id = ?", (OLD, old_job)
    )
    conn.execute(
        "UPDATE coach_evaluations SET updated_at = ? WHERE job_id = ?", (NEW, later_job)
    )
    conn.execute(
        "UPDATE player_notes SET created_at = ? WHERE text = 'старая заметка'", (OLD,)
    )
    conn.execute(
        "UPDATE player_notes SET created_at = ? WHERE text = 'будущая заметка'", (NEW,)
    )
    conn.execute(
        "UPDATE player_focus SET set_at = ?, previous_focus = 'старый фокус', "
        "previous_set_at = ?",
        (NEW, OLD),
    )
    conn.commit()
    conn.close()
    return db, job


def _count(db: Path, sql: str) -> list:
    conn = sqlite3.connect(str(db))
    try:
        return [row[0] for row in conn.execute(sql)]
    finally:
        conn.close()


def test_trim_keeps_only_rows_before_the_job(tmp_path):
    db, _ = _snapshot(tmp_path)
    trim_to_moment(db, "2026-09-20 09:58:00")
    assert _count(db, "SELECT created_at FROM player_sessions") == [OLD]
    assert _count(db, "SELECT delta_text FROM coach_evaluations") == ["старая правка"]
    assert _count(db, "SELECT text FROM player_notes") == ["старая заметка"]
    assert _count(db, "SELECT focus FROM player_focus") == ["старый фокус"]


def test_context_is_taken_at_job_time_and_snapshot_is_untouched(tmp_path):
    db, job_id = _snapshot(tmp_path)
    job = pick_jobs(db, [job_id])[0]
    ctx = context_for_job(db, job, tmp_path)
    assert len(ctx["history"]) == 1
    assert ctx["corrections"] == []
    assert [n["text"] for n in ctx["notes"]] == ["старая заметка"]
    assert ctx["today"] == "2026-09-20"
    assert len(_count(db, "SELECT id FROM player_sessions")) == 2


def test_sample_skips_ios_jobs_without_a_file(tmp_path):
    db, _ = _snapshot(tmp_path)
    jobs = pick_jobs(db, sample=5)
    assert all(not j["video_file_id"].startswith("ios:") for j in jobs)
    assert video_context_for({"stroke": "serve", "source_channel": "telegram"}) == {
        "stroke": "serve"
    }


def test_each_variant_removes_only_its_layer(tmp_path):
    db, job_id = _snapshot(tmp_path)
    job = pick_jobs(db, [job_id])[0]
    base = context_for_job(db, job, tmp_path)
    vctx = video_context_for(job)

    def prompts_for(variant):
        with variant_patches(variant):
            return build_prompts(job, apply_variant(base, variant), vctx)

    system, user = prompts_for("full")
    assert system == prompts.build_system_prompt(
        "ru",
        base["history"],
        base["profile"],
        stroke="forehand",
        active_focus=base["focus"],
        drills_catalog=base["drills_catalog"],
        coach_corrections=base["corrections"],
        strokes=None,
        prompt_context=base,
    )
    for marker in ("ЗАМЕТКИ О ИГРОКЕ", "БАЗА ЗНАНИЙ"):
        assert marker in system
    assert "Пример:" in user
    assert "ЭТАЛОН ТРЕНЕРА" not in system

    assert "ЭТАЛОН ТРЕНЕРА" not in prompts_for("no_coach")[0]
    assert "ЗАМЕТКИ О ИГРОКЕ" not in prompts_for("no_memory")[0]
    assert "БАЗА ЗНАНИЙ" not in prompts_for("no_knowledge")[0]
    assert "Пример:" not in prompts_for("no_example")[1]
    bare_system, bare_user = prompts_for("bare")
    for marker in ("ЭТАЛОН ТРЕНЕРА", "ЗАМЕТКИ О ИГРОКЕ", "БАЗА ЗНАНИЙ"):
        assert marker not in bare_system
    assert "Пример:" not in bare_user
    assert "БАЗА ЗНАНИЙ" in prompts_for("full")[0]


def test_strip_example_keeps_the_rest():
    body = prompts.USER_PROMPT_RU
    stripped = strip_example(body)
    assert "```json" not in stripped
    assert "Поле detected_segments" in stripped
    assert "Важно: если на видео нет" in stripped


def test_metrics_compare_different_videos_only():
    items = [
        {
            "job_id": 1,
            "issue_tags": ["unit-turn"],
            "drill_ids": ["a"],
            "problems": ["поздно"],
            "text": "до отскока",
            "system_chars": 100,
        },
        {
            "job_id": 1,
            "issue_tags": ["unit-turn"],
            "drill_ids": ["a"],
            "problems": ["поздно"],
            "text": "",
            "system_chars": 100,
        },
        {
            "job_id": 2,
            "issue_tags": ["split-step"],
            "drill_ids": ["a"],
            "problems": ["поздно"],
            "text": "",
            "system_chars": 200,
        },
    ]
    row = metrics(items)
    assert row["tags_jaccard"] == 0.0
    assert row["drills_jaccard"] == 1.0
    assert row["problems_same"] == 1.0
    assert row["anchor_share"] == 1 / 3
    assert row["system_chars"] == 400 / 3


def test_dry_run_and_confirmation_do_not_call_gemini(tmp_path, capsys):
    db, job_id = _snapshot(tmp_path)
    with patch("analyzer.VideoAnalyzer.analyze") as analyze:
        assert main(["--db", str(db), "--jobs", str(job_id), "--dry-run"]) == 0
        assert main(["--db", str(db), "--jobs", str(job_id)]) == 0
    assert not analyze.called
    out = capsys.readouterr().out
    assert "| bare |" in out
    assert "Будет до 12 вызовов Gemini" in out


def test_named_local_videos_infer_backhand(tmp_path, capsys):
    one = tmp_path / "back.MOV"
    two = tmp_path / "back_2.MOV"
    one.write_bytes(b"x")
    two.write_bytes(b"y")
    assert stroke_from_name(one) == "backhand"
    assert stroke_from_name(two) == "backhand"
    assert stroke_from_name(Path("forh.MOV")) == "forehand"
    assert stroke_from_name(Path("serve.MP4")) == "serve"
    jobs = jobs_from_videos([one, two])
    assert [j["id"] for j in jobs] == ["back", "back_2"]
    assert jobs[0]["video_path"] == one.resolve()
    with patch("eval_prompt_ablation.empty_context") as ctx:
        ctx.return_value = {
            "history": [],
            "profile": None,
            "corrections": [],
            "focus": None,
            "drills_catalog": "",
            "session_count": None,
            "today": "2026-09-28",
            "foci": [],
            "practice": [],
            "notes": [],
            "path": None,
            "chronic_tags": [],
        }
        assert (
            main(
                [
                    "--videos",
                    f"{one},{two}",
                    "--dry-run",
                ]
            )
            == 0
        )
    out = capsys.readouterr().out
    assert "#back backhand" in out
    assert "no_coach и no_memory совпадут с full" in out
    assert main(["--videos", str(tmp_path / "missing.MOV"), "--dry-run"]) == 1
