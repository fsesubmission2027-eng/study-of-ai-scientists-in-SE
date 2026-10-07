"""Align legacy container mount paths with host-aligned TaskSandbox paths.

Agent tools run inside Docker with ``AGENT_ALIGNED_PATHS`` (default on): datasets are
bind-mounted under ``run_root/dataset_candidate/<name>/`` (zero-copy, workspace-visible)
and ``ENV_IN_CONTAINER_*`` values are remapped to workspace-relative access paths.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path

from benchmark_task_config import TaskBenchmarkConfig

AGENT_DATASET_CANDIDATE = "dataset_candidate"

# EXTRA_VOLUME mount basename -> runtime env var for experiment scripts (cwd = run root).
_VOLUME_ENV_VARS: dict[str, str] = {
    "pairsmell": "PAIRSMELL_HOME",
    "defects4j": "DEFECTS4J_HOME",
}


def volume_env_var_name(mount_basename: str) -> str:
    """Bash-safe ``*_HOME`` env var for a dataset mount basename.

    Mount dirs often contain hyphens (``ship-repo``, ``llm-agents-study``). Using
    ``name.upper()`` alone yields invalid shell identifiers like ``SHIP-REPO_HOME``
    that break ``export`` in ``bash -lc``. Always sanitize non-alnum to ``_``.
    """
    name = (mount_basename or "").strip()
    if not name:
        return "DATASET_HOME"
    if name in _VOLUME_ENV_VARS:
        return _VOLUME_ENV_VARS[name]
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if not sanitized:
        sanitized = "DATASET"
    if sanitized[0].isdigit():
        sanitized = f"DS_{sanitized}"
    return f"{sanitized}_HOME"

AGENT_DATASET_ACCESS_RULE = (
    "For `ls` / `read_file` / `write_file`: use **only** workspace-relative paths under "
    f"`{AGENT_DATASET_CANDIDATE}/<dataset_name>/` (e.g. `{AGENT_DATASET_CANDIDATE}/pairsmell/`). "
    "Never pass absolute host paths or legacy `/shared/*` paths to file tools."
)


def load_task_env(task_dir: Path) -> dict[str, str]:
    env_path = task_dir / "task.env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def aligned_paths_enabled(
    task_env: dict[str, str] | None = None,
    *,
    agent_tool: str | None = None,
) -> bool:
    env = task_env or {}
    raw = env.get("AGENT_ALIGNED_PATHS", "true").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(agent_tool) or raw in {"1", "true", "yes", "on"}


def build_volume_remap(task_env: dict[str, str]) -> dict[str, str]:
    """Map legacy container mount points to aligned host paths."""
    remap: dict[str, str] = {}
    for key in sorted(task_env):
        if not key.startswith("EXTRA_VOLUME_"):
            continue
        spec = task_env[key].strip()
        if not spec:
            continue
        parts = spec.split(":")
        if len(parts) < 2:
            continue
        host_path = str(Path(parts[0]).expanduser().resolve())
        container_mount = parts[1]
        remap[container_mount] = host_path
    return remap


def align_path(value: str, volume_remap: dict[str, str]) -> str:
    if not value or not volume_remap:
        return value
    if value in volume_remap:
        return volume_remap[value]
    for container_path, host_path in sorted(volume_remap.items(), key=lambda kv: -len(kv[0])):
        prefix = container_path + "/"
        if value.startswith(prefix):
            return host_path + value[len(container_path) :]
    return value


def _legacy_container_mounts(task_env: dict[str, str]) -> list[tuple[str, str]]:
    mounts: list[tuple[str, str]] = []
    for key in sorted(task_env):
        if not key.startswith("EXTRA_VOLUME_"):
            continue
        spec = task_env[key].strip()
        if not spec:
            continue
        parts = spec.split(":")
        if len(parts) < 2:
            continue
        container_mount = parts[1]
        name = Path(container_mount).name
        mounts.append((container_mount, agent_dataset_access_path(name)))
    return mounts


def remap_container_path_to_agent_access(value: str, task_env: dict[str, str]) -> str:
    """Map legacy in-container mount paths to workspace-relative dataset access paths."""
    if not value:
        return value
    mounts = _legacy_container_mounts(task_env)
    if not mounts:
        return value

    def remap_one(item: str) -> str:
        for container_mount, agent_path in sorted(mounts, key=lambda kv: -len(kv[0])):
            if item == container_mount:
                return agent_path
            prefix = container_mount + "/"
            if item.startswith(prefix):
                return agent_path + item[len(container_mount) :]
        return item

    if ":" in value and any(
        value == mount or value.startswith(mount + "/") or value.startswith(mount + ":")
        for mount, _ in mounts
    ):
        return ":".join(remap_one(part) for part in value.split(":"))
    return remap_one(value)


def align_text_paths(text: str, volume_remap: dict[str, str]) -> str:
    if not text or not volume_remap:
        return text
    out = text
    for container_path, host_path in sorted(volume_remap.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(container_path, host_path)
    return out


def agent_dataset_access_path(mount_basename: str) -> str:
    return f"{AGENT_DATASET_CANDIDATE}/{mount_basename}"


def agent_dataset_access_paths(task_env: dict[str, str]) -> dict[str, str]:
    """Workspace-relative dataset roots (for agent file tools and python3 with cwd=run_root)."""
    if not aligned_paths_enabled(task_env):
        return {}
    paths: dict[str, str] = {}
    for name, _target in dataset_symlink_targets(task_env):
        paths[volume_env_var_name(name)] = agent_dataset_access_path(name)
    return paths


def runtime_dataset_env(task_env: dict[str, str]) -> dict[str, str]:
    """Container env for agent processes: *_HOME vars use workspace-relative access paths."""
    env = dataset_env_from_task_env(task_env)
    env.update(agent_dataset_access_paths(task_env))
    return env


def rewrite_agent_dataset_text(text: str, task_env: dict[str, str]) -> str:
    """Replace host/legacy container dataset paths with workspace-relative access paths."""
    if not text or not aligned_paths_enabled(task_env):
        return text
    remap = build_volume_remap(task_env)
    out = text
    for container_path, host_path in sorted(remap.items(), key=lambda kv: -len(kv[0])):
        name = Path(container_path).name
        agent_path = agent_dataset_access_path(name)
        out = out.replace(host_path, agent_path)
        out = out.replace(container_path, agent_path)
    return out


def dataset_env_from_task_env(task_env: dict[str, str]) -> dict[str, str]:
    """Resolved ENV_IN_CONTAINER_* values for injection into agent processes."""
    if not aligned_paths_enabled(task_env):
        out: dict[str, str] = {}
        for key, value in task_env.items():
            if key.startswith("ENV_IN_CONTAINER_"):
                out[key[len("ENV_IN_CONTAINER_") :]] = value
        return out

    out = {}
    for key, value in task_env.items():
        if not key.startswith("ENV_IN_CONTAINER_"):
            continue
        env_name = key[len("ENV_IN_CONTAINER_") :]
        out[env_name] = remap_container_path_to_agent_access(value, task_env)
    return out


def align_task_benchmark_config(
    cfg: TaskBenchmarkConfig,
    task_env: dict[str, str],
) -> TaskBenchmarkConfig:
    if not aligned_paths_enabled(task_env):
        return cfg
    agent_paths = agent_dataset_access_paths(task_env)
    if not agent_paths:
        return cfg
    merged_env = dict(cfg.dataset_env)
    merged_env.update(agent_paths)
    return replace(
        cfg,
        pilot_data_note=rewrite_agent_dataset_text(cfg.pilot_data_note, task_env),
        benchmark_rules=[
            *([AGENT_DATASET_ACCESS_RULE] if agent_paths else []),
            *[rewrite_agent_dataset_text(rule, task_env) for rule in cfg.benchmark_rules],
        ],
        dataset_env=merged_env,
    )


def load_aligned_task_benchmark_config(task_dir: Path, task_env: dict[str, str] | None = None) -> TaskBenchmarkConfig:
    from benchmark_task_config import load_task_benchmark_config

    env = task_env if task_env is not None else load_task_env(task_dir)
    cfg = load_task_benchmark_config(task_dir)
    return align_task_benchmark_config(cfg, env)


def align_dataset_paths_document(data: dict, volume_remap: dict[str, str]) -> dict:
    """Rewrite dataset_paths.json: agent-visible paths are workspace-relative only."""
    if not volume_remap:
        return data

    out = copy.deepcopy(data)
    agent_access: dict[str, str] = {}

    for container_path, _host_path in sorted(volume_remap.items()):
        name = Path(container_path).name
        if not name:
            continue
        agent_path = agent_dataset_access_path(name)
        agent_access[volume_env_var_name(name)] = agent_path
        out[f"{name}_home_active"] = agent_path
        if name == "defects4j":
            out["defects4j_cli"] = f"{agent_path}/framework/bin/defects4j"

    for key in list(out.keys()):
        if key.endswith("_host") or key.endswith("_container"):
            del out[key]

    if "path_pattern" in out and "PAIRSMELL_HOME" in agent_access:
        out["path_pattern"] = f"{agent_access['PAIRSMELL_HOME']}/<project>/<snapshot>/entities.txt"

    dataset_env = out.get("dataset_env")
    if not isinstance(dataset_env, dict):
        dataset_env = {}
    merged_env = {str(k): str(v) for k, v in dataset_env.items()}
    merged_env.update(agent_access)
    for key, value in list(merged_env.items()):
        if key.endswith("_HOME"):
            merged_env[key] = agent_access.get(key, value)
    out["dataset_env"] = merged_env

    if agent_access:
        out["agent_dataset_access"] = agent_access
        out["workspace_symlink"] = next(iter(agent_access.values()))

    out["path_resolution"] = {
        "mode": "workspace_relative_access",
        "for_ls_read_file": f"Only `{AGENT_DATASET_CANDIDATE}/<dataset_name>/` inside this workspace.",
        "for_python_scripts": (
            "Use os.environ[*_HOME] (set to workspace-relative dataset_candidate/<name>/)."
        ),
        "forbidden_for_file_tools": [
            "absolute host paths outside the workspace",
            "legacy /shared/* container paths",
        ],
    }
    return out


def align_dataset_paths_file(path: Path, task_env: dict[str, str]) -> bool:
    if not path.is_file() or not aligned_paths_enabled(task_env):
        return False
    remap = build_volume_remap(task_env)
    if not remap:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    aligned = align_dataset_paths_document(data, remap)
    path.write_text(json.dumps(aligned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def dataset_symlink_targets(task_env: dict[str, str]) -> list[tuple[str, Path]]:
    """Map symlink basename under dataset_candidate/ to aligned host dataset roots."""
    if not aligned_paths_enabled(task_env):
        return []
    remap = build_volume_remap(task_env)
    targets: list[tuple[str, Path]] = []
    for container_path, host_path in sorted(remap.items()):
        name = Path(container_path).name
        if not name:
            continue
        targets.append((name, Path(host_path)))
    return targets


def prepare_dataset_mount_point(agent_mount: Path) -> None:
    """Prepare an empty host directory for Docker bind-mounting a dataset at this workspace path.

    Nested bind mounts (dataset inside an already bind-mounted workspace) require the
    mount-point directory to exist on the host before ``docker run``.
    """
    agent_mount.parent.mkdir(parents=True, exist_ok=True)
    if agent_mount.is_symlink():
        agent_mount.unlink()
    elif agent_mount.is_file():
        agent_mount.unlink()
    agent_mount.mkdir(exist_ok=True)


def ensure_dataset_symlinks(run_root: Path, task_env: dict[str, str]) -> list[str]:
    """Prepare dataset_candidate layout for workspace-relative access (bind mounts, not symlinks).

    Symlinks break EvoScientist/deepagents file tools: ``Path.resolve()`` follows the link
    and rejects paths outside the run root. Datasets are bind-mounted at
    ``dataset_candidate/<name>/`` when the sandbox starts with ``run_root``.
    """
    created: list[str] = []
    dest_base = run_root / AGENT_DATASET_CANDIDATE
    dest_base.mkdir(parents=True, exist_ok=True)
    for name, target in dataset_symlink_targets(task_env):
        if not target.is_dir():
            continue
        agent_mount = dest_base / name
        prepare_dataset_mount_point(agent_mount)
        created.append(f"{AGENT_DATASET_CANDIDATE}/{name} (bind mount -> {target})")
    if agent_dataset_access_paths(task_env):
        _write_mount_status(run_root, task_env, created)
    return created


def _write_mount_status(run_root: Path, task_env: dict[str, str], symlinks: list[str]) -> None:
    status_path = run_root / "dataset_candidate" / "MOUNT_STATUS.json"
    agent_access = agent_dataset_access_paths(task_env)
    payload = {
        "mode": "workspace_relative_dataset_access",
        "note": (
            f"Use `ls`/`read_file` only on `{AGENT_DATASET_CANDIDATE}/<name>/` paths below. "
            "Do not use absolute host paths with file tools."
        ),
        "agent_dataset_access": agent_access,
        "for_ls_and_read_file": sorted(agent_access.values()),
    }
    status_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def align_run_dataset_paths(run_root: Path, task_env: dict[str, str]) -> bool:
    aligned = align_dataset_paths_file(run_root / "dataset_candidate" / "dataset_paths.json", task_env)
    ensure_dataset_symlinks(run_root, task_env)
    return aligned


def sync_arc_dataset_cache(run_root: Path, task_env: dict[str, str]) -> list[str]:
    """Prepare per-run HOME/.cache/datasets/<name>/ mount points for ARC.

    AutoResearchClaw's experiment Docker mounts ``Path.home()/.cache/datasets``
    to the inner container as ``/workspace/data``. Empty directories are created
    here so TaskSandbox (or a host bind) can mount EXTRA_VOLUME_* corpora at
    those paths — **symlinks do not work**, because the inner Docker would see
    broken host-path links.
    """
    prepared: list[str] = []
    cache = run_root / ".container-home" / ".cache" / "datasets"
    cache.mkdir(parents=True, exist_ok=True)
    for name, target in dataset_symlink_targets(task_env):
        if not target.is_dir():
            continue
        mount_point = cache / name
        prepare_dataset_mount_point(mount_point)
        prepared.append(
            f".container-home/.cache/datasets/{name} (bind mount -> {target})"
        )
    return prepared


def arc_dataset_cache_mounts(
    run_root: Path, task_env: dict[str, str]
) -> list[tuple[Path, Path, str]]:
    """Host→run-root mounts so ARC HOME/.cache/datasets/<name> is real data."""
    mounts: list[tuple[Path, Path, str]] = []
    remap = build_volume_remap(task_env)
    for container_path, host_path_str in sorted(remap.items()):
        name = Path(container_path).name
        if not name:
            continue
        host_path = Path(host_path_str)
        if not host_path.is_dir():
            continue
        mount_point = run_root / ".container-home" / ".cache" / "datasets" / name
        prepare_dataset_mount_point(mount_point)
        # EXTRA_VOLUME mode is usually :ro — keep read-only for ARC cache.
        mounts.append((host_path, mount_point, "ro"))
    return mounts


def resolve_dataset_home(paths_data: dict, env_var: str) -> str | None:
    """Canonical dataset root for agent scripts (workspace-relative when aligned)."""
    import os

    agent_access = paths_data.get("agent_dataset_access")
    if isinstance(agent_access, dict) and env_var in agent_access:
        return str(agent_access[env_var]).strip()

    for candidate in (
        os.environ.get(env_var),
        (paths_data.get("dataset_env") or {}).get(env_var)
        if isinstance(paths_data.get("dataset_env"), dict)
        else None,
        paths_data.get(f"{_dataset_base(env_var)}_home_active"),
        _first_active_path(paths_data, env_var),
    ):
        if candidate and isinstance(candidate, str) and candidate.strip():
            value = candidate.strip()
            if value.startswith(f"{AGENT_DATASET_CANDIDATE}/"):
                return value
            if not value.startswith("/"):
                return value
    return None


def _dataset_base(env_var: str) -> str:
    return env_var.lower().removesuffix("_home")


def _first_active_path(paths_data: dict, env_var: str) -> str | None:
    suffix = env_var.lower()
    for key, value in paths_data.items():
        if key.endswith("_active") and isinstance(value, str) and suffix in key.lower():
            return value
    return None


def preflight_dataset_volumes(
    container_id: str,
    task_env: dict[str, str],
    *,
    run_root: Path | None = None,
    timeout_sec: int = 30,
) -> tuple[bool, str]:
    """Verify dataset directories are visible inside the agent container."""
    import subprocess

    if not aligned_paths_enabled(task_env):
        return True, "dataset volume preflight skipped (legacy container paths)"

    checks: list[str] = []
    agent_access = agent_dataset_access_paths(task_env)
    if run_root is not None and agent_access:
        for env_var, rel_path in sorted(agent_access.items()):
            container_path = str((run_root / rel_path).resolve())
            probe = (
                "import os,sys;"
                f"sys.exit(0 if os.path.isdir({container_path!r}) else 1)"
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
                return False, f"dataset preflight timed out for {env_var} ({rel_path})"
            except OSError as exc:
                return False, f"dataset preflight failed: {exc}"
            if proc.returncode != 0:
                return False, (
                    f"dataset bind mount missing in container: {rel_path} "
                    f"(expected at {container_path})"
                )
            checks.append(f"{env_var} OK ({rel_path})")
    else:
        for key in sorted(task_env):
            if not key.startswith("EXTRA_VOLUME_"):
                continue
            spec = task_env[key].strip()
            if not spec:
                continue
            parts = spec.split(":")
            if len(parts) < 2:
                continue
            host_path = str(Path(parts[0]).expanduser().resolve())
            label = parts[1]
            probe = (
                "import os,sys;"
                f"sys.exit(0 if os.path.isdir({host_path!r}) else 1)"
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
                return False, f"dataset preflight timed out for {label} ({host_path})"
            except OSError as exc:
                return False, f"dataset preflight failed: {exc}"
            if proc.returncode != 0:
                return False, f"dataset mount missing in container: {label} -> {host_path}"
            checks.append(f"{label} OK ({host_path})")

    if not checks:
        return True, "dataset volume preflight skipped (no EXTRA_VOLUME_*)"
    return True, "; ".join(checks)


def path_tokens_in_text(text: str) -> list[str]:
    return re.findall(r"/(?:shared|workplace|workspace|task)[^\s`'\"]*", text)
