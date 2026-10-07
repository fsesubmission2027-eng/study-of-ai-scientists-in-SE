"""Peer-review quality scoring from a downloaded Stanford APR (or similar) report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_client import chat_json
from paths import find_pdf, find_tex

try:
    from paperreview_client import (
        apr_json_has_score,
        ensure_paperreview_report,
        extract_apr_scores,
        parse_score_from_text,
        peer_review_dir,
        run_has_apr_score,
    )
except ImportError:  # pragma: no cover
    apr_json_has_score = None  # type: ignore[assignment,misc]
    ensure_paperreview_report = None  # type: ignore[assignment,misc]
    extract_apr_scores = None  # type: ignore[assignment,misc]
    parse_score_from_text = None  # type: ignore[assignment,misc]
    peer_review_dir = None  # type: ignore[assignment,misc]
    run_has_apr_score = None  # type: ignore[assignment,misc]

REVIEW_CANDIDATES = [
    "artifacts/peer_review/stanford_apr.md",
    "artifacts/peer_review/stanford_apr.txt",
    "artifacts/peer_review/stanford_apr.html",
    "artifacts/peer_review/review.md",
    "artifacts/peer_review/review.txt",
    "peer_review/stanford_apr.md",
    "peer_review/stanford_apr.txt",
    "peer_review/review.md",
    "stanford_apr.md",
    "stanford_apr.txt",
    "stanford_apr.html",
]


def find_peer_review_report(run_dir: Path, explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    for rel in REVIEW_CANDIDATES:
        cand = run_dir / rel
        if cand.is_file() and cand.stat().st_size > 20:
            return cand
    # Soft glob
    for pattern in (
        "artifacts/peer_review/**/*",
        "peer_review/**/*",
        "**/*stanford*apr*",
        "**/*peer*review*",
    ):
        for path in run_dir.glob(pattern):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".html", ".json"}:
                if path.stat().st_size > 20:
                    return path
    return None


def _read_text_capped(path: Path, *, max_chars: int = 60000) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".html":
        raw = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
        raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\s+", " ", raw)
    return raw[:max_chars]


def _agent_paper_excerpt(run_dir: Path, *, max_chars: int = 12000) -> str:
    tex = find_tex(run_dir)
    if tex is not None:
        return tex.path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return ""


DIMENSIONS = (
    "soundness",
    "significance",
    "novelty",
    "presentation",
    "credibility",
)

# Integer 1–5 rubrics shown to the judge LLM (and available to callers).
DIMENSION_RUBRICS: dict[str, dict[int, str]] = {
    "soundness": {
        1: (
            "Critical technical flaws: incorrect method, invalid experiments, or conclusions "
            "that do not follow from the evidence; results are not trustworthy."
        ),
        2: (
            "Serious methodological or experimental issues that undermine the main claims; "
            "fixes would require substantial rework."
        ),
        3: (
            "Core approach is mostly valid, but notable gaps remain (weak baselines, limited "
            "ablation, shaky assumptions, or incomplete analysis)."
        ),
        4: (
            "Technically solid: methods and experiments largely support the claims; only minor "
            "issues or missing checks."
        ),
        5: (
            "Rigorous and correct: careful design, appropriate evaluation, and conclusions "
            "tightly supported by evidence."
        ),
    },
    "significance": {
        1: (
            "Negligible impact: problem is trivial, already solved, or the contribution would "
            "not matter to the community."
        ),
        2: (
            "Limited significance: narrow niche or incremental change with unclear practical "
            "or scientific value."
        ),
        3: (
            "Moderate significance: useful contribution for a subset of the field, but not "
            "broadly important."
        ),
        4: (
            "Important contribution: addresses a meaningful problem and would interest many "
            "researchers in the area."
        ),
        5: (
            "High impact: advances a central problem or opens a clearly valuable new direction "
            "for the community."
        ),
    },
    "novelty": {
        1: (
            "No novelty: restates known ideas, reproduces prior work without new insight, or "
            "is a trivial combination of existing methods."
        ),
        2: (
            "Mostly derivative: small variant of prior work with little conceptual or "
            "technical advance."
        ),
        3: (
            "Some novelty: mixes known pieces with a few new elements, but the advance is "
            "limited or partially anticipated."
        ),
        4: (
            "Clearly novel: new method, formulation, or insight that is not a minor tweak of "
            "prior art."
        ),
        5: (
            "Highly original: distinctive idea or approach that substantially changes how the "
            "problem is framed or solved."
        ),
    },
    "presentation": {
        1: (
            "Very poor presentation: disorganized, unreadable, missing critical sections, or "
            "figures/tables unusable."
        ),
        2: (
            "Hard to follow: major clarity, structure, or writing problems that impede "
            "understanding of the contribution."
        ),
        3: (
            "Adequate but uneven: main ideas can be understood, yet writing, structure, or "
            "visuals need substantial polishing."
        ),
        4: (
            "Clear and well structured: contribution, method, and experiments are easy to "
            "follow with only minor rough edges."
        ),
        5: (
            "Excellent presentation: precise writing, logical flow, and effective "
            "figures/tables that make the paper easy to assess."
        ),
    },
    "credibility": {
        1: (
            "Not credible: strong signs of fabrication, invented numbers, impossible results, "
            "or claims with no experimental support."
        ),
        2: (
            "Low credibility: serious overclaiming; key results lack evidence, conflict with "
            "the report, or look unreliable."
        ),
        3: (
            "Mixed credibility: some claims are supported, but others are weakly evidenced, "
            "vague, or risk overstatement."
        ),
        4: (
            "Generally credible: main claims match reported experiments and metrics; only "
            "minor inconsistencies or soft spots."
        ),
        5: (
            "Highly credible: claims are tightly backed by concrete experiments/data; little "
            "to no overclaim or fabrication risk."
        ),
    },
}


def _format_rubrics_for_prompt() -> str:
    lines: list[str] = []
    for name in DIMENSIONS:
        lines.append(f"### {name}")
        for score in range(1, 6):
            lines.append(f"  {score}: {DIMENSION_RUBRICS[name][score]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _clamp_score_1_to_5(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score:  # NaN
        return None
    return max(1.0, min(5.0, score))


def _clamp_score_1_to_10(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score:  # NaN
        return None
    return max(1.0, min(10.0, score))


def _load_apr_review_json(run_dir: Path) -> dict[str, Any] | None:
    if peer_review_dir is None:
        return None
    json_path = peer_review_dir(run_dir) / "stanford_apr.json"
    if not json_path.is_file():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_apr_scores(review_json: dict[str, Any] | None) -> dict[str, Any]:
    if not review_json or extract_apr_scores is None:
        return {"scale": "1-10", "overall": None, "dimensions": {}}
    fresh = extract_apr_scores(review_json)
    if fresh.get("overall") is not None:
        return fresh
    cached = review_json.get("_apr_scores")
    if isinstance(cached, dict) and cached.get("overall") is not None:
        return cached
    return fresh


APR_SCORE_LLM_SYSTEM = """You extract a single holistic paper quality score from a Stanford Agentic Reviewer report.
The score must reflect paperreview.ai / ICLR-style reviewer ratings on a 1-10 scale (10 = strong accept).
Return ONLY valid JSON."""


def _extract_apr_overall_via_llm(review_text: str, *, model: str | None) -> dict[str, Any]:
    user = f"""Read this automated peer-review report and output ONE overall score on a 1-10 scale.

Rules:
- Use 1-10 (not 1-5). Typical weak preliminary work: 3-5; solid but limited: 5-6.5; strong: 7+.
- Base the score only on the review tone, strengths/weaknesses, and overall assessment.
- If the report explicitly mentions a numeric rating or score, prefer that value.
- Provide a <= 80 word summary and any red flags.

Return JSON:
{{
  "overall_score": 1-10,
  "summary": "...",
  "red_flags": ["..."]
}}

=== REVIEW REPORT ===
{review_text[:55000]}
"""
    return chat_json(system=APR_SCORE_LLM_SYSTEM, user=user, model=model, max_tokens=1200)


def _finalize_apr_peer_review(
    base: dict[str, Any],
    *,
    overall: float | None,
    apr_dimensions: dict[str, float],
    score_scale: str,
    scoring_source: str,
    summary: str = "",
    red_flags: list[str] | None = None,
    llm_meta: Any = None,
) -> dict[str, Any]:
    base.update(
        {
            "status": "ok" if overall is not None else "apr_score_missing",
            "scoring_method": "paperreview_apr",
            "scoring_source": scoring_source,
            "score_scale": score_scale,
            "overall_score": overall,
            "dimensions": {},
            "apr_dimensions": apr_dimensions,
            "dimension_order": [],
            "summary": summary[:1000],
            "red_flags": red_flags or [],
            "notes": [
                "Scored from paperreview.ai (Stanford APR) native ratings; benchmark 5-dimension LLM rubric skipped.",
                f"Overall scale: {score_scale}.",
            ],
        }
    )
    if llm_meta is not None:
        base["llm_meta"] = llm_meta
    return base


def _evaluate_peer_review_from_apr(
    run_dir: Path,
    report: Path,
    base: dict[str, Any],
    *,
    model: str | None,
    skip_llm: bool,
    allow_llm_fallback: bool = False,
) -> dict[str, Any]:
    review_json = _load_apr_review_json(run_dir)
    apr = _resolve_apr_scores(review_json)
    overall = _clamp_score_1_to_10(apr.get("overall"))
    raw_dims = apr.get("dimensions") or {}
    apr_dimensions: dict[str, float] = {}
    if isinstance(raw_dims, dict):
        for name, value in raw_dims.items():
            try:
                fv = float(value)
            except (TypeError, ValueError):
                continue
            # paperreview.ai triple rubric uses -1 / 0 / +1
            if -1.5 <= fv <= 1.5:
                apr_dimensions[str(name)] = fv
            else:
                clamped = _clamp_score_1_to_10(fv)
                if clamped is not None:
                    apr_dimensions[str(name)] = clamped

    score_scale = "1-10"
    if overall is None and apr_dimensions:
        overall = round(sum(apr_dimensions.values()) / len(apr_dimensions), 2)

    if overall is not None:
        return _finalize_apr_peer_review(
            base,
            overall=overall,
            apr_dimensions=apr_dimensions,
            score_scale=score_scale,
            scoring_source="paperreview_json",
        )

    if parse_score_from_text is not None:
        report_text = _read_text_capped(report, max_chars=8000)
        parsed = parse_score_from_text(report_text)
        if parsed is not None:
            return _finalize_apr_peer_review(
                base,
                overall=parsed,
                apr_dimensions=apr_dimensions,
                score_scale="1-10",
                scoring_source="parsed_from_report_text",
            )

    if skip_llm or not allow_llm_fallback:
        base["status"] = "apr_score_missing"
        base["scoring_method"] = "paperreview_apr"
        base["hint"] = (
            "Review report exists but no numerical_score found. Add "
            f"{run_dir / 'artifacts' / 'peer_review' / 'stanford_apr.json'} "
            'with {"numerical_score": X.X}, or put "numerical_score: X.X" in the report header, '
            "or use --paperreview-resubmit to fetch a scored JSON from paperreview.ai."
        )
        return base

    review_text = _read_text_capped(report)
    try:
        data = _extract_apr_overall_via_llm(review_text, model=model)
    except Exception as exc:  # noqa: BLE001
        base["status"] = "llm_failed"
        base["scoring_method"] = "paperreview_apr"
        base["error"] = str(exc)
        return base

    overall = _clamp_score_1_to_10(data.get("overall_score"))
    return _finalize_apr_peer_review(
        base,
        overall=overall,
        apr_dimensions=apr_dimensions,
        score_scale="1-10",
        scoring_source="llm_extract_from_apr_report",
        summary=str(data.get("summary") or ""),
        red_flags=data.get("red_flags") if isinstance(data.get("red_flags"), list) else [],
        llm_meta=data.get("_meta"),
    )


SYSTEM_PROMPT = """You are an expert meta-reviewer for an AI-scientist benchmark.
You are given (1) an external automated peer-review report (e.g. Stanford Agentic Reviewer)
and optionally (2) a short excerpt of the agent-generated paper.
Score the paper on fixed dimensions using the review report as primary evidence.
Use ONLY the provided 1-5 rubrics. Return ONLY valid JSON.
"""


def evaluate_peer_review(
    run_dir: Path,
    *,
    review_path: Path | None = None,
    model: str | None = None,
    skip_llm: bool = False,
    auto_paperreview: bool = False,
    paperreview_email: str | None = None,
    paperreview_venue: str = "ICLR",
    paperreview_custom_venue: str = "",
    paperreview_wait: bool = True,
    paperreview_interval_min: float = 10.0,
    paperreview_max_hours: float = 48.0,
    paperreview_resubmit: bool = False,
    paperreview_llm_fallback: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    report = find_peer_review_report(run_dir, review_path)
    pdf = find_pdf(run_dir, auto_compile=True)
    tex = find_tex(run_dir)

    base: dict[str, Any] = {
        "run_dir": str(run_dir),
        "review_report": str(report) if report else None,
        "paper_pdf": str(pdf.path) if pdf else None,
        "paper_tex": str(tex.path) if tex else None,
        "status": "ok",
        "dimensions": {},
        "overall_score": None,
        "score_scale": "1-5",
        "dimension_order": list(DIMENSIONS),
        "notes": [
            "Stanford Agentic Reviewer (paperreview.ai): manual download to "
            "artifacts/peer_review/stanford_apr.md, or pass --auto-paperreview.",
            "Dimensions: soundness, significance, novelty, presentation, credibility (each 1-5).",
        ],
        "paperreview": None,
    }

    # Upload when no cached numeric score; skip upload only if score already on disk.
    has_cached_score = run_has_apr_score(run_dir) if run_has_apr_score is not None else False
    needs_apr_fetch = (
        auto_paperreview
        and ensure_paperreview_report is not None
        and (paperreview_resubmit or not has_cached_score)
    )
    if needs_apr_fetch:
        if pdf is None:
            base["paperreview"] = {"status": "skipped", "reason": "no_pdf"}
        else:
            try:
                artifacts = ensure_paperreview_report(
                    run_dir,
                    pdf.path,
                    email=paperreview_email,
                    venue=paperreview_venue,
                    custom_venue=paperreview_custom_venue,
                    wait=paperreview_wait,
                    interval_min=paperreview_interval_min,
                    max_hours=paperreview_max_hours,
                    resubmit=paperreview_resubmit,
                )
                if artifacts is not None:
                    base["paperreview"] = {
                        "status": "fetched",
                        "token_file": str(artifacts.token_path),
                        "json": str(artifacts.json_path),
                        "markdown": str(artifacts.md_path),
                        "apr_scores": artifacts.review.get("_apr_scores"),
                        "pdf_rebuild": (artifacts.review or {}).get("_pdf_rebuild"),
                    }
                    # Rebuild may have replaced paper/main.pdf — refresh paths.
                    pdf = find_pdf(run_dir, auto_compile=False)
                    tex = find_tex(run_dir)
                    base["paper_pdf"] = str(pdf.path) if pdf else base["paper_pdf"]
                    base["paper_tex"] = str(tex.path) if tex else base["paper_tex"]
                else:
                    base["paperreview"] = {
                        "status": "submitted_or_cached",
                        "hint": "Review not ready yet; re-run with --auto-paperreview after polling completes.",
                    }
                report = find_peer_review_report(run_dir, review_path)
                base["review_report"] = str(report) if report else None
            except Exception as exc:  # noqa: BLE001
                base["paperreview"] = {"status": "error", "error": str(exc)}
    elif auto_paperreview and has_cached_score:
        base["paperreview"] = {
            "status": "cached",
            "hint": "Cached APR score found; no re-upload.",
        }

    if report is None:
        base["status"] = "not_provided"
        base["optional"] = True
        base["hint"] = (
            "Optional external review (Stanford APR). Upload paper/main.pdf to https://paperreview.ai/ , "
            f"save review to {run_dir / 'artifacts' / 'peer_review' / 'stanford_apr.md'}"
        )
        return base

    if auto_paperreview:
        return _evaluate_peer_review_from_apr(
            run_dir,
            report,
            base,
            model=model,
            skip_llm=skip_llm,
            allow_llm_fallback=paperreview_llm_fallback,
        )

    if skip_llm:
        base["status"] = "report_found_llm_skipped"
        base["report_chars"] = report.stat().st_size
        return base

    review_text = _read_text_capped(report)
    paper_excerpt = _agent_paper_excerpt(run_dir)
    rubrics_block = _format_rubrics_for_prompt()
    user = f"""Score this paper using the review report as primary evidence.

Score each dimension as an INTEGER 1-5. Choose the rubric level that best matches the evidence.
For every dimension, justification must cite concrete phrases from the review report (and paper excerpt if used).

## Rubrics
{rubrics_block}

Also provide:
- overall_score: float in [1, 5] (holistic judgment; if credibility <= 2, overall must be pulled down strongly)
- summary: <= 120 words
- red_flags: string array

Return JSON schema:
{{
  "soundness": {{"score": 1-5, "justification": "..."}},
  "significance": {{"score": 1-5, "justification": "..."}},
  "novelty": {{"score": 1-5, "justification": "..."}},
  "presentation": {{"score": 1-5, "justification": "..."}},
  "credibility": {{"score": 1-5, "justification": "..."}},
  "overall_score": 1-5,
  "summary": "...",
  "red_flags": ["..."]
}}

=== REVIEW REPORT ===
{review_text}

=== PAPER EXCERPT (optional, may be empty) ===
{paper_excerpt or "(no tex excerpt)"}
"""
    try:
        data = chat_json(system=SYSTEM_PROMPT, user=user, model=model, max_tokens=3000)
    except Exception as exc:  # noqa: BLE001
        base["status"] = "llm_failed"
        base["error"] = str(exc)
        return base

    dims: dict[str, Any] = {}
    scores: list[float] = []
    for name in DIMENSIONS:
        block = data.get(name) or {}
        if isinstance(block, dict):
            score = _clamp_score_1_to_5(block.get("score"))
            rubric_key = int(round(score)) if score is not None else None
            dims[name] = {
                "score": score,
                "justification": str(block.get("justification") or "")[:800],
                "rubric": DIMENSION_RUBRICS[name].get(rubric_key) if rubric_key else None,
            }
            if score is not None:
                scores.append(score)
        elif isinstance(block, (int, float)):
            score = _clamp_score_1_to_5(block)
            rubric_key = int(round(score)) if score is not None else None
            dims[name] = {
                "score": score,
                "justification": "",
                "rubric": DIMENSION_RUBRICS[name].get(rubric_key) if rubric_key else None,
            }
            if score is not None:
                scores.append(score)

    overall = data.get("overall_score")
    overall_f = _clamp_score_1_to_5(overall)
    if overall_f is None and scores:
        overall_f = sum(scores) / len(scores)

    base.update(
        {
            "status": "ok",
            "dimensions": dims,
            "overall_score": overall_f,
            "summary": str(data.get("summary") or "")[:1000],
            "red_flags": data.get("red_flags") if isinstance(data.get("red_flags"), list) else [],
            "llm_meta": data.get("_meta"),
        }
    )
    return base
