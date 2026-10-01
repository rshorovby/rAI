"""Замер слоёв промпта: какой слой делает ответы на разные видео одинаковыми.

Снимок базы только читается. Для каждой заявки контекст берётся на момент заявки.
Локальные ролики с любым именем — через --videos, снимок тогда не обязателен.

    .venv/bin/python eval_prompt_ablation.py --db data/rally-backup.db --sample 6 --dry-run
    .venv/bin/python eval_prompt_ablation.py --videos videos/back.MOV,videos/back_2.MOV --dry-run
    .venv/bin/python eval_prompt_ablation.py --videos videos/back.MOV,videos/back_2.MOV --runs 2 --yes
"""

import argparse
import contextlib
import copy
import difflib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import prompts
import storage
import wiki_context
from report_parser import parse_report

CUTOFF_MARGIN = timedelta(minutes=2)
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LAYERS = ("coach", "memory", "knowledge", "example")
VARIANTS = {
    "full": (),
    "no_coach": ("coach",),
    "no_memory": ("memory",),
    "no_knowledge": ("knowledge",),
    "no_example": ("example",),
    "bare": LAYERS,
}
ANCHORS = (
    "unit-turn",
    "count-for-more-time",
    "до отскока",
    "before the bounce",
)
_EXAMPLE_RE = re.compile(r"\n(?:Пример|Example):\n```json\n.*?\n```\n", re.DOTALL)
_MIME_SUFFIX = {"video/quicktime": ".mov", "video/webm": ".webm"}
_STEM_STROKE = {
    "back": "backhand",
    "bh": "backhand",
    "backhand": "backhand",
    "fh": "forehand",
    "forh": "forehand",
    "forehand": "forehand",
    "serve": "serve",
    "volley": "volley",
    "foot": "footwork",
    "footwork": "footwork",
    "rally": "rally",
}


def cutoff_for(created_at: str) -> str:
    moment = datetime.strptime(created_at.strip()[:19], _TIME_FORMAT)
    return (moment - CUTOFF_MARGIN).strftime(_TIME_FORMAT)


def copy_snapshot(snapshot: Path, target: Path) -> None:
    source = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    dest = sqlite3.connect(str(target))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()


def trim_to_moment(db_path: Path, cutoff: str) -> None:
    """Удаляет в копии всё, что появилось не раньше cutoff."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            UPDATE player_focus
            SET focus = previous_focus, set_at = previous_set_at,
                previous_focus = NULL, previous_set_at = NULL
            WHERE set_at >= ? AND previous_set_at < ?
              AND TRIM(COALESCE(previous_focus, '')) != ''
            """,
            (cutoff, cutoff),
        )
        for table, column in (
            ("player_sessions", "created_at"),
            ("coach_evaluations", "updated_at"),
            ("player_focus", "set_at"),
            ("player_notes", "created_at"),
            ("practice_plans", "created_at"),
        ):
            conn.execute(f"DELETE FROM {table} WHERE {column} >= ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


def _read_rows(snapshot: Path, sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


_JOB_SQL = """
    SELECT id, user_id, created_at, video_file_id, video_mime, language_code,
           stroke, source_channel, intake_strokes_json
    FROM review_jobs
"""


def pick_jobs(
    snapshot: Path,
    job_ids: Optional[list] = None,
    sample: int = 0,
    video_dir: Optional[Path] = None,
) -> list:
    if job_ids:
        marks = ",".join("?" * len(job_ids))
        rows = _read_rows(
            snapshot, _JOB_SQL + f" WHERE id IN ({marks})", tuple(job_ids)
        )
        by_id = {row["id"]: row for row in rows}
        return [by_id[i] for i in job_ids if i in by_id]
    rows = _read_rows(
        snapshot, _JOB_SQL + " WHERE TRIM(draft_text) != '' ORDER BY id DESC"
    )
    usable = [row for row in rows if _has_video(row, video_dir)]
    chosen: list = []
    seen: set = set()
    for row in usable:
        if len(chosen) >= sample:
            break
        if row["stroke"] not in seen:
            seen.add(row["stroke"])
            chosen.append(row)
    for row in usable:
        if len(chosen) >= sample:
            break
        if row not in chosen:
            chosen.append(row)
    return chosen


def stroke_from_name(path: Path, override: str = "") -> str:
    if override:
        return override
    stem = re.sub(r"[-_]\d+$", "", path.stem.lower())
    return _STEM_STROKE.get(stem, "")


def jobs_from_videos(paths: list, stroke: str = "") -> list:
    jobs = []
    for path in paths:
        resolved = Path(path).resolve()
        jobs.append(
            {
                "id": resolved.stem,
                "user_id": 0,
                "created_at": datetime.now().strftime(_TIME_FORMAT),
                "video_file_id": "",
                "video_mime": "",
                "language_code": "ru",
                "stroke": stroke_from_name(resolved, stroke),
                "source_channel": "local",
                "intake_strokes_json": "[]",
                "video_path": resolved,
            }
        )
    return jobs


def parse_video_args(raw: str) -> list:
    return [Path(item.strip()) for item in raw.split(",") if item.strip()]


def empty_context(snapshot: Optional[Path] = None) -> dict:
    import drills

    corrections = []
    catalog = ""
    if snapshot is not None:
        with patch.object(storage, "DB_PATH", snapshot):
            corrections = storage.get_coach_corrections_for_prompt(None)
            catalog = drills.catalog_for_prompt()
    else:
        catalog = drills.catalog_for_prompt()
    return {
        "history": [],
        "profile": None,
        "corrections": corrections,
        "focus": None,
        "drills_catalog": catalog,
        "session_count": None,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "foci": [],
        "practice": [],
        "notes": [],
        "path": None,
        "chronic_tags": [],
    }


def context_for(snapshot: Optional[Path], job: dict, workdir: Path) -> dict:
    if job.get("video_path"):
        return empty_context(snapshot)
    if snapshot is None:
        raise ValueError("Нужен снимок базы")
    return context_for_job(snapshot, job, workdir)


def _local_video(job: dict, video_dir: Optional[Path]) -> Optional[Path]:
    raw = job.get("video_path")
    if raw:
        path = Path(raw)
        return path if path.is_file() else None
    if video_dir is None:
        return None
    for path in sorted(video_dir.glob(f"{job['id']}.*")):
        return path
    return None


def _has_video(job: dict, video_dir: Optional[Path]) -> bool:
    if _local_video(job, video_dir) is not None:
        return True
    return not (job.get("video_file_id") or "").startswith("ios:")


def video_context_for(job: dict) -> dict:
    stroke = (job.get("stroke") or "").strip()
    if (job.get("source_channel") or "telegram") == "ios":
        try:
            intake = json.loads(job.get("intake_strokes_json") or "[]")
        except ValueError:
            intake = []
        return {"stroke": stroke, "strokes": intake if isinstance(intake, list) else []}
    return {"stroke": stroke}


def context_for_job(snapshot: Path, job: dict, workdir: Path) -> dict:
    import services

    db_copy = workdir / f"job_{job['id']}.db"
    copy_snapshot(snapshot, db_copy)
    trim_to_moment(db_copy, cutoff_for(job["created_at"]))
    vctx = video_context_for(job)
    with patch.object(storage, "DB_PATH", db_copy):
        ctx = services.load_analysis_context(
            int(job["user_id"]), vctx.get("stroke"), vctx.get("strokes")
        )
    ctx["today"] = job["created_at"][:10]
    return ctx


def apply_variant(ctx: dict, variant: str) -> dict:
    out = copy.deepcopy(ctx)
    off = VARIANTS[variant]
    if "coach" in off:
        out["corrections"] = []
    if "memory" in off:
        out.update(
            history=[],
            foci=[],
            practice=[],
            notes=[],
            path=None,
            chronic_tags=[],
            focus=None,
            session_count=None,
        )
    return out


def strip_example(body: str) -> str:
    return _EXAMPLE_RE.sub("\n", body, count=1)


@contextlib.contextmanager
def variant_patches(variant: str):
    off = VARIANTS[variant]
    with contextlib.ExitStack() as stack:
        if "knowledge" in off:
            stack.enter_context(
                patch.object(wiki_context, "build_knowledge_block", lambda *a, **k: "")
            )
        if "example" in off:
            original = prompts.get_user_prompt_body
            stack.enter_context(
                patch.object(
                    prompts,
                    "get_user_prompt_body",
                    lambda language_code, structured=False: strip_example(
                        original(language_code, structured=structured)
                    ),
                )
            )
        yield


def build_prompts(job: dict, ctx: dict, vctx: dict) -> tuple:
    language = job.get("language_code") or "ru"
    system = prompts.build_system_prompt(
        language,
        ctx["history"],
        ctx["profile"],
        stroke=vctx.get("stroke"),
        active_focus=ctx["focus"],
        drills_catalog=ctx["drills_catalog"],
        coach_corrections=ctx["corrections"],
        strokes=vctx.get("strokes"),
        prompt_context=ctx,
    )
    user = prompts.build_analysis_prompt(language, None, vctx)
    return system, user


def download_video(job: dict, token: str, workdir: Path) -> Optional[Path]:
    file_id = job.get("video_file_id") or ""
    if not file_id or file_id.startswith("ios:"):
        return None
    base = "https://api.telegram.org"
    query = urllib.parse.urlencode({"file_id": file_id})
    try:
        with urllib.request.urlopen(
            f"{base}/bot{token}/getFile?{query}", timeout=60
        ) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        file_path = (meta.get("result") or {}).get("file_path")
        if not meta.get("ok") or not file_path:
            return None
        suffix = _MIME_SUFFIX.get(job.get("video_mime") or "", ".mp4")
        target = workdir / f"{job['id']}{suffix}"
        with (
            urllib.request.urlopen(
                f"{base}/file/bot{token}/{file_path}", timeout=120
            ) as resp,
            target.open("wb") as out,
        ):
            shutil.copyfileobj(resp, out)
        return target
    except Exception as exc:
        print(f"Заявка {job['id']}: ролик не скачан ({type(exc).__name__}).")
        return None


def _jaccard(a: list, b: list) -> Optional[float]:
    left, right = set(a or []), set(b or [])
    if not left and not right:
        return None
    return len(left & right) / len(left | right)


def _mean(values: list) -> Optional[float]:
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def _problems(item: dict) -> str:
    return " ".join(p.strip().lower() for p in item.get("problems") or [])


def _ratio(a: str, b: str) -> Optional[float]:
    if not a and not b:
        return None
    return difflib.SequenceMatcher(None, a, b).ratio()


def metrics(items: list) -> dict:
    """items: {job_id, run, issue_tags, drill_ids, problems, text, system_chars}."""
    cross = [(a, b) for a, b in combinations(items, 2) if a["job_id"] != b["job_id"]]
    same = [(a, b) for a, b in combinations(items, 2) if a["job_id"] == b["job_id"]]
    anchored = [
        any(anchor in (item.get("text") or "").lower() for anchor in ANCHORS)
        for item in items
    ]
    return {
        "answers": len(items),
        "tags_jaccard": _mean(
            [_jaccard(a["issue_tags"], b["issue_tags"]) for a, b in cross]
        ),
        "drills_jaccard": _mean(
            [_jaccard(a["drill_ids"], b["drill_ids"]) for a, b in cross]
        ),
        "problems_cross": _mean([_ratio(_problems(a), _problems(b)) for a, b in cross]),
        "problems_same": _mean([_ratio(_problems(a), _problems(b)) for a, b in same]),
        "anchor_share": (sum(anchored) / len(anchored)) if anchored else None,
        "system_chars": _mean([item.get("system_chars") for item in items]),
    }


def _fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def render_report(rows: dict, skipped: list) -> str:
    lines = [
        "# Замер слоёв промпта",
        "",
        "Похожесть считается между ответами на разные видео внутри одного варианта. "
        "Чем ниже, тем разнообразнее ответы. «Тот же ролик» — похожесть между прогонами "
        "одного видео, это уровень шума.",
        "",
        "| Вариант | Ответов | Теги, Jaccard | Упражнения, Jaccard | "
        "Замечания, разные видео | Замечания, тот же ролик | Доля якорей | "
        "Системный промпт, символов |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for variant, row in rows.items():
        lines.append(
            f"| {variant} | {row['answers']} | {_fmt(row['tags_jaccard'])} | "
            f"{_fmt(row['drills_jaccard'])} | {_fmt(row['problems_cross'])} | "
            f"{_fmt(row['problems_same'])} | {_fmt(row['anchor_share'])} | "
            f"{_fmt(row['system_chars'], 0)} |"
        )
    if skipped:
        lines += ["", "Пропущены: " + ", ".join(skipped)]
    lines.append("")
    return "\n".join(lines)


def _record(job: dict, run: int, text: str, system: str, user: str) -> dict:
    parsed = parse_report(text)
    drill_ids = list(parsed.drill_ids or [])
    for finding in parsed.findings or []:
        for raw in finding.get("drill_ids") or []:
            if raw not in drill_ids:
                drill_ids.append(raw)
    return {
        "job_id": job["id"],
        "run": run,
        "stroke": job.get("stroke") or "",
        "system_chars": len(system),
        "user_chars": len(user),
        "focus": parsed.focus,
        "issue_tags": list(parsed.issue_tags or []),
        "drill_ids": drill_ids,
        "problems": [f.get("problem") or "" for f in parsed.findings or []],
        "text": text,
    }


def dry_run(
    snapshot: Optional[Path], jobs: list, variants: list, workdir: Path
) -> dict:
    rows: dict = {}
    contexts = {job["id"]: context_for(snapshot, job, workdir) for job in jobs}
    for variant in variants:
        items = []
        for job in jobs:
            ctx = apply_variant(contexts[job["id"]], variant)
            vctx = video_context_for(job)
            with variant_patches(variant):
                system, user = build_prompts(job, ctx, vctx)
            items.append({"system_chars": len(system), "user_chars": len(user)})
        rows[variant] = {
            "system_chars": _mean([i["system_chars"] for i in items]),
            "user_chars": _mean([i["user_chars"] for i in items]),
        }
    return rows


def live_run(
    snapshot: Optional[Path],
    jobs: list,
    variants: list,
    runs: int,
    out_dir: Path,
    workdir: Path,
    video_dir: Optional[Path],
) -> int:
    from analyzer import VideoAnalyzer
    from config import load_settings

    settings = load_settings()
    analyzer = VideoAnalyzer(settings.gemini_api_key, settings.gemini_model_pro)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    skipped: list = []
    ready: list = []
    for job in jobs:
        video = _local_video(job, video_dir) or download_video(
            job, settings.telegram_token, workdir
        )
        if video is None:
            skipped.append(f"#{job['id']} (нет ролика)")
            continue
        ready.append((job, video, context_for(snapshot, job, workdir)))
    results: dict = {variant: [] for variant in variants}
    for job, video, base_ctx in ready:
        vctx = video_context_for(job)
        for variant in variants:
            ctx = apply_variant(base_ctx, variant)
            for run in range(1, runs + 1):
                with variant_patches(variant):
                    system, user = build_prompts(job, ctx, vctx)
                    try:
                        result = analyzer.analyze(
                            video,
                            None,
                            ctx["history"],
                            job.get("language_code") or "ru",
                            ctx["profile"],
                            vctx,
                            settings.gemini_model_pro,
                            ctx["focus"],
                            ctx["drills_catalog"],
                            ctx["corrections"],
                            ctx,
                        )
                    except Exception as exc:
                        skipped.append(
                            f"#{job['id']} {variant} {run} ({type(exc).__name__})"
                        )
                        continue
                item = _record(job, run, result.text, system, user)
                item["model"] = result.model
                results[variant].append(item)
                name = f"{job['id']}_{variant}_{run}.json"
                (raw_dir / name).write_text(
                    json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"#{job['id']} {variant} {run}: ок")
    rows = {variant: metrics(items) for variant, items in results.items()}
    report = render_report(rows, skipped)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Замер слоёв промпта разбора")
    parser.add_argument("--db", help="Снимок rally.db, только чтение")
    parser.add_argument("--jobs", help="id заявок через запятую")
    parser.add_argument("--sample", type=int, default=6)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--video-dir", help="Свои ролики с именем <job_id>.mp4")
    parser.add_argument(
        "--videos",
        help="Локальные ролики через запятую, любое имя: videos/back.MOV,videos/back_2.MOV",
    )
    parser.add_argument(
        "--stroke",
        default="",
        help="Удар для --videos, иначе из имени файла (back → backhand)",
    )
    parser.add_argument("--out", default="eval_out")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Подтвердить вызовы Gemini")
    args = parser.parse_args(argv)

    snapshot = Path(args.db).resolve() if args.db else None
    if snapshot is not None and not snapshot.is_file():
        print(f"Нет снимка: {snapshot}")
        return 1
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in variants if v not in VARIANTS]
    if unknown:
        print("Неизвестные варианты: " + ", ".join(unknown))
        return 1
    video_dir = Path(args.video_dir).resolve() if args.video_dir else None
    if args.videos:
        video_paths = parse_video_args(args.videos)
        missing = [str(p) for p in video_paths if not p.is_file()]
        if missing:
            print("Нет роликов: " + ", ".join(missing))
            return 1
        jobs = jobs_from_videos(video_paths, args.stroke)
        if snapshot is None:
            print(
                "Без --db эталон тренера и память игрока пустые: "
                "no_coach и no_memory совпадут с full."
            )
    else:
        if snapshot is None:
            print("Нужен --db или --videos.")
            return 1
        job_ids = (
            [int(x) for x in args.jobs.split(",") if x.strip()] if args.jobs else None
        )
        jobs = pick_jobs(snapshot, job_ids, args.sample, video_dir)
    if not jobs:
        print("Заявок не нашлось.")
        return 1
    print("Заявки: " + ", ".join(f"#{j['id']} {j['stroke'] or '—'}" for j in jobs))

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        if args.dry_run:
            rows = dry_run(snapshot, jobs, variants, workdir)
            print("| Вариант | Системный промпт | Запрос |")
            print("|---|---|---|")
            for variant, row in rows.items():
                print(
                    f"| {variant} | {_fmt(row['system_chars'], 0)} | "
                    f"{_fmt(row['user_chars'], 0)} |"
                )
            return 0
        calls = len(jobs) * len(variants) * args.runs
        if not args.yes:
            print(f"Будет до {calls} вызовов Gemini. Запустите с --yes.")
            return 0
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = Path(args.out).resolve() / stamp
        return live_run(
            snapshot, jobs, variants, args.runs, out_dir, workdir, video_dir
        )


if __name__ == "__main__":
    sys.exit(main())
