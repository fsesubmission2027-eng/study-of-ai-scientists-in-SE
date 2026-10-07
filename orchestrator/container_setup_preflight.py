"""Optional per-task system-package setup for TaskSandbox containers.

Convention (generic across all tasks / agent tools):
  If ``<task_dir>/seeds/container_setup.sh`` exists, run it as root once after the
  container starts (same lifecycle as Defects4J preflight).

Opt out with ``CONTAINER_SETUP=false`` in ``task.env``.
Seeds are typically mounted read-only — invoke via ``bash script``, do not chmod.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from path_alignment import aligned_paths_enabled


def container_setup_script(task_dir: Path) -> Path:
    return (task_dir / "seeds" / "container_setup.sh").resolve()


def task_env_needs_container_setup(task_dir: Path, env: dict[str, str] | None = None) -> bool:
    env = env or {}
    flag = env.get("CONTAINER_SETUP", "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    return container_setup_script(task_dir).is_file()


def _script_path_in_container(task_dir: Path, env: dict[str, str]) -> str:
    script = container_setup_script(task_dir)
    if aligned_paths_enabled(env):
        return str(script)
    return "/task/seeds/container_setup.sh"


def _exec_root(
    container_id: str,
    command: str,
    *,
    timeout_sec: int = 1800,
    env_vars: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    cmd = ["docker", "exec", "-u", "0"]
    for key, value in (env_vars or {}).items():
        if value:
            cmd.extend(["-e", f"{key}={value}"])
    cmd.extend(
        [
            container_id,
            "bash",
            "-lc",
            command,
        ]
    )
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _kaggle_env_for_setup(env: dict[str, str]) -> dict[str, str]:
    """Forward Kaggle auth into container_setup (docker exec does not inherit host env)."""
    out: dict[str, str] = {}
    token = (env.get("KAGGLE_API_TOKEN") or "").strip()
    if not token:
        try:
            from benchmark_credentials import apply_benchmark_credentials

            token = (apply_benchmark_credentials(env).get("KAGGLE_API_TOKEN") or "").strip()
        except Exception:
            token = ""
    if not token:
        access = Path.home() / ".kaggle" / "access_token"
        if access.is_file():
            try:
                token = access.read_text(encoding="utf-8").strip()
            except OSError:
                token = ""
    if token:
        out["KAGGLE_API_TOKEN"] = token
    config_dir = (env.get("KAGGLE_CONFIG_DIR") or env.get("ENV_IN_CONTAINER_KAGGLE_CONFIG_DIR") or "").strip()
    if config_dir:
        out["KAGGLE_CONFIG_DIR"] = config_dir
    return out


def run_container_setup(
    container_id: str,
    task_dir: Path,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Execute seeds/container_setup.sh as root inside the container."""
    env = env or {}
    host_script = container_setup_script(task_dir)
    if not host_script.is_file():
        return True, "container setup not configured for this task"

    script_path = _script_path_in_container(task_dir, env)
    # seeds/ is usually :ro — never chmod; bash can run without +x.
    command = (
        "set -euo pipefail; "
        f'test -f "{script_path}" || {{ echo "missing container_setup.sh at {script_path}" >&2; exit 1; }}; '
        f'bash "{script_path}"'
    )
    code, stdout, stderr = _exec_root(
        container_id,
        command,
        timeout_sec=1800,
        env_vars=_kaggle_env_for_setup(env),
    )
    combined = f"{stdout}\n{stderr}".strip()
    if code != 0:
        detail = [line.strip() for line in combined.splitlines() if line.strip()]
        # CMake prints `cmake for <target>` on stderr after a successful
        # configure; the real failure is often a later silent test. Keep a
        # short tail plus the exit code so preflight is diagnosable.
        tail = " | ".join(detail[-8:]) if detail else f"exit {code}"
        return False, f"container_setup.sh failed (exit {code}): {tail}"

    summary = next(
        (
            line.strip()
            for line in combined.splitlines()
            if line.strip().startswith("[container_setup]")
        ),
        "container_setup.sh OK",
    )
    return True, summary


def ensure_container_setup_for_task(
    container_id: str,
    task_dir: Path,
    env: dict[str, str],
) -> tuple[bool, str]:
    if not task_env_needs_container_setup(task_dir, env):
        return True, "container setup not configured for this task"
    return run_container_setup(container_id, task_dir, env)
