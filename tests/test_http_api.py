from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

import http_api
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "http.db")


def _client():
    return TestClient(http_api.create_app(verify_apple=lambda token: token))


def test_apple_auth_me_logout(tmp_path):
    with _tmp_db(tmp_path):
        client = _client()
        res = client.post("/v1/auth/apple", json={"identity_token": "sub-1"})
        assert res.status_code == 200
        token = res.json()["token"]
        player_id = res.json()["player_id"]
        assert player_id > 0
        assert res.json()["telegram_linked"] is False
        me = client.get("/v1/me", headers={"Authorization": "Bearer " + token})
        assert me.status_code == 200
        assert me.json()["player_id"] == player_id
        out = client.post("/v1/me/logout", headers={"Authorization": "Bearer " + token})
        assert out.status_code == 204
        me2 = client.get("/v1/me", headers={"Authorization": "Bearer " + token})
        assert me2.status_code == 401


def test_link_telegram_into_empty_ios(tmp_path):
    with _tmp_db(tmp_path):
        tg = storage.get_or_create_telegram_player(1001)
        storage.create_review_job(tg, video_file_id="v", draft_text="old")
        code = storage.create_link_code(tg, storage.LINK_TG_TO_IOS)
        client = _client()
        res = client.post("/v1/auth/apple", json={"identity_token": "sub-2"})
        token = res.json()["token"]
        linked = client.post(
            "/v1/link/telegram",
            json={"code": code},
            headers={"Authorization": "Bearer " + token},
        )
        assert linked.status_code == 200
        assert linked.json()["player_id"] == tg
        assert linked.json()["telegram_linked"] is True


def test_link_telegram_rejects_nonempty_ios(tmp_path):
    with _tmp_db(tmp_path):
        tg = storage.get_or_create_telegram_player(1002)
        code = storage.create_link_code(tg, storage.LINK_TG_TO_IOS)
        client = _client()
        res = client.post("/v1/auth/apple", json={"identity_token": "sub-3"})
        token = res.json()["token"]
        ios_id = res.json()["player_id"]
        storage.create_review_job(
            ios_id,
            video_file_id="ios:x",
            source_channel=storage.CHANNEL_IOS,
        )
        linked = client.post(
            "/v1/link/telegram",
            json={"code": code},
            headers={"Authorization": "Bearer " + token},
        )
        assert linked.status_code == 409


def test_ios_jobs_do_not_cancel_each_other_or_telegram(tmp_path):
    with _tmp_db(tmp_path):
        pid = storage.get_or_create_apple_player("sub-4")
        a = storage.create_review_job(
            pid, video_file_id="a", source_channel=storage.CHANNEL_IOS
        )
        b = storage.create_review_job(
            pid, video_file_id="b", source_channel=storage.CHANNEL_IOS
        )
        assert storage.get_review_job(a)["status"] == "queued"
        assert storage.get_review_job(b)["status"] == "queued"
        tg_job = storage.create_review_job(
            pid, video_file_id="tg", source_channel=storage.CHANNEL_TELEGRAM
        )
        assert storage.get_review_job(a)["status"] == "queued"
        assert storage.get_review_job(b)["status"] == "queued"
        assert storage.get_review_job(tg_job)["status"] == "queued"
        storage.create_review_job(
            pid, video_file_id="tg2", source_channel=storage.CHANNEL_TELEGRAM
        )
        assert storage.get_review_job(tg_job)["status"] == "cancelled"
        assert storage.get_review_job(a)["status"] == "queued"


def test_create_job_and_open_list(tmp_path):
    with _tmp_db(tmp_path):
        client = _client()
        res = client.post("/v1/auth/apple", json={"identity_token": "sub-5"})
        token = res.json()["token"]
        headers = {"Authorization": "Bearer " + token}
        files = {"video": ("clip.mp4", b"fake-bytes", "video/mp4")}
        created = client.post(
            "/v1/jobs",
            files=files,
            data={"stroke": "forehand", "look": "technique"},
            headers=headers,
        )
        assert created.status_code == 201
        job_id = created.json()["id"]
        opened = client.get("/v1/jobs?open=1", headers=headers)
        assert opened.status_code == 200
        assert any(j["id"] == job_id for j in opened.json()["jobs"])
        one = client.get(f"/v1/jobs/{job_id}", headers=headers)
        assert one.status_code == 200
        assert one.json()["stroke"] == "forehand"


def test_app_code_and_device_token_and_delete(tmp_path):
    with _tmp_db(tmp_path):
        client = _client()
        res = client.post("/v1/auth/apple", json={"identity_token": "sub-6"})
        token = res.json()["token"]
        headers = {"Authorization": "Bearer " + token}
        code_res = client.post("/v1/link/app-code", headers=headers)
        assert code_res.status_code == 200
        assert len(code_res.json()["code"]) == 8
        dt = client.post(
            "/v1/device-tokens", json={"token": "apns-dev"}, headers=headers
        )
        assert dt.status_code == 204
        gone = client.delete("/v1/me", headers=headers)
        assert gone.status_code == 204
        me = client.get("/v1/me", headers=headers)
        assert me.status_code == 401


def test_telegram_new_job_still_cancels_previous_telegram(tmp_path):
    with _tmp_db(tmp_path):
        a = storage.create_review_job(1, video_file_id="a", draft_text="1")
        b = storage.create_review_job(1, video_file_id="b", draft_text="2")
        assert storage.get_review_job(a)["status"] == "cancelled"
        assert storage.get_open_review_job(1)["id"] == b
