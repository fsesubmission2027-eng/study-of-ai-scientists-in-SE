"""Extract and normalize literature references from agent runs and task gold sets."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from paths import find_tex, iter_paper_tex_paths

_JUNK_PARTS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "skills",
    "templates",
    "site-packages",
    ".deepscientist_npm",
    ".codex",
    "opencode-home",
    "python-env",
    "uv-cache",
    ".uv-cache",
}


@dataclass
class RefRecord:
    title: str = ""
    year: int | None = None
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    cite_key: str = ""
    authors: list[str] = field(default_factory=list)
    raw: str = ""
    source_file: str = ""
    source_kind: str = ""  # bib | thebibliography | shortlist | json | related_work_txt | arxiv_index

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Drop leading articles for softer matching.
    for art in ("the ", "a ", "an "):
        if t.startswith(art):
            t = t[len(art) :]
            break
    return t


def extract_doi(text: str) -> str:
    if not text:
        return ""
    m = re.search(
        r"(?:doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
        text,
        flags=re.I,
    )
    if not m:
        return ""
    doi = m.group(1).rstrip(").,;")
    return doi.lower()


def extract_arxiv_id(text: str) -> str:
    if not text:
        return ""
    m = re.search(
        r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:\s*)(\d{4}\.\d{4,5})(?:v\d+)?",
        text,
        flags=re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"\barXiv:(\d{4}\.\d{4,5})\b", text, flags=re.I)
    return m.group(1) if m else ""


def extract_year(text: str) -> int | None:
    if not text:
        return None
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    if not years:
        return None
    # Prefer the last plausible publication year in the snippet.
    for y in reversed(years):
        if 1950 <= y <= 2035:
            return y
    return years[-1]


def _is_junk_path(path: Path) -> bool:
    return any(p.lower() in _JUNK_PARTS for p in path.parts)


# Venue names must not be searched as if they were paper titles.
_VENUE_RE = re.compile(
    r"("
    r"\bproceedings\b"
    r"|\bproc\."
    r"|\bjournal of\b"
    r"|\btransactions on\b"
    r"|\btrans\."
    r"|\bworkshop\b"
    r"|\bconference\b"
    r"|\bsymposium\b"
    r"|\barxiv preprint\b"
    r"|\blec(?:ture)?\.?\s*notes\b"
    r")",
    re.I,
)


def clean_latex_inline(text: str) -> str:
    s = text or ""
    s = re.sub(r"\\(?:emph|textit|textbf|texttt|textrm|url|href)\{([^{}]*)\}", r"\1", s)
    s = (
        s.replace("\\.", ".")
        .replace("\\&", "&")
        .replace("\\%", "%")
        .replace("\\_", " ")
        .replace("~", " ")
    )
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", s)
    s = re.sub(r"[{}]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,.;")


def is_venue_fragment(text: str) -> bool:
    cleaned = clean_latex_inline(text)
    return bool(cleaned and _VENUE_RE.search(cleaned))


def _is_author_line(line: str) -> bool:
    if re.search(r"\bet al\.?\b", line, re.I):
        return True
    return bool(
        re.search(r"(?:^|[\s,])[A-Z]\.", line)
        and ("," in line or re.search(r"\band\b", line, re.I))
    )


def _plain_bibitem_sentences(body: str) -> list[str]:
    """Non-venue sentences after authors, with \\emph venues removed."""
    plain = re.sub(r"\\(?:emph|textit|textbf|texttt|url|href)\{([^{}]*)\}", " ", body)
    plain = plain.replace("\\newblock", " ")
    plain = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", plain)
    plain = plain.replace("~", " ")
    plain = re.sub(r"[{}]", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip(" ,;")
    sentences: list[str] = []
    for part in re.split(r"\.\s+", plain):
        part = re.sub(r"^in\s+", "", part, flags=re.I).strip(" ,.;")
        if len(part) < 12 or part.lower().startswith(("http", "doi")):
            continue
        if _is_author_line(part) or is_venue_fragment(part):
            continue
        sentences.append(part.rstrip("."))
    return sentences


def bibitem_title(body: str) -> str:
    """Pick the paper title from a thebibliography item, never the venue.

    Short \\emph{ISSTA} / \\emph{J. Syst. Softw.} fragments are venues.
    The title is the longer plain sentence when one exists.
    """
    body = re.split(r"\\end\{thebibliography\}", body, maxsplit=1)[0]
    quoted: list[str] = []
    for pat in (r"``(.+?)''", r"“(.+?)”", r"\"(.+?)\""):
        quoted.extend(m.group(1).strip() for m in re.finditer(pat, body, flags=re.S))
    good_quoted = [
        clean_latex_inline(t)
        for t in quoted
        if not is_venue_fragment(t) and len(clean_latex_inline(t)) >= 8
    ]
    if good_quoted:
        return max(good_quoted, key=len)

    sentences = _plain_bibitem_sentences(body)
    emph = [
        clean_latex_inline(m.group(1))
        for m in re.finditer(r"\\(?:emph|textit)\{([^{}]+)\}", body)
    ]
    emph_good = [t for t in emph if not is_venue_fragment(t) and len(t) >= 8]
    if sentences:
        longest = max(sentences, key=len)
        # A short italic venue ("IEEE TSE", "Ocean Engineering") must not beat the title.
        emph_good = [t for t in emph_good if len(t.split()) > 4 and len(t) >= len(longest)]
        if emph_good:
            return max(emph_good, key=len)
        return longest
    if emph_good:
        return max(emph_good, key=len)
    return ""


def title_search_queries(title: str) -> list[str]:
    """Full title, plus the longer side of a colon subtitle as a retrieval probe.

    Acceptance still compares hits against the full title.
    """
    title = re.sub(r"\s+", " ", title or "").strip(" .")
    if not title:
        return []
    queries = [title]
    if ":" in title:
        head, tail = [p.strip(" .") for p in title.split(":", 1)]
        extra = tail if len(tail) >= len(head) else head
        if len(extra) >= 12 and extra.lower() != title.lower():
            queries.append(extra)
    return queries


def _bib_field(block: str, name: str) -> str:
    # title = {...} or title = "..."
    pat = rf"(?im)^\s*{re.escape(name)}\s*=\s*(\{{([^{{}}]*)\}}|\"([^\"]*)\")"
    m = re.search(pat, block)
    if not m:
        # Nested braces fallback (one level).
        pat2 = rf"(?im)^\s*{re.escape(name)}\s*=\s*\{{((?:[^{{}}]|\{{[^{{}}]*\}})+)\}}"
        m2 = re.search(pat2, block)
        if not m2:
            return ""
        return re.sub(r"\s+", " ", m2.group(1)).strip()
    return re.sub(r"\s+", " ", (m.group(2) or m.group(3) or "")).strip()


def parse_bibtex(text: str, *, source_file: str = "") -> list[RefRecord]:
    out: list[RefRecord] = []
    for m in re.finditer(r"(?s)@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n\s*@|\Z)", text):
        key, body = m.group(1), m.group(2)
        # booktitle is the venue; using it as the paper title creates false misses.
        title = clean_latex_inline(_bib_field(body, "title"))
        if not title or is_venue_fragment(title):
            continue
        year_raw = _bib_field(body, "year")
        year = extract_year(year_raw) if year_raw else extract_year(body)
        doi = extract_doi(_bib_field(body, "doi") or body)
        arxiv = extract_arxiv_id(_bib_field(body, "eprint") or _bib_field(body, "url") or body)
        url = _bib_field(body, "url")
        author = _bib_field(body, "author")
        authors = [a.strip() for a in re.split(r"\s+and\s+", author)] if author else []
        out.append(
            RefRecord(
                title=title,
                year=year,
                doi=doi,
                arxiv_id=arxiv,
                url=url,
                cite_key=key,
                authors=authors,
                raw=m.group(0)[:500],
                source_file=source_file,
                source_kind="bib",
            )
        )
    return out


def parse_thebibliography(text: str, *, source_file: str = "") -> list[RefRecord]:
    out: list[RefRecord] = []
    # Split on \bibitem
    parts = re.split(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", text)
    # parts: preamble, key1, body1, key2, body2, ...
    i = 1
    while i + 1 < len(parts):
        key = parts[i].strip()
        body = parts[i + 1]
        i += 2
        title = bibitem_title(body)
        if not title or len(title) < 3 or is_venue_fragment(title):
            continue
        url_m = re.search(r"https?://[^\s\}]+", body)
        out.append(
            RefRecord(
                title=title,
                year=extract_year(body),
                doi=extract_doi(body),
                arxiv_id=extract_arxiv_id(body),
                url=url_m.group(0).rstrip(").,;") if url_m else "",
                cite_key=key,
                raw=body[:500],
                source_file=source_file,
                source_kind="thebibliography",
            )
        )
    return out


# LaTeX cite commands (natbib / biblatex / plain).
_CITE_CMD_RE = re.compile(
    r"\\(?:cite|citep|citet|citeauthor|citeyear|citeyearpar|footcite|textcite|autocite|parencite|supercite|Cite|nocite)"
    r"(?:\[[^\]]*\])*\{([^}]+)\}",
    re.IGNORECASE,
)

# Uncited bulk .bib files (e.g. ACL anthology dumps) are not scored as agent references.
_MAX_UNCITED_BIB_ENTRIES = 40


def extract_cite_keys_from_tex(text: str) -> set[str]:
    keys: set[str] = set()
    for m in _CITE_CMD_RE.finditer(text):
        for part in m.group(1).split(","):
            key = part.strip()
            if key and not key.startswith("*"):
                keys.add(key)
    return keys


_PAPER_TEX_SKIP_NAMES = {
    "template.tex",
    "sample.tex",
    "example.tex",
    "formatting.tex",
    "acl_lualatex.tex",
    "lualatex.tex",
}


def extract_cite_keys_from_run(run_dir: Path) -> set[str]:
    """Cite keys from the primary paper TeX only (not alternate template builds)."""
    primary = find_tex(run_dir)
    if primary is not None:
        try:
            return extract_cite_keys_from_tex(primary.path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return set()
    keys: set[str] = set()
    for path in iter_paper_tex_paths(run_dir):
        try:
            keys |= extract_cite_keys_from_tex(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return keys


def _parse_source_file(path: Path, kind: str) -> list[RefRecord]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if kind == "shortlist":
        return parse_shortlist_jsonl(path)
    if kind == "bib":
        return parse_bibtex(text, source_file=str(path))
    if kind == "thebibliography":
        return parse_thebibliography(text, source_file=str(path))
    if kind == "related_work_txt":
        return parse_related_work_txt(text, source_file=str(path))
    if kind == "literature_survey":
        return parse_literature_survey_md(text, source_file=str(path))
    if kind == "literature_synthesis":
        return parse_literature_synthesis_md(text, source_file=str(path))
    if kind == "arxiv_index":
        return parse_arxiv_index(path)
    return []


def _dedupe_refs(refs: list[RefRecord]) -> list[RefRecord]:
    deduped: list[RefRecord] = []
    seen_keys: set[str] = set()
    for ref in refs:
        key = ref.doi or ref.arxiv_id or normalize_title(ref.title)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(ref)
    return deduped


def parse_related_work_txt(text: str, *, source_file: str = "") -> list[RefRecord]:
    out: list[RefRecord] = []
    # Numbered blocks: "1) Title — Authors" or "7) Driller: ..."
    for m in re.finditer(
        r"(?ms)^\s*\d+\)\s*(.+?)(?=^\s*\d+\)|\Z)",
        text,
    ):
        block = m.group(1).strip()
        first = block.splitlines()[0].strip()
        title = re.split(r"\s+[—–-]\s+", first, maxsplit=1)[0].strip()
        title = re.sub(r"\s+", " ", title)
        if len(title) < 3:
            continue
        # Skip meta "Surveys on ..." style non-citations if no URL and vague
        url_m = re.search(r"https?://\S+", block)
        out.append(
            RefRecord(
                title=title,
                year=extract_year(block),
                doi=extract_doi(block),
                arxiv_id=extract_arxiv_id(block),
                url=url_m.group(0).rstrip(").,;") if url_m else "",
                raw=block[:500],
                source_file=source_file,
                source_kind="related_work_txt",
            )
        )
    return out


def _survey_citation_head(block: str) -> str:
    """Citation line only; later mechanism bullets are not paper titles."""
    lines: list[str] = []
    for line in (block or "").splitlines():
        if re.match(r"\s*[-*]\s+\S", line):
            break
        lines.append(line)
    return "\n".join(lines)


def _clean_survey_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    return title.strip(" ,.;*\"“”'‘’()[]")


def _is_survey_note(title: str) -> bool:
    low = title.lower()
    if "verified via" in low or low.startswith(("verified", "see also", "baseline", "brief ref")):
        return True
    return False


def _survey_quoted_or_italic_titles(text: str) -> list[str]:
    titles: list[str] = []
    for pattern in (
        r'(?:"|“)(.+?)(?:"|”)',
        r"(?<!\*)\*((?:(?!\*).)+?)\*(?!\*)",
    ):
        for m in re.finditer(pattern, text, flags=re.S):
            title = _clean_survey_title(m.group(1))
            if len(title) < 12 or len(title.split()) < 3:
                continue
            if not title[:1].isupper() and not title[:1].isdigit():
                continue
            if is_venue_fragment(title) or _is_survey_note(title):
                continue
            titles.append(title)
    return titles


def _bold_is_paper_title(bold: str, block: str) -> bool:
    """True when the bold span is itself a paper title, not a tool nickname.

    Gap notes continue the sentence after the bold (``**No approach** combines``).
    Paper entries put a dash or a citation before the authors.
    """
    head = _survey_citation_head(block).lstrip()
    separated = bool(re.match(r"(?:[—–]|--|-)\s+\S", head))
    paren_cite = bool(re.match(r"\([^)]{0,120}\d{4}", head))
    if not (separated or paren_cite):
        return False
    if re.search(r"\bbrief ref\b|\bdescribed in\b", head, re.I):
        return False
    bold = re.sub(r"\s+", " ", bold).strip(" ,.;")
    if len(bold.split()) < 3 or len(bold) < 20:
        return False
    if bold.count(",") >= 2 or re.search(r"\bet al\.?\b", bold, re.I):
        return False
    if re.match(r"^[A-Z][\w.'’-]+,\s+[A-Z]", bold):
        return False
    return True


def _survey_paper_title(bold: str, block: str) -> str:
    """Paper title from a survey entry. Empty means do not search it.

    DeepScientist notes look like ``**SQLancer** — Author, "Real Title"``.
    The bold span is usually a tool nickname. Search the quoted or italic
    title. Entries that only name a tool, or say the idea is described in
    another paper, are not independent references.
    """
    head = _survey_citation_head(block)
    titles = _survey_quoted_or_italic_titles(f"{bold}\n{head}")
    bold_clean = re.sub(r"\s+", " ", bold).strip(" ,.;")
    if _bold_is_paper_title(bold_clean, block):
        titles.append(bold_clean)
    if not titles:
        return ""
    return max(titles, key=len)


def parse_literature_survey_md(text: str, *, source_file: str = "") -> list[RefRecord]:
    """Parse DeepScientist-style literature_survey.md numbered entries."""
    out: list[RefRecord] = []
    # 1. **Nickname** — "Real Paper Title", venue, year
    for m in re.finditer(
        r"(?ms)^\s*\d+\.\s+\*\*(.+?)\*\*\s*(.*?)(?=^\s*\d+\.\s+\*\*|\Z)",
        text,
    ):
        bold = re.sub(r"\s+", " ", m.group(1)).strip()
        block = (m.group(2) or "").strip()
        title = _survey_paper_title(bold, block)
        if len(title) < 12:
            continue
        combined = f"{bold}\n{block}"
        url_m = re.search(r"https?://\S+", combined)
        out.append(
            RefRecord(
                title=title,
                year=extract_year(combined),
                doi=extract_doi(combined),
                arxiv_id=extract_arxiv_id(combined),
                url=url_m.group(0).rstrip(").,;") if url_m else "",
                raw=combined[:500],
                source_file=source_file,
                source_kind="literature_survey",
            )
        )
    return out


def parse_literature_synthesis_md(text: str, *, source_file: str = "") -> list[RefRecord]:
    """Parse EvoScientist-style literature_synthesis.md tool/paper bullet lists."""
    out: list[RefRecord] = []
    # Prefer the Sources / Papers sections when present.
    sections = text
    for marker in ("Sources and representative tools", "Papers / resources"):
        idx = text.lower().find(marker.lower())
        if idx >= 0:
            sections = text[idx:]
            break

    for m in re.finditer(
        r"(?m)^\s*[-*]\s+(.+?)(?::\s*|\s+)(https?://\S+)",
        sections,
    ):
        title = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(":")
        url = m.group(2).rstrip(").,;")
        if len(title) < 2:
            continue
        # Drop pure dataset bullets without scholarly framing if title is too generic? keep all.
        out.append(
            RefRecord(
                title=title,
                year=extract_year(title),
                doi=extract_doi(f"{title} {url}"),
                arxiv_id=extract_arxiv_id(url),
                url=url,
                raw=f"{title} {url}"[:500],
                source_file=source_file,
                source_kind="literature_synthesis",
            )
        )
    return out


def parse_shortlist_jsonl(path: Path) -> list[RefRecord]:
    out: list[RefRecord] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        title = str(obj.get("title") or "").strip()
        if not title:
            continue
        authors = obj.get("authors") or []
        author_names = []
        if isinstance(authors, list):
            for a in authors:
                if isinstance(a, dict) and a.get("name"):
                    author_names.append(str(a["name"]))
                elif isinstance(a, str):
                    author_names.append(a)
        year = obj.get("year")
        try:
            year_i = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_i = extract_year(str(year or ""))
        doi = extract_doi(str(obj.get("doi") or obj.get("url") or ""))
        out.append(
            RefRecord(
                title=title,
                year=year_i,
                doi=doi,
                arxiv_id=str(obj.get("arxiv_id") or extract_arxiv_id(str(obj.get("url") or ""))),
                url=str(obj.get("url") or ""),
                cite_key=str(obj.get("cite_key") or obj.get("paper_id") or ""),
                authors=author_names,
                raw=line[:500],
                source_file=str(path),
                source_kind="shortlist",
            )
        )
    return out


def parse_related_work_json(path: Path) -> list[RefRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    out: list[RefRecord] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        title = str(obj.get("title") or "").strip()
        if not title:
            continue
        authors = obj.get("authors") or []
        author_names = []
        if isinstance(authors, list):
            for a in authors:
                if isinstance(a, dict) and a.get("name"):
                    author_names.append(str(a["name"]))
                elif isinstance(a, str):
                    author_names.append(a)
        year = obj.get("year")
        try:
            year_i = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_i = None
        out.append(
            RefRecord(
                title=title,
                year=year_i,
                doi=extract_doi(str(obj.get("url") or obj.get("doi") or "")),
                arxiv_id=str(obj.get("arxiv_id") or ""),
                url=str(obj.get("url") or ""),
                cite_key=str(obj.get("cite_key") or obj.get("paper_id") or ""),
                authors=author_names,
                source_file=str(path),
                source_kind="related_work_json",
            )
        )
    return out


def parse_arxiv_index(path: Path) -> list[RefRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("papers") or data.get("items") or []
    out: list[RefRecord] = []
    if not isinstance(items, list):
        return out
    for obj in items:
        if not isinstance(obj, dict):
            continue
        title = str(obj.get("title") or "").strip()
        if not title:
            continue
        arxiv = str(obj.get("id") or obj.get("arxiv_id") or extract_arxiv_id(str(obj.get("url") or "")))
        year = obj.get("year") or extract_year(str(obj.get("published") or obj.get("updated") or ""))
        try:
            year_i = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_i = None
        out.append(
            RefRecord(
                title=title,
                year=year_i,
                arxiv_id=arxiv,
                url=str(obj.get("url") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")),
                source_file=str(path),
                source_kind="arxiv_index",
            )
        )
    return out


def _candidate_files(run_dir: Path) -> list[tuple[Path, str]]:
    """Return (path, kind_hint) in priority order."""
    cands: list[tuple[Path, str]] = []
    # Prefer final paper bibliography over intermediate literature shortlists.
    preferred = [
        ("paper/references.bib", "bib"),
        ("artifacts/paper/references.bib", "bib"),
        ("latex/custom.bib", "bib"),
        ("stage-22/references.bib", "bib"),
        ("stage-05/shortlist.jsonl", "shortlist"),
        ("stage-04/references.bib", "bib"),
        ("paper/related_work.txt", "related_work_txt"),
        ("artifacts/literature_summary.md", "related_work_txt"),
        ("artifacts/literature_synthesis.md", "literature_synthesis"),
        ("literature_synthesis.md", "literature_synthesis"),
        ("artifacts/idea/literature_survey.md", "literature_survey"),
        ("artifacts/literature_survey.md", "literature_survey"),
        ("literature_survey.md", "literature_survey"),
    ]
    for rel, kind in preferred:
        p = run_dir / rel
        if p.is_file() and p.stat().st_size > 20 and not _is_junk_path(p):
            cands.append((p.resolve(), kind))

    # AI-Scientist cached citations
    for p in sorted(run_dir.glob("experiments/**/cached_citations.bib")):
        if p.is_file() and not _is_junk_path(p):
            cands.append((p.resolve(), "bib"))

    # DeepScientist / generic literature surveys
    for p in sorted(run_dir.glob("**/literature_survey.md")):
        if p.is_file() and not _is_junk_path(p):
            cands.append((p.resolve(), "literature_survey"))

    # EvoScientist literature synthesis notes
    for p in sorted(run_dir.glob("**/literature_synthesis.md")):
        if p.is_file() and not _is_junk_path(p):
            cands.append((p.resolve(), "literature_synthesis"))

    # DeepScientist arxiv index
    for p in sorted(run_dir.glob("**/literature/arxiv/index.json")):
        if p.is_file() and not _is_junk_path(p):
            cands.append((p.resolve(), "arxiv_index"))

    # thebibliography inside paper / latex tex
    for path in iter_paper_tex_paths(run_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "thebibliography" in text:
            cands.append((path.resolve(), "thebibliography"))

    # De-dupe paths keeping first kind
    seen: set[Path] = set()
    uniq: list[tuple[Path, str]] = []
    for path, kind in cands:
        if path in seen:
            continue
        seen.add(path)
        uniq.append((path, kind))
    return uniq


def collect_agent_references(
    run_dir: Path,
) -> tuple[list[RefRecord], list[dict[str, str]], dict[str, Any]]:
    """Collect refs from literature artifacts, scoped to in-paper citations when possible."""
    run_dir = run_dir.resolve()
    files = _candidate_files(run_dir)
    sources_meta = [{"path": str(p), "kind": k} for p, k in files]
    audit: dict[str, Any] = {
        "cited_keys_count": 0,
        "filter_mode": "none",
        "bib_total_before_filter": 0,
        "bib_after_filter": 0,
        "uncited_bib_skipped": 0,
    }
    if not files:
        return [], sources_meta, audit

    cited_keys = extract_cite_keys_from_run(run_dir)
    audit["cited_keys_count"] = len(cited_keys)
    if cited_keys:
        audit["cited_keys_sample"] = sorted(cited_keys)[:40]

    by_kind: dict[str, list[RefRecord]] = {}
    for path, kind in files:
        try:
            parsed = _parse_source_file(path, kind)
        except (OSError, json.JSONDecodeError):
            continue
        by_kind.setdefault(kind, []).extend(parsed)

    bib_refs = by_kind.get("bib", [])
    biblio_refs = by_kind.get("thebibliography", [])
    non_bib_refs: list[RefRecord] = []
    for kind in (
        "literature_survey",
        "literature_synthesis",
        "related_work_txt",
        "shortlist",
        "arxiv_index",
    ):
        non_bib_refs.extend(by_kind.get(kind, []))

    audit["bib_total_before_filter"] = len(bib_refs)

    refs: list[RefRecord] = []
    if cited_keys:
        bib_filtered = [r for r in bib_refs if r.cite_key in cited_keys]
        biblio_filtered = [r for r in biblio_refs if r.cite_key in cited_keys]
        refs = bib_filtered + biblio_filtered
        audit["filter_mode"] = "paper_cite_keys"
        audit["bib_after_filter"] = len(bib_filtered)
        audit["thebibliography_after_filter"] = len(biblio_filtered)
        # If paper cites keys missing from bib, still keep non-bib surveys as supplement.
        if not refs and non_bib_refs:
            refs = non_bib_refs
            audit["filter_mode"] = "paper_cite_keys_empty_fallback_non_bib"
    elif non_bib_refs:
        refs = non_bib_refs
        audit["filter_mode"] = "non_bib_sources"
        audit["uncited_bib_skipped"] = len(bib_refs)
    elif bib_refs and len(bib_refs) <= _MAX_UNCITED_BIB_ENTRIES:
        refs = bib_refs + biblio_refs
        audit["filter_mode"] = "small_uncited_bib"
        audit["bib_after_filter"] = len(bib_refs)
    else:
        refs = []
        audit["filter_mode"] = "uncited_bulk_bib_skipped"
        audit["uncited_bib_skipped"] = len(bib_refs)

    deduped = _dedupe_refs(refs)
    audit["agent_ref_count"] = len(deduped)
    return deduped, sources_meta, audit


def load_gold_references(task_dir: Path) -> tuple[list[RefRecord], str]:
    """Gold bibliography for coverage recall: original paper REFERENCES (mineru).

    Prefer titles parsed from ``mineru_sections.json`` REFERENCES. Enrich with
    DOI/year/url from ``related_work.json`` when titles match. If mineru yields
    no titles, fall back to related_work.json alone.
    """
    task_dir = task_dir.resolve()
    # Local import avoids a hard cycle at module import time.
    from solution_space import (
        extract_titles_from_reference_text,
        load_mineru_reference_section_text,
        load_related_work_by_title,
    )

    ref_text = load_mineru_reference_section_text(task_dir)
    mineru_entries = extract_titles_from_reference_text(ref_text)
    related_by_title = load_related_work_by_title(task_dir)

    gold: list[RefRecord] = []
    seen: set[str] = set()
    used_related: set[str] = set()

    for i, ent in enumerate(mineru_entries):
        title = str(ent.get("title") or "").strip()
        if not title:
            continue
        norm = normalize_title(title)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        rw = related_by_title.get(norm)
        if rw is None:
            # soft match
            best = None
            best_score = 0.0
            for key, rec in related_by_title.items():
                if key in used_related:
                    continue
                if norm in key or key in norm:
                    score = 0.92
                else:
                    ta, tb = set(norm.split()), set(key.split())
                    score = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
                if score > best_score:
                    best_score = score
                    best = (key, rec)
            if best is not None and best_score >= 0.82:
                rw = best[1]
                used_related.add(best[0])
        elif norm not in used_related:
            used_related.add(norm)

        year = ent.get("year")
        doi = ""
        arxiv_id = ""
        url = ""
        cite_key = f"mineru_ref_{ent.get('ref_num') or (i + 1)}"
        if rw is not None:
            if year is None:
                year = rw.get("year")
            url = str(rw.get("url") or "")
            doi = extract_doi(url) or extract_doi(str(rw.get("paper_id") or ""))
            arxiv_id = extract_arxiv_id(url)
            if rw.get("cite_key"):
                cite_key = str(rw["cite_key"])
        try:
            year_i = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_i = None
        gold.append(
            RefRecord(
                title=title,
                year=year_i,
                doi=doi,
                arxiv_id=arxiv_id,
                url=url,
                cite_key=cite_key,
                raw=str(ent.get("raw") or "")[:400],
                source_file=str(task_dir / "mineru_sections.json"),
                source_kind="mineru_references",
            )
        )

    if gold:
        source = str(task_dir / "mineru_sections.json")
        return gold, source

    # Fallback: OpenAlex related_work subset
    rw = task_dir / "related_work.json"
    if rw.is_file() and rw.stat().st_size > 20:
        return parse_related_work_json(rw), str(rw)
    return [], ""


def titles_similar(a: str, b: str, *, threshold: float = 0.82) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Containment for truncated titles
    if na in nb or nb in na:
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        # Allow short gold titles like "Magma" when they are a whole-token prefix/match.
        if len(shorter) >= 12 and len(shorter) / max(len(longer), 1) >= 0.7:
            return True
        if len(shorter) >= 4:
            short_tokens = shorter.split()
            long_tokens = longer.split()
            if short_tokens and all(t in long_tokens for t in short_tokens):
                # Avoid ultra-generic single tokens unless exact token equality of whole short title
                if len(short_tokens) >= 2 or len(shorter) >= 6:
                    return True
    # Token Jaccard
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    union = len(ta | tb)
    return (inter / union) >= threshold


def match_ref_to_gold(ref: RefRecord, gold: Iterable[RefRecord]) -> RefRecord | None:
    if ref.doi:
        for g in gold:
            if g.doi and g.doi.lower() == ref.doi.lower():
                return g
    if ref.arxiv_id:
        for g in gold:
            if g.arxiv_id and g.arxiv_id == ref.arxiv_id:
                return g
    for g in gold:
        if titles_similar(ref.title, g.title):
            return g
    return None
