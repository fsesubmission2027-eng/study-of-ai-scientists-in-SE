"""HTTP client for Stanford Agentic Reviewer (https://paperreview.ai/).

Flow mirrors the public website:
  POST /api/get-upload-url  → presigned S3 POST
  POST S3                   → upload PDF
  POST /api/confirm-upload  → token
  GET  /api/review/{token}  → 202 processing | 200 JSON review

Reference implementations:
  https://github.com/cnfjlhj/paperreview
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://paperreview.ai"
MAX_PDF_BYTES = 10 * 1024 * 1024
TOKEN_FILENAME = "paperreview.token.txt"


class PaperRejectedError(RuntimeError):
    """paperreview.ai refused the PDF (e.g. HTTP 422 not a research paper)."""

    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"paperreview rejected PDF ({status}): {str(detail)[:500]}")


def _rejection_detail(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("detail") or data.get("message") or data)[:800]
    return str(data)[:800]


def _is_paper_rejection(status: int, data: Any) -> bool:
    if status == 422:
        return True
    detail = _rejection_detail(data).lower()
    return "does not appear to be a research paper" in detail or "unable to provide a review" in detail



@dataclass(frozen=True)
class SubmitResult:
    token: str
    s3_key: str
    venue: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ReviewArtifacts:
    json_path: Path
    md_path: Path
    token_path: Path
    review: dict[str, Any]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def is_pdf_file(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(8).startswith(b"%PDF-")
    except OSError:
        return False


def validate_pdf(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not is_pdf_file(path):
        raise ValueError(f"Not a PDF (missing %PDF- header): {path}")
    size = path.stat().st_size
    if size > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF is {size} bytes (>10MB). paperreview.ai may reject uploads over 10MB."
        )


def resolve_venue(venue: str, custom_venue: str = "") -> str:
    if venue.strip() == "Other":
        custom = custom_venue.strip()
        if not custom:
            raise ValueError("venue=Other requires custom_venue")
        return custom
    return venue.strip()


def submit_pdf(
    pdf_path: Path,
    *,
    email: str,
    venue: str = "ICLR",
    custom_venue: str = "",
    timeout: float = 60.0,
    session: requests.Session | None = None,
) -> SubmitResult:
    """Upload PDF and return review access token."""
    validate_pdf(pdf_path)
    email = email.strip()
    if not email:
        raise ValueError("email is required for paperreview.ai submission")

    selected_venue = resolve_venue(venue, custom_venue)
    http = session or requests.Session()

    get_resp = http.post(
        f"{BASE_URL}/api/get-upload-url",
        json={"filename": pdf_path.name, "venue": selected_venue},
        timeout=timeout,
    )
    if get_resp.status_code == 429:
        raise RuntimeError(f"Rate limited on get-upload-url: {get_resp.text[:500]}")
    get_resp.raise_for_status()
    get_data = get_resp.json()
    if not get_data.get("success"):
        raise RuntimeError(f"get-upload-url success=false: {json.dumps(get_data)[:1000]}")

    presigned_url = get_data["presigned_url"]
    presigned_fields = get_data["presigned_fields"]
    s3_key = get_data["s3_key"]

    with pdf_path.open("rb") as f:
        s3_resp = http.post(
            presigned_url,
            data=presigned_fields,
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=timeout,
        )
    if not s3_resp.ok:
        raise RuntimeError(f"S3 upload failed ({s3_resp.status_code}): {s3_resp.text[:1000]}")

    confirm_resp = http.post(
        f"{BASE_URL}/api/confirm-upload",
        data={"s3_key": s3_key, "venue": selected_venue, "email": email},
        timeout=timeout,
    )
    if confirm_resp.status_code == 429:
        raise RuntimeError(f"Rate limited on confirm-upload: {confirm_resp.text[:500]}")
    confirm_resp.raise_for_status()
    confirm_data = confirm_resp.json()
    token = confirm_data.get("token")
    if not token:
        raise RuntimeError(f"confirm-upload missing token: {json.dumps(confirm_data)[:1000]}")

    return SubmitResult(token=str(token), s3_key=s3_key, venue=selected_venue, raw=confirm_data)


def fetch_review(token: str, *, timeout: float = 30.0, session: requests.Session | None = None) -> tuple[int, Any]:
    http = session or requests.Session()
    resp = http.get(f"{BASE_URL}/api/review/{token}", timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text[:4000]}
    return resp.status_code, data


def poll_review(
    token: str,
    *,
    interval_min: float = 10.0,
    max_hours: float = 48.0,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Block until review is ready (HTTP 200) or max_hours exceeded."""
    interval_s = max(5.0, interval_min * 60.0)
    deadline = time.time() + max(0.0, max_hours) * 3600.0
    http = session or requests.Session()

    while True:
        status, data = fetch_review(token, timeout=timeout, session=http)
        if status == 200:
            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected review payload type: {type(data)}")
            return data
        if status == 202:
            if time.time() >= deadline:
                raise TimeoutError(
                    f"Review still processing after {max_hours}h (token={token[:8]}...)"
                )
            time.sleep(interval_s)
            continue
        if _is_paper_rejection(status, data):
            raise PaperRejectedError(status, data)
        raise RuntimeError(f"Unexpected review status {status}: {str(data)[:800]}")


def review_to_markdown(review: dict[str, Any]) -> str:
    """Convert paperreview.ai JSON to markdown (compatible with stanford_apr.md layout)."""
    lines: list[str] = []
    title = review.get("title") or ""
    if title:
        lines.append(f"# {title}\n")

    meta_bits: list[str] = []
    if review.get("venue"):
        meta_bits.append(f"Venue: {review['venue']}")
    if review.get("submission_date"):
        meta_bits.append(f"Submission: {review['submission_date']}")
    for key in ("numerical_score", "overall_score", "score", "rating"):
        if review.get(key) is not None:
            meta_bits.append(f"{key}: {review[key]}")
    if meta_bits:
        lines.append("> " + " | ".join(meta_bits) + "\n")

    sections = review.get("sections") or {}
    if isinstance(sections, dict):

        def add_section(header: str, content: Any) -> None:
            if content is None:
                return
            text = str(content).strip()
            if not text:
                return
            lines.append(f"## {header}\n")
            lines.append(text)
            lines.append("")

        add_section("Summary", sections.get("summary"))
        add_section("Strengths", sections.get("strengths"))
        add_section("Weaknesses", sections.get("weaknesses"))
        add_section("Detailed Comments", sections.get("detailed_comments"))
        add_section("Questions for Authors", sections.get("questions"))
        add_section("Overall Assessment", sections.get("overall_assessment"))

        known = {
            "summary",
            "strengths",
            "weaknesses",
            "detailed_comments",
            "questions",
            "overall_assessment",
        }
        for key, value in sections.items():
            if key in known:
                continue
            add_section(str(key).replace("_", " ").title(), value)
    else:
        content = review.get("content") or review.get("review") or review.get("markdown")
        if content:
            lines.append(str(content))
        else:
            lines.append("_No structured sections in review JSON._")

    return "\n".join(lines).rstrip() + "\n"


def extract_apr_scores(review: dict[str, Any]) -> dict[str, Any]:
    """Best-effort extraction of numeric scores from paperreview.ai JSON."""
    out: dict[str, Any] = {"scale": "unknown", "overall": None, "dimensions": {}}

    for key in ("numerical_score", "overall_score", "score", "rating"):
        if review.get(key) is not None:
            try:
                out["overall"] = float(review[key])
                out["scale"] = "1-10"
                break
            except (TypeError, ValueError):
                pass

    sections = review.get("sections") or {}
    if isinstance(sections, dict):
        triple_raw = sections.get("binary_scores") or sections.get("triple_scores")
        if isinstance(triple_raw, str):
            for line in triple_raw.splitlines():
                m = re.match(r"^\s*-\s*([A-Za-z_]+)\s*:\s*([+-]?\d+(?:\.\d+)?)", line.strip())
                if m:
                    try:
                        out["dimensions"][m.group(1)] = float(m.group(2))
                    except ValueError:
                        pass

    for container_key in ("dimension_scores", "scores", "rubric", "dimensions"):
        block = review.get(container_key)
        if isinstance(block, dict):
            for k, v in block.items():
                if isinstance(v, (int, float)):
                    out["dimensions"][str(k)] = float(v)
                elif isinstance(v, dict) and v.get("score") is not None:
                    try:
                        out["dimensions"][str(k)] = float(v["score"])
                    except (TypeError, ValueError):
                        pass

    if out["dimensions"]:
        out["scale"] = "1-10" if max(out["dimensions"].values()) > 5.5 else out["scale"]

    return out


def peer_review_dir(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "peer_review"


def save_review_artifacts(
    run_dir: Path,
    review: dict[str, Any],
    *,
    token: str,
) -> ReviewArtifacts:
    out_dir = peer_review_dir(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "stanford_apr.json"
    md_path = out_dir / "stanford_apr.md"
    token_path = out_dir / TOKEN_FILENAME

    payload = dict(review)
    payload["_retrieved_at"] = _now_iso()
    payload["_token"] = token
    payload["_apr_scores"] = extract_apr_scores(review)

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(review_to_markdown(review), encoding="utf-8")
    token_path.write_text(f"{token}\n", encoding="utf-8")

    return ReviewArtifacts(json_path=json_path, md_path=md_path, token_path=token_path, review=payload)


def load_cached_token(run_dir: Path) -> str | None:
    token_path = peer_review_dir(run_dir) / TOKEN_FILENAME
    if not token_path.is_file():
        return None
    token = token_path.read_text(encoding="utf-8").strip()
    return token or None


def load_credentials_email() -> str | None:
    email = (os.environ.get("PAPERREVIEW_EMAIL") or "").strip()
    if email:
        return email
    cred_path = os.environ.get("BENCHMARK_CREDENTIALS_FILE", "").strip()
    if not cred_path:
        try:
            from integrations.benchmark_credentials import credentials_file_path

            cred_path = str(credentials_file_path())
        except Exception:
            return None
    path = Path(cred_path).expanduser()
    if not path.is_file():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pr = data.get("paperreview") or {}
        if isinstance(pr, dict):
            return (pr.get("email") or "").strip() or None
    except Exception:
        return None
    return None


def apr_json_has_score(run_dir: Path) -> bool:
    json_path = peer_review_dir(run_dir) / "stanford_apr.json"
    if not json_path.is_file():
        return False
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return extract_apr_scores(data).get("overall") is not None


def run_has_apr_score(run_dir: Path) -> bool:
    """True when a cached official/numeric APR score is already on disk."""
    if apr_json_has_score(run_dir):
        return True
    md = peer_review_dir(run_dir) / "stanford_apr.md"
    if md.is_file():
        try:
            text = md.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            return False
        return parse_score_from_text(text) is not None
    return False


def parse_score_from_text(text: str) -> float | None:
    """Parse paperreview-style numeric score from markdown / plain review text."""
    patterns = (
        r"numerical_score\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"overall[_\s-]?score\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"(?:rating|score)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
        r"Overall\s+(?:Score|Rating)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
        r"Overall\s+(?:Score|Rating)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 1.0 <= value <= 10.0:
                return value
    return None


def _prepare_pdf_for_upload(run_dir: Path, pdf_path: Path) -> tuple[Path, dict[str, Any]]:
    """Preflight: if PDF looks empty/broken, rebuild from TeX/Markdown once."""
    meta: dict[str, Any] = {
        "original_pdf": str(pdf_path),
        "rebuilt": False,
        "rebuild_reason": None,
        "rebuild_source": None,
    }
    try:
        from paths import pdf_looks_unreadable, rebuild_canonical_paper_pdf
    except ImportError:
        return pdf_path, meta

    if not pdf_looks_unreadable(pdf_path):
        return pdf_path, meta

    rebuilt = rebuild_canonical_paper_pdf(run_dir)
    if rebuilt is None:
        meta["rebuild_reason"] = "unreadable_pdf_but_rebuild_failed"
        return pdf_path, meta

    meta.update(
        {
            "rebuilt": True,
            "rebuild_reason": "unreadable_pdf_preflight",
            "rebuild_source": "tex_or_md",
            "rebuilt_pdf": str(rebuilt),
        }
    )
    return rebuilt, meta


def ensure_paperreview_report(
    run_dir: Path,
    pdf_path: Path,
    *,
    email: str | None = None,
    venue: str = "ICLR",
    custom_venue: str = "",
    wait: bool = True,
    interval_min: float = 10.0,
    max_hours: float = 48.0,
    resubmit: bool = False,
) -> ReviewArtifacts | None:
    """Submit PDF (if needed), poll for review, save stanford_apr.md/json under run_dir.

    If paperreview.ai rejects the PDF (422 / not a research paper), try rebuilding
    ``paper/main.pdf`` from TeX or Markdown once and resubmit.
    """
    run_dir = run_dir.resolve()
    out_dir = peer_review_dir(run_dir)
    pdf_path = Path(pdf_path).resolve()

    if not resubmit and run_has_apr_score(run_dir):
        return None

    resolved_email = (email or load_credentials_email() or "").strip()
    if not resolved_email:
        raise ValueError(
            "paperreview email required: set PAPERREVIEW_EMAIL, "
            "benchmark_credentials.yaml paperreview.email, or pass --paperreview-email"
        )

    session = requests.Session()
    rebuild_meta: dict[str, Any] = {}
    pdf_path, rebuild_meta = _prepare_pdf_for_upload(run_dir, pdf_path)

    token = None if resubmit else load_cached_token(run_dir)
    rejection: PaperRejectedError | None = None

    if token:
        status, data = fetch_review(token, session=session)
        if status == 200 and isinstance(data, dict):
            return save_review_artifacts(run_dir, data, token=token)
        if _is_paper_rejection(status, data):
            rejection = PaperRejectedError(status, data)
            token = None  # force a fresh upload after rebuild
        elif status != 202:
            raise RuntimeError(f"Unexpected review status {status}: {str(data)[:800]}")

    def _submit_and_maybe_wait(upload_pdf: Path, *, do_wait: bool) -> ReviewArtifacts | None:
        result = submit_pdf(
            upload_pdf,
            email=resolved_email,
            venue=venue,
            custom_venue=custom_venue,
            session=session,
        )
        tok = result.token
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / TOKEN_FILENAME).write_text(f"{tok}\n", encoding="utf-8")
        if not do_wait:
            return None
        review = poll_review(tok, interval_min=interval_min, max_hours=max_hours, session=session)
        arts = save_review_artifacts(run_dir, review, token=tok)
        return arts

    # Fresh submit (or resubmit after clearing rejected token).
    if token is None:
        try:
            artifacts = _submit_and_maybe_wait(pdf_path, do_wait=wait)
            if artifacts is not None and rebuild_meta.get("rebuilt"):
                # Annotate saved JSON with rebuild info.
                try:
                    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
                    payload["_pdf_rebuild"] = rebuild_meta
                    artifacts.json_path.write_text(
                        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                except OSError:
                    pass
            return artifacts
        except PaperRejectedError as exc:
            rejection = exc

    # Existing token still processing.
    if token is not None and rejection is None:
        if not wait:
            return None
        try:
            review = poll_review(token, interval_min=interval_min, max_hours=max_hours, session=session)
            return save_review_artifacts(run_dir, review, token=token)
        except PaperRejectedError as exc:
            rejection = exc

    # Rejected: rebuild from tex/md once, then resubmit.
    if rejection is not None:
        try:
            from paths import rebuild_canonical_paper_pdf
        except ImportError as exc:  # pragma: no cover
            raise rejection from exc

        rebuilt = rebuild_canonical_paper_pdf(run_dir)
        if rebuilt is None:
            raise RuntimeError(
                f"{rejection}; rebuild from tex/md also failed (no usable source or compile error)"
            )
        if rebuilt.resolve() == pdf_path.resolve() and not rebuild_meta.get("rebuilt"):
            # Same path overwritten — still retry upload with new bytes.
            pass

        rebuild_meta = {
            "rebuilt": True,
            "rebuild_reason": "paperreview_rejected",
            "rejection": str(rejection)[:500],
            "rebuilt_pdf": str(rebuilt),
        }
        artifacts = _submit_and_maybe_wait(rebuilt, do_wait=wait)
        if artifacts is not None:
            try:
                payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
                payload["_pdf_rebuild"] = rebuild_meta
                artifacts.json_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass
        return artifacts

    return None
