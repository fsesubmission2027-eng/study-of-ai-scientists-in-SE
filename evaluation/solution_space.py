"""Build a lightweight Solution Space for idea Novelty scoring.

Primary titles come from the original paper's REFERENCES section in
``mineru_sections.json``. Abstracts are attached from ``related_work.json``
when title matching succeeds. Each entry's key innovation is LLM-extracted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from literature_sources import normalize_title
from llm_client import chat_json

EXTRACT_SYSTEM = """You extract the key technical innovation from research paper titles and abstracts.
Return ONLY valid JSON. Be concise and concrete. Do not invent methods not supported by the text.
If the abstract is missing, infer cautiously from the title only and mark low confidence.
"""

_BATCH_SIZE = 18
_ABS_MAX_CHARS = 900

_NUM_REF_RE = re.compile(r"\[\s*(\d+)\s*\]\s*")
_QUOTE_RE = re.compile(r"[“\"]([^“”\"]{6,320})[”\"]")
_YEAR_TITLE_RE = re.compile(
    r"\b((?:19|20)\d{2})\.\s+(.+?)(?="
    r"\.\s+(?:In\s|Proc\.|Proceedings|ACM\s|IEEE\s|Software:|Computer\s|"
    r"Commun\.|Trans\.|Journal|arXiv|http|https|Retrieved|Original|Vol\.|"
    r"pp\.|pages\b|Article\b)|$"
    r")",
    re.I | re.S,
)
_TRAILING_JUNK_RE = re.compile(
    r"\s*(?:,|\.|:|;|https?://|accessed:).*$",
    re.I,
)


def _looks_like_citation_meta(abstract: str) -> bool:
    a = abstract.strip()
    if not a:
        return False
    bib = bool(
        re.search(
            r"(Proceedings of|In Proceedings|arXiv:|doi\.org|Findings of the|\bACM\b|\bIEEE\b)",
            a,
        )
    )
    sci = bool(
        re.search(
            r"\b(we |this paper|propose|present|approach|method|results|evaluate|framework)\b",
            a,
            re.I,
        )
    )
    if bib and not sci and len(a) < 450:
        return True
    return False


def _clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    t = t.strip(" \t\r\n\"“”'‘’")
    t = _TRAILING_JUNK_RE.sub("", t).strip(" ,.;:")
    # Drop ultra-short / URL-only junk.
    if len(t) < 8 or re.fullmatch(r"https?://\S+", t, flags=re.I):
        return ""
    return t


def _title_from_ref_body(body: str) -> tuple[str, int | None]:
    """Extract title (+ optional year) from one bibliography entry body."""
    body = re.sub(r"\s+", " ", (body or "").strip())
    if not body:
        return "", None

    year: int | None = None
    ym = re.search(r"\b((?:19|20)\d{2})\b", body)
    if ym:
        try:
            year = int(ym.group(1))
        except ValueError:
            year = None

    quotes = _QUOTE_RE.findall(body)
    if quotes:
        cands = sorted((_clean_title(q) for q in quotes), key=len, reverse=True)
        for c in cands:
            if not c:
                continue
            if re.search(r"https?://|doi\.org|available:", c, re.I):
                continue
            return c, year

    m = _YEAR_TITLE_RE.search(body)
    if m:
        title = _clean_title(m.group(2))
        try:
            year = int(m.group(1))
        except ValueError:
            pass
        if title:
            return title, year

    # IEEE-ish unquoted: Author, Title. Venue, year.
    m2 = re.search(
        r"^[A-Z][^.]{0,180}?,\s+([A-Z][^.]{8,220})\.\s+",
        body,
    )
    if m2:
        title = _clean_title(m2.group(1))
        if title and not re.search(r"https?://", title, re.I):
            return title, year

    return "", year


def load_mineru_reference_section_text(task_dir: Path) -> str:
    path = task_dir / "mineru_sections.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    chunks: list[str] = []
    for sec in data.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "")
        key = str(sec.get("key") or "").lower()
        if key in {"references", "reference", "bibliography"} or re.search(
            r"^\s*references\s*$|bibliograph", title, re.I
        ):
            text = str(sec.get("text") or "").strip()
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)


def extract_titles_from_reference_text(text: str) -> list[dict[str, Any]]:
    """Parse bibliography text into title entries (numbered IEEE/ACM + unnumbered ACM)."""
    text = (text or "").strip()
    if not text:
        return []

    # Drop trailing "Received ... accepted ..." footer.
    text = re.sub(r"\nReceived\s+\d{4}-\d{2}-\d{2};.*$", "", text, flags=re.I | re.S)

    entries: list[dict[str, Any]] = []
    seen_norm: set[str] = set()

    def _add(title: str, *, year: int | None, raw: str, via: str, num: str | None = None) -> None:
        title = _clean_title(title)
        if not title:
            return
        norm = normalize_title(title)
        if not norm or norm in seen_norm:
            return
        seen_norm.add(norm)
        entries.append(
            {
                "title": title,
                "year": year,
                "raw": raw[:400],
                "via": via,
                "ref_num": num,
            }
        )

    parts = _NUM_REF_RE.split(text)
    if len(parts) >= 3:
        for i in range(1, len(parts) - 1, 2):
            num = parts[i]
            body = parts[i + 1].strip()
            # Stop at "Received" footer fragments inside body.
            body = re.split(r"\bReceived\s+\d{4}-\d{2}-\d{2}", body, maxsplit=1)[0].strip()
            title, year = _title_from_ref_body(body)
            _add(title, year=year, raw=body, via="numbered", num=num)

    # Unnumbered ACM-style blocks (common when [n] markers are missing).
    if len(entries) < 5:
        for m in re.finditer(
            r"(?:^|\n)([A-Z][\s\S]{10,500}?\.\s*((?:19|20)\d{2})\.\s+[\s\S]{8,400}?)(?="
            r"\n[A-Z]|\nReceived\s|\Z)",
            text,
        ):
            block = m.group(1).strip()
            title, year = _title_from_ref_body(block)
            _add(title, year=year, raw=block, via="acm_unnumbered")

    return entries


def load_related_work_by_title(task_dir: Path) -> dict[str, dict[str, Any]]:
    """Map normalized title -> related_work record (prefer richer abstract)."""
    path = task_dir / "related_work.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        title = _clean_title(str(item.get("title") or ""))
        if not title:
            continue
        norm = normalize_title(title)
        if not norm:
            continue
        abstract = str(item.get("abstract") or "").strip()
        rec = {
            "title": title,
            "year": item.get("year"),
            "abstract": abstract[:_ABS_MAX_CHARS],
            "abstract_is_citation_meta": _looks_like_citation_meta(abstract),
            "cite_key": item.get("cite_key"),
            "url": item.get("url"),
            "paper_id": item.get("paper_id"),
        }
        prev = out.get(norm)
        if prev is None:
            out[norm] = rec
            continue
        # Prefer the record with a usable abstract.
        prev_abs = (prev.get("abstract") or "").strip()
        new_abs = abstract
        prev_good = bool(prev_abs) and not prev.get("abstract_is_citation_meta")
        new_good = bool(new_abs) and not rec["abstract_is_citation_meta"]
        if new_good and not prev_good:
            out[norm] = rec
        elif len(new_abs) > len(prev_abs) and not rec["abstract_is_citation_meta"]:
            out[norm] = rec
    return out


def _token_overlap(a: str, b: str) -> float:
    ta = set(normalize_title(a).split())
    tb = set(normalize_title(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _match_related(
    title: str,
    related_by_title: dict[str, dict[str, Any]],
    *,
    used: set[str],
) -> dict[str, Any] | None:
    norm = normalize_title(title)
    if norm in related_by_title and norm not in used:
        return related_by_title[norm]
    # Soft containment / overlap match.
    best_key = None
    best_score = 0.0
    for key, rec in related_by_title.items():
        if key in used:
            continue
        if norm in key or key in norm:
            score = 0.92
        else:
            score = _token_overlap(title, rec.get("title") or "")
        if score > best_score:
            best_score = score
            best_key = key
    if best_key is not None and best_score >= 0.82:
        return related_by_title[best_key]
    return None


def load_solution_space_papers(task_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """All original-paper reference titles + abstracts from related_work when available."""
    task_dir = task_dir.resolve()
    mineru_path = task_dir / "mineru_sections.json"
    rw_path = task_dir / "related_work.json"

    ref_text = load_mineru_reference_section_text(task_dir)
    mineru_entries = extract_titles_from_reference_text(ref_text)
    related_by_title = load_related_work_by_title(task_dir)

    papers: list[dict[str, Any]] = []
    used_related: set[str] = set()
    matched_abs = 0

    for i, ent in enumerate(mineru_entries):
        title = ent["title"]
        year = ent.get("year")
        rw = _match_related(title, related_by_title, used=used_related)
        abstract = ""
        cite_meta = False
        cite_key = None
        url = None
        paper_id = None
        abs_source = None
        if rw is not None:
            used_related.add(normalize_title(rw["title"]))
            abstract = str(rw.get("abstract") or "")
            cite_meta = bool(rw.get("abstract_is_citation_meta"))
            cite_key = rw.get("cite_key")
            url = rw.get("url")
            paper_id = rw.get("paper_id")
            if year is None:
                year = rw.get("year")
            if abstract.strip():
                matched_abs += 1
                abs_source = "related_work.json"
        papers.append(
            {
                "id": f"R{i + 1}",
                "title": title,
                "year": year,
                "abstract": abstract[:_ABS_MAX_CHARS],
                "abstract_is_citation_meta": cite_meta,
                "abstract_source": abs_source,
                "cite_key": cite_key,
                "url": url,
                "paper_id": paper_id,
                "title_source": "mineru_references",
                "ref_num": ent.get("ref_num"),
            }
        )

    # Keep OpenAlex-only refs that mineru parsing missed.
    extras = 0
    for norm, rw in related_by_title.items():
        if norm in used_related:
            continue
        extras += 1
        i = len(papers) + 1
        abstract = str(rw.get("abstract") or "")
        papers.append(
            {
                "id": f"R{i}",
                "title": rw["title"],
                "year": rw.get("year"),
                "abstract": abstract[:_ABS_MAX_CHARS],
                "abstract_is_citation_meta": bool(rw.get("abstract_is_citation_meta")),
                "abstract_source": "related_work.json" if abstract.strip() else None,
                "cite_key": rw.get("cite_key"),
                "url": rw.get("url"),
                "paper_id": rw.get("paper_id"),
                "title_source": "related_work_only",
                "ref_num": None,
            }
        )
        if abstract.strip():
            matched_abs += 1

    meta = {
        "mineru_path": str(mineru_path) if mineru_path.is_file() else None,
        "related_work_path": str(rw_path) if rw_path.is_file() else None,
        "mineru_titles": len(mineru_entries),
        "related_work_titles": len(related_by_title),
        "merged_papers": len(papers),
        "abstracts_attached": matched_abs,
        "related_work_extras": extras,
        "reference_text_chars": len(ref_text),
    }
    return papers, meta


# Back-compat alias used by older call sites / smoke tests.
def load_related_work_papers(task_dir: Path) -> list[dict[str, Any]]:
    papers, _ = load_solution_space_papers(task_dir)
    return papers


def _format_batch_for_prompt(papers: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for p in papers:
        year = p.get("year")
        year_s = f" ({year})" if year not in (None, "") else ""
        abs_text = (p.get("abstract") or "").strip()
        note_parts: list[str] = []
        if p.get("title_source") == "related_work_only":
            note_parts.append("title from related_work only")
        if p.get("abstract_is_citation_meta"):
            note_parts.append("abstract looks like citation metadata")
        elif not abs_text:
            note_parts.append("abstract missing; title-only")
        elif p.get("abstract_source"):
            note_parts.append(f"abstract from {p['abstract_source']}")
        note = f" [{'; '.join(note_parts)}]" if note_parts else ""
        blocks.append(
            f"### {p['id']}: {p['title']}{year_s}{note}\n"
            f"Abstract: {abs_text or '(none)'}"
        )
    return "\n\n".join(blocks)


def _extract_batch(
    papers: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> list[dict[str, Any]]:
    if not papers:
        return []
    user = f"""For each paper below, extract its key innovation / core technical contribution
in one short sentence (≤35 words). Focus on the method or mechanism, not the application domain alone.

Return JSON:
{{
  "entries": [
    {{
      "id": "R1",
      "key_innovation": "...",
      "mechanism_tags": ["short", "tags"],
      "confidence": 0.0
    }}
  ]
}}

Include one entry per paper id. If the abstract is missing, still give a best-effort
innovation from the title and set confidence <= 0.4.

=== PAPERS ===
{_format_batch_for_prompt(papers)}
"""
    data = chat_json(system=EXTRACT_SYSTEM, user=user, model=model, max_tokens=3500)
    raw = data.get("entries") if isinstance(data.get("entries"), list) else []
    by_id = {
        str(e.get("id")): e
        for e in raw
        if isinstance(e, dict) and e.get("id")
    }
    out: list[dict[str, Any]] = []
    for p in papers:
        e = by_id.get(p["id"]) or {}
        innovation = str(e.get("key_innovation") or "").strip()
        tags = e.get("mechanism_tags") if isinstance(e.get("mechanism_tags"), list) else []
        try:
            conf = float(e.get("confidence"))
        except (TypeError, ValueError):
            conf = 0.3 if not (p.get("abstract") or "").strip() else 0.5
        out.append(
            {
                "id": p["id"],
                "title": p["title"],
                "year": p.get("year"),
                "cite_key": p.get("cite_key"),
                "key_innovation": innovation or f"(title-only) {p['title']}",
                "mechanism_tags": [str(t)[:40] for t in tags[:8]],
                "confidence": max(0.0, min(1.0, conf)),
                "abstract_missing": not bool((p.get("abstract") or "").strip()),
                "abstract_is_citation_meta": bool(p.get("abstract_is_citation_meta")),
                "abstract_source": p.get("abstract_source"),
                "title_source": p.get("title_source"),
            }
        )
    return out


def format_solution_space_digest(
    space: dict[str, Any],
    *,
    max_chars: int = 16000,
) -> str:
    """Compact digest for Novelty scoring prompts."""
    entries = space.get("entries") if isinstance(space.get("entries"), list) else []
    src_meta = space.get("source_meta") or {}
    lines: list[str] = [
        "Solution Space (key innovations from the original paper's references):",
        f"mineru_titles={src_meta.get('mineru_titles')} "
        f"related_work={src_meta.get('related_work_titles')} "
        f"merged={space.get('paper_count')} extracted={len(entries)} "
        f"abstracts_attached={src_meta.get('abstracts_attached')}",
        "",
    ]
    for e in entries:
        if not isinstance(e, dict):
            continue
        year = e.get("year")
        year_s = f" ({year})" if year not in (None, "") else ""
        conf = e.get("confidence")
        conf_s = f" conf={conf:.2f}" if isinstance(conf, (int, float)) else ""
        weak = []
        if e.get("abstract_missing"):
            weak.append("no-abstract")
        if e.get("abstract_is_citation_meta"):
            weak.append("cite-meta-abstract")
        if e.get("title_source") == "related_work_only":
            weak.append("related-work-only")
        weak_s = f" [{','.join(weak)}]" if weak else ""
        lines.append(f"- [{e.get('id')}] {e.get('title')}{year_s}{conf_s}{weak_s}")
        lines.append(f"  Innovation: {e.get('key_innovation')}")
        tags = e.get("mechanism_tags") or []
        if tags:
            lines.append(f"  Tags: {', '.join(str(t) for t in tags)}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n...[truncated]"
    return text


def build_solution_space(
    task_dir: Path,
    *,
    model: str | None = None,
    evals_root: Path | None = None,
    force: bool = False,
    cache_path: Path | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Build or load cached Solution Space for a task."""
    task_dir = task_dir.resolve()
    if cache_path is None:
        from eval_layout import solution_space_path

        cache_path = solution_space_path(task_dir, evals_root=evals_root)

    if cache_path.is_file() and not force:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("status") == "ok" and cached.get("entries"):
                # Require new schema (mineru+related_work merge).
                if (cached.get("source_meta") or {}).get("mineru_titles") is not None:
                    cached = dict(cached)
                    cached["cache_hit"] = True
                    return cached
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass

    papers, source_meta = load_solution_space_papers(task_dir)
    mineru_path = task_dir / "mineru_sections.json"
    rw_path = task_dir / "related_work.json"
    base: dict[str, Any] = {
        "status": "ok",
        "task_dir": str(task_dir),
        "source_file": source_meta.get("mineru_path") or source_meta.get("related_work_path"),
        "source_meta": source_meta,
        "paper_count": len(papers),
        "entries": [],
        "notes": [
            "Titles primarily from mineru_sections.json REFERENCES of the original paper.",
            "Abstracts attached from related_work.json when titles match.",
            "Unmatched related_work entries are appended as extras.",
            "Each entry's key_innovation is LLM-extracted from title (+ abstract if present).",
        ],
        "cache_hit": False,
    }

    if not mineru_path.is_file() and not rw_path.is_file():
        base["status"] = "missing_reference_sources"
        base["hint"] = f"Expected {mineru_path} and/or {rw_path}"
        return base

    if not papers:
        base["status"] = "empty_references"
        base["hint"] = "No reference titles parsed from mineru REFERENCES or related_work.json"
        return base

    if skip_llm:
        base["status"] = "papers_found_llm_skipped"
        base["entries"] = [
            {
                "id": p["id"],
                "title": p["title"],
                "year": p.get("year"),
                "cite_key": p.get("cite_key"),
                "key_innovation": None,
                "mechanism_tags": [],
                "confidence": None,
                "abstract_missing": not bool((p.get("abstract") or "").strip()),
                "abstract_is_citation_meta": bool(p.get("abstract_is_citation_meta")),
                "abstract_source": p.get("abstract_source"),
                "title_source": p.get("title_source"),
            }
            for p in papers
        ]
        return base

    entries: list[dict[str, Any]] = []
    meta_batches: list[Any] = []
    for i in range(0, len(papers), _BATCH_SIZE):
        batch = papers[i : i + _BATCH_SIZE]
        try:
            extracted = _extract_batch(batch, model=model)
            entries.extend(extracted)
        except Exception as exc:  # noqa: BLE001
            base["status"] = "llm_failed"
            base["error"] = str(exc)
            base["entries"] = entries
            return base
        meta_batches.append({"batch_start": i, "batch_size": len(batch)})

    usable_abs = sum(
        1
        for p in papers
        if (p.get("abstract") or "").strip() and not p.get("abstract_is_citation_meta")
    )
    base.update(
        {
            "status": "ok",
            "entries": entries,
            "stats": {
                "papers": len(papers),
                "extracted": len(entries),
                "usable_abstracts": usable_abs,
                "citation_meta_abstracts": sum(
                    1 for p in papers if p.get("abstract_is_citation_meta")
                ),
                "missing_abstracts": sum(
                    1 for p in papers if not (p.get("abstract") or "").strip()
                ),
                "mineru_titles": source_meta.get("mineru_titles"),
                "related_work_titles": source_meta.get("related_work_titles"),
                "abstracts_attached": source_meta.get("abstracts_attached"),
                "related_work_extras": source_meta.get("related_work_extras"),
                "batches": len(meta_batches),
            },
        }
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
    return base
