from analysis_dialog import clear_dialog, get_dialog, parse_report, start_dialog

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


def test_top3_item_keeps_why_line():
    report = """\
## Краткое резюме
Ок.

## Топ-3 приоритета для тренировки
1. **Действие:** удерживать левую руку
**Зачем:** корпус не раскрывается раньше удара
2. Добавить сплит-степ
"""
    sections = parse_report(report, "ru")
    assert "Зачем" in sections["top3_items"][0]
    assert sections["top3_items"][1] == "Добавить сплит-степ"
    assert sections["errors"][0] == sections["top3_items"][0]


STRUCTURED = """\
## Краткое резюме
Две подачи, подброс за голову.

## Разбор по категориям
### Техника удара
00:03
**Наблюдение:** Подброс уходит за голову.
**Проблема / плюс:** Блокирует перенос веса.
**Критичность:** 🟠 Важно
**Рекомендация:** Сместить точку подброса вперед.

00:03
**Наблюдение:** Глубокое сгибание коленей.
**Проблема / плюс:** Потенциал мощности от опоры.
**Критичность:** 🟢 Сильная сторона

### Передвижение и работа ног
В этом разборе не в приоритете

### Позиционирование и баланс
00:04
**Наблюдение:** Приземление почти на месте.
**Проблема / плюс:** Энергия уходит только вверх.
**Критичность:** 🟠 Важно
**Рекомендация:** Приземляться левой ногой внутри корта.

## Топ-3 приоритета для тренировки
1. **Действие:** Сместите точку подброса.
**Зачем:** Подброс уходит за голову.
"""


def test_structured_remarks_skip_empty_and_hide_recommendation():
    from analysis_dialog import format_error_card, keyboard_remark, start_dialog

    user_data: dict = {}
    state = start_dialog(user_data, STRUCTURED, "ru")
    remarks = state["sections"]["remarks"]
    assert len(remarks) == 3
    assert remarks[0]["kind"] == "remark"
    assert remarks[1]["kind"] == "strength"
    assert "Рекомендация" not in remarks[0]["card"]
    assert "Сместить точку подброса" in remarks[0]["full"]
    state["error_index"] = 0
    first = format_error_card("ru", state)
    assert "Замечание 1 из 3" in first
    assert "Ошибка" not in first
    assert "Рекомендация" not in first
    state["error_index"] = 1
    second = format_error_card("ru", state)
    assert "Сильная сторона 2 из 3" in second
    assert (
        keyboard_remark("ru", 1).inline_keyboard[0][0].callback_data == "d:err:deep:1"
    )


def test_error_card_and_index():
    from analysis_dialog import format_error_card, start_dialog

    user_data: dict = {}
    state = start_dialog(user_data, SAMPLE, "ru")
    card = format_error_card("ru", state)
    assert "1 из 3" in card
    assert "локоть" in card.lower()
    state["error_index"] = 1
    card2 = format_error_card("ru", state)
    assert "2 из 3" in card2


def test_summary_drops_error_and_deep_dive_buttons():
    from analysis_dialog import keyboard_after_video, keyboard_summary, keyboard_top3

    hidden = {"d:errors", "d:cats"}
    for markup in (keyboard_summary("ru"), keyboard_after_video("ru")):
        callbacks = {
            button.callback_data for row in markup.inline_keyboard for button in row
        }
        assert hidden.isdisjoint(callbacks)
        assert "d:top3" in callbacks

    tips = keyboard_top3("ru", {"sections": {"top3_items": ["один", "два"]}})
    assert [button.callback_data for row in tips.inline_keyboard for button in row] == [
        "d:drills",
        "d:next",
        "d:summary",
    ]


def test_start_and_clear_dialog():
    user_data: dict = {}
    state = start_dialog(user_data, SAMPLE, "ru")
    assert get_dialog(user_data) is state
    assert state["step"] == "summary"
    clear_dialog(user_data)
    assert get_dialog(user_data) is None
