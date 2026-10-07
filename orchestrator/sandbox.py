"""Docker sandbox wrapper: one container per task run."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from container_setup_preflight import ensure_container_setup_for_task
from defects4j_preflight import ensure_defects4j_for_task_env


class TaskSandbox:
    def __init__(self, task_dir: Path, *, agent_tool: str | None = None):
        self.task_dir = task_dir.resolve()
        self.env = self._load_env()
        self.agent_tool = agent_tool or self.env.get("AGENT_TOOL", "").strip() or None
        self.aligned_paths = self._aligned_paths_enabled()
        self.container_id: str | None = None
        self.container_name = f"task-{self.env.get('TASK_ID', self.task_dir.name)}-{uuid.uuid4().hex[:8]}"
        self.defects4j_preflight: str | None = None
        self.container_setup_preflight: str | None = None
        self._volume_remap: dict[str, str] = {}
        self._run_root: Path | None = None

    def _aligned_paths_enabled(self) -> bool:
        raw = self.env.get("AGENT_ALIGNED_PATHS", "true").strip().lower()
        if raw in {"0", "false", "no", "off"}:
            return False
        return bool(self.agent_tool) or raw in {"1", "true", "yes", "on"}

    def _load_env(self) -> dict[str, str]:
        env_path = self.task_dir / "task.env"
        values: dict[str, str] = {}
        if not env_path.exists():
            return values
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _run(self, cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _runtime_mounts(self) -> list[tuple[Path, Path, str]]:
        if not self.agent_tool:
            return []
        from agent_container import runtime_mounts

        return runtime_mounts(self.agent_tool)

    def _append_mount(self, cmd: list[str], host_path: Path, container_path: Path, mode: str) -> None:
        spec = f"{host_path}:{container_path}:{mode}"
        if spec in cmd:
            return
        cmd.extend(["-v", spec])

    def start(self, *, agent_tool: str | None = None, run_root: Path | None = None) -> str:
        if agent_tool:
            self.agent_tool = agent_tool
            self.aligned_paths = self._aligned_paths_enabled()
        self._run_root = run_root.resolve() if run_root else None

        image = self.env.get("IMAGE", "ai-scientist-base:20260615")
        memory = self.env.get("MEMORY", "32g")
        cpus = self.env.get("CPUS", "8")

        (self.task_dir / "workspace").mkdir(parents=True, exist_ok=True)
        seeds_dir = self.task_dir / "seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)

        workspace_dir = (self.task_dir / "workspace").resolve()
        workplace_path = self.env.get("WORKPLACE_CONTAINER_PATH", "").strip()

        cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            self.container_name,
            "--memory",
            memory,
            "--cpus",
            cpus,
        ]

        if self.agent_tool:
            uid = os.getuid()
            gid = os.getgid()
            cmd.extend(["--user", f"{uid}:{gid}"])
            cmd.extend(["--add-host", f"host.docker.internal:host-gateway"])

        publish_ports = self.env.get("AGENT_PUBLISH_PORTS", "").strip()
        if publish_ports:
            for port in publish_ports.split(","):
                port = port.strip()
                if port:
                    cmd.extend(["-p", f"{port}:{port}"])

        if self.aligned_paths:
            mount_root = self._run_root if self._run_root is not None else workspace_dir
            self._append_mount(cmd, mount_root, mount_root, "rw")
        else:
            cmd.extend(["-v", f"{workspace_dir}:/workspace"])
            if workplace_path and workplace_path != "/workspace":
                cmd.extend(["-v", f"{workspace_dir}:{workplace_path}"])

        seeds_mount = seeds_dir.resolve()
        if self.aligned_paths:
            self._append_mount(cmd, seeds_mount, seeds_mount, "ro")
        else:
            cmd.extend(["-v", f"{seeds_dir}:/task/seeds:ro"])

        mounts = [
            ("task.md", "/task/input/task.md"),
            ("metadata.json", "/task/input/metadata.json"),
            ("references.bib", "/task/input/references.bib"),
        ]
        for host_name, container_path in mounts:
            host_path = self.task_dir / host_name
            if not host_path.exists():
                continue
            resolved = host_path.resolve()
            if self.aligned_paths:
                self._append_mount(cmd, resolved, resolved, "ro")
            else:
                cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

        self._volume_remap = {}
        for key in sorted(self.env):
            if not key.startswith("EXTRA_VOLUME_"):
                continue
            spec = self.env[key].strip()
            if not spec:
                continue
            parts = spec.split(":")
            if len(parts) < 2:
                raise ValueError(f"Invalid {key}={spec!r}; expected host:container[:mode]")
            host_path = Path(parts[0]).expanduser().resolve()
            container_mount = parts[1]
            mode = parts[2] if len(parts) > 2 else "ro"
            if not host_path.exists():
                raise FileNotFoundError(f"{key} host path does not exist: {host_path}")
            if self.aligned_paths and self._run_root is not None:
                from path_alignment import (
                    agent_dataset_access_path,
                    prepare_dataset_mount_point,
                )

                name = Path(container_mount).name
                agent_mount = self._run_root / agent_dataset_access_path(name)
                prepare_dataset_mount_point(agent_mount)
                self._append_mount(cmd, host_path, agent_mount, mode)
                self._volume_remap[container_mount] = agent_dataset_access_path(name)
            elif self.aligned_paths:
                self._append_mount(cmd, host_path, host_path, mode)
                self._volume_remap[container_mount] = str(host_path)
            else:
                cmd.extend(["-v", f"{host_path}:{container_mount}:{mode}"])

        # ResearchClaw: also bind EXTRA_VOLUME_* under per-run HOME/.cache/datasets
        # so ARC's inner Docker (/workspace/data/<name>/) sees real data, not symlinks.
        if (
            self.agent_tool == "researchclaw"
            and self.aligned_paths
            and self._run_root is not None
        ):
            from path_alignment import arc_dataset_cache_mounts

            for host_path, mount_point, mode in arc_dataset_cache_mounts(
                self._run_root, self.env
            ):
                self._append_mount(cmd, host_path, mount_point, mode)

        for host_path, container_path, mode in self._runtime_mounts():
            self._append_mount(cmd, host_path, container_path, mode)
            # Agents that talk to the host Docker daemon (e.g. ResearchClaw)
            # need the docker.sock group even when run as the host uid.
            if host_path.name == "docker.sock":
                try:
                    cmd.extend(["--group-add", str(host_path.stat().st_gid)])
                except OSError:
                    pass

        if self.aligned_paths:
            from path_alignment import runtime_dataset_env

            for env_name, value in runtime_dataset_env(self.env).items():
                cmd.extend(["-e", f"{env_name}={value}"])
        else:
            for key, value in self.env.items():
                if key.startswith("ENV_IN_CONTAINER_"):
                    env_name = key[len("ENV_IN_CONTAINER_") :]
                    cmd.extend(["-e", f"{env_name}={value}"])

        if self.agent_tool:
            from agent_container import literature_scrub_enabled, scrub_base_url

            if literature_scrub_enabled():
                cmd.extend(["-e", f"LITERATURE_SCRUB_BASE_URL={scrub_base_url()}"])
            cmd.extend(["-e", "LITERATURE_SCRUB_ENABLED=0"])

        cmd.append(image)
        proc = self._run(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start container:\n{proc.stderr.strip()}")

        self.container_id = proc.stdout.strip()
        ok, msg = ensure_defects4j_for_task_env(
            self.container_id,
            self.env,
            run_root=self._run_root,
        )
        self.defects4j_preflight = msg
        if not ok:
            self.destroy()
            raise RuntimeError(f"Defects4J preflight failed: {msg}")
        if msg != "Defects4J not configured for this task":
            print(f"[preflight] Defects4J container setup: {msg}")

        ok_setup, setup_msg = ensure_container_setup_for_task(
            self.container_id,
            self.task_dir,
            self.env,
        )
        self.container_setup_preflight = setup_msg
        if not ok_setup:
            self.destroy()
            raise RuntimeError(f"Container setup preflight failed: {setup_msg}")
        if setup_msg != "container setup not configured for this task":
            print(f"[preflight] {setup_msg}")
        return self.container_id

    def _remap_env_value(self, value: str) -> str:
        from path_alignment import align_path

        return align_path(value, self._volume_remap)

    def seeds_path(self) -> str:
        if self.aligned_paths:
            return str((self.task_dir / "seeds").resolve())
        return "/task/seeds"

    def default_workdir(self) -> str:
        if self.aligned_paths:
            if self._run_root is not None:
                return str(self._run_root)
            return str((self.task_dir / "workspace").resolve())
        return self.env.get("WORKPLACE_CONTAINER_PATH", "/workspace").strip() or "/workspace"

    def exec(
        self,
        command: str,
        *,
        workdir: str | None = None,
        timeout: int = 3600,
    ) -> tuple[int, str, str]:
        if not self.container_id:
            raise RuntimeError("Container is not running. Call start() first.")

        wd = workdir or self.default_workdir()
        cmd = [
            "docker",
            "exec",
            "-w",
            wd,
            self.container_id,
            "bash",
            "-lc",
            command,
        ]
        proc = self._run(cmd, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr

    def evaluate(self) -> tuple[int, str, str]:
        if not self.container_id:
            raise RuntimeError("Container is not running. Call start() first.")

        evaluator_dir = self.task_dir / "evaluator"
        if not evaluate_script_exists(evaluator_dir):
            raise FileNotFoundError(f"Missing evaluator at {evaluator_dir}")

        copy_proc = self._run(
            ["docker", "cp", f"{evaluator_dir}/.", f"{self.container_id}:/evaluator"]
        )
        if copy_proc.returncode != 0:
            raise RuntimeError(f"Failed to copy evaluator:\n{copy_proc.stderr.strip()}")

        proc = self._run(
            [
                "docker",
                "exec",
                self.container_id,
                "bash",
                "/evaluator/evaluate.sh",
            ]
        )

        host_results = evaluator_dir / "results"
        host_results.mkdir(parents=True, exist_ok=True)
        pull_proc = self._run(
            [
                "docker",
                "cp",
                f"{self.container_id}:/evaluator/results/.",
                f"{host_results}/",
            ]
        )
        if pull_proc.returncode != 0:
            raise RuntimeError(f"Failed to pull evaluation results:\n{pull_proc.stderr.strip()}")

        return proc.returncode, proc.stdout, proc.stderr

    def destroy(self) -> None:
        if not self.container_id:
            return
        self._run(["docker", "rm", "-f", self.container_id])
        self.container_id = None


def evaluate_script_exists(evaluator_dir: Path) -> bool:
    return (evaluator_dir / "evaluate.sh").is_file()
