"""Convert task related_work.json into AI-Researcher source_papers.

AI-Researcher InnoFlow expects each paper as::

    {"reference": "...", "usage": "...", "rank": N, "type": [...], "justification": "..."}

Benchmark tasks store curated references as ``related_work.json`` (title / authors /
year / cite_key / abstract / …). This module normalizes that list into the
``source_papers`` shape so any ``ai_scientist_inputs`` task can run without a
hand-written ``AI-Researcher/benchmark/final/.../*.json`` instance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from researchclaw_literature_seed import (
    RelatedWorkError,
    find_related_work_path,
    load_related_work_entries,
    normalize_paper_entry,
)

DEFAULT_USAGE = (
    "Use as related work and conceptual inspiration when forming the research idea, "
    "baselines, and evaluation framing."
)


def _author_et_al(authors: list[Any]) -> str:
    if not authors:
        return "Anonymous"
    first = authors[0]
    if isinstance(first, dict):
        name = str(first.get("name") or first.get("author") or "Anonymous").strip()
    else:
        name = str(first).strip() or "Anonymous"
    parts = name.replace(",", " ").split()
    surname = parts[-1] if parts else name
    if len(authors) == 1:
        return surname
    return f"{surname} et al."


def _reference_string(entry: dict[str, Any]) -> str:
    title = str(entry.get("title") or "").strip()
    year = entry.get("year") or ""
    authors = entry.get("authors") or []
    author_bit = _author_et_al(authors)
    if year and title:
        return f"{author_bit}, {title} ({year})"
    if title:
        return f"{author_bit}, {title}"
    return author_bit


def _usage_from_entry(entry: dict[str, Any]) -> str:
    abstract = str(entry.get("abstract") or "").strip()
    keep = str(entry.get("keep_reason") or "").strip()
    # Prefer abstract as actionable "how to use" guidance for InnoFlow.
    if abstract:
        sentence = re.split(r"(?<=[.!?])\s+", abstract, maxsplit=1)[0].strip()
        if len(sentence) > 280:
            sentence = sentence[:277].rstrip() + "..."
        return f"Background / method cue: {sentence}"
    if keep and not keep.lower().startswith("cited by source paper"):
        return keep
    if keep:
        return keep
    return DEFAULT_USAGE


def _justification_from_entry(entry: dict[str, Any]) -> str:
    keep = str(entry.get("keep_reason") or "").strip()
    if keep:
        return keep
    source = str(entry.get("source") or "").strip()
    if source:
        return f"Seeded from related_work.json ({source})."
    return "Seeded from task related_work.json."


def related_work_to_source_papers(
    entries: list[dict[str, Any]],
    *,
    max_papers: int | None = None,
) -> list[dict[str, Any]]:
    """Normalize related-work rows into AI-Researcher ``source_papers`` objects."""
    papers: list[dict[str, Any]] = []
    for idx, raw in enumerate(entries):
        if not isinstance(raw, dict):
            continue
        # Accept already-native source_papers rows.
        if "reference" in raw and "usage" in raw:
            ref = str(raw.get("reference") or "").strip()
            if not ref:
                continue
            papers.append(
                {
                    "reference": ref,
                    "rank": int(raw.get("rank") or len(papers) + 1),
                    "type": list(raw.get("type") or ["conceptual inspiration"]),
                    "justification": str(
                        raw.get("justification") or _justification_from_entry(raw)
                    ).strip(),
                    "usage": str(raw.get("usage") or DEFAULT_USAGE).strip(),
                }
            )
            continue

        entry = normalize_paper_entry(raw, index=idx)
        if not entry.get("title"):
            continue
        papers.append(
            {
                "reference": _reference_string(entry),
                "rank": len(papers) + 1,
                "type": ["conceptual inspiration"],
                "justification": _justification_from_entry(entry),
                "usage": _usage_from_entry(entry),
            }
        )
        if max_papers is not None and len(papers) >= max_papers:
            break
    return papers


def warp_source_papers(source_papers: list[dict[str, Any]]) -> str:
    """Match AI-Researcher ``run_infer_plan.warp_source_papers`` formatting."""
    return "\n".join(
        f"Title: {p['reference']}; You can use this paper in the following way: {p['usage']}"
        for p in source_papers
    )


def load_source_papers_for_task(
    task_dir: Path,
    *,
    related_work_path: Path | None = None,
    max_papers: int | None = None,
    min_papers: int = 1,
) -> tuple[list[dict[str, Any]], Path | None, list[str]]:
    """Load related_work (or native source_papers) for a task.

    Returns ``(source_papers, source_path, warnings)``.
    """
    warnings: list[str] = []
    src = find_related_work_path(task_dir, related_work_path)
    if src is None:
        raise RelatedWorkError(
            f"No related_work.json found under {task_dir}. "
            "Expected related_work.json (or seeds/literature/shortlist.jsonl)."
        )
    raw_entries = load_related_work_entries(src)
    papers = related_work_to_source_papers(raw_entries, max_papers=max_papers)
    if len(papers) < min_papers:
        raise RelatedWorkError(
            f"Need at least {min_papers} paper(s) after conversion; got {len(papers)} from {src}"
        )
    if len(papers) < 5:
        warnings.append(
            f"only {len(papers)} source_papers after conversion "
            "(AI-Researcher prepare_agent prefers >=5 GitHub repos / papers)"
        )
    return papers, src, warnings


def write_source_papers_json(path: Path, source_papers: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(source_papers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
