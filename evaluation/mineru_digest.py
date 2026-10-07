"""Build a claim-relevant digest from mineru_sections.json.

MinerU ``key`` fields are often wrong (many true experiment/method/result
sections are labeled ``other``). Selection therefore treats ``key`` as a weak
hint only and primarily uses:

1. section titles (I./II./RQ/Results/...)
2. body text cues (tables, metrics, ``we evaluate``...)
3. structural inheritance from the nearest major section heading
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Weak hint only — never required for inclusion.
KEY_HINT_ROLE = {
    "abstract": "abstract",
    "introduction": "introduction",
    "background": "background",
    "method": "method",
    "experiment": "experiment",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "threats": "threats",
    "related_work": "related_work",
}

DROP_ROLES = {"acknowledgment", "references", "appendix", "biography", "checklist"}

TITLE_DROP_RE = re.compile(
    r"(acknowledgment|acknowledgement|^references$|\breferences\b|"
    r"appendix|biography|checklist|artifact evaluat)",
    re.I,
)

# Major / subsection title → inferred role.
# More specific experiment patterns are checked before broad method patterns.
TITLE_ROLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\babstract\b", re.I), "abstract"),
    (re.compile(r"\bintroduct", re.I), "introduction"),
    (re.compile(r"\bbackground\b|\bpreliminar", re.I), "background"),
    (re.compile(r"\brelated\s+work\b|\bprior\s+work\b", re.I), "related_work"),
    (
        re.compile(
            r"threats?\s+to\s+valid|\bexternal\s+valid|\binternal\s+valid|"
            r"\blimitations?\s+of\s+(this|our|the)\s+study",
            re.I,
        ),
        "threats",
    ),
    (
        re.compile(
            r"\bexperiment|\bempiric|\bevaluat|\bresult|\bfinding|"
            r"\brq\s*\d|\bresearch\s+question|\bbenchmark|\bcompar|"
            r"\bbaseline|\bablation|\bcase\s+study|\bsetup\b|\bmethodolog|"
            r"\banalysis\b|\bperform|\boverall\s+performance",
            re.I,
        ),
        "experiment",
    ),
    (
        re.compile(
            r"\bapproach\b|\bdesign\b|\bframework\b|\barchitecture\b|"
            r"\bimplement|\bpropos|\bmethod",
            re.I,
        ),
        "method",
    ),
    (re.compile(r"\bdiscussion\b|\bimplication", re.I), "discussion"),
    (re.compile(r"\bconclusion|\bconclud|\bfuture\s+work", re.I), "conclusion"),
]

BODY_ROLE_CUES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\babstract\b.{0,80}\bwe\b", re.I), "abstract", 0.4),
    (re.compile(r"<table>|\\begin\{table\}|\bTable\s+[IVXLC\d]", re.I), "experiment", 0.8),
    (
        re.compile(
            r"\bsuccess\s+ratio\b|\bAUROC\b|\bF1\b|\baccuracy\b|\bbaseline\b|"
            r"\bSOTA\b|\bp-value\b|\bconfidence\s+interval\b|\bRQ\s*\d",
            re.I,
        ),
        "experiment",
        0.9,
    ),
    (
        re.compile(r"\bwe\s+(evaluate|conduct|compare|measure|report)\b", re.I),
        "experiment",
        0.6,
    ),
    (re.compile(r"\bin\s+this\s+paper,?\s+we\s+(propose|present|introduce)\b", re.I), "introduction", 0.5),
]

MAJOR_TITLE_RE = re.compile(
    r"^(?:[IVXLC]{1,6}|\d{1,2})(?:\.[A-Z0-9]+)*[\.\):]?\s+\S+",
    re.I,
)
SUBSECTION_TITLE_RE = re.compile(r"^(?:[A-Z]|\d+)(?:\.\d+)*[\.\):]\s+\S+")

ROLE_PRIORITY = {
    "experiment": 0,
    "conclusion": 1,
    "discussion": 2,
    "method": 3,
    "abstract": 4,
    "introduction": 5,
    "threats": 6,
    "background": 7,
    "related_work": 8,
    "other": 9,
}


def load_mineru(task_dir: Path) -> dict[str, Any] | None:
    path = task_dir / "mineru_sections.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _clip(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n...[truncated]..."


def infer_role_from_title(title: str) -> str | None:
    title = (title or "").strip()
    if not title:
        return None
    if TITLE_DROP_RE.search(title):
        return "drop"
    for pattern, role in TITLE_ROLE_PATTERNS:
        if pattern.search(title):
            return role
    return None


def infer_role_from_body(text: str) -> tuple[str | None, float]:
    best_role: str | None = None
    best_score = 0.0
    head = (text or "")[:2500]
    for pattern, role, score in BODY_ROLE_CUES:
        if pattern.search(head) and score > best_score:
            best_role, best_score = role, score
    return best_role, best_score


def infer_section_role(
    *,
    title: str,
    text: str,
    raw_key: str,
    inherited_role: str | None,
) -> tuple[str, str]:
    """Return (inferred_role, reason)."""
    title_role = infer_role_from_title(title)
    if title_role == "drop":
        return "drop", "title_drop"

    body_role, body_score = infer_role_from_body(text)
    key_role = KEY_HINT_ROLE.get((raw_key or "").lower())
    # Roman majors like "V. EMPIRICAL STUDY" also match lettered-subsection regex;
    # decide major first so inheritance logic stays correct.
    is_major = bool(MAJOR_TITLE_RE.match(title.strip()))
    is_subsection = (not is_major) and bool(SUBSECTION_TITLE_RE.match(title.strip()))

    # Under an experiment/method major section, lettered subsections inherit
    # unless the title clearly starts a new major role (discussion/conclusion/...).
    if inherited_role and inherited_role not in DROP_ROLES | {"other"}:
        if is_subsection or not is_major:
            if title_role in {
                "discussion",
                "conclusion",
                "threats",
                "related_work",
                "abstract",
            }:
                return title_role, "title"
            if body_role == "experiment" and body_score >= 0.8:
                return "experiment", "body_override"
            # Ambiguous titles like "Methodology"/"System Setup" under Empirical Study
            # should stay with the parent experiment section.
            if inherited_role == "experiment":
                return "experiment", "inherited"
            if title_role:
                return title_role, "title"
            return inherited_role, "inherited"

    if title_role:
        return title_role, "title"
    if body_role and body_score >= 0.6:
        return body_role, "body"
    if key_role:
        return key_role, "key_hint"
    if body_role:
        return body_role, "body_weak"
    return "other", "fallback"


def _is_near_duplicate(a: str, b: str) -> bool:
    a = re.sub(r"\s+", " ", (a or "").strip().lower())
    b = re.sub(r"\s+", " ", (b or "").strip().lower())
    if not a or not b:
        return False
    if a == b:
        return True
    # Prefix overlap for field vs section copies.
    n = min(400, len(a), len(b))
    return n >= 200 and a[:n] == b[:n]


def annotate_sections(mineru: dict[str, Any]) -> list[dict[str, Any]]:
    """Annotate every section with an inferred role (key-agnostic)."""
    annotated: list[dict[str, Any]] = []
    inherited: str | None = None
    sections = mineru.get("sections") or []
    if not isinstance(sections, list):
        return annotated

    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or f"section_{idx}")
        text = str(sec.get("text") or "").strip()
        raw_key = str(sec.get("key") or "other").lower()
        if not text:
            continue

        role, reason = infer_section_role(
            title=title,
            text=text,
            raw_key=raw_key,
            inherited_role=inherited,
        )

        # Update inheritance on major headings / strong title roles.
        if role != "drop":
            if MAJOR_TITLE_RE.match(title.strip()) or reason == "title":
                if role in {
                    "introduction",
                    "background",
                    "method",
                    "experiment",
                    "discussion",
                    "threats",
                    "related_work",
                    "conclusion",
                }:
                    inherited = role
            elif reason == "inherited" and inherited:
                pass

        annotated.append(
            {
                "idx": idx,
                "title": title,
                "text": text,
                "raw_key": raw_key,
                "inferred_role": role,
                "infer_reason": reason,
            }
        )
    return annotated


def select_mineru_blocks(
    mineru: dict[str, Any],
    *,
    max_total_chars: int = 32000,
    per_section_chars: int = 7000,
) -> list[dict[str, str]]:
    """Return ordered text blocks for LLM claim/SOTA extraction."""
    annotated = annotate_sections(mineru)
    blocks: list[dict[str, str]] = []

    # Top-level fields — useful when present, but often incomplete.
    field_texts: dict[str, str] = {}
    for key in ("abstract", "introduction", "experiment"):
        text = mineru.get(key)
        if isinstance(text, str) and text.strip():
            field_texts[key] = text.strip()
            blocks.append(
                {
                    "source": f"field:{key}",
                    "key": key,  # backward compatible
                    "inferred_role": key,
                    "raw_key": f"field:{key}",
                    "infer_reason": "top_level_field",
                    "title": key.upper(),
                    "text": _clip(
                        text,
                        per_section_chars if key != "experiment" else per_section_chars + 2000,
                    ),
                }
            )

    # If a top-level field is missing/short, fill from inferred sections later.
    for sec in annotated:
        role = sec["inferred_role"]
        if role == "drop":
            continue
        # Always keep claim-relevant roles, including rescued ``other``.
        if role not in {
            "abstract",
            "introduction",
            "background",
            "method",
            "experiment",
            "discussion",
            "threats",
            "conclusion",
            "related_work",
        }:
            # Keep remaining ``other`` only when body looks metric-heavy.
            body_role, score = infer_role_from_body(sec["text"])
            if not (body_role == "experiment" and score >= 0.8):
                continue
            role = "experiment"
            sec = dict(sec)
            sec["inferred_role"] = role
            sec["infer_reason"] = "body_rescue"

        text = sec["text"]
        # Drop near-duplicates of top-level fields.
        field_copy = field_texts.get(role)
        if field_copy and _is_near_duplicate(field_copy, text):
            # Prefer the longer variant.
            if len(text) <= len(field_copy) * 1.05:
                continue
            blocks = [b for b in blocks if not (b.get("source") == f"field:{role}")]
        blocks.append(
            {
                "source": f"section:{sec['idx']}",
                "key": role,
                "inferred_role": role,
                "raw_key": sec["raw_key"],
                "infer_reason": sec["infer_reason"],
                "title": sec["title"],
                "text": _clip(text, per_section_chars),
            }
        )

    # Budget with reserved seats so long experiment tables do not drop conclusion.
    reserved_roles = ("abstract", "conclusion", "discussion", "introduction")
    reserved_budget = min(12000, max_total_chars // 2)
    selected: list[dict[str, str]] = []
    used = 0
    selected_ids: set[str] = set()

    def _take(block: dict[str, str], remain_cap: int | None = None) -> bool:
        nonlocal used
        bid = f"{block['source']}::{block.get('title')}"
        if bid in selected_ids:
            return False
        text = block["text"]
        if remain_cap is not None and len(text) > remain_cap:
            block = dict(block)
            block["text"] = _clip(text, remain_cap)
            text = block["text"]
        if used + len(text) > max_total_chars:
            remain = max_total_chars - used
            if remain < 600:
                return False
            block = dict(block)
            block["text"] = _clip(text, remain)
            text = block["text"]
        selected.append(block)
        selected_ids.add(bid)
        used += len(text)
        return True

    # Pass 1: ensure core narrative roles are represented.
    reserved_used = 0
    for role in reserved_roles:
        candidates = [b for b in blocks if (b.get("inferred_role") or b.get("key")) == role]
        # Prefer section over short field when both exist and section is longer.
        candidates.sort(key=lambda b: len(b["text"]), reverse=True)
        if not candidates:
            continue
        remain = reserved_budget - reserved_used
        if remain < 500:
            break
        before = used
        if _take(candidates[0], remain_cap=min(per_section_chars, remain)):
            reserved_used += used - before

    # Pass 2: fill with experiment/method/threats/etc.
    priority = sorted(
        blocks,
        key=lambda b: (
            ROLE_PRIORITY.get(b.get("inferred_role") or b.get("key") or "other", 9),
            0 if str(b.get("source", "")).startswith("field:") else 1,
            0 if b.get("infer_reason") in {"title", "inherited", "body", "body_override"} else 1,
            -len(b["text"]),
        ),
    )
    for block in priority:
        if used >= max_total_chars:
            break
        _take(block)

    def sort_key(b: dict[str, str]) -> tuple:
        src = b["source"]
        if src.startswith("field:"):
            order = {"abstract": 0, "introduction": 1, "experiment": 2}.get(b["inferred_role"], 9)
            return (0, order, src)
        try:
            idx = int(src.split(":")[1])
        except (IndexError, ValueError):
            idx = 999
        return (1, idx, src)

    selected.sort(key=sort_key)
    return selected


def format_mineru_digest(blocks: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for block in blocks:
        role = block.get("inferred_role") or block.get("key") or "other"
        raw = block.get("raw_key") or ""
        reason = block.get("infer_reason") or ""
        parts.append(
            f"### [{role}] {block['title']} "
            f"(source={block['source']}; mineru_key={raw}; via={reason})\n"
            f"{block['text']}"
        )
    return "\n\n".join(parts)


def mineru_selection_stats(blocks: list[dict[str, str]]) -> dict[str, Any]:
    roles: dict[str, int] = {}
    raw_keys: dict[str, int] = {}
    reasons: dict[str, int] = {}
    rescued_from_other = 0
    for b in blocks:
        role = b.get("inferred_role") or b.get("key") or "other"
        roles[role] = roles.get(role, 0) + 1
        raw = b.get("raw_key") or ""
        raw_keys[raw] = raw_keys.get(raw, 0) + 1
        reason = b.get("infer_reason") or ""
        reasons[reason] = reasons.get(reason, 0) + 1
        if raw == "other" and role != "other":
            rescued_from_other += 1
    return {
        "num_blocks": len(blocks),
        "total_chars": sum(len(b["text"]) for b in blocks),
        "inferred_roles": roles,
        "mineru_raw_keys": raw_keys,
        "infer_reasons": reasons,
        "rescued_from_other": rescued_from_other,
        "note": (
            "mineru key is unreliable; blocks are selected by title/body/inheritance. "
            "rescued_from_other counts sections labeled other but treated as typed roles."
        ),
    }
