"""Доменный слой без типов Telegram: квота, анализ, очередь, прогресс."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import billing
import drills
import storage
from analyzer import AnalysisResult, VideoAnalyzer
from report_parser import SKILL_KEYS, parse_report

COVERAGE_SEGMENTS = (
    "forehand",
    "backhand",
    "serve",
    "volley",
    "footwork",
    "rally",
)
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


def load_analysis_context(player_id: int) -> dict:
    focus_row = storage.get_player_focus(player_id)
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


def prepare_report(
    result: AnalysisResult,
    video_context: Optional[dict] = None,
) -> PreparedReport:
    parsed = parse_report(result.text)
    stroke = ""
    if video_context:
        stroke = (video_context.get("stroke") or "") or ""
    return PreparedReport(
        text=parsed.text,
        scores=parsed.scores,
        focus=parsed.focus or "",
        stroke=stroke,
        drill_ids=list(parsed.drill_ids or []),
        result=result,
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
    ctx = load_analysis_context(player_id)
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
    if prepared.focus:
        storage.set_player_focus(player_id, prepared.focus, prepared.stroke or None, 7)


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
    )
    apply_coverage(player_id, job_id, prepared, look=look)
    return job_id


def apply_coverage(
    player_id: int,
    job_id: int,
    prepared: PreparedReport,
    look: str = "",
) -> list:
    segment = (prepared.stroke or "").strip()
    if segment not in COVERAGE_SEGMENTS:
        return []
    look_slot = LOOK_TO_SLOT.get((look or "").strip().lower())
    added = []
    for slot in COVERAGE_SLOTS:
        score = prepared.scores.get(slot)
        if score is None:
            continue
        need = LOOK_CLOSE if slot == look_slot else SCORE_CLOSE
        if float(score) < need:
            continue
        storage.add_coverage_contribution(player_id, job_id, segment, slot)
        added.append({"segment": segment, "slot": slot, "status": "pending"})
    return added


def _segment_coverage(filled: set, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * len(filled) / total, 1)


def dossier_payload(player_id: int) -> dict:
    rows = storage.list_coverage_contributions(player_id)
    pending_by: dict = {s: set() for s in COVERAGE_SEGMENTS}
    committed_by: dict = {s: set() for s in COVERAGE_SEGMENTS}
    for row in rows:
        segment = row.get("segment") or ""
        slot = row.get("slot") or ""
        if segment not in pending_by or slot not in COVERAGE_SLOTS:
            continue
        status = row.get("status") or "pending"
        if status == "voided":
            continue
        pending_by[segment].add(slot)
        if status == "committed":
            committed_by[segment].add(slot)
    slot_total = len(COVERAGE_SLOTS)
    segments = []
    player_pending = 0.0
    player_committed = 0.0
    core_committed_positive = 0
    for segment in COVERAGE_SEGMENTS:
        pending_pct = _segment_coverage(pending_by[segment], slot_total)
        committed_pct = _segment_coverage(committed_by[segment], slot_total)
        weight = COVERAGE_WEIGHTS[segment]
        player_pending += weight * pending_pct
        player_committed += weight * committed_pct
        if segment in COVERAGE_CORE and committed_pct > 0:
            core_committed_positive += 1
        slots = []
        for slot in COVERAGE_SLOTS:
            slots.append(
                {
                    "id": slot,
                    "pending": slot in pending_by[segment],
                    "committed": slot in committed_by[segment],
                }
            )
        next_to_film = [s["id"] for s in slots if not s["pending"]]
        segments.append(
            {
                "id": segment,
                "coverage_pending": pending_pct,
                "coverage_committed": committed_pct,
                "slots": slots,
                "next_to_film": next_to_film,
            }
        )
    player_pending = round(player_pending, 1)
    player_committed = round(player_committed, 1)
    return {
        "player": {
            "coverage_pending": player_pending,
            "coverage_committed": player_committed,
            "goals_unlocked": player_committed >= 40 and core_committed_positive >= 2,
        },
        "segments": segments,
    }


def job_coverage_payload(job_id: int) -> dict:
    rows = storage.list_coverage_for_job(job_id)
    return {
        "accent_mismatch": False,
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
        "stroke": "",
    }
