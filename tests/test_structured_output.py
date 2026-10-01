"""Схема, проверки, рендер и повтор structured output."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from analysis_checks import ALLOWED_AXES, apply_checks, player_text_issues
from analysis_schema import (
    build_response_schema,
    drill_ids_from_catalog,
    schema_errors,
    to_sdk_schema,
)
from analyzer import _video_fps_metadata
from focus_strokes import stroke_key
from pricing import Usage
from prompts import build_foci_block, build_scores_block
from render_report import legacy_scores, render_report
from report_parser import parse_report
from structured_pipeline import AnalysisFailed, run_structured

FIXTURES = Path(__file__).parent / "fixtures" / "structured"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _serve() -> dict:
    return _load("serve")


def _reasons(data: dict, drill_ids=None) -> list:
    ids = ["toss-spot"] if drill_ids is None else drill_ids
    schema = build_response_schema(ids)
    errors = schema_errors(data, schema)
    if errors:
        return errors
    blocking, _, _ = apply_checks(data, drill_ids=ids)
    return blocking


def test_valid_fixture_passes_and_invalid_ones_fail():
    assert _reasons(_serve()) == []
    empty = _serve()
    empty["findings"] = []
    assert any("findings" in item for item in _reasons(empty))
    missing = _serve()
    del missing["summary"]
    assert any("summary" in item for item in _reasons(missing))
    unknown = _serve()
    unknown["primary_segment"] = "dropshot"
    assert any("enum" in item for item in _reasons(unknown))


@pytest.mark.parametrize("name", ["serve", "serve_series", "not_tennis", "rally"])
def test_render_matches_golden(name):
    data = _load(name)
    rendered = render_report(data)
    assert rendered == (FIXTURES / f"{name}.md").read_text(encoding="utf-8")
    if name == "not_tennis":
        assert rendered.strip().startswith("## Краткое резюме")
        assert "## Разбор" not in rendered
        return
    assert "**Действие:**" in rendered
    assert "**Зачем:**" in rendered
    assert player_text_issues(rendered)["phrase"] is False


def test_legacy_scores_follow_the_segment_table():
    serve = legacy_scores(
        "serve",
        [
            {"axis": "toss", "value": 3},
            {"axis": "leg_drive", "value": 4},
            {"axis": "contact", "value": 5},
            {"axis": "preparation", "value": 6},
            {"axis": "follow_through", "value": 7},
            {"axis": "footwork", "value": 9},
        ],
    )
    assert serve["footwork"] == 4
    assert "toss" not in serve
    forehand = legacy_scores(
        "forehand",
        [
            {"axis": "footwork", "value": 6},
            {"axis": "contact", "value": 5},
            {"axis": "preparation", "value": 7},
            {"axis": "follow_through", "value": 8},
            {"axis": "balance", "value": 2},
        ],
    )
    assert forehand == {
        "footwork": 6,
        "contact": 5,
        "preparation": 7,
        "follow_through": 8,
    }
    volley = legacy_scores(
        "volley",
        [
            {"axis": "footwork", "value": 5},
            {"axis": "contact", "value": 6},
            {"axis": "preparation", "value": 7},
            {"axis": "follow_through", "value": 8},
        ],
    )
    assert "follow_through" not in volley
    assert volley["contact"] == 6
    feet = legacy_scores(
        "footwork",
        [
            {"axis": "footwork", "value": 5},
            {"axis": "preparation", "value": 4},
            {"axis": "contact", "value": 9},
            {"axis": "balance", "value": 3},
        ],
    )
    assert feet == {"footwork": 5, "preparation": 4}
    parsed = parse_report(render_report(_serve()))
    assert parsed.scores["footwork"] == 4
    assert parsed.primary_segment == "serve"


def test_validators_timecode_focus_and_axis():
    data = _serve()
    data["observations"][0]["t"] = "9:00"
    _, notes, _ = apply_checks(data, duration_sec=8, drill_ids=["toss-spot"])
    assert any("длиннее" in note for note in notes)

    broken = _serve()
    broken["findings"][0]["t"] = "2"
    _, notes, _ = apply_checks(broken, duration_sec=8, drill_ids=["toss-spot"])
    assert any("таймкод" in note for note in notes)

    improved = _serve()
    improved["focus_checks"] = [
        {"stroke": "serve", "evidence": "стало лучше", "status": "improved"}
    ]
    _, notes, fixed = apply_checks(improved, drill_ids=["toss-spot"])
    assert fixed["focus_checks"][0]["status"] == "not_visible"
    assert any("evidence" in note for note in notes)

    foreign = _serve()
    foreign["focus_checks"] = [
        {"stroke": "forehand", "evidence": "0:02", "status": "same"}
    ]
    _, notes, fixed = apply_checks(foreign, drill_ids=["toss-spot"])
    assert fixed["focus_checks"][0]["status"] == "not_visible"
    assert any("detected_segments" in note for note in notes)

    illegal = _serve()
    _, notes, fixed = apply_checks(illegal, drill_ids=["toss-spot"])
    assert all(item["axis"] in ALLOWED_AXES["serve"] for item in fixed["scores"])
    # фикстура подачи без лишней оси: добавим balance
    illegal["scores"].append({"axis": "balance", "evidence": "0:05", "value": 3})
    _, notes, fixed = apply_checks(illegal, drill_ids=["toss-spot"])
    assert all(item["axis"] != "balance" for item in fixed["scores"])
    assert any("ось balance" in note for note in notes)


def test_phrase_retry_then_returns_draft_with_incident():
    dirty = _serve()
    dirty["summary"] = "Поднос официанта на подбросе."
    calls = {"n": 0}

    def generate():
        calls["n"] += 1
        return json.dumps(dirty, ensure_ascii=False), Usage(1, 1, 0, "m")

    outcome = run_structured(
        generate,
        schema=build_response_schema(["toss-spot"]),
        drill_ids=["toss-spot"],
        duration_sec=8,
        downgrade_missing_evidence=True,
        system_prompt="system",
        user_prompt="user",
        model="m",
    )
    assert calls["n"] == 2
    assert outcome["run_log"]["retries"] == 1
    assert outcome["run_log"]["phrase_incident"] is True
    assert "Поднос" in outcome["text"]


def test_schema_failure_after_retries_raises():
    def generate():
        return "не json", Usage(1, 0, 0, "m")

    with pytest.raises(AnalysisFailed):
        run_structured(
            generate,
            schema=build_response_schema(["toss-spot"]),
            drill_ids=["toss-spot"],
            duration_sec=None,
            downgrade_missing_evidence=True,
            system_prompt="s",
            user_prompt="u",
            model="m",
        )


def test_focus_mapping_and_prompt_key():
    assert stroke_key("подача") == "serve"
    assert stroke_key("Вольё") == "volley"
    assert stroke_key("бэкхенд") == "backhand"
    assert stroke_key("ноги") == "footwork"
    assert stroke_key("розыгрыш") == "rally"
    assert stroke_key("смэш") == ""
    block = build_foci_block(
        [{"stroke": "serve", "focus": "подброс в одну точку"}],
        "ru",
        include_stroke_key=True,
    )
    assert "ключ: serve" in block
    scores = build_scores_block(
        [{"stroke": "serve", "created_at": "t", "scores": {"footwork": 4}}],
        "ru",
        label_serve_leg_drive=True,
    )
    assert "leg_drive" in scores
    assert "'footwork'" not in scores


def test_drill_enum_empty_and_full():
    empty = build_response_schema([])
    assert "enum" not in empty["properties"]["drills"]["items"]
    ids = [f"drill-{index}" for index in range(41)]
    full = build_response_schema(ids)
    enum = full["properties"]["drills"]["items"]["enum"]
    finding_enum = full["properties"]["findings"]["items"]["properties"]["drill_ids"][
        "items"
    ]["enum"]
    assert enum == finding_enum == ids[:40]
    tags = full["properties"]["issue_tags"]["items"]["enum"]
    finding_tags = full["properties"]["findings"]["items"]["properties"]["issue_tags"][
        "items"
    ]["enum"]
    assert tags == finding_tags
    assert drill_ids_from_catalog("- id=toss-spot: точка\n- id=toss-spot: ещё") == [
        "toss-spot"
    ]


def test_sdk_schema_keeps_field_order_and_drops_long_enums():
    schema = to_sdk_schema(build_response_schema(["toss-spot"]))
    assert schema.property_ordering[0] == "video"
    assert schema.property_ordering[-1] == "summary"
    assert schema.properties["issue_tags"].items.enum is None
    assert schema.properties["drills"].items.enum == ["toss-spot"]
    local = build_response_schema(["toss-spot"])
    assert "unit-turn" in local["properties"]["issue_tags"]["items"]["enum"]
    wide = to_sdk_schema(build_response_schema([f"drill-{i}" for i in range(40)]))
    assert wide.properties["drills"].items.enum is None


def test_video_fps_is_not_sent_on_this_sdk():
    assert _video_fps_metadata(None) is None
    assert _video_fps_metadata(5) is None


def test_analyze_structured_uses_schema_and_writes_log(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    from analyzer import AnalysisResult, VideoAnalyzer

    raw = json.dumps(_serve(), ensure_ascii=False)
    analyzer = VideoAnalyzer(api_key="x", model="gemini-3.1-pro-preview")
    response = MagicMock()
    response.text = raw

    class Meta:
        prompt_token_count = 10
        candidates_token_count = 4
        thoughts_token_count = 1

    response.usage_metadata = Meta()
    with (
        patch.object(analyzer, "_generate_with_retry", return_value=response) as gen,
        patch("analyzer.strip_audio_for_upload", return_value=(Path("v.mp4"), None)),
        patch("analyzer.video_duration_sec", return_value=8),
        patch.object(
            analyzer._client.files,
            "upload",
            return_value=MagicMock(uri="u", mime_type="video/mp4", name="f"),
        ),
        patch.object(analyzer, "_wait_until_active", side_effect=lambda item: item),
        patch.object(analyzer, "_safe_delete"),
    ):
        result = analyzer.analyze(
            Path("v.mp4"),
            language_code="ru",
            drills_catalog="- id=toss-spot: точка",
            run_log_dir=tmp_path,
        )
    assert isinstance(result, AnalysisResult)
    assert result.raw_json["primary_segment"] == "serve"
    assert "## Краткое резюме" in result.text
    config = gen.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.temperature == 0.3
    assert list(tmp_path.glob("*.json"))
    assert result.run_log["retries"] == 0
