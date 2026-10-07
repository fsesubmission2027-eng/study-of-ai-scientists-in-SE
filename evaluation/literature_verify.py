"""Verify references via Semantic Scholar and arXiv (stdlib only)."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from literature_sources import (
    RefRecord,
    extract_arxiv_id,
    extract_doi,
    is_venue_fragment,
    normalize_title,
    title_search_queries,
    titles_similar,
)

EVAL_ROOT = Path(__file__).resolve().parent
BENCHMARK_ROOT = EVAL_ROOT.parent
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

from benchmark_credentials import apply_benchmark_credentials  # noqa: E402

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_DOI = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
S2_ARXIV = "https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}"
ARXIV_API = "http://export.arxiv.org/api/query"
S2_FIELDS = "paperId,title,year,externalIds,url,authors"

# Non-paper resources: tools, repos, docs pages — not counted as fabricated scholarly refs.
_NON_PAPER_HOST_HINTS = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "llvm.org",
    "lcamtuf.coredump.cx",
    "google.github.io",
    "readthedocs.io",
    "wikipedia.org",
    "stackoverflow.com",
)


def _s2_title_hit(candidates: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    for cand in candidates:
        if titles_similar(title, str(cand.get("title") or ""), threshold=0.78):
            return cand
    return None


def looks_like_non_paper(ref: RefRecord) -> bool:
    blob = " ".join([ref.url, ref.title, ref.raw]).lower()
    if any(h in blob for h in _NON_PAPER_HOST_HINTS):
        # Scholarly arxiv/doi always treated as paper candidates.
        if ref.doi or ref.arxiv_id or "arxiv" in blob:
            return False
        return True
    # Titles that are clearly product/tool names without venue cues.
    if re.search(r"\b(github|documentation|homepage|website)\b", blob):
        return True
    return False


class LiteratureVerifier:
    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        override_path: Path | None = None,
        min_interval_sec: float = 1.1,
        env: dict[str, str] | None = None,
    ) -> None:
        merged = apply_benchmark_credentials(dict(env or os.environ))
        self.api_key = (merged.get("S2_API_KEY") or "").strip()
        self.min_interval = min_interval_sec
        self._last_req = 0.0
        self.cache_path = cache_path
        self.override_path = override_path
        self.cache: dict[str, Any] = {}
        self.overrides: dict[str, Any] = {}
        if cache_path and cache_path.is_file():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.cache = {}
        if override_path and override_path.is_file():
            try:
                raw = json.loads(override_path.read_text(encoding="utf-8"))
                self.overrides = raw if isinstance(raw, dict) else {}
            except (OSError, json.JSONDecodeError):
                self.overrides = {}

    def save_cache(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=2, ensure_ascii=False), encoding="utf-8")

    def _lookup_override(self, ref: RefRecord, cache_key: str) -> dict[str, Any] | None:
        """Manual overrides win over auto cache/API.

        Override file keys may be: cache_key (normalized title), raw title, doi, arxiv_id, cite_key.
        Value may be a status string (\"verified\") or a full result dict.
        """
        keys = [
            cache_key,
            ref.title,
            normalize_title(ref.title),
            ref.doi,
            ref.arxiv_id,
            ref.cite_key,
        ]
        hit = None
        for k in keys:
            if k and k in self.overrides:
                hit = self.overrides[k]
                break
        if hit is None:
            return None
        if isinstance(hit, str):
            return {
                "title": ref.title,
                "doi": ref.doi,
                "arxiv_id": ref.arxiv_id,
                "year": ref.year,
                "status": hit,
                "matched_via": "manual_override",
                "resolved_title": ref.title,
                "resolved_year": ref.year,
                "notes": ["Manually overridden via reference_verify_overrides.json"],
                "cache_hit": False,
                "override": True,
            }
        if isinstance(hit, dict):
            out = {
                "title": ref.title,
                "doi": ref.doi,
                "arxiv_id": ref.arxiv_id,
                "year": ref.year,
                "status": "verified",
                "matched_via": "manual_override",
                "resolved_title": ref.title,
                "resolved_year": ref.year,
                "notes": ["Manually overridden via reference_verify_overrides.json"],
                "cache_hit": False,
                "override": True,
            }
            out.update(hit)
            out["override"] = True
            out["matched_via"] = out.get("matched_via") or "manual_override"
            return out
        return None

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_req)
        if wait > 0:
            time.sleep(wait)
        self._last_req = time.monotonic()

    def _http_json(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[dict[str, Any] | None, str]:
        """Return (json_or_none, status) where status in ok|not_found|error."""
        self._throttle()
        req_headers = {"User-Agent": "ai-scientist-benchmark-eval/1.0"}
        if headers:
            req_headers.update(headers)
        if self.api_key and "semanticscholar.org" in url:
            req_headers["X-API-KEY"] = self.api_key
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw), "ok"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None, "not_found"
            if exc.code == 429:
                time.sleep(8)
                return None, "error"
            return None, "error"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None, "error"

    def _http_text(self, url: str) -> tuple[str | None, str]:
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": "ai-scientist-benchmark-eval/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace"), "ok"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None, "not_found"
            return None, "error"
        except (urllib.error.URLError, TimeoutError, OSError):
            return None, "error"

    def s2_by_doi(self, doi: str) -> tuple[dict[str, Any] | None, str]:
        url = S2_DOI.format(doi=urllib.parse.quote(doi, safe="")) + f"?fields={S2_FIELDS}"
        return self._http_json(url)

    def s2_by_arxiv(self, arxiv_id: str) -> tuple[dict[str, Any] | None, str]:
        url = S2_ARXIV.format(arxiv_id=urllib.parse.quote(arxiv_id, safe="")) + f"?fields={S2_FIELDS}"
        return self._http_json(url)

    def s2_search_title(self, title: str, *, limit: int = 5) -> tuple[list[dict[str, Any]], str]:
        q = urllib.parse.urlencode({"query": title, "limit": str(limit), "fields": S2_FIELDS})
        data, st = self._http_json(f"{S2_SEARCH}?{q}")
        if st != "ok" or not data:
            return [], st
        items = data.get("data") or []
        return (items if isinstance(items, list) else []), "ok"

    def arxiv_exists(self, arxiv_id: str) -> tuple[bool, str]:
        q = urllib.parse.urlencode({"id_list": arxiv_id})
        text, st = self._http_text(f"{ARXIV_API}?{q}")
        if st != "ok" or not text:
            return False, st
        ok = "<entry>" in text and arxiv_id.split("v")[0] in text
        return ok, "ok"

    def arxiv_search_title(self, title: str, *, match_against: str | None = None) -> tuple[bool, str]:
        needle = match_against or title
        q = urllib.parse.urlencode(
            {
                "search_query": f'ti:"{title[:120]}"',
                "start": "0",
                "max_results": "3",
            }
        )
        text, st = self._http_text(f"{ARXIV_API}?{q}")
        if st != "ok" or not text:
            return False, st
        if "<entry>" not in text:
            return False, "ok"
        titles = re.findall(r"<title>([^<]+)</title>", text)
        for t in titles[1:]:
            if titles_similar(needle, t):
                return True, "ok"
        return False, "ok"

    def verify(self, ref: RefRecord) -> dict[str, Any]:
        cache_key = ref.doi or ref.arxiv_id or normalize_title(ref.title) or ref.raw[:80]
        override = self._lookup_override(ref, cache_key)
        if override is not None:
            # Keep cache in sync so evaluation.json stays consistent on re-runs.
            self.cache[cache_key] = {k: v for k, v in override.items() if k not in {"cache_hit", "override"}}
            return override
        if cache_key in self.cache:
            cached = dict(self.cache[cache_key])
            # Invalidate stale cache entries from older verifier policies.
            stale = False
            notes = cached.get("notes") or []
            if not isinstance(notes, list):
                notes = [notes]
            # API failures are inconclusive. Retry them so the rate can be decided.
            if cached.get("status") == "lookup_failed":
                stale = True
            if cached.get("status") == "fabricated_or_unfound" and any(
                "API error" in str(n) for n in notes
            ):
                stale = True
            if cached.get("status") == "fabricated_or_unfound" and is_venue_fragment(
                str(cached.get("title") or "")
            ):
                stale = True
            cached_title = str(cached.get("title") or "")
            if (
                ref.title
                and cached_title
                and normalize_title(ref.title) != normalize_title(cached_title)
                and not titles_similar(ref.title, cached_title, threshold=0.55)
            ):
                stale = True
            if (
                cached.get("status") == "verified"
                and cached.get("matched_via") in {"s2_doi", "s2_arxiv"}
                and ref.title
                and cached.get("resolved_title")
                and not titles_similar(ref.title, str(cached["resolved_title"]), threshold=0.55)
            ):
                stale = True
            if not stale:
                cached["cache_hit"] = True
                return cached
            # Drop stale entry and re-verify below.
            self.cache.pop(cache_key, None)

        result: dict[str, Any] = {
            "title": ref.title,
            "doi": ref.doi,
            "arxiv_id": ref.arxiv_id,
            "year": ref.year,
            "status": "unverified",
            "matched_via": None,
            "resolved_title": None,
            "resolved_year": None,
            "cache_hit": False,
            "notes": [],
        }
        api_errors = 0
        definitive_misses = 0

        if looks_like_non_paper(ref):
            result["status"] = "non_paper"
            result["notes"].append("Treated as tool/docs/repo resource, not a scholarly paper.")
            self.cache[cache_key] = {k: v for k, v in result.items() if k != "cache_hit"}
            return result

        if not (ref.title or ref.doi or ref.arxiv_id):
            result["status"] = "insufficient_metadata"
            self.cache[cache_key] = {k: v for k, v in result.items() if k != "cache_hit"}
            return result

        def _store_verified(**kwargs: Any) -> dict[str, Any]:
            result.update({"status": "verified", **kwargs})
            self.cache[cache_key] = {k: v for k, v in result.items() if k != "cache_hit"}
            return result

        if ref.doi:
            hit, st = self.s2_by_doi(ref.doi)
            if st == "ok" and hit and hit.get("title"):
                resolved = str(hit.get("title") or "")
                # Reject DOI hits whose title clearly disagrees with the citation.
                if ref.title and resolved and not titles_similar(ref.title, resolved, threshold=0.55):
                    result["notes"].append(
                        f"DOI resolved to unrelated title ({resolved!r}); continuing other lookups."
                    )
                else:
                    return _store_verified(
                        matched_via="s2_doi",
                        resolved_title=resolved or hit.get("title"),
                        resolved_year=hit.get("year"),
                    )
            if st == "not_found":
                definitive_misses += 1
            elif st == "error":
                api_errors += 1

        arxiv_id = ref.arxiv_id or extract_arxiv_id(ref.url or ref.raw)
        if arxiv_id:
            hit, st = self.s2_by_arxiv(arxiv_id)
            if st == "ok" and hit and hit.get("title"):
                resolved = str(hit.get("title") or "")
                if ref.title and resolved and not titles_similar(ref.title, resolved, threshold=0.55):
                    result["notes"].append(
                        f"arXiv/S2 resolved to unrelated title ({resolved!r}); continuing other lookups."
                    )
                else:
                    return _store_verified(
                        matched_via="s2_arxiv",
                        resolved_title=resolved or hit.get("title"),
                        resolved_year=hit.get("year"),
                        arxiv_id=arxiv_id,
                    )
            if st == "error":
                api_errors += 1
            exists, st2 = self.arxiv_exists(arxiv_id)
            if st2 == "ok" and exists:
                return _store_verified(matched_via="arxiv_id", arxiv_id=arxiv_id)
            if st2 == "ok" and not exists:
                definitive_misses += 1
            elif st2 == "error":
                api_errors += 1

        if ref.title:
            queries = title_search_queries(ref.title)
            # The full title decides miss vs error. A subtitle probe can only add a hit.
            primary, extras = queries[0], queries[1:]
            candidates, st = self.s2_search_title(primary)
            hit = _s2_title_hit(candidates, ref.title) if st == "ok" else None
            if hit is None:
                for query in extras:
                    extra, st_extra = self.s2_search_title(query)
                    if st_extra == "ok":
                        hit = _s2_title_hit(extra, ref.title)
                        if hit is not None:
                            break
            if hit is not None:
                ext = hit.get("externalIds") or {}
                return _store_verified(
                    matched_via="s2_title",
                    resolved_title=str(hit.get("title") or ""),
                    resolved_year=hit.get("year"),
                    doi=result["doi"] or extract_doi(str((ext or {}).get("DOI") or "")),
                    arxiv_id=result["arxiv_id"]
                    or str((ext or {}).get("ArXiv") or extract_arxiv_id(str(hit.get("url") or ""))),
                )
            if st != "ok":
                api_errors += 1
            else:
                definitive_misses += 1

            found, st2 = self.arxiv_search_title(primary, match_against=ref.title)
            if st2 == "ok" and found:
                return _store_verified(matched_via="arxiv_title")
            for query in extras:
                found_extra, st_extra = self.arxiv_search_title(query, match_against=ref.title)
                if st_extra == "ok" and found_extra:
                    return _store_verified(matched_via="arxiv_title")
            if st2 == "error":
                api_errors += 1
            else:
                definitive_misses += 1

        # Any API error → inconclusive (lookup_failed), never fabricated.
        # Fabricated only when all attempted lookups returned conclusive misses.
        if api_errors:
            result["status"] = "lookup_failed"
            result["notes"].append(
                "API errors prevented a conclusive existence check; not counted as fabricated."
            )
            if definitive_misses:
                result["notes"].append(
                    f"Saw {definitive_misses} conclusive miss(es) mixed with {api_errors} API error(s)."
                )
        else:
            result["status"] = "fabricated_or_unfound"
            result["notes"].append(
                "Not found on Semantic Scholar or arXiv with DOI/arxiv/title lookup."
            )
        self.cache[cache_key] = {k: v for k, v in result.items() if k != "cache_hit"}
        return result
