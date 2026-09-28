"""Load reviewed wiki pages into a prompt knowledge block by intake stroke."""

import re
from pathlib import Path
from typing import Optional

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


def _read_reviewed(rel: str, root: Path = KNOWLEDGE_ROOT) -> Optional[str]:
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
    """Slug проблем, которые модели разрешено писать в issue_tags."""
    slugs: list = []
    for folder in ("wiki/concepts", "wiki/errors"):
        directory = root / folder
        if not directory.is_dir():
            continue
        slugs.extend(path.stem for path in sorted(directory.glob("*.md")))
    return _dedupe_pages(slugs)


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
) -> str:
    """Assemble a capped knowledge block for system prompts."""
    if strokes is not None:
        page_list = pages_for_strokes(strokes, chronic_tags)
    else:
        page_list = pages_for_stroke(stroke, chronic_tags)
    sections: list[str] = []
    for rel in page_list:
        section = _read_reviewed(rel, root=root)
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
