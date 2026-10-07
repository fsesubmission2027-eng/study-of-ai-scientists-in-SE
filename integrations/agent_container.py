"""Shared helpers for running AI Scientist agents inside TaskSandbox containers."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from path_alignment import (
    align_path,
    build_volume_remap,
    runtime_dataset_env,
)

HOST_GATEWAY_ALIAS = "host.docker.internal"
DEFAULT_SCRUB_BASE_URL = f"http://{HOST_GATEWAY_ALIAS}:8787/v1"
DEFAULT_MODELVERSE_BASE_URL = "https://api-sg.umodelverse.ai/v1"
DEFAULT_METERING_PORT = 8788

# LiteLLM / DeepScientist routing prefix — not the umodelverse model id.
_UMODELVERSE_STRIP_PREFIXES = ("modelverse/",)


def normalize_umodelverse_model(model: str) -> str:
    """Normalize model id for umodelverse API.

    Keep provider ids like ``openai/gpt-5-mini`` as-is (listed in /v1/models).
    Only strip internal routing prefixes such as ``modelverse/``.
    """
    normalized = (model or "").strip()
    for prefix in _UMODELVERSE_STRIP_PREFIXES:
        if normalized.startswith(prefix):
            return normalized.split("/", 1)[-1]
    return normalized
BENCHMARK_AGENT_NATIVE_ENV = "BENCHMARK_AGENT_NATIVE"
BENCHMARK_RUN_ROOT_ENV = "BENCHMARK_RUN_ROOT"
DEFAULT_AI_SCIENTIST_ROOT = Path.home() / "AI-Scientist-v2"
DEFAULT_BENCHMARK_ROOT = Path.home() / "ai_scientist_benchmark"
INTEGRATIONS_ROOT = Path(__file__).resolve().parent
DEFAULT_AI_SCIENTIST_CONDA_ENVS = ("ai_scientist-v2", "ai_scientist")
AI_SCIENTIST_BFTS_IMPORT_CHECK = (
    "import sys;"
    "import torch;"
    "sys.path.insert(0, {root!r});"
    "from ai_scientist.llm import create_client;"
    "from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import perform_experiments_bfts;"
    "print('ok')"
)

# (host path template, container path template, mode)
_RUNTIME_MOUNT_SPECS: dict[str, list[tuple[str, str, str]]] = {
    "evoscientist": [
        ("~/miniconda3/envs/EvoSci", "~/miniconda3/envs/EvoSci", "ro"),
        ("~/ai_scientist_benchmark", "~/ai_scientist_benchmark", "ro"),
    ],
    "aris": [
        ("~/.local/bin", "~/.local/bin", "ro"),
        ("~/.npm-global", "~/.npm-global", "ro"),
        ("~/Auto-claude-code-research-in-sleep", "~/Auto-claude-code-research-in-sleep", "ro"),
    ],
    "deepscientist": [
        ("~/.npm-global", "~/.npm-global", "ro"),
        ("~/DeepScientist", "~/DeepScientist", "ro"),
    ],
    "aiscientist": [
        ("~/AI-Scientist-v2", "~/AI-Scientist-v2", "ro"),
        ("~/miniconda3/envs/ai_scientist-v2", "~/miniconda3/envs/ai_scientist-v2", "ro"),
        ("~/miniconda3/envs/ai_scientist", "~/miniconda3/envs/ai_scientist", "ro"),
        ("~/ai_scientist_benchmark", "~/ai_scientist_benchmark", "ro"),
    ],
    "tinyscientist": [
        ("~/miniconda3/envs/pure_tiny_env", "~/miniconda3/envs/pure_tiny_env", "ro"),
        ("~/miniconda3/bin", "~/miniconda3/bin", "ro"),
        ("~/AI-Scientist-v2", "~/AI-Scientist-v2", "ro"),
        ("~/ai_scientist_benchmark", "~/ai_scientist_benchmark", "ro"),
    ],
    "airesearcher": [
        # AI-Researcher writes paper_db / flow caches / __pycache__ under its tree
        # (and module import of terminal_tools opens chromadb). Keep rw.
        ("~/AI-Researcher", "~/AI-Researcher", "rw"),
        # AI-Researcher/.venv/bin/python → ~/.local/share/uv/python/...
        ("~/.local/share/uv", "~/.local/share/uv", "ro"),
        # Playwright Chromium (PLAYWRIGHT_BROWSERS_PATH); host HOME is not fully mounted.
        ("~/.cache/ms-playwright", "~/.cache/ms-playwright", "ro"),
        ("~/miniconda3", "~/miniconda3", "ro"),
        ("~/AI-Scientist-v2", "~/AI-Scientist-v2", "ro"),
        ("~/ai_scientist_benchmark", "~/ai_scientist_benchmark", "ro"),
    ],
    "researchclaw": [
        ("~/AutoResearchClaw", "~/AutoResearchClaw", "ro"),
        ("~/arc_env", "~/arc_env", "ro"),
        # arc_env/bin/python3 -> ~/miniconda3/bin/python3 (shebang chain)
        ("~/miniconda3", "~/miniconda3", "ro"),
        ("~/AI-Scientist-v2", "~/AI-Scientist-v2", "ro"),
        ("~/ai_scientist_benchmark", "~/ai_scientist_benchmark", "ro"),
        ("/usr/bin/docker", "/usr/bin/docker", "ro"),
        ("/var/run/docker.sock", "/var/run/docker.sock", "rw"),
    ],
}

_PATH_PREFIX_SPECS: dict[str, list[str]] = {
    "evoscientist": ["~/miniconda3/envs/EvoSci/bin"],
    "aris": ["~/.local/bin", "~/.npm-global/bin"],
    "deepscientist": ["~/.npm-global/bin"],
    "aiscientist": [
        "~/miniconda3/envs/ai_scientist-v2/bin",
        "~/miniconda3/envs/ai_scientist/bin",
    ],
    "tinyscientist": [
        "~/miniconda3/envs/pure_tiny_env/bin",
        "~/miniconda3/bin",
    ],
    "airesearcher": ["~/miniconda3/bin"],
    "researchclaw": ["~/arc_env/bin"],
}


def literature_scrub_enabled(host_env: dict[str, str] | None = None) -> bool:
    """Literature year/target-paper scrubbing is off by default for all tools."""
    env = host_env or os.environ
    raw = (env.get("LITERATURE_SCRUB_ENABLED") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Default: disabled (year_filter.yaml also has enabled: false).
    return False


def _is_scrub_proxy_url(value: str) -> bool:
    lower = value.lower()
    return (
        ":8787" in lower
        or "literature_scrub" in lower
        or lower.endswith(":8787/v1")
        or "/8787/" in lower
    )


def _is_metering_proxy_url(value: str) -> bool:
    lower = (value or "").lower()
    if not lower:
        return False
    if f":{DEFAULT_METERING_PORT}" in lower:
        return True
    return "/m/" in lower and "/v1" in lower


def _real_upstream_base_url(host_env: dict[str, str] | None = None) -> str:
    """Upstream for the metering proxy: scrub proxy or Modelverse (never metering itself)."""
    env = host_env or os.environ
    scrub_on = literature_scrub_enabled(env)
    candidates: list[str] = []
    for key in (
        "CUSTOM_OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "API_BASE_URL",
        "LITERATURE_SCRUB_BASE_URL",
    ):
        value = (env.get(key) or "").strip().rstrip("/")
        if not value:
            continue
        if _is_metering_proxy_url(value):
            continue
        candidates.append(value if value.endswith("/v1") else f"{value}/v1")

    if scrub_on:
        for value in candidates:
            if _is_scrub_proxy_url(value) or "127.0.0.1" in value or "localhost" in value:
                return DEFAULT_SCRUB_BASE_URL
            return value
        return DEFAULT_SCRUB_BASE_URL

    for value in candidates:
        if _is_scrub_proxy_url(value):
            continue
        if "127.0.0.1" in value or "localhost" in value:
            continue
        return value
    return DEFAULT_MODELVERSE_BASE_URL


def scrub_base_url(host_env: dict[str, str] | None = None) -> str:
    """Resolve OpenAI-compatible base URL for agent LLM calls.

    Literature scrubbing is disabled by default: prefer a real Modelverse /
    OpenAI-compatible URL. When LITERATURE_SCRUB_ENABLED=1, keep routing via
    the local scrub proxy (:8787).
    """
    env = host_env or os.environ
    scrub_on = literature_scrub_enabled(env)

    candidates: list[str] = []
    for key in (
        "CUSTOM_OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "API_BASE_URL",
        "LITERATURE_SCRUB_BASE_URL",
    ):
        value = (env.get(key) or "").strip().rstrip("/")
        if value:
            candidates.append(value if value.endswith("/v1") else f"{value}/v1")

    if scrub_on:
        for value in candidates:
            if _is_scrub_proxy_url(value) or "127.0.0.1" in value or "localhost" in value:
                return DEFAULT_SCRUB_BASE_URL
            return value
        return DEFAULT_SCRUB_BASE_URL

    for value in candidates:
        if _is_scrub_proxy_url(value):
            continue
        if _is_metering_proxy_url(value):
            # Prefer an already-applied metering URL (per-run token path).
            return value
        if "127.0.0.1" in value or "localhost" in value:
            # Local scrub proxy leftovers — skip when scrub is off.
            continue
        return value
    return DEFAULT_MODELVERSE_BASE_URL


def apply_run_metering_to_env(
    env: dict[str, str],
    *,
    run_root: Path,
    for_container: bool = True,
) -> dict[str, str]:
    """Route OpenAI-compatible traffic through the per-run metering proxy."""
    if str(INTEGRATIONS_ROOT) not in sys.path:
        sys.path.insert(0, str(INTEGRATIONS_ROOT))
    from run_metering import begin_run_metering, metering_enabled

    if not metering_enabled(env):
        return env
    upstream = _real_upstream_base_url(env)
    session = begin_run_metering(
        run_root,
        upstream=upstream,
        for_container=for_container,
    )
    if session is None:
        return env
    return session.apply_to_env(env, for_container=for_container)


def preflight_llm_model_chain(
    *,
    base_url: str,
    api_key: str,
    models: list[str],
    min_max_tokens: int = 16,
) -> tuple[bool, str]:
    """Ping chat/completions with umodelverse-safe limits.

    ResearchClaw's built-in preflight uses ``max_tokens=1``, which umodelverse
    rejects for ``openai/gpt-5-mini`` (HTTP 400). EvoScientist avoids this via
    LangChain defaults. Benchmark runs should call this helper instead.
    """
    import json
    import urllib.error
    import urllib.request

    if not api_key.strip():
        return False, "Missing OPENAI_API_KEY"
    if not models:
        return False, "No models configured for preflight"

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    last_error = "unknown error"
    for model in models:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": min_max_tokens,
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
            return True, f"OK - model {model} responding"
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:  # noqa: BLE001
                pass
            last_error = f"Model {model} failed: HTTP {exc.code}"
            if detail:
                last_error += f" ({detail})"
            continue
        except (urllib.error.URLError, OSError) as exc:
            last_error = f"Model {model} failed: {exc}"
            continue
    return False, last_error


def apply_literature_scrub_to_env(env: dict[str, str]) -> dict[str, str]:
    """Set OpenAI-compatible base URLs for agents (scrub optional, off by default)."""
    merged = env.copy()
    base = scrub_base_url(merged)
    if literature_scrub_enabled(merged):
        merged.setdefault("LITERATURE_SCRUB_BASE_URL", base)
    for key in (
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "CUSTOM_OPENAI_BASE_URL",
        "API_BASE_URL",
    ):
        cur = (merged.get(key) or "").strip()
        if (not cur) or ("umodelverse.ai" in cur) or _is_scrub_proxy_url(cur) or "127.0.0.1" in cur or "localhost" in cur:
            merged[key] = base
    return merged


def workdir_for_run(run_root: Path) -> str:
    """Aligned-path workdir: identical on host and inside the container."""
    return str(run_root.resolve())


def expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def reuse_benchmark_run_root() -> Path | None:
    raw = os.environ.get(BENCHMARK_RUN_ROOT_ENV, "").strip()
    if not raw:
        return None
    run_root = Path(raw).expanduser()
    return run_root.resolve() if run_root.is_dir() else None


def load_api_env(
    env: dict[str, str],
    *,
    env_file: Path | None = None,
) -> bool:
    """Load LLM keys/models from benchmark_credentials.yaml (with legacy .env fallback)."""
    del env_file  # legacy arg kept for call-site compatibility
    if str(INTEGRATIONS_ROOT) not in sys.path:
        sys.path.insert(0, str(INTEGRATIONS_ROOT))
    from benchmark_credentials import apply_benchmark_credentials, require_llm_api_key

    merged = apply_benchmark_credentials(env)
    env.clear()
    env.update(merged)
    base = scrub_base_url(env)
    for key in ("OPENAI_API_BASE", "OPENAI_BASE_URL", "API_BASE_URL", "CUSTOM_OPENAI_BASE_URL"):
        cur = (env.get(key) or "").strip()
        if (not cur) or ("umodelverse.ai" in cur) or _is_scrub_proxy_url(cur) or "127.0.0.1" in cur or "localhost" in cur:
            env[key] = base
    return require_llm_api_key(env)


def print_log_tail(log_path: Path, *, max_lines: int = 40) -> None:
    if not log_path.is_file():
        return
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return
    tail = lines[-max_lines:]
    print(f"[log] last {len(tail)} line(s) from {log_path}:", file=sys.stderr)
    for line in tail:
        print(line, file=sys.stderr)


def aiscientist_python_candidates(host_env: dict[str, str] | None = None) -> list[str]:
    env = host_env or os.environ
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        resolved = str(Path(candidate).expanduser())
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    explicit = (env.get("AI_SCIENTIST_PYTHON") or "").strip()
    if explicit:
        add(explicit)
    for env_name in DEFAULT_AI_SCIENTIST_CONDA_ENVS:
        add(str(Path.home() / "miniconda3/envs" / env_name / "bin/python"))
    add(str(Path.home() / "miniconda3/bin/python3"))
    add("python3")
    return candidates


def aiscientist_import_check(ai_scientist_root: Path | str) -> str:
    return AI_SCIENTIST_BFTS_IMPORT_CHECK.format(root=str(Path(ai_scientist_root).resolve()))


def resolve_aiscientist_python(
    *,
    host_env: dict[str, str] | None = None,
    container_id: str | None = None,
    cwd: Path | None = None,
    ai_scientist_root: Path | str | None = None,
) -> tuple[str | None, str]:
    """Pick the first Python that can import the BFTS launch stack."""
    root = Path(ai_scientist_root or DEFAULT_AI_SCIENTIST_ROOT).resolve()
    import_stmt = aiscientist_import_check(root)
    errors: list[str] = []

    for candidate in aiscientist_python_candidates(host_env):
        if container_id:
            ok_bin, bin_msg = preflight_binary(container_id, candidate, cwd=cwd)
            if not ok_bin:
                errors.append(bin_msg)
                continue
            ok_import, import_msg = preflight_python_import(
                container_id,
                python_bin=candidate,
                import_stmt=import_stmt,
                cwd=cwd,
            )
            if ok_import:
                return candidate, import_msg
            errors.append(import_msg)
            continue

        path = Path(candidate)
        if candidate != "python3" and not path.exists():
            errors.append(f"{candidate} not found on host")
            continue
        try:
            proc = subprocess.run(
                [candidate, "-c", import_stmt],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                stdin=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            errors.append(f"{candidate}: {exc}")
            continue
        if proc.returncode == 0:
            return candidate, f"{candidate} BFTS import OK"
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        errors.append(f"{candidate}: {detail[-1] if detail else proc.returncode}")

    summary = errors[-1] if errors else "no python candidates"
    return None, (
        "No Python environment can import AI-Scientist-v2 BFTS dependencies "
        f"(need conda env {DEFAULT_AI_SCIENTIST_CONDA_ENVS[0]}). Last error: {summary}"
    )


def runtime_mounts(agent_tool: str) -> list[tuple[Path, Path, str]]:
    mounts: list[tuple[Path, Path, str]] = []
    seen: set[str] = set()
    for host_tmpl, container_tmpl, mode in _RUNTIME_MOUNT_SPECS.get(agent_tool, []):
        host_path = expand_path(host_tmpl)
        container_path = expand_path(container_tmpl)
        if not host_path.exists():
            continue
        key = str(host_path)
        if key in seen:
            continue
        seen.add(key)
        mounts.append((host_path, container_path, mode))
    extra = os.environ.get("BENCHMARK_AGENT_RUNTIME_MOUNTS", "").strip()
    if extra:
        for spec in extra.split(","):
            spec = spec.strip()
            if not spec:
                continue
            parts = spec.split(":")
            if len(parts) < 2:
                continue
            host_path = expand_path(parts[0])
            container_path = expand_path(parts[1])
            mode = parts[2] if len(parts) > 2 else "ro"
            if host_path.exists():
                mounts.append((host_path, container_path, mode))
    return mounts


def path_prefix_for(agent_tool: str) -> str:
    parts: list[str] = []
    for tmpl in _PATH_PREFIX_SPECS.get(agent_tool, []):
        path = expand_path(tmpl)
        if path.exists():
            parts.append(str(path))
    return ":".join(parts)


def merge_path_entries(*segments: str) -> str:
    """Deduplicate PATH-like segments while preserving first-seen order."""
    seen: set[str] = set()
    parts: list[str] = []
    for seg in segments:
        if not seg:
            continue
        for part in seg.split(":"):
            if part and part not in seen:
                seen.add(part)
                parts.append(part)
    return ":".join(parts)


# Tool conda/env bins must not be mistaken for task experiment venvs.
_TOOL_PYTHON_PATH_MARKERS = (
    "/envs/ai_scientist-v2/",
    "/envs/ai_scientist/",
    "/envs/EvoSci/",
    "/envs/pure_tiny_env/",
    "/arc_env/",
)


def _path_looks_like_task_venv_bin(bin_dir: Path) -> bool:
    if bin_dir.name != "bin":
        return False
    parent = bin_dir.parent.name
    if parent in {".venv", "venv"} or parent.endswith("-venv") or parent.endswith("_venv"):
        return True
    # Generic /opt/<task>-env style used by some setups.
    return parent.endswith("-env") and "envs" not in bin_dir.parts


def _python_from_bin_dir(bin_dir: Path, *, require_exists: bool = True) -> str | None:
    for name in ("python3", "python"):
        cand = bin_dir / name
        if require_exists:
            if cand.is_file() and os.access(cand, os.X_OK):
                try:
                    return str(cand.resolve())
                except OSError:
                    return str(cand)
        else:
            # Env is often assembled on the host before the container venv exists.
            return str(cand)
    return None


def discover_task_experiment_python(
    *,
    env: dict[str, str] | None = None,
    task_env: dict[str, str] | None = None,
    require_exists: bool = True,
) -> str | None:
    """Find a task-local venv Python for experiment code (not the tool launcher).

    Priority:
    1. Explicit ``AI_SCIENTIST_EXPERIMENT_PYTHON`` / ``TASK_EXPERIMENT_PYTHON``
    2. ``*/-venv/bin`` (or ``.venv`` / ``venv``) entries from task PATH / env PATH

    When ``require_exists`` is False, task-venv PATH entries may be returned even if
    the binary is not present on the current host (typical when building container
    env before ``container_setup`` finishes, or from the host orchestrator).
    """
    sources: list[dict[str, str]] = []
    if env:
        sources.append(env)
    if task_env:
        sources.append(task_env)
        sources.append(runtime_dataset_env(task_env))

    for src in sources:
        for key in ("AI_SCIENTIST_EXPERIMENT_PYTHON", "TASK_EXPERIMENT_PYTHON"):
            raw = (src.get(key) or "").strip()
            if not raw:
                continue
            path = Path(raw).expanduser()
            if path.is_file() and os.access(path, os.X_OK):
                try:
                    return str(path.resolve())
                except OSError:
                    return str(path)
            if not require_exists and raw.startswith("/"):
                return str(path)

    path_blobs: list[str] = []
    for src in sources:
        for key in ("PATH", "ENV_IN_CONTAINER_PATH"):
            val = (src.get(key) or "").strip()
            if val:
                path_blobs.append(val)

    for blob in path_blobs:
        for part in blob.split(":"):
            if not part or any(m in part for m in _TOOL_PYTHON_PATH_MARKERS):
                continue
            bin_dir = Path(part)
            if not _path_looks_like_task_venv_bin(bin_dir):
                continue
            found = _python_from_bin_dir(bin_dir, require_exists=True)
            if found:
                return found
            if not require_exists:
                speculative = _python_from_bin_dir(bin_dir, require_exists=False)
                if speculative:
                    return speculative
    return None


def apply_aiscientist_writable_home(env: dict[str, str], run_root: Path) -> dict[str, str]:
    """Redirect HOME / pip user-site into the per-run workspace (writable in Docker)."""
    container_home = run_root / ".container-home"
    local_base = container_home / ".local"
    cache_home = container_home / ".cache"
    container_home.mkdir(parents=True, exist_ok=True)
    local_base.mkdir(parents=True, exist_ok=True)
    cache_home.mkdir(parents=True, exist_ok=True)
    (cache_home / "pip").mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(container_home)
    env["PYTHONUSERBASE"] = str(local_base)
    env.setdefault("XDG_CACHE_HOME", str(cache_home))
    env.setdefault("PIP_CACHE_DIR", str(cache_home / "pip"))
    return env


def ensure_aiscientist_experiment_env(
    env: dict[str, str],
    *,
    run_root: Path | None = None,
    task_env: dict[str, str] | None = None,
    task_dir: Path | None = None,
) -> dict[str, str]:
    """Wire writable HOME + task experiment Python for AI-Scientist BFTS runs.

    Generic across tasks: discovers ``/opt/*-venv`` (or similar) from task.env PATH
    without hard-coding task ids. No-op when nothing is discoverable.
    """
    merged = env.copy()
    resolved_task_env = task_env
    if resolved_task_env is None and task_dir is not None:
        env_file = Path(task_dir) / "task.env"
        if env_file.is_file():
            from path_alignment import load_task_env

            resolved_task_env = load_task_env(Path(task_dir))

    if run_root is not None:
        in_container = Path("/.dockerenv").exists()
        host_local = Path.home() / ".local"
        need_writable_home = in_container or not os.access(
            host_local if host_local.exists() else Path.home(), os.W_OK
        )
        if need_writable_home:
            merged = apply_aiscientist_writable_home(merged, Path(run_root))

    if resolved_task_env:
        task_runtime = runtime_dataset_env(resolved_task_env)
        task_path = (task_runtime.get("PATH") or "").strip()
        if task_path:
            tool_prefix = path_prefix_for("aiscientist")
            merged["PATH"] = merge_path_entries(
                tool_prefix, task_path, merged.get("PATH", "")
            )
        for key, value in task_runtime.items():
            if key == "PATH":
                continue
            merged.setdefault(key, value)

    experiment_python = discover_task_experiment_python(
        env=merged, task_env=resolved_task_env, require_exists=True
    )
    if not experiment_python:
        # Host-side / pre-setup: still inject the container venv path from task.env.
        experiment_python = discover_task_experiment_python(
            env=merged, task_env=resolved_task_env, require_exists=False
        )
    if experiment_python:
        merged["AI_SCIENTIST_EXPERIMENT_PYTHON"] = experiment_python
    return merged


def build_container_env(
    host_env: dict[str, str],
    *,
    agent_tool: str,
    run_root: Path | None = None,
    task_env: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env = host_env.copy()
    prefix = path_prefix_for(agent_tool)
    task_runtime = runtime_dataset_env(task_env) if task_env else {}
    task_path = (task_runtime.get("PATH") or "").strip()
    if prefix or task_path:
        # Keep tool launcher bins first, then task venv / dataset PATH, then host PATH.
        env["PATH"] = merge_path_entries(prefix, task_path, env.get("PATH", ""))

    scrub = scrub_base_url(host_env)
    if literature_scrub_enabled(host_env):
        env.setdefault("LITERATURE_SCRUB_BASE_URL", scrub)
    for key in (
        "CUSTOM_OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "API_BASE_URL",
    ):
        cur = (env.get(key) or "").strip()
        if (not cur) or ("umodelverse.ai" in cur) or _is_scrub_proxy_url(cur) or "127.0.0.1" in cur or "localhost" in cur:
            if _is_metering_proxy_url(cur):
                continue
            env[key] = scrub

    if run_root is not None:
        env["BENCHMARK_RUN_ROOT"] = str(run_root.resolve())
        if agent_tool == "evoscientist":
            data_dir = run_root / ".evoscientist"
            container_home = run_root / ".container-home"
            # langgraph dev writes pid/log under Path.home()/.config/evoscientist.
            # Host HOME is copied into api_env; must override (setdefault is not enough).
            env["HOME"] = str(container_home)
            env["XDG_CONFIG_HOME"] = str(run_root / ".xdg-config")
            env.setdefault("EVOSCIENTIST_DATA_DIR", str(data_dir))
            env.setdefault("EVOSCIENTIST_MEMORIES_DIR", str(data_dir / "memories"))
            env.setdefault("EVOSCIENTIST_WORKSPACE_DIR", str(run_root.resolve()))
            # Aligned Docker workdir: file tools and execute share real filesystem paths.
            env["EVOSCIENTIST_DANGEROUS_MODE"] = "true"
        elif agent_tool == "aris":
            container_home = run_root / ".container-home"
            container_home.mkdir(parents=True, exist_ok=True)
            env["HOME"] = str(container_home)
        elif agent_tool == "deepscientist":
            container_home = run_root / ".container-home"
            container_home.mkdir(parents=True, exist_ok=True)
            env["HOME"] = str(container_home)
        elif agent_tool == "researchclaw":
            container_home = run_root / ".container-home"
            container_home.mkdir(parents=True, exist_ok=True)
            # ARC experiment Docker mounts Path.home()/.cache/datasets → /workspace/data
            env["HOME"] = str(container_home)
            env["XDG_CACHE_HOME"] = str(container_home / ".cache")
        elif agent_tool == "airesearcher":
            # Host /home/<user> is not fully mounted; only nested bind mounts exist.
            # tiktoken / chromadb / huggingface write under ~/.cache → redirect HOME.
            container_home = run_root / ".container-home"
            container_home.mkdir(parents=True, exist_ok=True)
            (container_home / ".cache").mkdir(parents=True, exist_ok=True)
            env["HOME"] = str(container_home)
            env["XDG_CACHE_HOME"] = str(container_home / ".cache")
            env["XDG_CONFIG_HOME"] = str(run_root / ".xdg-config")
            (run_root / ".xdg-config").mkdir(parents=True, exist_ok=True)
            # Keep Playwright browsers on the shared host cache (mounted above),
            # not under the empty per-run HOME/.cache.
            playwright_browsers = Path.home() / ".cache" / "ms-playwright"
            if playwright_browsers.is_dir():
                env["PLAYWRIGHT_BROWSERS_PATH"] = str(playwright_browsers)
        elif agent_tool == "aiscientist":
            # Host HOME is not fully writable in the sandbox; pip --user must land
            # under the per-run workspace. Task venvs on PATH are discovered below.
            env = apply_aiscientist_writable_home(env, run_root)
        # Route LLM traffic through per-run metering proxy (tokens + cost).
        env = apply_run_metering_to_env(env, run_root=run_root, for_container=True)
    if task_runtime:
        for key, value in task_runtime.items():
            if key == "PATH":
                continue
            env.setdefault(key, value)
    if agent_tool == "aiscientist":
        experiment_python = discover_task_experiment_python(
            env=env, task_env=task_env, require_exists=False
        )
        if experiment_python:
            env["AI_SCIENTIST_EXPERIMENT_PYTHON"] = experiment_python
    if extra:
        env.update(extra)
        # Re-apply metering after extras so accidental base_url overrides still meter.
        if run_root is not None and not any(
            _is_metering_proxy_url((env.get(k) or ""))
            for k in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "API_BASE_URL")
        ):
            env = apply_run_metering_to_env(env, run_root=run_root, for_container=True)
        if agent_tool == "aiscientist" and not (env.get("AI_SCIENTIST_EXPERIMENT_PYTHON") or "").strip():
            experiment_python = discover_task_experiment_python(
                env=env, task_env=task_env, require_exists=False
            )
            if experiment_python:
                env["AI_SCIENTIST_EXPERIMENT_PYTHON"] = experiment_python
    return env


def aligned_extra_volume_mount(spec: str) -> tuple[Path, Path, str]:
    """Parse EXTRA_VOLUME host:container[:mode] and return aligned host:host mount."""
    parts = spec.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid extra volume spec: {spec!r}")
    host_path = expand_path(parts[0])
    mode = parts[2] if len(parts) > 2 else "ro"
    return host_path, host_path, mode


def remap_container_env_value(env_name: str, value: str, volume_map: dict[str, str]) -> str:
    """Map legacy container-only paths (e.g. /shared/pairsmell) to aligned host paths."""
    return align_path(value, volume_map)


def launch_agent(
    *,
    container_id: str,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    append: bool = False,
    timeout: int | None = None,
) -> int:
    """Run a long-lived agent process inside the container, streaming output to log_path."""
    if str(INTEGRATIONS_ROOT) not in sys.path:
        sys.path.insert(0, str(INTEGRATIONS_ROOT))
    from run_metering import start_run_timer, stop_run_timer

    run_root_raw = (env.get(BENCHMARK_RUN_ROOT_ENV) or "").strip()
    run_root = Path(run_root_raw).resolve() if run_root_raw else None
    if run_root is not None and run_root.is_dir():
        start_run_timer(run_root, phase="agent")

    cwd_str = str(cwd.resolve())
    # Skip keys that are not valid bash identifiers (e.g. legacy SHIP-REPO_HOME).
    # Docker ``-e`` can still set them; ``export`` in ``bash -lc`` cannot.
    env_exports = " ".join(
        f"export {key}={shlex.quote(value)};"
        for key, value in sorted(env.items())
        if value is not None and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key)
    )
    quoted_cmd = " ".join(shlex.quote(part) for part in cmd)
    shell_cmd = f"{env_exports} cd {shlex.quote(cwd_str)} && exec {quoted_cmd}"

    docker_cmd = [
        "docker",
        "exec",
        "-i",
        "-w",
        cwd_str,
        container_id,
        "bash",
        "-lc",
        shell_cmd,
    ]

    mode = "a" if append else "w"
    returncode = 1
    try:
        with log_path.open(mode, encoding="utf-8") as log_file:
            proc = subprocess.run(
                docker_cmd,
                check=False,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        returncode = int(proc.returncode)
    finally:
        if run_root is not None and run_root.is_dir():
            stop_run_timer(run_root, phase="agent", returncode=returncode)
    return returncode


def preflight_scrub_proxy(
    container_id: str,
    *,
    base_url: str | None = None,
    timeout_sec: int = 10,
) -> tuple[bool, str]:
    """Verify literature_scrub is reachable, or skip when scrubbing is disabled."""
    if not literature_scrub_enabled():
        return True, "literature scrub disabled (passthrough; year/target filters off)"
    health_url = (base_url or scrub_base_url()).rstrip("/")
    if health_url.endswith("/v1"):
        health_url = health_url[: -len("/v1")]
    health_url = f"{health_url}/health"
    probe = (
        "import urllib.request,sys;"
        f"urllib.request.urlopen({health_url!r}, timeout={max(3, timeout_sec - 2)});"
        "print('ok')"
    )
    try:
        proc = subprocess.run(
            ["docker", "exec", container_id, "python3", "-c", probe],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"literature_scrub preflight timed out ({health_url})"
    except OSError as exc:
        return False, f"literature_scrub preflight failed: {exc}"

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        hint = (
            " Start the proxy on the host (BIND=0.0.0.0) with "
            "ai_scientist_benchmark/literature_scrub/run_proxy.sh"
        )
        err = detail[-1] if detail else f"exit {proc.returncode}"
        return False, f"literature_scrub unreachable from container at {health_url}: {err}.{hint}"
    return True, f"literature_scrub OK ({health_url})"


def preflight_python(container_id: str, cwd: Path, *, timeout_sec: int = 60) -> tuple[bool, str]:
    cwd_str = str(cwd.resolve())
    try:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                "-w",
                cwd_str,
                container_id,
                "python3",
                "--version",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "python3 preflight timed out"
    except OSError as exc:
        return False, f"python3 preflight failed to start: {exc}"

    version = (proc.stdout or proc.stderr or "").strip().splitlines()
    if proc.returncode != 0 or not version:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, f"python3 preflight exit {proc.returncode}: {detail}"
    return True, f"container python OK ({version[0]})"


def _container_node_major(version_line: str) -> int | None:
    text = version_line.strip()
    if text.startswith("v"):
        text = text[1:]
    major = text.split(".", 1)[0]
    return int(major) if major.isdigit() else None


def preflight_node(
    container_id: str,
    *,
    min_major: int = 18,
    timeout_sec: int = 30,
) -> tuple[bool, str]:
    """Verify Node.js is available inside the agent container (required for in-container DS)."""
    try:
        proc = subprocess.run(
            ["docker", "exec", container_id, "bash", "-lc", "node --version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "node preflight timed out"
    except OSError as exc:
        return False, f"node preflight failed to start: {exc}"
    version = (proc.stdout or proc.stderr or "").strip().splitlines()
    if proc.returncode != 0 or not version:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, f"node missing in container (required for in-container DeepScientist): {detail}"
    major = _container_node_major(version[0])
    if major is None or major < min_major:
        return False, f"node {version[0]} is too old (need >= v{min_major})"
    return True, f"container node OK ({version[0]})"


def ensure_container_node(
    container_id: str,
    *,
    min_major: int = 18,
    timeout_sec: int = 600,
) -> tuple[bool, str]:
    """Install or upgrade Node.js inside the container when host bind-mount is incompatible."""
    ok, msg = preflight_node(container_id, min_major=min_major, timeout_sec=30)
    if ok:
        return ok, msg

    # Ubuntu's nodejs leaves libnode-dev/libnode72; NodeSource nodejs conflicts on
    # /usr/include/node/* unless those packages are purged first.
    install_script = f"""set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if command -v node >/dev/null 2>&1; then
  major=$(node -p "process.versions.node.split('.')[0]")
  if [ "$major" -ge {min_major} ]; then
    node --version
    exit 0
  fi
fi
apt-get remove -y --purge nodejs npm libnode-dev libnode72 >/dev/null 2>&1 || true
apt-get autoremove -y >/dev/null 2>&1 || true
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get remove -y --purge nodejs npm libnode-dev libnode72 >/dev/null 2>&1 || true
apt-get install -y nodejs
node --version
"""
    try:
        proc = subprocess.run(
            ["docker", "exec", "-u", "0", container_id, "bash", "-lc", install_script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "node install timed out in container"
    except OSError as exc:
        return False, f"node install failed to start: {exc}"

    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    if proc.returncode != 0:
        tail = detail[-1] if detail else proc.returncode
        return False, f"node install failed in container: {tail}"
    return preflight_node(container_id, min_major=min_major, timeout_sec=30)


def preflight_path(
    container_id: str,
    path: str,
    *,
    cwd: Path | None = None,
    must_be_dir: bool = False,
    timeout_sec: int = 60,
) -> tuple[bool, str]:
    """Verify a host-aligned path exists inside the container."""
    flag = "-d" if must_be_dir else "-f"
    shell_probe = f"test {flag} {shlex.quote(path)} && echo {shlex.quote(path)}"
    cmd = ["docker", "exec"]
    if cwd is not None:
        cmd.extend(["-w", str(cwd.resolve())])
    cmd.extend([container_id, "bash", "-lc", shell_probe])
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"{path} preflight timed out"
    except OSError as exc:
        return False, f"{path} preflight failed: {exc}"

    resolved = (proc.stdout or "").strip()
    if proc.returncode != 0 or not resolved:
        kind = "directory" if must_be_dir else "file"
        return False, f"{path} not found as mounted {kind} in container"
    return True, f"{path} OK ({resolved})"


def preflight_python_import(
    container_id: str,
    *,
    python_bin: str,
    import_stmt: str,
    cwd: Path | None = None,
    timeout_sec: int = 120,
) -> tuple[bool, str]:
    cmd = ["docker", "exec"]
    if cwd is not None:
        cmd.extend(["-w", str(cwd.resolve())])
    cmd.extend([container_id, python_bin, "-c", import_stmt])
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"{python_bin} import preflight timed out"
    except OSError as exc:
        return False, f"{python_bin} import preflight failed: {exc}"

    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    if proc.returncode != 0:
        err = detail[-1] if detail else f"exit {proc.returncode}"
        return False, f"{python_bin} import check failed: {err}"
    return True, f"{python_bin} import OK"


def preflight_runtime_mounts(
    container_id: str,
    agent_tool: str,
    *,
    cwd: Path | None = None,
) -> tuple[bool, list[str]]:
    """Verify declared runtime mounts are visible inside the container."""
    issues: list[str] = []
    for host_path, container_path, _mode in runtime_mounts(agent_tool):
        ok, msg = preflight_path(
            container_id,
            str(container_path),
            cwd=cwd,
            must_be_dir=True,
        )
        if not ok:
            issues.append(f"{host_path} -> {container_path}: {msg}")
    return not issues, issues


def preflight_binary(
    container_id: str,
    binary: str,
    *,
    cwd: Path | None = None,
    timeout_sec: int = 60,
) -> tuple[bool, str]:
    cmd = ["docker", "exec"]
    if cwd is not None:
        cmd.extend(["-w", str(cwd.resolve())])
    if "/" in binary:
        # .py launchers are usually not chmod +x; only require readability.
        if binary.endswith((".py", ".sh")):
            shell_probe = f'test -f {shlex.quote(binary)} && echo {shlex.quote(binary)}'
        else:
            shell_probe = (
                f'(test -x {shlex.quote(binary)} || test -f {shlex.quote(binary)}) '
                f"&& echo {shlex.quote(binary)}"
            )
    else:
        shell_probe = f"command -v {shlex.quote(binary)}"
    cmd.extend([container_id, "bash", "-lc", shell_probe])
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"{binary} preflight timed out"
    except OSError as exc:
        return False, f"{binary} preflight failed: {exc}"

    path = (proc.stdout or "").strip()
    if proc.returncode != 0 or not path:
        return False, f"{binary} not found in container PATH"
    return True, f"{binary} OK ({path})"


def resolve_binary(agent_tool: str, name: str, host_env: dict[str, str] | None = None) -> str:
    env = host_env or os.environ
    env_key = f"{agent_tool.upper()}_BIN"
    for candidate in (env.get(env_key), env.get(f"{name.upper()}_BIN"), shutil.which(name)):
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser().resolve())
    raise FileNotFoundError(f"Could not find `{name}` for agent tool {agent_tool!r}")
