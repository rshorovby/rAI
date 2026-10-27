from formatting import markdown_to_html


def test_bold():
    assert markdown_to_html("**важно**") == "<b>важно</b>"


def test_headers_to_bold():
    assert markdown_to_html("## Резюме") == "<b>Резюме</b>"
    assert markdown_to_html("### Техника") == "<b>Техника</b>"


def test_html_special_chars_escaped():
    result = markdown_to_html("a < b & c > d")
    assert "&lt;" in result
    assert "&amp;" in result
    assert "&gt;" in result


def test_bold_after_escaping():
    result = markdown_to_html("**a & b**")
    assert result == "<b>a &amp; b</b>"


def test_plain_text_unchanged():
    assert markdown_to_html("обычный текст") == "обычный текст"


def test_emoji_preserved():
    assert "🔴" in markdown_to_html("Критичность: 🔴")


def test_cabinet_draft_to_html():
    from formatting import cabinet_draft_to_html

    src = (
        "## Что происходит\n- 00:00.500: Начало\n"
        "### Техника\n00:03.125\n**Наблюдение:** рука <низко>\n"
    )
    out = cabinet_draft_to_html(src)
    assert "<b>Что происходит</b>" in out
    assert "• <code>00:00.500</code> Начало" in out
    assert "⏱ <code>00:03.125</code>" in out
    assert "👁 <b>Наблюдение:</b> рука &lt;низко&gt;" in out
