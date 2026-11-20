from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from starlette.testclient import TestClient

import http_api
import services
import storage
from analyzer import AnalysisResult
from pricing import Usage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "http.db")


def _job(client, token, player_id, text="Черновик разбора подачи."):
    job_id = storage.create_review_job(
        player_id,
        video_file_id="ios:clip",
        draft_text=text,
        source_channel=storage.CHANNEL_IOS,
        stroke="serve",
    )
    storage.mark_review_sent(job_id, status="ai_sent", final_text=text)
    return job_id


def _auth(client):
    res = client.post("/v1/auth/apple", json={"identity_token": "sub-chat"})
    return res.json()["token"], res.json()["player_id"]


def test_followup_is_scoped_and_refuses_other_topics(tmp_path):
    seen = {}

    class Fake:
        def chat(self, *args, **kwargs):
            seen["scoped"] = kwargs.get("scoped")
            seen["report"] = args[0]
            seen["history"] = args[1]
            return AnalysisResult(
                text="OUT_OF_SCOPE",
                usage=Usage(),
                model="gemini-3.1-pro-preview",
            )

    settings = SimpleNamespace(
        model_for=lambda is_pro=False: "gemini-3.1-pro-preview",
        gemini_model="gemini-3.1-pro-preview",
        gemini_api_key="test",
    )
    with (
        _tmp_db(tmp_path),
        patch("config.load_settings", return_value=settings),
        patch.object(storage, "log_usage") as logged,
    ):
        text = services.answer_job_followup(
            1,
            "отчёт",
            [{"user": "а", "assistant": "б"}],
            "кто победит на выборах",
            "ru",
            "serve",
            analyzer=Fake(),
        )
    assert seen["scoped"] is True
    assert seen["report"] == "отчёт"
    assert seen["history"] == [{"user": "а", "assistant": "б"}]
    assert "только по этому разбору" in text
    assert logged.call_args.args[1] == "chat"


def test_messages_round_trip_trims_to_ten_turns(tmp_path):
    seen = []

    def fake(player_id, report, history, user_text, language_code, stroke):
        seen.append((list(history), user_text, language_code, stroke, report))
        return f"ответ {len(seen)}"

    with _tmp_db(tmp_path):
        client = TestClient(
            http_api.create_app(verify_apple=lambda token: token, chat=fake)
        )
        token, player_id = _auth(client)
        headers = {"Authorization": "Bearer " + token}
        job_id = _job(client, token, player_id)
        empty = client.get(f"/v1/jobs/{job_id}/messages", headers=headers)
        assert empty.status_code == 200
        assert empty.json()["messages"] == []
        for index in range(1, 12):
            res = client.post(
                f"/v1/jobs/{job_id}/messages",
                json={"text": f" вопрос {index} ", "language_code": "ru"},
                headers=headers,
            )
            assert res.status_code == 200
        window = res.json()["messages"]
        assert len(window) == 20
        assert window[0]["text"] == "вопрос 2"
        assert window[-1]["text"] == "ответ 11"
        assert seen[1][0] == [{"user": "вопрос 1", "assistant": "ответ 1"}]
        assert seen[0][2] == "ru"
        assert seen[0][3] == "serve"
        assert "Черновик" in seen[0][4]


def test_rejects_empty_long_and_bad_language(tmp_path):
    calls = []

    def fake(*args):
        calls.append(args)
        return "нет"

    with _tmp_db(tmp_path):
        client = TestClient(
            http_api.create_app(verify_apple=lambda token: token, chat=fake)
        )
        token, player_id = _auth(client)
        headers = {"Authorization": "Bearer " + token}
        job_id = _job(client, token, player_id)
        path = f"/v1/jobs/{job_id}/messages"
        assert (
            client.post(
                path, json={"text": "  ", "language_code": "ru"}, headers=headers
            ).status_code
            == 400
        )
        assert (
            client.post(
                path,
                json={"text": "а" * 2001, "language_code": "ru"},
                headers=headers,
            ).status_code
            == 400
        )
        assert (
            client.post(
                path, json={"text": "вопрос", "language_code": "de"}, headers=headers
            ).status_code
            == 400
        )
        assert calls == []


def test_missing_report_and_foreign_job_are_404(tmp_path):
    with _tmp_db(tmp_path):
        client = TestClient(
            http_api.create_app(verify_apple=lambda token: token, chat=lambda *a: "x")
        )
        token, player_id = _auth(client)
        headers = {"Authorization": "Bearer " + token}
        empty_id = storage.create_review_job(
            player_id,
            video_file_id="ios:empty",
            source_channel=storage.CHANNEL_IOS,
        )
        assert (
            client.get(f"/v1/jobs/{empty_id}/messages", headers=headers).status_code
            == 404
        )
        other = client.post("/v1/auth/apple", json={"identity_token": "sub-other"})
        other_headers = {"Authorization": "Bearer " + other.json()["token"]}
        job_id = _job(client, token, player_id)
        assert (
            client.get(f"/v1/jobs/{job_id}/messages", headers=other_headers).status_code
            == 404
        )


def test_busy_gate_does_not_call_the_model(tmp_path):
    calls = []

    def fake(*args):
        calls.append(args)
        return "ответ"

    with _tmp_db(tmp_path):
        token_box = {}
        gate = http_api.JobChatGate()
        client = TestClient(
            http_api.create_app(
                verify_apple=lambda token: token, chat=fake, chat_gate=gate
            )
        )
        token, player_id = _auth(client)
        token_box["t"] = token
        headers = {"Authorization": "Bearer " + token}
        job_id = _job(client, token, player_id)
        assert gate.try_enter(job_id) is True
        res = client.post(
            f"/v1/jobs/{job_id}/messages",
            json={"text": "ещё", "language_code": "en"},
            headers=headers,
        )
        assert res.status_code == 409
        assert calls == []
        gate.leave(job_id)


def test_model_failure_stores_nothing_and_releases_the_gate(tmp_path):
    calls = {"n": 0}

    def fake(*args):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("down")
        return "ответ"

    with _tmp_db(tmp_path):
        client = TestClient(
            http_api.create_app(verify_apple=lambda token: token, chat=fake)
        )
        token, player_id = _auth(client)
        headers = {"Authorization": "Bearer " + token}
        job_id = _job(client, token, player_id)
        path = f"/v1/jobs/{job_id}/messages"
        failed = client.post(
            path, json={"text": "вопрос", "language_code": "ru"}, headers=headers
        )
        assert failed.status_code == 502
        assert client.get(path, headers=headers).json()["messages"] == []
        ok = client.post(
            path, json={"text": "вопрос", "language_code": "ru"}, headers=headers
        )
        assert ok.status_code == 200
        assert ok.json()["messages"][-1]["text"] == "ответ"
