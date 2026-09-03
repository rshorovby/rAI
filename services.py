"""Доменный слой без типов Telegram: квота, анализ, очередь, прогресс."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import billing
import drills
import storage
from analyzer import AnalysisResult, VideoAnalyzer
from report_parser import parse_report


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
) -> int:
    return storage.create_review_job(
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
    )


def report_payload(text: str) -> dict:
    parsed = parse_report(text)
    return {
        "markdown": parsed.text,
        "scores": parsed.scores,
        "focus": parsed.focus,
        "drills": parsed.drill_ids,
        "stroke": "",
    }
