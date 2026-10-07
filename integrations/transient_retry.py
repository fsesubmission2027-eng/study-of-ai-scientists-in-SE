"""Shared transient-failure detection and auto-continuation for benchmark runners.

When an agent exits due to upstream/API flakiness (empty stream, 5xx, rate limit,
connection drop), integrations can reuse the same ``run_root`` and relaunch with a
continuation prompt instead of starting a brand-new workspace.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent_task_document import BENCHMARK_RESUME_CONTINUATION_BRIEF

DEFAULT_MAX_TRANSIENT_RESUME_ROUNDS = 2

# Matched against the *tail* of the agent log (case-insensitive).
_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"assistant stream produced no content",
        r"assistant stream ended without a message stop event",
        r"Request failed",
        r"upstream unreachable",
        r"Connection reset",
        r"Connection refused",
        r"Temporary failure in name resolution",
        r"Name or service not known",
        r"SSL: CERTIFICATE_VERIFY_FAILED",  # intermittent TLS blips still worth one retry
        r"\b502\b|\b503\b|\b504\b|\b429\b",
        r"rate.?limit",
        r"Too Many Requests",
        r"server_error",
        r"internal.?server.?error",
        r"overloaded",
        r"model.?unavailable",
        r"EOF occurred in violation of protocol",
        r"Remote end closed connection",
        r"Broken pipe",
        r"Read timed out",
        r"timed? ?out waiting",
        r"DeadlineExceeded",
        r"context deadline exceeded",
        r"empty response",
        r"no content",
        r"stream closed",
        r"incomplete chunked read",
    )
)

# If these appear as the dominant failure signal, do not auto-retry.
_NON_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"Missing API key",
        r"Missing OPENAI_API_KEY",
        r"Task directory not found",
        r"Could not locate .* repo",
        r"docker is required",
        r"Permission denied",
        r"No space left on device",
        r"Disk quota exceeded",
        r"invalid api key",
        r"Incorrect API key",
        r"authentication.?failed",
        r"Unauthorized",
        r"Forbidden",
        r"ModuleNotFoundError",
        r"SyntaxError:",
        r"ImportError:",
    )
)


@dataclass(frozen=True)
class TransientProbe:
    is_transient: bool
    reason: str
    matched: str = ""


def _read_log_tail(log_path: Path | None, *, max_chars: int = 80_000) -> str:
    if log_path is None or not log_path.is_file():
        return ""
    try:
        data = log_path.read_bytes()
    except OSError:
        return ""
    if len(data) > max_chars:
        data = data[-max_chars:]
    return data.decode("utf-8", errors="replace")


def probe_transient_failure(
    *,
    returncode: int,
    log_path: Path | None,
    stderr_snippet: str = "",
) -> TransientProbe:
    """Return whether an agent exit looks like a retryable upstream/agent flake."""
    if returncode == 0:
        return TransientProbe(False, "clean exit")

    text = _read_log_tail(log_path)
    if stderr_snippet:
        text = f"{text}\n{stderr_snippet}"
    if not text.strip():
        # Non-zero with empty log: often killed mid-stream; allow limited retry.
        return TransientProbe(True, "non-zero exit with empty/short log", "empty_log")

    for pat in _NON_TRANSIENT_PATTERNS:
        m = pat.search(text)
        if m:
            return TransientProbe(False, f"non-transient match: {pat.pattern}", m.group(0))

    # Prefer matches near the end of the log.
    tail = text[-12_000:] if len(text) > 12_000 else text
    for pat in _TRANSIENT_PATTERNS:
        m = pat.search(tail) or pat.search(text)
        if m:
            return TransientProbe(True, f"transient match: {pat.pattern}", m.group(0)[:120])

    # Generic non-zero without a known pattern: do not auto-retry (avoid burning cost).
    return TransientProbe(False, "non-zero exit without known transient pattern")


def build_transient_continuation_prompt(
    *,
    tool: str,
    run_root: Path,
    extra_hints: list[str] | None = None,
) -> str:
    """Prompt for a fresh agent process continuing the same workspace."""
    hints = [
        f"Workspace (continue here): `{run_root}`",
        "Do **not** recreate the workspace or re-run long completed experiments unless results are missing/corrupt.",
        "Inspect existing artifacts (idea/, project/, experiment_results/, results/, paper/, logs) and continue from the first incomplete stage.",
        "If metrics live under `experiment_results/metrics.json`, also publish/copy to `results/metrics.json` when the benchmark expects that path.",
        "Follow task-required metric keys in `dataset_candidate/metrics.json` / `dataset_candidate/metrics_schema.json` when present.",
        "Finish review / narrative / paper deliverables if still missing.",
    ]
    if extra_hints:
        hints.extend(extra_hints)
    bullet = "\n".join(f"- {h}" for h in hints)
    return (
        f"{BENCHMARK_RESUME_CONTINUATION_BRIEF}\n\n"
        f"Tool: {tool}\n"
        "Continuation constraints:\n"
        f"{bullet}\n"
    )


def add_transient_retry_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_rounds: int = DEFAULT_MAX_TRANSIENT_RESUME_ROUNDS,
) -> None:
    parser.add_argument(
        "--max-transient-resume-rounds",
        type=int,
        default=default_rounds,
        help=(
            "After a transient agent/upstream failure (empty stream, 5xx, rate limit, …), "
            f"relaunch continuation in the same run directory up to this many times "
            f"(default {default_rounds})."
        ),
    )
    parser.add_argument(
        "--no-auto-resume-on-transient",
        action="store_true",
        help="Disable automatic continuation after transient agent/upstream failures.",
    )


def resolve_transient_retry_policy(args: argparse.Namespace) -> tuple[bool, int]:
    enabled = not bool(getattr(args, "no_auto_resume_on_transient", False))
    rounds = max(0, int(getattr(args, "max_transient_resume_rounds", DEFAULT_MAX_TRANSIENT_RESUME_ROUNDS)))
    return enabled, rounds


def resolve_existing_run_dir(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"--run-dir does not exist or is not a directory: {path}")
    return path


def retry_launch_on_transient(
    *,
    returncode: int,
    log_path: Path,
    args: argparse.Namespace,
    label: str,
    relaunch: Callable[[], int],
    stderr_snippet: str = "",
) -> int:
    """If *returncode* looks transient, call *relaunch* up to the configured rounds.

    *relaunch* must be a zero-arg callable returning a new integer exit code.
    The first *returncode* is the initial launch result (already executed).
    """
    auto, max_rounds = resolve_transient_retry_policy(args)
    resume_round = 0
    while returncode != 0 and auto and resume_round < max_rounds:
        probe = probe_transient_failure(
            returncode=returncode,
            log_path=log_path,
            stderr_snippet=stderr_snippet,
        )
        if not probe.is_transient:
            print(f"[retry] {label}: skip auto-resume ({probe.reason})", file=sys.stderr)
            break
        resume_round += 1
        print(
            f"[retry] {label}: transient failure ({probe.matched or probe.reason}); "
            f"continuation {resume_round}/{max_rounds}",
            file=sys.stderr,
        )
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n\n# {label} auto-continuation {resume_round}/{max_rounds} "
                f"reason={probe.reason}\n\n"
            )
        returncode = int(relaunch())
        stderr_snippet = ""
    return returncode
