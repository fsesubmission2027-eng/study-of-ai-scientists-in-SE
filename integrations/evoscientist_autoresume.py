"""Engineering auto-resume helpers for unattended EvoScientist benchmark runs.

EvoSci may Goodbye while waiting on background jobs or after asking the user
what to do next. Benchmark integrations use these helpers to:
- sync container ``/workspace`` artifacts onto the host ``run_root``
- wait for background experiment processes before resuming
- detect "asking for confirmation" exits and force a no-questions continuation
- stop after repeated ineffective resume rounds
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_ASK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"Which (?:of the|would you like|option)",
        r"What (?:should|do) (?:I|you|we) (?:do|run) next",
        r"should I run automatically next",
        r"What I need from you",
        r"optional (?:choices|tasks|next steps)",
        r"Confirm (?:to|whether|if)",
        r"Please (?:confirm|choose|select|let me know)",
        r"Would you like me to",
        r"Shall I\b",
    )
)

_WAIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"monitor the background",
        r"wait(?:ing)? for (?:the )?(?:background|grid|experiment)",
        r"running in the background",
        r"as soon as (?:the )?(?:aggregated )?metrics",
        r"grid-?run to finish",
        r"let the grid run finish",
    )
)

# Detect lingering experiment workers across task types (fuzz grids, runners, etc.).
_BG_PROCESS_REGEX = (
    r"(run_grid|afl-fuzz|run_baseline|experiment_runner|"
    r"timeout .*afl|fuzzing|grid_run|"
    r"pytest|python3? .*(experiment|train|eval|benchmark|specflow|watsup))"
)

_SYNC_DIRS = (
    "results",
    "project",
    "paper",
    "analysis",
    "artifacts",
    "dataset_candidate",
    "idea",
    "idea-stage",
    "review-stage",
)

_SYNC_FILES = (
    "plan.md",
    "todos.md",
    "README.md",
    "NARRATIVE_REPORT.md",
    "RESEARCH_BRIEF.md",
)


@dataclass(frozen=True)
class ExitKind:
    asking: bool
    waiting: bool
    matched: str = ""


def _read_log_tail(log_path: Path | None, *, max_chars: int = 40_000) -> str:
    if log_path is None or not log_path.is_file():
        return ""
    try:
        data = log_path.read_bytes()
    except OSError:
        return ""
    if len(data) > max_chars:
        data = data[-max_chars:]
    text = data.decode("utf-8", errors="replace")
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def classify_evosci_exit(log_path: Path | None) -> ExitKind:
    """Classify the latest EvoSci exit from the log tail."""
    text = _read_log_tail(log_path)
    if not text.strip():
        return ExitKind(False, False)
    # Agent often asks/waits then prints Goodbye — inspect the text *before*
    # the last Goodbye within the latest resume/launch segment.
    parts = re.split(r"(?m)^# EvoScientist (?:launch|resume)", text)
    segment = parts[-1] if parts else text
    goodbye_idx = segment.rfind("Goodbye!")
    if goodbye_idx >= 0:
        window = segment[max(0, goodbye_idx - 8_000) : goodbye_idx]
    else:
        window = segment[-8_000:] if len(segment) > 8_000 else segment

    for pat in _ASK_PATTERNS:
        m = pat.search(window)
        if m:
            return ExitKind(True, False, m.group(0)[:120])
    for pat in _WAIT_PATTERNS:
        m = pat.search(window)
        if m:
            return ExitKind(False, True, m.group(0)[:120])
    return ExitKind(False, False)


def list_background_experiment_procs(container_id: str) -> list[str]:
    """Return running experiment-like process command lines inside the container."""
    proc = subprocess.run(
        [
            "docker",
            "exec",
            container_id,
            "bash",
            "-lc",
            "ps -eo args --no-headers 2>/dev/null || ps -eo args",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    pat = re.compile(_BG_PROCESS_REGEX, re.I)
    out: list[str] = []
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s or s.startswith("bash -lc") or "ps -eo" in s:
            continue
        if pat.search(s):
            out.append(s[:240])
    return out


def wait_for_background_experiments(
    container_id: str,
    *,
    poll_sec: float = 20.0,
    max_wait_sec: float = 3600.0,
    log_path: Path | None = None,
) -> bool:
    """Block until experiment-like background processes exit (or timeout).

    Returns True if clear / already clear; False on timeout.
    """
    deadline = time.time() + max(0.0, max_wait_sec)
    while True:
        procs = list_background_experiment_procs(container_id)
        if not procs:
            return True
        remaining = deadline - time.time()
        if remaining <= 0:
            msg = (
                f"[resume] background experiments still running after wait "
                f"({len(procs)} procs); continuing anyway"
            )
            print(msg)
            if log_path is not None:
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"\n# {msg}\n")
            return False
        preview = procs[0]
        print(
            f"[resume] waiting for background experiments "
            f"({len(procs)} procs; e.g. {preview!r}); "
            f"sleep {poll_sec:.0f}s, ~{remaining:.0f}s left"
        )
        time.sleep(min(poll_sec, remaining))


def sync_container_workspace_to_run_root(
    container_id: str,
    run_root: Path,
) -> list[str]:
    """Copy common artifact paths from container ``/workspace`` onto ``run_root``."""
    synced: list[str] = []
    run_root.mkdir(parents=True, exist_ok=True)

    for name in _SYNC_DIRS:
        dest = run_root / name
        dest.mkdir(parents=True, exist_ok=True)
        check = subprocess.run(
            ["docker", "exec", container_id, "bash", "-lc", f"test -d /workspace/{name}"],
            capture_output=True,
            check=False,
        )
        if check.returncode != 0:
            continue
        proc = subprocess.run(
            ["docker", "cp", f"{container_id}:/workspace/{name}/.", str(dest)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            synced.append(f"{name}/")
        else:
            err = (proc.stderr or proc.stdout or "").strip()
            print(f"[sync] warn: failed to copy /workspace/{name}: {err}")

    for name in _SYNC_FILES:
        check = subprocess.run(
            ["docker", "exec", container_id, "bash", "-lc", f"test -f /workspace/{name}"],
            capture_output=True,
            check=False,
        )
        if check.returncode != 0:
            continue
        dest = run_root / name
        proc = subprocess.run(
            ["docker", "cp", f"{container_id}:/workspace/{name}", str(dest)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            synced.append(name)

    # Prefer grid summary into results/metrics.json when host metrics missing/empty.
    metrics = run_root / "results" / "metrics.json"
    grid = run_root / "results" / "grid" / "metrics_summary.json"
    summary = run_root / "results" / "metrics_summary.json"
    if not metrics.is_file() or metrics.stat().st_size < 32:
        for src in (grid, summary):
            if src.is_file() and src.stat().st_size >= 32:
                metrics.write_bytes(src.read_bytes())
                synced.append(f"results/metrics.json<-{src.name}")
                break

    # Promote analysis scripts into project/ when agent never wrote project/*.py.
    project = run_root / "project"
    analysis = run_root / "analysis"
    project.mkdir(parents=True, exist_ok=True)
    has_project_py = any(project.rglob("*.py"))
    if not has_project_py and analysis.is_dir():
        copied = 0
        for src in analysis.rglob("*.py"):
            dest = project / src.relative_to(analysis)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(src, dest)
                copied += 1
        if copied:
            synced.append(f"project/<-analysis/*.py({copied})")

    # Also copy obstacle generator if still no project py.
    if not any(project.rglob("*.py")):
        gen = run_root / "dataset_candidate" / "obstacles" / "generator.py"
        if gen.is_file():
            shutil.copy2(gen, project / "generator.py")
            synced.append("project/generator.py<-dataset_candidate")

    return synced


def build_hard_continuation_prompt(
    *,
    run_root: Path,
    issues: list[str],
    asking: bool = False,
    waiting: bool = False,
    task_dir: Path | None = None,
    required_metrics: list[str] | None = None,
) -> str:
    """Continuation that forbids questions and optional scaled experiments.

    Metrics guidance is task-specific: pass ``task_dir`` and/or ``required_metrics``
    from ``seeds/agent/metrics.json``. Never hard-code one task's metric names.
    """
    from agent_task_document import BENCHMARK_RESUME_CONTINUATION_BRIEF
    from metrics_schema import (
        format_required_metrics_prompt_note,
        format_required_metrics_prompt_note_for_task,
    )

    reasons: list[str] = []
    if asking:
        reasons.append("You previously asked the user what to do next and then exited.")
    if waiting:
        reasons.append(
            "You previously said you would wait/monitor background experiments and then exited."
        )
    reason_block = "\n".join(f"- {r}" for r in reasons) if reasons else "- Continue incomplete work."
    issue_block = "\n".join(f"- {i}" for i in issues) if issues else "- (validator issues not listed)"
    if required_metrics is not None:
        metrics_note = format_required_metrics_prompt_note(list(required_metrics))
    elif task_dir is not None:
        metrics_note = format_required_metrics_prompt_note_for_task(task_dir)
    else:
        metrics_note = format_required_metrics_prompt_note([])
    return (
        f"{BENCHMARK_RESUME_CONTINUATION_BRIEF}\n\n"
        "Hard constraints for this unattended benchmark continuation:\n"
        "- Do **not** ask the user any questions, options, or confirmations.\n"
        "- Do **not** propose or start optional large-scale follow-up experiments "
        "while the required benchmark deliverables below are still incomplete.\n"
        "- Do **not** Goodbye until the missing deliverables below exist on disk.\n"
        f"- Write files under the host workdir `{run_root}` "
        "(same path inside the container). Avoid orphan `/workspace`-only copies; "
        "if you already wrote under `/workspace`, copy/sync into the host workdir paths.\n"
        "- Pending gates: use Lite code-generation mode when delegating implementation.\n\n"
        f"Why this continuation fired:\n{reason_block}\n\n"
        f"Missing / invalid deliverables to fix now:\n{issue_block}\n\n"
        f"{metrics_note}\n"
    )


def issues_fingerprint(issues: list[str]) -> tuple[str, ...]:
    return tuple(sorted(issues))
