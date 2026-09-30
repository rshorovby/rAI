"""Load reviewed wiki pages into a prompt knowledge block by intake stroke."""

import re
from pathlib import Path
from typing import Optional

_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_WIKI_LABEL_RE = re.compile(r"\b(?:P[123]|RESOLVED|unverified)\b", re.IGNORECASE)
_FEEL_TENNIS_RE = re.compile(r"feel\s*tennis", re.IGNORECASE)
_WAITER_RE = re.compile(
    r"waiter(?:['’]s)?(?:\s+tray)?|поднос(?:\s+официанта)?",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b")
_EMPTY_PARENS_RE = re.compile(r"\(\s*-?\s*(?:,\s*)*\)")
_HANGING_HEADING_RE = re.compile(r"(?m)^(#{1,6}\s*)[—–-]+\s*")
_ARROW_JUNK_RE = re.compile(r"\s*·\s*→\s*|\s*→\s*")
_SLUG_FRAGMENT_RE = re.compile(r"-?[a-z0-9]+(?:-[a-z0-9]+)+\)")
TERMS_PATH = Path(__file__).resolve().parent / "wiki_terms_ru.yml"
_AUTHOR_NAMES = ("Николаев", "Джумок", "Feel Tennis")

KNOWLEDGE_ROOT = Path(__file__).resolve().parent / "knowledge"
MAX_KNOWLEDGE_CHARS = 7000

_CORE_GS = (
    "wiki/concepts/contact-point.md",
    "wiki/concepts/unit-turn.md",
    "wiki/concepts/gradual-acceleration.md",
    "wiki/concepts/ground-force.md",
    "wiki/concepts/hip-rotation.md",
)

# Stroke pages first (priority when truncating), then concepts.
_STROKE_PAGES = {
    "forehand": ("wiki/strokes/forehand.md",) + _CORE_GS,
    "backhand": (
        "wiki/strokes/backhand.md",
        "wiki/strokes/backhand-2h.md",
    )
    + _CORE_GS,
    "serve": (
        "wiki/strokes/serve.md",
        "wiki/concepts/ground-force.md",
    ),
    "volley": (
        "wiki/strokes/volley.md",
        "wiki/concepts/split-step.md",
        "wiki/concepts/contact-point.md",
    ),
    "footwork": (
        "wiki/concepts/footwork.md",
        "wiki/concepts/split-step.md",
        "wiki/concepts/mezhdudarnoe-vremya.md",
        "wiki/concepts/balance.md",
    ),
    "rally": (
        "wiki/concepts/footwork.md",
        "wiki/concepts/split-step.md",
        "wiki/concepts/mezhdudarnoe-vremya.md",
        "wiki/concepts/balance.md",
        "wiki/concepts/contact-point.md",
    ),
}

_GENERAL_PAGES = _CORE_GS + (
    "wiki/concepts/footwork.md",
    "wiki/concepts/split-step.md",
    "wiki/concepts/balance.md",
)

_POLICY_REL = "policy-modern-defaults.md"

_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_STATUS_RE = re.compile(r"^status:\s*(\w+)\s*$", re.MULTILINE)


def _strip_frontmatter(text: str) -> tuple[str, Optional[str]]:
    status = None
    m_status = _STATUS_RE.search(text[:800])
    if m_status:
        status = m_status.group(1)
    body = _FRONTMATTER_RE.sub("", text, count=1).strip()
    return body, status


def load_wiki_terms(path: Path = TERMS_PATH) -> dict:
    """Черновик slug → русская формулировка. Строки без двоеточия пропускает."""
    terms = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return terms
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            terms[key] = value
    return terms


def _table_has_empty_cell(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if not cells:
        return False
    if all(cell and set(cell) <= set("-: ") for cell in cells):
        return False
    return any(cell == "" for cell in cells)


def lint_sanitized_wiki(text: str) -> list:
    """Следы сырой wiki, которых в промпте быть не должно."""
    hits = []
    if "[[" in text or "]]" in text:
        hits.append("brackets")
    if _EMPTY_PARENS_RE.search(text):
        hits.append("empty parens")
    if re.search(r"(?m)^#{1,6}\s*[—–]", text) or "· →" in text:
        hits.append("hanging mark")
    if re.search(r"-[a-z0-9]+(?:-[a-z0-9]+)*\)", text):
        hits.append("slug fragment")
    if any(_table_has_empty_cell(line) for line in text.splitlines()):
        hits.append("empty table cell")
    return hits


def sanitize_wiki(text: str, terms: Optional[dict] = None) -> str:
    """Убрать из текста страницы ссылки, служебные метки и запрещённые фразы.

    Slug из таблицы становится русской формулировкой. Неизвестного slug в тексте
    не остаётся. Имена авторов не трогает: их печатает lint_wiki_authors.
    """
    glossary = load_wiki_terms() if terms is None else terms

    def _link(match: re.Match) -> str:
        inner = match.group(1).strip()
        shown = ""
        key = inner
        if "|" in inner:
            key, shown = inner.split("|", 1)
            shown = shown.strip()
        key = key.split("#", 1)[0].strip()
        if key in glossary:
            return glossary[key]
        if shown and not _SLUG_RE.search(shown) and not re.search(r"[A-Za-z]", shown):
            return shown
        return ""

    cleaned = _WIKI_LINK_RE.sub(_link, text)
    cleaned = _WIKI_LABEL_RE.sub("", cleaned)
    cleaned = _FEEL_TENNIS_RE.sub("", cleaned)
    cleaned = _WAITER_RE.sub("", cleaned)

    def _slug(match: re.Match) -> str:
        return glossary.get(match.group(0), "")

    cleaned = _SLUG_RE.sub(_slug, cleaned)
    lines = []
    for line in cleaned.splitlines():
        line = _EMPTY_PARENS_RE.sub("", line)
        line = _SLUG_FRAGMENT_RE.sub("", line)
        line = _ARROW_JUNK_RE.sub(" ", line)
        line = _HANGING_HEADING_RE.sub(r"\1", line)
        line = re.sub(r"(?<=\S) {2,}", " ", line)
        line = re.sub(r"\s+([,.;:])", r"\1", line)
        if _table_has_empty_cell(line):
            continue
        if line.strip() in {"—", "–", "-", "·", "→"}:
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def lint_wiki_authors(root: Path = KNOWLEDGE_ROOT) -> list:
    """Упоминания имён источников в wiki. Страницы не правит."""
    wiki = root / "wiki"
    if not wiki.is_dir():
        return []
    hits = []
    for path in sorted(wiki.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        for name in _AUTHOR_NAMES:
            if name.lower() in text.lower():
                hits.append(f"{rel}: {name}")
    return hits


def _read_reviewed(
    rel: str, root: Path = KNOWLEDGE_ROOT, sanitize: bool = False
) -> Optional[str]:
    path = root / rel
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    body, status = _strip_frontmatter(raw)
    if status and status != "reviewed":
        return None
    if sanitize:
        body = sanitize_wiki(body)
    if not body:
        return None
    title = path.stem
    return f"### {title}\n\n{body}"


def pages_for_stroke(
    stroke: Optional[str], chronic_tags: Optional[list] = None
) -> list[str]:
    """Return relative paths: policy first, then stroke-specific pages."""
    pages: list[str] = [_POLICY_REL]
    key = (stroke or "").strip().lower()
    if key in ("", "general"):
        pages.extend(_GENERAL_PAGES)
    else:
        pages.extend(_STROKE_PAGES.get(key, _STROKE_PAGES["footwork"]))
    return _with_chronic(_dedupe_pages(pages), chronic_tags)


def pages_for_strokes(
    strokes: Optional[list] = None, chronic_tags: Optional[list] = None
) -> list[str]:
    keys = [str(s).strip().lower() for s in (strokes or []) if str(s).strip()]
    keys = [k for k in keys if k and k != "general"]
    if not keys:
        pages = pages_for_stroke("general")
    else:
        pages = [_POLICY_REL]
        for key in keys:
            pages.extend(_STROKE_PAGES.get(key, ()))
        pages = _dedupe_pages(pages)
    return _with_chronic(pages, chronic_tags)


def issue_tag_slugs(root: Path = KNOWLEDGE_ROOT) -> list:
    """Slug проблем из единого реестра. Каталог wiki больше не источник списка."""
    del root
    from issue_tags import issue_tag_slugs as registry_slugs

    return registry_slugs()


def _chronic_pages(chronic_tags: Optional[list]) -> list:
    pages: list = []
    for tag in list(chronic_tags or [])[:2]:
        slug = str(tag).strip()
        if not slug or "/" in slug or slug.startswith("."):
            continue
        for folder in ("wiki/concepts", "wiki/errors"):
            pages.append(f"{folder}/{slug}.md")
    return pages


def _with_chronic(pages: list, chronic_tags: Optional[list]) -> list:
    extra = _chronic_pages(chronic_tags)
    if not extra:
        return _dedupe_pages(pages)
    policy = [
        page
        for page in pages
        if "/strokes/" not in page
        and "/concepts/" not in page
        and "/errors/" not in page
    ]
    stroke_pages = [page for page in pages if "/strokes/" in page]
    rest = [page for page in pages if page not in policy and page not in stroke_pages]
    rest = [page for page in rest if page not in extra]
    return _dedupe_pages(policy + stroke_pages + extra + rest)


def _dedupe_pages(pages: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def build_knowledge_block(
    stroke: Optional[str] = None,
    language_code: str = "en",
    root: Path = KNOWLEDGE_ROOT,
    max_chars: int = MAX_KNOWLEDGE_CHARS,
    strokes: Optional[list] = None,
    chronic_tags: Optional[list] = None,
    sanitize: bool = False,
    omit_serve_page: bool = False,
) -> str:
    """Assemble a capped knowledge block for system prompts."""
    if strokes is not None:
        page_list = pages_for_strokes(strokes, chronic_tags)
    else:
        page_list = pages_for_stroke(stroke, chronic_tags)
    if omit_serve_page:
        page_list = [page for page in page_list if page != "wiki/strokes/serve.md"]
    sections: list[str] = []
    for rel in page_list:
        section = _read_reviewed(rel, root=root, sanitize=sanitize)
        if section:
            sections.append(section)

    if not sections:
        return ""

    base = (language_code or "en").lower()
    if base.startswith("ru"):
        header = "БАЗА ЗНАНИЙ (reviewed wiki — опирайся при разборе):"
        rules = [
            "Используй эти страницы для терминов, чеклистов и рекомендаций.",
            "Факты только с видео; wiki — эталон техники, не описание ролика.",
            "Соблюдай policy: P1 (gradual/relax), P2/P3 situational по стойкам.",
            "Не советуй «рывковую» жёсткость кисти как норму.",
        ]
    else:
        header = "KNOWLEDGE BASE (reviewed wiki — use for coaching guidance):"
        rules = [
            "Use these pages for terms, checklists, and recommendations.",
            "Facts only from the video; wiki is technique reference, not footage description.",
            "Follow policy: P1 (gradual/relax), P2/P3 situational stances.",
            "Do not prescribe a late 'jerk' firm wrist as the norm.",
        ]

    parts: list[str] = [
        "─────────────────────────────────────────",
        header,
        "",
    ]
    parts.extend(rules)
    parts.append("")

    packed: list[str] = []
    budget = max_chars
    header_text = "\n".join(parts)
    budget -= len(header_text) + 2

    for section in sections:
        chunk = section + "\n\n"
        if len(chunk) <= budget:
            packed.append(section)
            budget -= len(chunk)
        elif budget > 200:
            packed.append(section[: budget - 20].rstrip() + "\n…")
            break
        else:
            break

    if not packed:
        return ""

    lines = parts + packed
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def knowledge_slugs_for_tests(stroke: Optional[str]) -> list[str]:
    """Expose map for unit tests."""
    return pages_for_stroke(stroke)
