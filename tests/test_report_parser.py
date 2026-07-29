from report_parser import parse_report, sparkline

SAMPLE = """\
## Краткое резюме
Хороший форхенд.

## Топ-3 приоритета для тренировки
1. Подготовка раньше

```json
{"scores":{"footwork":6,"contact":5,"preparation":7,"follow_through":6},"focus":"Повернуться до отскока","drills":["count-for-more-time"]}
```
"""


def test_parse_full_report():
    parsed = parse_report(SAMPLE)
    assert "Хороший форхенд" in parsed.text
    assert "```" not in parsed.text
    assert parsed.scores["footwork"] == 6
    assert parsed.focus.startswith("Повернуться")
    assert parsed.drill_ids == ["count-for-more-time"]


def test_parse_without_json():
    parsed = parse_report("## Краткое резюме\nПросто текст")
    assert parsed.scores == {}
    assert parsed.focus == ""
    assert "Просто текст" in parsed.text


def test_parse_broken_json():
    text = 'report\n```json\n{"scores": bad}\n```'
    parsed = parse_report(text)
    assert parsed.scores == {}
    assert "report" in parsed.text


def test_sparkline():
    assert len(sparkline([1, 2, 3, 4])) == 4
    assert sparkline([]) == "—"
