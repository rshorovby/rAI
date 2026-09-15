"""Доменный слой без типов Telegram: квота, анализ, очередь, прогресс."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json

import billing
import drills
import storage
from analyzer import AnalysisResult, VideoAnalyzer
from report_parser import SKILL_KEYS, parse_report, SEGMENT_KEYS

COVERAGE_SEGMENTS = SEGMENT_KEYS
COVERAGE_SLOTS = SKILL_KEYS
COVERAGE_WEIGHTS = {
    "serve": 0.25,
    "forehand": 0.25,
    "backhand": 0.25,
    "volley": 1.0 / 12,
    "footwork": 1.0 / 12,
    "rally": 1.0 / 12,
}
COVERAGE_CORE = ("serve", "forehand", "backhand")
FAMILIARITY_CAP = 4
FOCUS_TTL_DAYS = 3650
LEVEL_TO_NTRP = {
    "beginner": 2.0,
    "recreational": 3.0,
    "advanced": 4.0,
    "competitive": 5.0,
}
SCORE_CLOSE = 7.0
LOOK_CLOSE = 5.0
LOOK_TO_SLOT = {
    "technique": "preparation",
    "footwork": "footwork",
    "contact": "contact",
}


def get_plan(player_id: int):
    return billing.get_plan(player_id)


def has_quota(player_id: int) -> bool:
    return billing.has_quota(player_id)


def grant_pro(
    player_id: int,
    months: int = billing.PRO_MONTHS_DEFAULT,
    provider: str = billing.PROVIDER_STARS,
    payment_id: Optional[str] = None,
) -> dict:
    return billing.grant_pro(player_id, months, provider, payment_id)


def progress_scores(player_id: int, days: int = 90) -> list:
    return storage.get_progress_scores(player_id, days)


def load_analysis_context(player_id: int, stroke: Optional[str] = None) -> dict:
    focus_row = storage.get_player_focus(player_id, stroke)
    return {
        "history": storage.get_player_history(player_id),
        "profile": storage.get_player_profile(player_id),
        "corrections": storage.get_coach_corrections_for_prompt(player_id),
        "focus": (focus_row or {}).get("focus"),
        "drills_catalog": drills.catalog_for_prompt(),
    }


@dataclass
class PreparedReport:
    text: str
    scores: dict
    focus: str
    stroke: str
    drill_ids: list
    result: AnalysisResult
    primary_segment: str = ""
    detected_segments: Optional[list] = None
    intake_strokes: Optional[list] = None
    use_detect: bool = False
    accent_mismatch: bool = False
    write_full: str = ""
    write_secondary: Optional[list] = None


def intake_strokes_from_context(video_context: Optional[dict]) -> list:
    if not video_context:
        return []
    raw = video_context.get("strokes")
    if isinstance(raw, list):
        out = []
        seen = set()
        for item in raw:
            key = str(item).strip()
            if key in COVERAGE_SEGMENTS and key not in seen:
                seen.add(key)
                out.append(key)
        return out
    stroke = (video_context.get("stroke") or "").strip()
    if stroke in COVERAGE_SEGMENTS:
        return [stroke]
    return []


def compatibility_stroke(strokes: list) -> str:
    if len(strokes) == 1:
        return strokes[0]
    return "general"


def resolve_write_plan(
    intake_strokes: list,
    primary: str,
    detected: list,
) -> dict:
    """Куда писать покрытие (lock #80)."""
    detected = [s for s in detected if s in COVERAGE_SEGMENTS]
    if primary not in COVERAGE_SEGMENTS:
        primary = detected[0] if detected else ""
    if primary and primary not in detected:
        detected = [primary] + [s for s in detected if s != primary]

    if not intake_strokes:
        full = primary
        secondary = [s for s in detected if s != full]
        job_stroke = primary or "general"
        return {
            "job_stroke": job_stroke,
            "full": full,
            "secondary": secondary,
            "accent_mismatch": False,
        }

    if len(intake_strokes) == 1:
        accent = intake_strokes[0]
        if primary and primary != accent:
            return {
                "job_stroke": primary,
                "full": primary,
                "secondary": [s for s in detected if s != primary],
                "accent_mismatch": True,
            }
        return {
            "job_stroke": accent,
            "full": accent,
            "secondary": [],
            "accent_mismatch": False,
        }

    first = intake_strokes[0]
    if primary and primary not in intake_strokes:
        return {
            "job_stroke": primary,
            "full": primary,
            "secondary": [s for s in detected if s != primary],
            "accent_mismatch": True,
        }
    return {
        "job_stroke": first,
        "full": first,
        "secondary": [s for s in detected if s != first],
        "accent_mismatch": False,
    }


def prepare_report(
    result: AnalysisResult,
    video_context: Optional[dict] = None,
) -> PreparedReport:
    parsed = parse_report(result.text)
    use_detect = video_context is not None and "strokes" in video_context
    intake = intake_strokes_from_context(video_context) if use_detect else []
    if use_detect:
        plan = resolve_write_plan(
            intake, parsed.primary_segment, list(parsed.detected_segments or [])
        )
        stroke = plan["job_stroke"]
        mismatch = plan["accent_mismatch"]
        write_full = plan["full"]
        write_secondary = plan["secondary"]
    else:
        stroke = ""
        if video_context:
            stroke = (video_context.get("stroke") or "") or ""
        mismatch = False
        intake = intake_strokes_from_context(video_context)
        write_full = stroke if stroke in COVERAGE_SEGMENTS else ""
        write_secondary = []
    return PreparedReport(
        text=parsed.text,
        scores=parsed.scores,
        focus=parsed.focus or "",
        stroke=stroke,
        drill_ids=list(parsed.drill_ids or []),
        result=result,
        primary_segment=parsed.primary_segment,
        detected_segments=list(parsed.detected_segments or []),
        intake_strokes=intake,
        use_detect=use_detect,
        accent_mismatch=mismatch,
        write_full=write_full,
        write_secondary=write_secondary,
    )


def analyze_video(
    analyzer: VideoAnalyzer,
    video_path: Path,
    *,
    player_id: int,
    user_comment: Optional[str],
    video_context: Optional[dict],
    language_code: str,
    model: str,
) -> PreparedReport:
    stroke = ""
    if video_context:
        stroke = (video_context.get("stroke") or "") or ""
    ctx = load_analysis_context(player_id, stroke)
    result = analyzer.analyze(
        video_path,
        user_comment,
        ctx["history"],
        language_code,
        ctx["profile"],
        video_context,
        model,
        ctx["focus"],
        ctx["drills_catalog"],
        ctx["corrections"],
    )
    return prepare_report(result, video_context)


def save_analysis_session(
    player_id: int,
    prepared: PreparedReport,
    language_code: str,
) -> None:
    storage.save_session(
        player_id,
        prepared.text,
        language_code,
        prepared.scores,
        prepared.focus,
        prepared.stroke,
    )
    if prepared.focus and prepared.stroke in COVERAGE_SEGMENTS:
        storage.set_player_focus(
            player_id, prepared.focus, prepared.stroke, FOCUS_TTL_DAYS
        )


def enqueue_review(
    player_id: int,
    prepared: PreparedReport,
    *,
    language_code: str,
    video_file_id: str,
    video_mime: str,
    drill_text: str = "",
    drill_id: Optional[str] = None,
    source_channel: str = storage.CHANNEL_TELEGRAM,
    look: str = "",
) -> int:
    job_id = storage.create_review_job(
        player_id,
        video_file_id=video_file_id,
        video_mime=video_mime,
        language_code=language_code,
        draft_text=prepared.text,
        focus_text=prepared.focus,
        drill_text=drill_text,
        drill_id=drill_id,
        scores=prepared.scores,
        stroke=prepared.stroke,
        source_channel=source_channel,
        accent_mismatch=prepared.accent_mismatch,
        detected_json=json.dumps(prepared.detected_segments or [], ensure_ascii=False),
        intake_strokes_json=json.dumps(prepared.intake_strokes or [], ensure_ascii=False),
    )
    apply_coverage(player_id, job_id, prepared, look=look)
    if prepared.focus and prepared.stroke in COVERAGE_SEGMENTS:
        storage.set_player_focus(
            player_id, prepared.focus, prepared.stroke, FOCUS_TTL_DAYS
        )
    return job_id


def apply_coverage(
    player_id: int,
    job_id: int,
    prepared: PreparedReport,
    look: str = "",
) -> list:
    look_slot = LOOK_TO_SLOT.get((look or "").strip().lower())
    full = (prepared.write_full or "").strip()
    secondary = list(prepared.write_secondary or [])
    if not prepared.use_detect:
        full = (prepared.stroke or "").strip()
        secondary = []
    added = []
    if full in COVERAGE_SEGMENTS:
        added.extend(
            _write_segment_slots(
                player_id, job_id, prepared, full, look_slot, max_slots=None
            )
        )
    for segment in secondary:
        if segment not in COVERAGE_SEGMENTS or segment == full:
            continue
        added.extend(
            _write_segment_slots(
                player_id, job_id, prepared, segment, "", max_slots=1
            )
        )
    return added


def _write_segment_slots(
    player_id: int,
    job_id: int,
    prepared: PreparedReport,
    segment: str,
    look_slot: str,
    max_slots: Optional[int],
) -> list:
    ranked = []
    for slot in COVERAGE_SLOTS:
        score = prepared.scores.get(slot)
        if score is None:
            continue
        need = LOOK_CLOSE if slot == look_slot else SCORE_CLOSE
        if float(score) < need:
            continue
        ranked.append((float(score), slot))
    ranked.sort(key=lambda row: -row[0])
    if max_slots is not None:
        ranked = ranked[:max_slots]
    added = []
    for _, slot in ranked:
        storage.add_coverage_contribution(player_id, job_id, segment, slot)
        added.append({"segment": segment, "slot": slot, "status": "pending"})
    return added


def _parse_job_scores(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _mean_skill_scores(scores: dict) -> Optional[float]:
    values = []
    for key in COVERAGE_SLOTS:
        value = scores.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _round1(value: float) -> float:
    return round(float(value), 1)


def _familiarity(count: int, mean: Optional[float]) -> float:
    if count <= 0 or mean is None:
        return 0.0
    return _round1(min(count / FAMILIARITY_CAP, 1.0) * (mean / 10.0) * 100.0)


def _progress_percent(mean: Optional[float]) -> float:
    if mean is None:
        return 0.0
    return _round1(mean / 10.0 * 100.0)


def _pool_stats(jobs: list) -> tuple:
    count = len(jobs)
    means = []
    for job in jobs:
        mean = _mean_skill_scores(_parse_job_scores(job.get("scores_json")))
        if mean is not None:
            means.append(mean)
    mean = sum(means) / len(means) if means else None
    return count, mean, _familiarity(count, mean), _progress_percent(mean)


def _round_ntrp(value: float) -> float:
    return round(float(value) * 2.0 + 1e-9) / 2.0


def ensure_ntrp_seed(player_id: int) -> Optional[float]:
    row = storage.get_player_ntrp_row(player_id)
    if row.get("ntrp_locked"):
        return row.get("ntrp")
    seed = row.get("ntrp_seed")
    if seed is None:
        profile = storage.get_player_profile(player_id) or {}
        if not profile.get("skipped"):
            seed = LEVEL_TO_NTRP.get(profile.get("level") or "")
        if seed is not None:
            current = row.get("ntrp")
            storage.set_player_ntrp(
                player_id,
                current if current is not None else seed,
                seed=seed,
            )
            return current if current is not None else seed
    return row.get("ntrp") if row.get("ntrp") is not None else seed


def apply_ntrp(player_id: int, progress_mean: float, core_counts: dict) -> Optional[float]:
    row = storage.get_player_ntrp_row(player_id)
    if row.get("ntrp_locked"):
        value = row.get("ntrp")
        return None if value is None else _round1(float(value))
    current = ensure_ntrp_seed(player_id)
    row = storage.get_player_ntrp_row(player_id)
    current = row.get("ntrp") if row.get("ntrp") is not None else current
    core_with_jobs = sum(1 for key in COVERAGE_CORE if core_counts.get(key, 0) >= 1)
    if core_with_jobs < 2:
        return None if current is None else _round1(float(current))
    raw = 2.0 + 3.0 * (float(progress_mean) / 10.0)
    stepped = max(2.0, min(5.0, _round_ntrp(raw)))
    if current is not None:
        delta = max(-0.5, min(0.5, stepped - float(current)))
        stepped = max(2.0, min(5.0, _round_ntrp(float(current) + delta)))
    storage.set_player_ntrp(player_id, stepped)
    return _round1(stepped)


def player_ntrp(player_id: int) -> Optional[float]:
    scales = compute_player_scales(player_id)
    return apply_ntrp(
        player_id,
        scales["player"]["progress_mean_pending"],
        {
            segment["id"]: segment["job_count_pending"]
            for segment in scales["segments"]
        },
    )


def compute_player_scales(player_id: int) -> dict:
    rows = storage.list_coverage_contributions(player_id)
    pending_slots: dict = {s: set() for s in COVERAGE_SEGMENTS}
    committed_slots: dict = {s: set() for s in COVERAGE_SEGMENTS}
    for row in rows:
        segment = row.get("segment") or ""
        slot = row.get("slot") or ""
        if segment not in pending_slots or slot not in COVERAGE_SLOTS:
            continue
        status = row.get("status") or "pending"
        if status == "voided":
            continue
        pending_slots[segment].add(slot)
        if status == "committed":
            committed_slots[segment].add(slot)
    voided = storage.voided_job_ids(player_id)
    jobs = [
        job
        for job in storage.list_scale_jobs(player_id)
        if int(job["id"]) not in voided
    ]
    pending_jobs: dict = {s: [] for s in COVERAGE_SEGMENTS}
    committed_jobs: dict = {s: [] for s in COVERAGE_SEGMENTS}
    latest_by_segment: dict = {}
    for job in jobs:
        segment = job.get("stroke") or ""
        if segment not in pending_jobs:
            continue
        pending_jobs[segment].append(job)
        if job.get("status") == "sent_coach":
            committed_jobs[segment].append(job)
        if segment not in latest_by_segment:
            latest_by_segment[segment] = job
    foci = {
        row.get("stroke"): (row.get("focus") or "").strip()
        for row in storage.list_player_foci(player_id)
        if row.get("stroke")
    }
    segments = []
    player_fam_pending = 0.0
    player_fam_committed = 0.0
    player_prog_pending = 0.0
    player_prog_committed = 0.0
    core_committed_positive = 0
    for segment in COVERAGE_SEGMENTS:
        p_count, p_mean, p_fam, p_prog = _pool_stats(pending_jobs[segment])
        c_count, c_mean, c_fam, c_prog = _pool_stats(committed_jobs[segment])
        weight = COVERAGE_WEIGHTS[segment]
        player_fam_pending += weight * p_fam
        player_fam_committed += weight * c_fam
        player_prog_pending += weight * (p_mean or 0.0)
        player_prog_committed += weight * (c_mean or 0.0)
        if segment in COVERAGE_CORE and c_count > 0:
            core_committed_positive += 1
        slots = []
        for slot in COVERAGE_SLOTS:
            slots.append(
                {
                    "id": slot,
                    "pending": slot in pending_slots[segment],
                    "committed": slot in committed_slots[segment],
                }
            )
        next_to_film = [s["id"] for s in slots if not s["pending"]]
        focus_text = foci.get(segment) or ""
        latest = latest_by_segment.get(segment)
        focus_status = ""
        if focus_text:
            if latest and latest.get("status") == "sent_coach":
                focus_status = "agreed"
            else:
                focus_status = "supervision"
        p_mean_out = None if p_mean is None else _round1(p_mean)
        c_mean_out = None if c_mean is None else _round1(c_mean)
        segments.append(
            {
                "id": segment,
                "coverage_pending": p_fam,
                "coverage_committed": c_fam,
                "familiarity_pending": p_fam,
                "familiarity_committed": c_fam,
                "progress_pending": p_prog,
                "progress_committed": c_prog,
                "progress_mean_pending": p_mean_out,
                "progress_mean_committed": c_mean_out,
                "job_count_pending": p_count,
                "job_count_committed": c_count,
                "focus": focus_text,
                "focus_status": focus_status,
                "slots": slots,
                "next_to_film": next_to_film,
            }
        )
    player_fam_pending = _round1(player_fam_pending)
    player_fam_committed = _round1(player_fam_committed)
    player_prog_pending = _round1(player_prog_pending)
    player_prog_committed = _round1(player_prog_committed)
    return {
        "player": {
            "coverage_pending": player_fam_pending,
            "coverage_committed": player_fam_committed,
            "familiarity_pending": player_fam_pending,
            "familiarity_committed": player_fam_committed,
            "progress_pending": _progress_percent(player_prog_pending),
            "progress_committed": _progress_percent(player_prog_committed),
            "progress_mean_pending": player_prog_pending,
            "progress_mean_committed": player_prog_committed,
            "goals_unlocked": player_fam_committed >= 40 and core_committed_positive >= 2,
        },
        "segments": segments,
    }


def dossier_payload(player_id: int) -> dict:
    scales = compute_player_scales(player_id)
    core_counts = {
        segment["id"]: segment["job_count_pending"]
        for segment in scales["segments"]
    }
    ntrp = apply_ntrp(
        player_id, scales["player"]["progress_mean_pending"], core_counts
    )
    scales["player"]["ntrp"] = ntrp
    return scales


def job_coverage_payload(job_id: int) -> dict:
    rows = storage.list_coverage_for_job(job_id)
    job = storage.get_review_job(job_id) or {}
    detected = []
    raw = job.get("detected_json") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                detected = [str(s) for s in parsed if str(s).strip()]
        except json.JSONDecodeError:
            detected = []
    return {
        "accent_mismatch": bool(job.get("accent_mismatch")),
        "primary_segment": job.get("stroke") or "",
        "detected_segments": detected,
        "contributions": [
            {
                "segment": r.get("segment") or "",
                "slot": r.get("slot") or "",
                "status": r.get("status") or "pending",
            }
            for r in rows
        ],
    }


def report_payload(text: str) -> dict:
    parsed = parse_report(text)
    return {
        "markdown": parsed.text,
        "scores": parsed.scores,
        "focus": parsed.focus,
        "drills": parsed.drill_ids,
        "findings": parsed.findings,
        "summary": parsed.summary,
        "next_video": parsed.next_video,
        "stroke": "",
    }
