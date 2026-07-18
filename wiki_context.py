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
        "wiki/concepts/grip.md",
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


def pages_for_stroke(stroke: Optional[str]) -> list[str]:
    """Return relative paths: policy first, then stroke-specific pages."""
    pages: list[str] = [_POLICY_REL]
    key = (stroke or "").strip().lower()
    pages.extend(_STROKE_PAGES.get(key, _STROKE_PAGES["footwork"]))
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
) -> str:
    """Assemble a capped knowledge block for system prompts."""
    sections: list[str] = []
    for rel in pages_for_stroke(stroke):
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
