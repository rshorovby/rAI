"""Имена роликов и сухой план лабораторного прогона. Gemini не вызывается."""

from pathlib import Path

import eval_fps_lab as lab


def test_stroke_comes_from_prefix():
    assert lab.stroke_of(Path("serve__yard.mp4")) == "serve"
    assert lab.stroke_of(Path("Forehand__basket.MOV")) == "forehand"
    assert lab.stroke_of(Path("backhand_nik.mov")) == "backhand"
    assert lab.stroke_of(Path("serve_rus.mov")) == "serve"
    assert lab.stroke_of(Path("forhand_nik.MOV")) == "forehand"
    assert lab.stroke_of(Path("просто.mp4")) == "general"


def test_general_sends_empty_strokes():
    assert lab.video_context_for("general") == {"stroke": "general", "strokes": []}
    assert lab.video_context_for("serve")["strokes"] == ["serve"]


def test_fps_list_overrides_defaults():
    assert [item.name for item in lab.variants_from_fps("1,8,16")] == ["fps1", "fps8", "fps16"]


def test_high_adds_one_variant():
    assert [item.name for item in lab.variants_for(False)] == ["fps1", "fps4", "fps8"]
    assert lab.variants_for(True)[-1].name == "fps8-high"
    assert lab.variants_for(True)[-1].high_resolution is True


def test_dry_run_does_not_call_gemini(tmp_path, capsys):
    (tmp_path / "serve__a.mp4").write_bytes(b"not a video")
    code = lab.main(["--dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Вызовов: 3" in out
    assert "serve__a.mp4" in out
    assert "--yes" in out


def test_empty_dir_asks_for_files(tmp_path):
    assert lab.main(["--dir", str(tmp_path)]) == 1


def test_natali_matrix_is_eight_cells():
    names = [item.name for item in lab.natali_matrix()]
    assert names == [
        "fps4-res-default-think-low",
        "fps4-res-default-think-high",
        "fps4-res-high-think-low",
        "fps4-res-high-think-high",
        "fps8-res-default-think-low",
        "fps8-res-default-think-high",
        "fps8-res-high-think-low",
        "fps8-res-high-think-high",
    ]
    assert {item.thinking for item in lab.natali_matrix()} == {"low", "high"}


def test_natali_matrix_dry_run_is_one_file(tmp_path, capsys):
    (tmp_path / "serve_natali.mov").write_bytes(b"not a video")
    (tmp_path / "serve_rus.mov").write_bytes(b"not a video")
    code = lab.main(["--dir", str(tmp_path), "--matrix", "natali"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Вызовов: 8" in out
    assert "serve_natali.mov" in out
    assert "serve_rus.mov" not in out


def test_resolution_matrix_honors_only(tmp_path, capsys):
    (tmp_path / "forhand_maks.mov").write_bytes(b"not a video")
    (tmp_path / "serve_natali.mov").write_bytes(b"not a video")
    code = lab.main(["--dir", str(tmp_path), "--matrix", "resolution", "--only", "forhand_maks"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Вызовов: 8" in out
    assert "forhand_maks.mov" in out
    assert "serve_natali.mov" not in out


def test_prompt_matrix_needs_one_file(tmp_path, capsys):
    (tmp_path / "forhand_maks.mov").write_bytes(b"not a video")
    assert lab.main(["--dir", str(tmp_path), "--matrix", "prompt"]) == 1
    code = lab.main(
        ["--dir", str(tmp_path), "--matrix", "prompt", "--only", "forhand_maks"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Вызовов: 6" in out
    assert "old-fps1-res-high-think-high" in out
    assert "new-fps8-res-high-think-high" in out


def test_temperature_matrix_is_two_cells():
    assert [item.name for item in lab.temperature_matrix()] == ["fps8-temp-0.3", "fps8-temp-1"]
    assert [item.temperature for item in lab.temperature_matrix()] == [0.3, 1.0]
    assert all(item.fps == 8 and item.prompt == "" for item in lab.temperature_matrix())


def test_temperature_matrix_takes_several_files(tmp_path, capsys):
    for name in ("serve_natali.mov", "serve_rus.mov", "backhand_nik.mov"):
        (tmp_path / name).write_bytes(b"not a video")
    assert lab.main(["--dir", str(tmp_path), "--matrix", "temp"]) == 1
    code = lab.main(
        [
            "--dir",
            str(tmp_path),
            "--matrix",
            "temp",
            "--only",
            "serve_rus,serve_natali",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Вызовов: 4" in out
    assert "serve_rus.mov" in out
    assert "serve_natali.mov" in out
    assert "backhand_nik.mov" not in out
    assert lab.main(["--dir", str(tmp_path), "--matrix", "temp", "--only", "нет_такого"]) == 1
