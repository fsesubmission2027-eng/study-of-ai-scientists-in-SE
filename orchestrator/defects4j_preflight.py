"""Defects4J + Java 11 preflight for benchmark TaskSandbox containers."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_INTEGRATIONS = Path(__file__).resolve().parents[1] / "integrations"
if str(_INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(_INTEGRATIONS))

from path_alignment import (
    AGENT_DATASET_CANDIDATE,
    agent_dataset_access_path,
    align_path,
    aligned_paths_enabled,
    build_volume_remap,
    runtime_dataset_env,
)


def task_env_needs_defects4j(env: dict[str, str]) -> bool:
    """Return True when task.env mounts or configures Defects4J."""
    if env.get("ENV_IN_CONTAINER_DEFECTS4J_HOME", "").strip():
        return True
    for key, value in env.items():
        if key.startswith("EXTRA_VOLUME_") and "defects4j" in value.lower():
            return True
    return False


def defects4j_home_from_task_env(
    env: dict[str, str],
    *,
    run_root: Path | None = None,
) -> str:
    """Resolve DEFECTS4J_HOME as seen inside the agent container."""
    raw = env.get("ENV_IN_CONTAINER_DEFECTS4J_HOME", "").strip() or "/shared/defects4j"
    if aligned_paths_enabled(env):
        if run_root is not None:
            # Aligned sandbox bind-mounts corpora under run_root/dataset_candidate/<name>/,
            # not at the host shared_datasets path (which is absent inside the container).
            return str((run_root / agent_dataset_access_path("defects4j")).resolve())
        # Fallback for callers without run_root: workspace-relative (requires matching cwd).
        return agent_dataset_access_path("defects4j")
    return raw


def _absolute_agent_env_paths(value: str, run_root: Path) -> str:
    parts: list[str] = []
    prefix = f"{AGENT_DATASET_CANDIDATE}/"
    for item in value.split(":"):
        if item.startswith(prefix):
            parts.append(str((run_root / item).resolve()))
        else:
            parts.append(item)
    return ":".join(parts)


def perl5lib_from_task_env(
    env: dict[str, str],
    *,
    defects4j_home: str,
    run_root: Path | None = None,
) -> str:
    raw = runtime_dataset_env(env).get("PERL5LIB", "").strip()
    if not raw:
        raw = (
            f"{defects4j_home}/perl-local/lib/perl5:"
            f"{defects4j_home}/perl-local/lib/perl5/x86_64-linux-gnu-thread-multi"
        )
    elif run_root is not None and aligned_paths_enabled(env):
        raw = _absolute_agent_env_paths(raw, run_root)
    return raw


def java_home_from_task_env(env: dict[str, str]) -> str:
    raw = (
        env.get("ENV_IN_CONTAINER_JAVA_HOME", "").strip()
        or os.environ.get("BENCHMARK_JAVA_HOME", "").strip()
        or os.environ.get("ARIS_BENCHMARK_JAVA_HOME", "").strip()
        or "/usr/lib/jvm/java-11-openjdk-amd64"
    )
    if aligned_paths_enabled(env):
        return align_path(raw, build_volume_remap(env))
    return raw


def _exec_in_container(
    container_id: str,
    command: str,
    *,
    user: str = "agent",
    workdir: str = "/workspace",
    timeout_sec: int = 600,
) -> tuple[int, str, str]:
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "-u",
            user,
            "-w",
            workdir,
            container_id,
            "bash",
            "-lc",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def setup_defects4j_container(
    container_id: str,
    *,
    java_home: str | None = None,
    defects4j_home: str | None = None,
    task_env: dict[str, str] | None = None,
    run_root: Path | None = None,
) -> tuple[bool, str]:
    """Install Defects4J prerequisites in the benchmark container and verify Java 11 + svn."""
    env = task_env or {}
    java_home = java_home or java_home_from_task_env(env)
    defects4j_home = defects4j_home or defects4j_home_from_task_env(env, run_root=run_root)
    perl5lib = perl5lib_from_task_env(env, defects4j_home=defects4j_home, run_root=run_root)
    messages: list[str] = []

    code, stdout, stderr = _exec_in_container(
        container_id,
        "command -v svn >/dev/null 2>&1 || "
        "(export DEBIAN_FRONTEND=noninteractive && "
        "apt-get update -qq && apt-get install -y -qq subversion)",
        user="root",
        timeout_sec=900,
    )
    if code != 0:
        detail = (stderr or stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit {code}"
        return False, f"failed to ensure subversion in container: {tail}"
    messages.append("svn OK")

    java_setup_cmd = textwrap.dedent(
        f"""\
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive
        export JAVA_HOME="{java_home}"
        if [ ! -x "$JAVA_HOME/bin/javac" ]; then
          apt-get update -qq
          apt-get install -y -qq openjdk-11-jdk
        fi
        test -x "$JAVA_HOME/bin/javac"
        "$JAVA_HOME/bin/javac" --version
        """
    )
    code, stdout, stderr = _exec_in_container(
        container_id,
        java_setup_cmd,
        user="root",
        timeout_sec=900,
    )
    if code != 0:
        detail = (stderr or stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit {code}"
        return False, f"failed to ensure OpenJDK 11 javac in container: {tail}"
    javac_line = next(
        (line.strip() for line in (stderr + stdout).splitlines() if "javac" in line.lower()),
        "javac OK",
    )
    messages.append(javac_line)

    verify_cmd = textwrap.dedent(
        f"""\
        set -euo pipefail
        export DEFECTS4J_HOME="{defects4j_home}"
        export JAVA_HOME="{java_home}"
        export PERL5LIB="{perl5lib}"
        export PATH="$JAVA_HOME/bin:$DEFECTS4J_HOME/framework/bin:$PATH"
        command -v svn
        "$JAVA_HOME/bin/java" -version
        "$JAVA_HOME/bin/javac" --release 11 -version 2>&1 | head -1
        "$DEFECTS4J_HOME/framework/bin/defects4j" info -p Lang | head -5
        """
    )
    code, stdout, stderr = _exec_in_container(container_id, verify_cmd, timeout_sec=120)
    if code != 0:
        detail = (stderr or stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit {code}"
        return False, f"Defects4J preflight failed: {tail}"

    version_line = next(
        (line.strip() for line in (stderr + stdout).splitlines() if "version" in line.lower()),
        "java OK",
    )
    messages.append(version_line)
    if "defects4j" in stdout.lower() or "lang" in stdout.lower():
        messages.append("defects4j info -p Lang OK")
    return True, "; ".join(messages)


def ensure_defects4j_for_task_env(
    container_id: str,
    env: dict[str, str],
    *,
    run_root: Path | None = None,
) -> tuple[bool, str]:
    """Run Defects4J preflight when task.env indicates Defects4J is in use."""
    if not task_env_needs_defects4j(env):
        return True, "Defects4J not configured for this task"
    return setup_defects4j_container(
        container_id,
        java_home=java_home_from_task_env(env),
        defects4j_home=defects4j_home_from_task_env(env, run_root=run_root),
        task_env=env,
        run_root=run_root,
    )
