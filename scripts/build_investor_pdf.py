#!/usr/bin/env python3
"""Сборка PDF из markdown-документов для инвесторов и команды.

Использование:
    .venv/bin/python scripts/build_investor_pdf.py            # все документы
    .venv/bin/python scripts/build_investor_pdf.py ROADMAP.md # один документ
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
# встроенный Courier не покрывает кириллицу и псевдографику в диаграммах
FONT_MONO = Path("/System/Library/Fonts/Supplemental/Courier New.ttf")
# знак рубля (U+20BD) отсутствует в системных Arial — подставляем текстом
RUBLE = "₽"

DOCS = {
    "INVESTOR_UNIT_ECONOMICS.md": (
        "RallyMind — Unit Economics",
        "Финансовая модель и экономика раунда · V9-aligned",
    ),
    "ROADMAP.md": (
        "RallyMind — Roadmap",
        "Продуктовый и инженерный план: Telegram → iOS → Android",
    ),
}

CSS = """
@font-face { font-family: Uni; src: url('%(font)s'); }
@font-face { font-family: Uni; src: url('%(font_bold)s'); font-weight: bold; }
@font-face { font-family: Mono; src: url('%(font_mono)s'); }
@page { size: A4; margin: 1.4cm 1.3cm; }
body { font-family: Uni, sans-serif; font-size: 9.5pt; line-height: 1.4; color: #14161a; }
h1 { font-size: 15pt; margin: 14pt 0 5pt; color: #0d0f12; font-weight: bold; }
h2 { font-size: 12pt; margin: 13pt 0 4pt; padding-bottom: 2pt;
     border-bottom: 0.6pt solid #b9bec7; color: #0d0f12; font-weight: bold; }
h3 { font-size: 10.5pt; margin: 9pt 0 3pt; color: #23272e; font-weight: bold; }
p { margin: 3pt 0; }
ul, ol { margin: 3pt 0 5pt 13pt; padding: 0; }
li { margin: 1.5pt 0; }
strong, b { font-weight: bold; color: #000; }
table { border-collapse: collapse; width: 100%%; margin: 5pt 0 9pt; font-size: 8pt; }
th, td { border: 0.5pt solid #a8adb6; padding: 3pt 4pt; vertical-align: top; }
th { background: #eceef1; font-weight: bold; color: #000; }
tr { page-break-inside: avoid; }
pre { background: #f4f5f7; border: 0.5pt solid #dcdfe4; padding: 5pt;
      font-family: Mono; font-size: 7.5pt; margin: 5pt 0 8pt; }
code { font-family: Mono; font-size: 8pt; }
blockquote { border-left: 2pt solid #a8adb6; margin: 5pt 0; padding-left: 7pt; color: #33383f; }
hr { border: none; border-top: 0.5pt solid #c8ccd3; margin: 9pt 0; }
.cover-title { font-size: 21pt; margin: 0 0 4pt; color: #0d0f12; font-weight: bold; }
.cover-sub { font-size: 10.5pt; color: #4a505a; margin: 0 0 3pt; }
.cover-meta { font-size: 8.5pt; color: #6b717b; }
"""


def build(md_name: str, title: str, subtitle: str) -> bool:
    import markdown
    from xhtml2pdf import pisa

    md_path = ROOT / md_name
    out_path = md_path.with_suffix(".pdf")
    if not md_path.is_file():
        print(f"пропуск, нет файла: {md_path}", file=sys.stderr)
        return False

    text = md_path.read_text(encoding="utf-8").replace(RUBLE, " руб.")
    # первый H1 уезжает на обложку
    lines = text.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = markdown.markdown(
        "\n".join(lines), extensions=["tables", "fenced_code", "sane_lists"]
    )

    styles = CSS % {
        "font": FONT.as_posix(),
        "font_bold": FONT_BOLD.as_posix(),
        "font_mono": FONT_MONO.as_posix(),
    }
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{styles}</style></head>
<body>
<p class="cover-title">{title}</p>
<p class="cover-sub">{subtitle}</p>
<p class="cover-meta">RallyMind · июль 2026 · конфиденциально</p>
<hr/>
{body}
</body></html>"""

    with out_path.open("wb") as fh:
        status = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if status.err:
        print(f"ошибки рендера {md_name}: {status.err}", file=sys.stderr)
        return False

    print(f"OK: {out_path.name} ({out_path.stat().st_size // 1024} KB)")
    return True


def main() -> int:
    try:
        import markdown  # noqa: F401
        import xhtml2pdf  # noqa: F401
    except ImportError:
        print(".venv/bin/pip install markdown xhtml2pdf", file=sys.stderr)
        return 1
    for font in (FONT, FONT_BOLD, FONT_MONO):
        if not font.is_file():
            print(f"нет шрифта с кириллицей: {font}", file=sys.stderr)
            return 1

    targets = sys.argv[1:] or list(DOCS)
    ok = True
    for name in targets:
        meta = DOCS.get(name)
        if meta is None:
            print(f"неизвестный документ: {name}", file=sys.stderr)
            ok = False
            continue
        ok = build(name, *meta) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
