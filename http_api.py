"""HTTP API канала iOS. Без IAP."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

import services
import storage
from i18n import resolve_ui_lang

logger = logging.getLogger(__name__)


def enqueue_ios_job_live(
    player_id,
    path,
    video_context=None,
    comment=None,
    language_code="ru",
):
    from analyzer import VideoAnalyzer
    from config import load_settings

    settings = load_settings()
    analyzer = VideoAnalyzer(settings.gemini_api_key, settings.gemini_model)
    prepared = services.analyze_video(
        analyzer,
        Path(path),
        player_id=player_id,
        user_comment=comment,
        video_context=video_context,
        language_code=language_code,
        model=settings.gemini_model,
    )
    services.save_analysis_session(player_id, prepared, language_code)
    return services.enqueue_review(
        player_id,
        prepared,
        language_code=language_code,
        video_file_id="ios:" + path,
        video_mime="video/mp4",
        source_channel=storage.CHANNEL_IOS,
    )


VerifyApple = Callable[[str], str]


class AuthError(Exception):
    pass


def _bearer_player(request: Request) -> int:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        raise AuthError("missing token")
    token = header.split(" ", 1)[1].strip()
    player_id = storage.player_id_for_session(token)
    if player_id is None:
        raise AuthError("invalid token")
    request.state.token = token
    request.state.player_id = player_id
    return player_id


def _job_json(job: dict) -> dict:
    scores = {}
    raw = job.get("scores_json") or ""
    if raw:
        try:
            scores = json.loads(raw)
        except json.JSONDecodeError:
            scores = {}
    text = (job.get("final_text") or "").strip() or (job.get("draft_text") or "")
    parsed = (
        services.report_payload(text)
        if text
        else {
            "markdown": "",
            "scores": scores,
            "focus": job.get("focus_text") or "",
            "drills": [],
            "stroke": job.get("stroke") or "",
        }
    )
    if not parsed.get("stroke"):
        parsed["stroke"] = job.get("stroke") or ""
    if scores and not parsed.get("scores"):
        parsed["scores"] = scores
    return {
        "id": job["id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "source_channel": job.get("source_channel") or storage.CHANNEL_TELEGRAM,
        "stroke": job.get("stroke") or "",
        "focus": job.get("focus_text") or "",
        "markdown": parsed.get("markdown") or text,
        "scores": parsed.get("scores") or {},
        "drills": parsed.get("drills") or [],
    }


def _me_json(player_id: int, language_code: str = "") -> dict:
    lang = language_code or storage.player_language_code(player_id)
    return {
        "player_id": player_id,
        "telegram_linked": storage.player_has_telegram(player_id),
        "language_code": resolve_ui_lang(lang or None),
    }


def create_app(
    *,
    verify_apple: Optional[VerifyApple] = None,
    enqueue_ios_job: Optional[Callable] = None,
) -> Starlette:
    if verify_apple is None:
        from apple_auth import verify_apple_identity_token

        verify_apple = verify_apple_identity_token

    async def auth_apple(request: Request) -> Response:
        body = await request.json()
        token = (body.get("identity_token") or "").strip()
        language_code = (body.get("language_code") or "").strip()
        if not token:
            return JSONResponse({"error": "identity_token required"}, status_code=400)
        try:
            sub = verify_apple(token)
        except Exception:
            logger.exception("apple token verify failed")
            return JSONResponse({"error": "invalid apple token"}, status_code=401)
        player_id = storage.get_or_create_apple_player(sub)
        session = storage.create_api_session(player_id)
        payload = _me_json(player_id, language_code)
        payload["token"] = session
        return JSONResponse(payload)

    async def me(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        return JSONResponse(_me_json(player_id))

    async def logout(request: Request) -> Response:
        try:
            _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        storage.delete_api_session(request.state.token)
        return Response(status_code=204)

    async def delete_me(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        storage.delete_player_account(player_id)
        return Response(status_code=204)

    async def link_telegram(request: Request) -> Response:
        try:
            ios_player = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        body = await request.json()
        code = body.get("code") or ""
        telegram_player = storage.consume_link_code(code, storage.LINK_TG_TO_IOS)
        if telegram_player is None:
            return JSONResponse({"error": "invalid code"}, status_code=400)
        if storage.has_player_history(ios_player):
            return JSONResponse({"error": "ios account not empty"}, status_code=409)
        if ios_player != telegram_player:
            storage.move_apple_identity(ios_player, telegram_player)
        session = storage.create_api_session(telegram_player)
        payload = _me_json(telegram_player)
        payload["token"] = session
        return JSONResponse(payload)

    async def app_code(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        code = storage.create_link_code(player_id, storage.LINK_IOS_TO_TG)
        return JSONResponse({"code": code, "expires_in": 600})

    async def create_job(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        form = await request.form()
        upload = form.get("video")
        if upload is None:
            return JSONResponse({"error": "video required"}, status_code=400)
        stroke = (form.get("stroke") or "") or ""
        look = (form.get("look") or "") or ""
        comment = (form.get("comment") or "") or ""
        language_code = (form.get("language_code") or "") or "ru"
        if not services.has_quota(player_id):
            return JSONResponse({"error": "quota"}, status_code=403)
        suffix = ".mp4"
        filename = getattr(upload, "filename", "") or ""
        if "." in filename:
            suffix = "." + filename.rsplit(".", 1)[-1]
        data = await upload.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.close()
        path = tmp.name
        video_context = {}
        if stroke:
            video_context["stroke"] = stroke
        if look:
            video_context["look"] = look
        if enqueue_ios_job is not None:
            job_id = enqueue_ios_job(
                player_id,
                path,
                video_context=video_context or None,
                comment=comment or None,
                language_code=language_code,
            )
        else:
            job_id = storage.create_review_job(
                player_id,
                video_file_id="ios:" + path,
                language_code=language_code,
                draft_text="",
                stroke=stroke,
                source_channel=storage.CHANNEL_IOS,
            )
        job = storage.get_review_job(job_id)
        return JSONResponse(_job_json(job), status_code=201)

    async def list_jobs(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        open_only = request.query_params.get("open") == "1"
        jobs = storage.list_player_jobs(player_id, open_only=open_only)
        return JSONResponse({"jobs": [_job_json(j) for j in jobs]})

    async def get_job(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        job_id = int(request.path_params["job_id"])
        job = storage.get_review_job(job_id)
        if not job or int(job["user_id"]) != player_id:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(_job_json(job))

    async def progress(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        rows = services.progress_scores(player_id, 90)
        return JSONResponse({"rows": rows})

    async def device_tokens(request: Request) -> Response:
        try:
            player_id = _bearer_player(request)
        except AuthError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        body = await request.json()
        token = (body.get("token") or "").strip()
        if not token:
            return JSONResponse({"error": "token required"}, status_code=400)
        storage.save_device_token(player_id, token)
        return Response(status_code=204)

    routes = [
        Route("/v1/auth/apple", auth_apple, methods=["POST"]),
        Route("/v1/me", me, methods=["GET"]),
        Route("/v1/me/logout", logout, methods=["POST"]),
        Route("/v1/me", delete_me, methods=["DELETE"]),
        Route("/v1/link/telegram", link_telegram, methods=["POST"]),
        Route("/v1/link/app-code", app_code, methods=["POST"]),
        Route("/v1/jobs", create_job, methods=["POST"]),
        Route("/v1/jobs", list_jobs, methods=["GET"]),
        Route("/v1/jobs/{job_id:int}", get_job, methods=["GET"]),
        Route("/v1/progress", progress, methods=["GET"]),
        Route("/v1/device-tokens", device_tokens, methods=["POST"]),
    ]
    return Starlette(routes=routes)
