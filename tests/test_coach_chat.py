"""Тесты фидбэка живого тренера и голосовых сообщений в чате разбора."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

import bot
import coach_media
import http_api
import review
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "coach_chat.db")


def _auth(client: TestClient, sub: str = "sub-coach-1"):
    res = client.post("/v1/auth/apple", json={"identity_token": sub})
    assert res.status_code == 200
    return res.json()["token"], res.json()["player_id"]


def _make_job(
    player_id: int,
    *,
    text: str = "Черновик разбора подачи.",
    forum_chat_id: int = -100500,
    thread_id: int = 77,
) -> int:
    job_id = storage.create_review_job(
        player_id,
        video_file_id="ios:clip",
        draft_text=text,
        source_channel=storage.CHANNEL_IOS,
        stroke="serve",
    )
    storage.update_review_job(
        job_id,
        forum_chat_id=forum_chat_id,
        message_thread_id=thread_id,
    )
    storage.mark_review_sent(job_id, status=review.STATUS_AI_SENT, final_text=text)
    return job_id


def _forum_settings():
    return SimpleNamespace(
        coach_forum_chat_id=-100500,
        is_coach=lambda uid: uid == 777,
    )


def _coach_update(
    *,
    text=None,
    caption=None,
    voice=None,
    audio=None,
    photo=None,
    message_id: int = 501,
    thread_id: int = 77,
    reply_to_message=None,
):
    msg = MagicMock()
    msg.chat_id = -100500
    msg.message_thread_id = thread_id
    msg.message_id = message_id
    msg.from_user = SimpleNamespace(id=777)
    msg.text = text
    msg.caption = caption
    msg.voice = voice
    msg.audio = audio
    msg.photo = photo
    msg.video = None
    msg.video_note = None
    msg.document = None
    msg.sticker = None
    msg.animation = None
    msg.contact = None
    msg.location = None
    msg.venue = None
    msg.poll = None
    msg.dice = None
    msg.reply_to_message = reply_to_message
    msg.reply_text = AsyncMock()
    upd = MagicMock()
    upd.message = msg
    return upd


def _coach_context(settings):
    ctx = MagicMock()
    ctx.application.bot_data = {"settings": settings}
    ctx.bot.send_message = AsyncMock()
    ctx.bot.copy_message = AsyncMock()
    ctx.bot.get_file = AsyncMock()
    return ctx


def test_coach_messages_survive_ai_trim_and_stay_out_of_ai_history(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_apple_player("sub-trim")
        job_id = _make_job(player_id)

        coach_id = storage.append_coach_message(
            job_id,
            kind="text",
            text="Совет от живого тренера",
            telegram_message_id=10,
        )
        storage.append_player_coach_message(job_id, "Уточнение живому тренеру")

        for i in range(1, 13):
            storage.append_job_chat_turn(job_id, f"ai q {i}", f"ai a {i}")

        messages = storage.list_job_messages(job_id)
        coach_msgs = [m for m in messages if m["role"] == "coach"]
        player_to_coach = [
            m for m in messages if m["role"] == "user" and m["target"] == "coach"
        ]
        ai_msgs = [m for m in messages if m["target"] == "ai"]

        assert len(coach_msgs) == 1
        assert coach_msgs[0]["id"] == coach_id
        assert coach_msgs[0]["text"] == "Совет от живого тренера"
        assert len(player_to_coach) == 1
        assert player_to_coach[0]["text"] == "Уточнение живому тренеру"
        assert len(ai_msgs) == 20
        assert ai_msgs[0]["text"] == "ai q 3"

        history = storage.job_chat_history(job_id)
        assert len(history) == 10
        assert all("живого тренера" not in pair["user"] for pair in history)


def test_coach_text_delivered_to_ios_only_player_without_telegram(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_apple_player("sub-ios-only")
        storage.save_player_forum_topic(player_id, -100500, 77, title="Player")
        job_id = _make_job(player_id)

        settings = _forum_settings()
        update = _coach_update(text="Подброс чуть правее и выше", message_id=900)
        context = _coach_context(settings)

        ok = asyncio.run(bot._handle_coach_forum_message(update, context))
        assert ok is True
        context.bot.send_message.assert_not_awaited()
        reply_text = update.message.reply_text.await_args.args[0]
        assert "iOS" in reply_text
        assert f"#{job_id}" in reply_text

        msgs = storage.list_job_messages(job_id)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "coach"
        assert msgs[0]["kind"] == "text"
        assert msgs[0]["text"] == "Подброс чуть правее и выше"

        summary = storage.job_coach_summary(job_id)
        assert summary == {"count": 1, "last_id": msgs[0]["id"]}


def test_coach_reply_binds_to_referenced_older_job(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_apple_player("sub-reply-bind")
        storage.save_player_forum_topic(player_id, -100500, 77, title="Player")
        job1 = _make_job(player_id)
        job2 = _make_job(player_id)
        storage.save_forum_job_message(-100500, 300, job1)

        settings = _forum_settings()
        reply_ref = SimpleNamespace(message_id=300, text="старый пост", caption=None)
        update = _coach_update(
            text="Комментарий именно к первому видео",
            message_id=901,
            reply_to_message=reply_ref,
        )
        context = _coach_context(settings)

        assert asyncio.run(bot._handle_coach_forum_message(update, context)) is True
        assert len(storage.list_job_messages(job1)) == 1
        assert len(storage.list_job_messages(job2)) == 0


def test_coach_unsupported_media_warns_for_ios_only_player(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_apple_player("sub-photo")
        storage.save_player_forum_topic(player_id, -100500, 77, title="Player")
        _make_job(player_id)

        settings = _forum_settings()
        update = _coach_update(photo=[MagicMock()], message_id=902)
        context = _coach_context(settings)

        assert asyncio.run(bot._handle_coach_forum_message(update, context)) is True
        reply_text = update.message.reply_text.await_args.args[0]
        assert "только текст и голосовые" in reply_text


def test_post_message_to_coach_forwards_to_forum_and_persists(tmp_path):
    forwarded = []

    async def fake_forward(player_id, job_id, text):
        forwarded.append((player_id, job_id, text))
        return 4242

    with _tmp_db(tmp_path):
        client = TestClient(
            http_api.create_app(
                verify_apple=lambda token: token,
                forward_to_coach=fake_forward,
            )
        )
        token, player_id = _auth(client)
        headers = {"Authorization": "Bearer " + token}
        job_id = _make_job(player_id)

        res = client.post(
            f"/v1/jobs/{job_id}/messages",
            json={
                "text": "Тренер, глянь пожалуйста колено на 0:04",
                "language_code": "ru",
                "target": "coach",
            },
            headers=headers,
        )
        assert res.status_code == 200
        msgs = res.json()["messages"]
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["target"] == "coach"
        assert msgs[0]["text"] == "Тренер, глянь пожалуйста колено на 0:04"
        assert forwarded == [
            (player_id, job_id, "Тренер, глянь пожалуйста колено на 0:04")
        ]

        bad = client.post(
            f"/v1/jobs/{job_id}/messages",
            json={"text": "hi", "language_code": "ru", "target": "unknown"},
            headers=headers,
        )
        assert bad.status_code == 400


def test_voice_media_endpoint_and_job_summary_access_control(tmp_path):
    with _tmp_db(tmp_path):
        client = TestClient(http_api.create_app(verify_apple=lambda token: token))
        token, player_id = _auth(client, "sub-owner")
        other_token, _ = _auth(client, "sub-other")
        headers = {"Authorization": "Bearer " + token}
        other_headers = {"Authorization": "Bearer " + other_token}
        job_id = _make_job(player_id)

        rel_path = f"{player_id}/{job_id}_777.m4a"
        dst = coach_media.media_root() / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        payload = b"fake-m4a-audio-bytes"
        dst.write_bytes(payload)

        msg_id = storage.append_coach_message(
            job_id,
            kind="voice",
            text="Слушай с 5 секунды",
            media_path=rel_path,
            media_mime="audio/mp4",
            duration_sec=19,
            waveform=[0.2, 0.8, 0.5],
            telegram_message_id=777,
        )

        job_res = client.get(f"/v1/jobs/{job_id}", headers=headers)
        assert job_res.status_code == 200
        assert job_res.json()["coach_messages_count"] == 1
        assert job_res.json()["last_coach_message_id"] == msg_id

        msgs_res = client.get(f"/v1/jobs/{job_id}/messages", headers=headers)
        assert msgs_res.status_code == 200
        item = msgs_res.json()["messages"][0]
        assert item["id"] == msg_id
        assert item["role"] == "coach"
        assert item["kind"] == "voice"
        assert item["text"] == "Слушай с 5 секунды"
        assert item["audio"] == {"duration_sec": 19, "waveform": [0.2, 0.8, 0.5]}

        media_res = client.get(
            f"/v1/jobs/{job_id}/media/{msg_id}", headers=headers
        )
        assert media_res.status_code == 200
        assert media_res.content == payload
        assert "audio/mp4" in media_res.headers["content-type"]

        # Другой игрок не может скачать чужое голосовое
        denied = client.get(
            f"/v1/jobs/{job_id}/media/{msg_id}", headers=other_headers
        )
        assert denied.status_code == 404

        # Удаление аккаунта чистит и аудиофайл
        del_res = client.delete("/v1/me", headers=headers)
        assert del_res.status_code == 204
        assert not dst.exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="нужен ffmpeg")
def test_transcode_voice_to_m4a_produces_playable_file_and_waveform(tmp_path):
    with _tmp_db(tmp_path):
        src = tmp_path / "sample.ogg"
        res = subprocess.run(
            [
                shutil.which("ffmpeg"),
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:a",
                "libopus",
                str(src),
            ],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            # Если libopus не собран в локальном ffmpeg, генерируем wav как вход
            src = tmp_path / "sample.wav"
            subprocess.run(
                [
                    shutil.which("ffmpeg"),
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    str(src),
                ],
                check=True,
            )

        meta = coach_media.transcode_voice_to_m4a(
            src,
            player_id=42,
            job_id=9,
            message_key="101",
            duration_hint=2,
        )
        assert meta["media_mime"] == "audio/mp4"
        assert meta["duration_sec"] == 2
        assert len(meta["waveform"]) > 0
        resolved = coach_media.resolve_media_path(meta["media_path"])
        assert resolved is not None and resolved.stat().st_size > 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="нужен ffmpeg")
def test_coach_forum_voice_end_to_end_to_ios_http(tmp_path):
    with _tmp_db(tmp_path):
        client = TestClient(http_api.create_app(verify_apple=lambda token: token))
        token, player_id = _auth(client, "sub-voice-e2e")
        headers = {"Authorization": "Bearer " + token}
        storage.save_player_forum_topic(player_id, -100500, 77, title="Player")
        job_id = _make_job(player_id)

        sample = tmp_path / "coach.wav"
        subprocess.run(
            [
                shutil.which("ffmpeg"),
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=520:duration=2",
                str(sample),
            ],
            check=True,
        )

        async def fake_download(custom_path):
            Path(custom_path).write_bytes(sample.read_bytes())

        tg_file = MagicMock()
        tg_file.download_to_drive = AsyncMock(side_effect=fake_download)

        settings = _forum_settings()
        voice = SimpleNamespace(file_id="tg-voice-1", duration=2)
        update = _coach_update(voice=voice, caption="Послушай про локоть", message_id=955)
        context = _coach_context(settings)
        context.bot.get_file = AsyncMock(return_value=tg_file)

        assert asyncio.run(bot._handle_coach_forum_message(update, context)) is True
        reply_text = update.message.reply_text.await_args.args[0]
        assert "iOS" in reply_text

        msgs = client.get(f"/v1/jobs/{job_id}/messages", headers=headers).json()["messages"]
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg["role"] == "coach"
        assert msg["kind"] == "voice"
        assert msg["text"] == "Послушай про локоть"
        assert msg["audio"]["duration_sec"] == 2
        assert len(msg["audio"]["waveform"]) > 0

        media_res = client.get(
            f"/v1/jobs/{job_id}/media/{msg['id']}", headers=headers
        )
        assert media_res.status_code == 200
        assert len(media_res.content) > 100


def test_forward_ios_message_to_coach_records_forum_mapping(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_apple_player("sub-fwd")
        storage.set_player_display_name(player_id, "Иван")
        storage.save_player_forum_topic(player_id, -100500, 77, title="Player")
        job_id = _make_job(player_id)

        application = MagicMock()
        application.bot_data = {"settings": _forum_settings()}
        application.bot.send_message = AsyncMock(
            return_value=SimpleNamespace(message_id=8888)
        )

        sent_id = asyncio.run(
            bot.forward_ios_message_to_coach(
                application, player_id, job_id, "Вопрос живому тренеру"
            )
        )
        assert sent_id == 8888
        assert storage.get_job_id_by_forum_message(-100500, 8888) == job_id
        kwargs = application.bot.send_message.await_args.kwargs
        assert kwargs["chat_id"] == -100500
        assert kwargs["message_thread_id"] == 77
        assert f"#{job_id}" in kwargs["text"]
        assert "Вопрос живому тренеру" in kwargs["text"]
