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
    assert parsed.summary == "Хороший форхенд."
    assert parsed.findings == []


def test_parse_findings():
    text = """\
## Краткое резюме
Резюме.

## Следующее видео
Снимите форхенд сбоку.

```json
{"scores":{"preparation":7},"focus":"Повернуться","drills":["count-for-more-time"],"findings":[{"problem":"Ракетка опаздывает.","recommendation":"Отведите ракетку до отскока.","drill_ids":["count-for-more-time"]},{"problem":"Только проблема."},{"problem":"Лишний","recommendation":"Четвёртый не берём.","drill_ids":[]},{"problem":"Третий","recommendation":"Ок.","drill_ids":[]}]}
```
"""
    parsed = parse_report(text)
    assert parsed.summary == "Резюме."
    assert parsed.next_video == "Снимите форхенд сбоку."
    assert len(parsed.findings) == 3
    assert parsed.findings[0]["problem"].startswith("Ракетка")
    assert parsed.findings[0]["drill_ids"] == ["count-for-more-time"]
    assert parsed.findings[1]["problem"] == "Лишний"
    assert parsed.findings[2]["problem"] == "Третий"


def test_parse_without_json():
    parsed = parse_report("## Краткое резюме\nПросто текст")
    assert parsed.scores == {}
    assert parsed.focus == ""
    assert "Просто текст" in parsed.text


def test_findings_from_top3_draft():
    text = """\
## Краткое резюме
Любительский уровень.

## Что происходит на видео
- **Уровень игры:** Любитель.

## Разбор по категориям

### Техника удара
- **Наблюдение:** Левая рука опускается.
- **Проблема / плюс:** Нет unit turn.
- **Критичность:** 🟠 Важно
- **Рекомендация:** Вытягивать левую руку (id: two-hand-sync).

## Топ-3 приоритета для тренировки
1. **Перенос веса на форхенде:** На каждом ударе справа переносить вес вперёд.
2. **Баланс корпуса:** Держать лёгкий наклон груди вперёд.
3. **Работа левой руки:** Вытягивать левую руку параллельно задней линии.

## Следующее видео
Снимите бэкхенд сбоку.
"""
    parsed = parse_report(text)
    assert parsed.summary.startswith("Любительский")
    assert parsed.next_video.startswith("Снимите бэкхенд")
    assert len(parsed.findings) == 3
    assert parsed.findings[0]["problem"] == "Перенос веса на форхенде"
    assert "переносить вес" in parsed.findings[0]["recommendation"]
    assert parsed.findings[2]["problem"] == "Работа левой руки"


def test_findings_from_observations_when_no_top3():
    text = """\
## Краткое резюме
Ок.

### Техника удара
- **Наблюдение:** Контакт поздний.
- **Проблема / плюс:** Мяч близко к корпусу.
- **Критичность:** 🔴 Критично
- **Рекомендация:** Встречать мяч впереди (id: two-hand-sync).

- **Наблюдение:** Хороший ритм замаха.
- **Проблема / плюс:** Стабильный ритм.
- **Критичность:** 🟢 Сильная сторона
- **Рекомендация:** Сохранить ритм.

### Передвижение и работа ног
- **Наблюдение:** Нет сплит-степа.
- **Проблема / плюс:** Ноги залипают.
- **Критичность:** 🟠 Важно
- **Рекомендация:** Делать разножку в момент наброса.
"""
    parsed = parse_report(text)
    assert len(parsed.findings) == 2
    assert parsed.findings[0]["problem"] == "Мяч близко к корпусу."
    assert parsed.findings[0]["drill_ids"] == ["two-hand-sync"]
    assert parsed.findings[1]["problem"] == "Ноги залипают."


def test_parse_broken_json():
    text = 'report\n```json\n{"scores": bad}\n```'
    parsed = parse_report(text)
    assert parsed.scores == {}
    assert "report" in parsed.text


def test_sparkline():
    assert len(sparkline([1, 2, 3, 4])) == 4
    assert sparkline([]) == "—"
