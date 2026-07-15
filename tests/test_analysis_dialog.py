from analysis_dialog import parse_report, start_dialog, clear_dialog, get_dialog

SAMPLE = """\
## Краткое резюме
Игрок любительского уровня. Сильная сторона — бэкхенд.

## Что происходит на видео
- 15 секунд, сбоку
- Форхенд

## Разбор по категориям

### Техника удара
- **Наблюдение:** локоть высоко
- **Критичность:** 🔴 Критично

### Передвижение и работа ног
- **Наблюдение:** нет сплит-степа

### Позиционирование и баланс
- **Наблюдение:** вес на задней ноге

## Топ-3 приоритета для тренировки
1. Опустить локоть на форхенде
2. Добавить сплит-степ
3. Перенос веса вперёд

## Следующее видео
Сними форхенд сбоку, 15 сек.

## Ограничения анализа
Лицо не видно.
"""


def test_parse_report_ru():
    sections = parse_report(SAMPLE, "ru")
    assert "любительского" in sections["summary"]
    assert "Форхенд" in sections["video"]
    assert len(sections["categories"]) == 3
    assert sections["categories"][0]["key"] == "stroke"
    assert sections["categories"][1]["key"] == "footwork"
    assert len(sections["top3_items"]) == 3
    assert "локоть" in sections["top3_items"][0].lower()
    assert "форхенд" in sections["next_video"].lower()
    assert sections["errors"] == sections["top3_items"]


def test_parse_report_en_headers_on_ru_request():
    en = """\
## Brief summary
Recreational player.

## What happens in the video
Side angle.

## Breakdown by category

### Stroke technique
Elbow high.

## Top 3 training priorities
1. Lower the elbow
2. Split step
3. Weight transfer

## Next video
Film forehand side view.

## Analysis limitations
Dark video.
"""
    sections = parse_report(en, "ru")
    assert "Recreational" in sections["summary"]
    assert sections["categories"][0]["key"] == "stroke"
    assert sections["top3_items"][0].startswith("Lower")


def test_error_card_and_index():
    from analysis_dialog import format_error_card, start_dialog

    user_data: dict = {}
    state = start_dialog(
        user_data, SAMPLE, "ru", video_file_id="x", video_mime="video/mp4"
    )
    card = format_error_card("ru", state)
    assert "1 из 3" in card
    assert "локоть" in card.lower()
    state["error_index"] = 1
    card2 = format_error_card("ru", state)
    assert "2 из 3" in card2


def test_start_and_clear_dialog():
    user_data: dict = {}
    state = start_dialog(
        user_data,
        SAMPLE,
        "ru",
        video_file_id="abc",
        video_mime="video/mp4",
    )
    assert get_dialog(user_data) is state
    assert state["video_file_id"] == "abc"
    assert state["step"] == "summary"
    clear_dialog(user_data)
    assert get_dialog(user_data) is None
