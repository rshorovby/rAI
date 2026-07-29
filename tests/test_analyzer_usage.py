from pathlib import Path
from unittest.mock import MagicMock, patch

from analyzer import AnalysisResult, VideoAnalyzer
from pricing import Usage


def test_analyze_returns_usage():
    analyzer = VideoAnalyzer(api_key="x", model="gemini-3.5-flash")

    class Meta:
        prompt_token_count = 10
        candidates_token_count = 5
        thoughts_token_count = 2

    response = MagicMock()
    response.text = "ok report"
    response.usage_metadata = Meta()

    with (
        patch.object(analyzer, "_generate_with_retry", return_value=response),
        patch("analyzer.strip_audio_for_upload", return_value=(Path("v.mp4"), None)),
        patch.object(
            analyzer._client.files,
            "upload",
            return_value=MagicMock(uri="u", mime_type="video/mp4", name="f"),
        ),
        patch.object(analyzer, "_wait_until_active", side_effect=lambda f: f),
        patch.object(analyzer, "_safe_delete"),
    ):
        result = analyzer.analyze(Path("v.mp4"))

    assert isinstance(result, AnalysisResult)
    assert result.text == "ok report"
    assert result.usage == Usage(10, 5, 2, "gemini-3.5-flash")
