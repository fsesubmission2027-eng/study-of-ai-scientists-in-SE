"""Convert task related_work.json into ARC stage-05/shortlist.jsonl.

AutoResearchClaw Stage 6 (KNOWLEDGE_EXTRACT) reads ``stage-05/shortlist.jsonl``
(JSONL: one paper object per line). Benchmark tasks store curated references as
``related_work.json`` (a JSON array). This module normalizes, validates, and
writes the ARC-compatible shortlist so --from-stage KNOWLEDGE_EXTRACT can skip
Stages 3–5 without changing ARC upstream.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Fields ARC Stage 6 / paper writing actually rely on.
_REQUIRED_FIELDS = ("title", "authors", "year", "cite_key")
_RECOMMENDED_FIELDS = ("abstract", "url", "paper_id", "source")
_OPTIONAL_PASSTHROUGH = (
    "venue",
    "doi",
    "arxiv_id",
    "citation_count",
    "relevance_score",
    "quality_score",
    "keep_reason",
)

DEFAULT_RELATED_WORK_NAMES = (
    "related_work.json",
    "seeds/literature/related_work.json",
    "seeds/literature/shortlist.jsonl",
    "seeds/literature/shortlist.json",
)

# ARC literature_screen aims for >=15 papers when supplementing shortlists.
MIN_SHORTLIST_WARN = 15


class RelatedWorkError(ValueError):
    """Invalid or missing related-work seed for skip-literature mode."""


def find_related_work_path(task_dir: Path, explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        path = explicit.expanduser()
        if not path.is_absolute():
            path = (task_dir / path).resolve()
        return path if path.is_file() else None
    for name in DEFAULT_RELATED_WORK_NAMES:
        candidate = task_dir / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _slug_cite_key(title: str, year: Any, authors: list[Any]) -> str:
    surname = "anon"
    if authors:
        first = authors[0]
        if isinstance(first, dict):
            name = str(first.get("name") or first.get("author") or "anon")
        else:
            name = str(first)
        parts = name.replace(",", " ").split()
        surname = re.sub(r"[^a-z0-9]", "", (parts[-1] if parts else "anon").lower()) or "anon"
    try:
        y = int(year)
    except (TypeError, ValueError):
        y = 0
    words = re.findall(r"[a-z0-9]+", (title or "paper").lower())
    hint = "".join(words[:2]) or "paper"
    return f"{surname}{y}{hint}"[:48]


def _normalize_authors(raw: Any) -> list[dict[str, str]]:
    if not raw:
        return []
    out: list[dict[str, str]] = []
    if isinstance(raw, str):
        for part in re.split(r"\s+and\s+|;\s*", raw):
            name = part.strip()
            if name:
                out.append({"name": name})
        return out
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("author") or "").strip()
                if name:
                    out.append({"name": name})
            else:
                name = str(item).strip()
                if name:
                    out.append({"name": name})
    return out


def _extract_doi(url: str, doi: str = "") -> str:
    if doi:
        return doi.strip()
    m = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", url or "", flags=re.I)
    return m.group(1) if m else ""


def _extract_arxiv_id(url: str, arxiv_id: str = "") -> str:
    if arxiv_id:
        return arxiv_id.strip()
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+(?:v\d+)?)", url or "", flags=re.I)
    return m.group(1) if m else ""


def normalize_paper_entry(raw: dict[str, Any], *, index: int) -> dict[str, Any]:
    title = str(raw.get("title") or "").strip()
    authors = _normalize_authors(raw.get("authors"))
    year = raw.get("year")
    try:
        year_i = int(year) if year not in (None, "") else 0
    except (TypeError, ValueError):
        year_i = 0

    cite_key = str(raw.get("cite_key") or "").strip()
    if not cite_key:
        cite_key = _slug_cite_key(title, year_i or "0000", authors)

    url = str(raw.get("url") or "").strip()
    doi = _extract_doi(url, str(raw.get("doi") or "").strip())
    arxiv_id = _extract_arxiv_id(url, str(raw.get("arxiv_id") or "").strip())
    abstract = str(raw.get("abstract") or "").strip()
    paper_id = str(raw.get("paper_id") or "").strip() or f"manual-{index + 1}"
    source = str(raw.get("source") or "").strip() or "manual"

    try:
        relevance = float(raw.get("relevance_score", 0.9))
    except (TypeError, ValueError):
        relevance = 0.9
    try:
        quality = float(raw.get("quality_score", 0.85 if abstract else 0.55))
    except (TypeError, ValueError):
        quality = 0.85 if abstract else 0.55

    keep_reason = str(raw.get("keep_reason") or "").strip() or (
        "Curated related_work.json seed for benchmark skip-literature"
    )

    citation_raw = raw.get("citation_count", 0)
    try:
        citation_count = int(citation_raw) if citation_raw not in (None, "") else 0
    except (TypeError, ValueError):
        citation_count = 0

    entry: dict[str, Any] = {
        "paper_id": paper_id,
        "title": title,
        "authors": authors,
        "year": year_i,
        "abstract": abstract,
        "venue": str(raw.get("venue") or "").strip(),
        "citation_count": citation_count,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "url": url,
        "source": source,
        "cite_key": cite_key,
        "relevance_score": relevance,
        "quality_score": quality,
        "keep_reason": keep_reason,
    }
    return entry


def load_related_work_entries(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    # JSONL source
    if path.suffix == ".jsonl" or (
        "\n" in text and text.lstrip().startswith("{") and not text.lstrip().startswith("[")
    ):
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    data = json.loads(text)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("papers", "shortlist", "entries", "related_work"):
            val = data.get(key)
            if isinstance(val, list):
                return [row for row in val if isinstance(row, dict)]
        if any(k in data for k in ("title", "cite_key")):
            return [data]
    raise RelatedWorkError(f"Unsupported related_work format in {path}")


def validate_shortlist_entries(
    entries: list[dict[str, Any]],
    *,
    min_papers: int = 1,
    warn_below: int = MIN_SHORTLIST_WARN,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize, drop invalid rows, dedupe cite_keys. Returns (entries, warnings)."""
    warnings: list[str] = []
    cleaned: list[dict[str, Any]] = []
    seen_keys: dict[str, int] = {}
    seen_titles: set[str] = set()

    for idx, raw in enumerate(entries):
        if not isinstance(raw, dict):
            warnings.append(f"skip entry {idx}: not an object")
            continue
        entry = normalize_paper_entry(raw, index=idx)
        title = entry["title"]
        if not title:
            warnings.append(f"skip entry {idx}: missing title")
            continue
        if not entry["authors"]:
            warnings.append(f"entry {idx} ({title[:40]}): missing authors — using anon")
            entry["authors"] = [{"name": "Anonymous"}]
        if not entry["year"]:
            warnings.append(f"entry {idx} ({title[:40]}): missing/invalid year — set 0")
        if not entry["abstract"]:
            warnings.append(f"entry {idx} ({title[:40]}): empty abstract")
        if not (entry["url"] or entry["doi"] or entry["arxiv_id"]):
            warnings.append(f"entry {idx} ({title[:40]}): no url/doi/arxiv_id")

        title_key = re.sub(r"\s+", " ", title.lower()).strip()
        if title_key in seen_titles:
            warnings.append(f"skip duplicate title: {title[:60]}")
            continue
        seen_titles.add(title_key)

        cite_key = entry["cite_key"]
        if cite_key in seen_keys:
            n = seen_keys[cite_key] + 1
            seen_keys[cite_key] = n
            entry["cite_key"] = f"{cite_key}_{n}"
            warnings.append(
                f"duplicate cite_key {cite_key!r} → renamed to {entry['cite_key']!r}"
            )
        else:
            seen_keys[cite_key] = 1

        cleaned.append(entry)

    if len(cleaned) < min_papers:
        raise RelatedWorkError(
            f"Need at least {min_papers} valid paper(s) after normalization; got {len(cleaned)}"
        )
    if len(cleaned) < warn_below:
        warnings.append(
            f"only {len(cleaned)} papers after cleaning "
            f"(ARC often prefers >= {warn_below} for related work)"
        )
    return cleaned, warnings


def write_shortlist_jsonl(path: Path, entries: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in entries:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def write_skip_literature_stubs(
    run_root: Path,
    entries: list[dict[str, Any]],
    *,
    source_path: Path,
) -> None:
    """Write minimal stage-03/04 artifacts so later stages can find references.bib."""
    stage04 = run_root / "stage-04"
    stage04.mkdir(parents=True, exist_ok=True)
    stage03 = run_root / "stage-03"
    stage03.mkdir(parents=True, exist_ok=True)

    # candidates.jsonl: same papers (upstream of screen)
    write_shortlist_jsonl(stage04 / "candidates.jsonl", entries)

    bib_lines: list[str] = []
    for e in entries:
        key = e["cite_key"]
        authors = " and ".join(a.get("name", "") for a in e.get("authors") or [])
        title = e.get("title", "").replace("{", "").replace("}", "")
        year = e.get("year") or ""
        url = e.get("url") or ""
        doi = e.get("doi") or ""
        arxiv_id = e.get("arxiv_id") or ""
        venue = e.get("venue") or ""
        entry_type = "article"
        if arxiv_id:
            entry_type = "misc"
        elif venue and any(x in venue.lower() for x in ("conf", "icse", "fse", "ase", "issta")):
            entry_type = "inproceedings"
        fields = [
            f"  title = {{{title}}}",
            f"  author = {{{authors or 'Anonymous'}}}",
            f"  year = {{{year}}}",
        ]
        if venue:
            fields.append(f"  {'booktitle' if entry_type == 'inproceedings' else 'journal'} = {{{venue}}}")
        if doi:
            fields.append(f"  doi = {{{doi}}}")
        if url:
            fields.append(f"  url = {{{url}}}")
        if arxiv_id:
            fields.append(f"  eprint = {{{arxiv_id}}}")
            fields.append("  archivePrefix = {arXiv}")
        bib_lines.append(f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}\n")
    (stage04 / "references.bib").write_text("\n".join(bib_lines) + "\n", encoding="utf-8")

    meta = {
        "real_search": False,
        "seeded_from": str(source_path),
        "queries_used": [],
        "total_candidates": len(entries),
        "bibtex_entries": len(entries),
        "note": "Benchmark integration seeded literature; Stages 3–5 skipped.",
    }
    (stage04 / "search_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (stage04 / "decision.json").write_text(
        json.dumps(
            {
                "stage_id": "04-literature_collect",
                "status": "done",
                "decision": "seeded_skip",
                "output_artifacts": ["candidates.jsonl", "references.bib", "search_meta.json"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage03 / "queries.json").write_text(
        json.dumps(
            {
                "queries": [],
                "year_min": 0,
                "model_queries_extracted": False,
                "fallback_reason": "skip_literature_seeded",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage03 / "decision.json").write_text(
        json.dumps(
            {
                "stage_id": "03-search_strategy",
                "status": "done",
                "decision": "seeded_skip",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def seed_literature_for_skip(
    task_dir: Path,
    run_root: Path,
    *,
    related_work_path: Path | None = None,
    min_papers: int = 1,
    write_stubs: bool = True,
    topic: str = "",
    write_goal_stub: bool = False,
) -> tuple[Path, list[dict[str, Any]], list[str]]:
    """Load related_work, write stage-05/shortlist.jsonl (+ optional 03/04 stubs).

    Returns (shortlist_path, entries, warnings).
    """
    src = find_related_work_path(task_dir, related_work_path)
    if src is None:
        raise RelatedWorkError(
            f"No related_work.json found under {task_dir}. "
            "Expected related_work.json (or seeds/literature/shortlist.jsonl)."
        )
    raw_entries = load_related_work_entries(src)
    entries, warnings = validate_shortlist_entries(raw_entries, min_papers=min_papers)
    out = write_shortlist_jsonl(run_root / "stage-05" / "shortlist.jsonl", entries)
    screen_meta = {
        "outcome": "seeded_skip_literature",
        "candidates_screened": len(entries),
        "shortlist_size": len(entries),
        "source": str(src),
        "note": (
            "Benchmark integration converted related_work.json → shortlist.jsonl; "
            "Stages 3–5 were skipped; pipeline resumes at KNOWLEDGE_EXTRACT."
        ),
    }
    (run_root / "stage-05" / "screen_meta.json").write_text(
        json.dumps(screen_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_root / "stage-05" / "decision.json").write_text(
        json.dumps(
            {
                "stage_id": "05-literature_screen",
                "status": "done",
                "decision": "seeded_skip",
                "output_artifacts": ["shortlist.jsonl", "screen_meta.json"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if write_stubs:
        write_skip_literature_stubs(run_root, entries, source_path=src)
    # Only when resuming from KNOWLEDGE_EXTRACT without running TOPIC_INIT (e.g. --from-stage).
    if write_goal_stub and topic.strip():
        stage01 = run_root / "stage-01"
        stage01.mkdir(parents=True, exist_ok=True)
        goal_path = stage01 / "goal.md"
        if not goal_path.is_file():
            goal_path.write_text(
                "# Research Goal\n\n"
                f"{topic.strip()}\n\n"
                "## Note\n\n"
                "Seeded by benchmark integration (`--from-stage KNOWLEDGE_EXTRACT`); "
                "TOPIC_INIT was not executed.\n",
                encoding="utf-8",
            )
        decision_path = stage01 / "decision.json"
        if not decision_path.is_file():
            decision_path.write_text(
                json.dumps(
                    {
                        "stage_id": "01-topic_init",
                        "status": "done",
                        "decision": "seeded_skip",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    return out, entries, warnings
