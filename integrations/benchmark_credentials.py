"""Central credentials and model routing for ai_scientist_benchmark integrations.

All run_*_task.py entrypoints should load keys and default models via this module
instead of reading ~/AI-Scientist-v2/.env or per-tool DEFAULT_MODEL constants.

Primary file (gitignored):
  ~/ai_scientist_benchmark/benchmark_credentials.yaml

Override path:
  BENCHMARK_CREDENTIALS_FILE=/absolute/path/to/benchmark_credentials.yaml
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS_FILE = BENCHMARK_ROOT / "benchmark_credentials.yaml"
EXAMPLE_CREDENTIALS_FILE = BENCHMARK_ROOT / "benchmark_credentials.example.yaml"
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
AI_RESEARCHER_ROOT = BENCHMARK_ROOT.parent / "AI-Researcher"

# Legacy per-tool env var names (still populated for downstream tools).
TOOL_MODEL_ENV: dict[str, str] = {
    "evoscientist": "EVOSCIENTIST_MODEL",
    "researchclaw": "AI_SCIENTIST_MODEL",
    "deepscientist": "DEEPSCIENTIST_MODEL",
    "tinyscientist": "TINY_SCIENTIST_MODEL",
    "aris": "ARIS_MODEL",
    "aiscientist": "AI_SCIENTIST_MODEL",
    "airesearcher": "COMPLETION_MODEL",
}


@dataclass
class BenchmarkCredentials:
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_provider: str = "custom-openai"
    s2_api_key: str = ""
    github_token: str = ""
    kaggle_api_token: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = ""
    models: dict[str, Any] = field(default_factory=dict)
    source_files: list[str] = field(default_factory=list)


def credentials_file_path() -> Path:
    raw = (os.environ.get("BENCHMARK_CREDENTIALS_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CREDENTIALS_FILE.resolve()


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_yaml_credentials(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, None
    if yaml is None:
        raise RuntimeError("PyYAML is required to load benchmark_credentials.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid credentials file (expected mapping): {path}")
    return data, str(path)


def _nested_get(data: dict[str, Any], *keys: str) -> str:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return str(cur or "").strip()


def _coalesce(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _merge_models_block(*blocks: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            if value is None:
                continue
            merged[key] = copy.deepcopy(value)
    return merged


def load_benchmark_credentials(
    env: dict[str, str] | None = None,
) -> BenchmarkCredentials:
    """Load credentials from yaml, then fill gaps from legacy .env files."""
    runtime = dict(env or os.environ)
    yaml_data, yaml_path = _load_yaml_credentials(credentials_file_path())

    legacy_v2 = _read_dotenv(AI_SCIENTIST_ROOT / ".env")
    legacy_ar = _read_dotenv(AI_RESEARCHER_ROOT / ".env")

    llm = yaml_data.get("llm") if isinstance(yaml_data.get("llm"), dict) else {}
    s2 = yaml_data.get("semantic_scholar") if isinstance(yaml_data.get("semantic_scholar"), dict) else {}
    gh = yaml_data.get("github") if isinstance(yaml_data.get("github"), dict) else {}
    kaggle = yaml_data.get("kaggle") if isinstance(yaml_data.get("kaggle"), dict) else {}
    orouter = yaml_data.get("openrouter") if isinstance(yaml_data.get("openrouter"), dict) else {}
    models_yaml = yaml_data.get("models") if isinstance(yaml_data.get("models"), dict) else {}

    models = _merge_models_block(models_yaml)

    # Fallback: modern Kaggle access_token file (~/.kaggle/access_token)
    access_token_file = Path.home() / ".kaggle" / "access_token"
    access_token_from_file = ""
    if access_token_file.is_file():
        try:
            access_token_from_file = access_token_file.read_text(encoding="utf-8").strip()
        except OSError:
            access_token_from_file = ""

    creds = BenchmarkCredentials(
        llm_api_key=_coalesce(
            runtime.get("OPENAI_API_KEY", ""),
            runtime.get("CUSTOM_OPENAI_API_KEY", ""),
            _nested_get(llm, "api_key") if llm else "",
            legacy_v2.get("OPENAI_API_KEY", ""),
            legacy_ar.get("OPENAI_API_KEY", ""),
        ),
        llm_base_url=_coalesce(
            runtime.get("OPENAI_BASE_URL", ""),
            runtime.get("OPENAI_API_BASE", ""),
            runtime.get("CUSTOM_OPENAI_BASE_URL", ""),
            runtime.get("API_BASE_URL", ""),
            _nested_get(llm, "base_url") if llm else "",
            legacy_v2.get("OPENAI_API_BASE", ""),
            legacy_v2.get("OPENAI_BASE_URL", ""),
            legacy_ar.get("OPENAI_API_BASE", ""),
            legacy_ar.get("OPENAI_BASE_URL", ""),
            legacy_ar.get("API_BASE_URL", ""),
        ),
        llm_provider=_coalesce(
            runtime.get("EVOSCIENTIST_PROVIDER", ""),
            _nested_get(llm, "provider") if llm else "",
            "custom-openai",
        ),
        s2_api_key=_coalesce(
            runtime.get("S2_API_KEY", ""),
            _nested_get(s2, "api_key") if s2 else "",
            legacy_v2.get("S2_API_KEY", ""),
        ),
        github_token=_coalesce(
            runtime.get("GITHUB_TOKEN", ""),
            runtime.get("GITHUB_AI_TOKEN", ""),
            _nested_get(gh, "token") if gh else "",
            legacy_ar.get("GITHUB_AI_TOKEN", ""),
        ),
        kaggle_api_token=_coalesce(
            runtime.get("KAGGLE_API_TOKEN", ""),
            _nested_get(kaggle, "api_token") if kaggle else "",
            access_token_from_file,
            legacy_v2.get("KAGGLE_API_TOKEN", ""),
            legacy_ar.get("KAGGLE_API_TOKEN", ""),
        ),
        openrouter_api_key=_coalesce(
            runtime.get("OPENROUTER_API_KEY", ""),
            _nested_get(orouter, "api_key") if orouter else "",
            legacy_ar.get("OPENROUTER_API_KEY", ""),
        ),
        openrouter_base_url=_coalesce(
            runtime.get("OPENROUTER_API_BASE", ""),
            _nested_get(orouter, "base_url") if orouter else "",
            legacy_ar.get("OPENROUTER_API_BASE", ""),
        ),
        models=models,
    )

    if yaml_path:
        creds.source_files.append(yaml_path)

    # Legacy model env vars → models block (only when yaml did not define them).
    legacy_model_map = {
        "default": _coalesce(
            runtime.get("BENCHMARK_DEFAULT_MODEL", ""),
            legacy_v2.get("AI_SCIENTIST_MODEL", ""),
        ),
        "evoscientist": _coalesce(runtime.get("EVOSCIENTIST_MODEL", "")),
        "researchclaw": _coalesce(runtime.get("AI_SCIENTIST_MODEL", ""), legacy_v2.get("AI_SCIENTIST_MODEL", "")),
        "deepscientist": _coalesce(runtime.get("DEEPSCIENTIST_MODEL", "")),
        "tinyscientist": _coalesce(runtime.get("TINY_SCIENTIST_MODEL", "")),
        "aris_executor": _coalesce(runtime.get("ARIS_MODEL", ""), runtime.get("EVOSCIENTIST_MODEL", "")),
        "aris_reviewer": _coalesce(runtime.get("ARIS_REVIEWER_MODEL", "")),
        "aiscientist_code": _coalesce(runtime.get("AI_SCIENTIST_MODEL", ""), legacy_v2.get("AI_SCIENTIST_MODEL", "")),
        "aiscientist_feedback": _coalesce(runtime.get("AI_SCIENTIST_FEEDBACK_MODEL", "")),
        "aiscientist_vlm": _coalesce(runtime.get("AI_SCIENTIST_VLM_MODEL", "")),
        "airesearcher": _coalesce(runtime.get("COMPLETION_MODEL", ""), legacy_ar.get("COMPLETION_MODEL", "")),
        "airesearcher_cheap": _coalesce(runtime.get("CHEEP_MODEL", ""), legacy_ar.get("CHEEP_MODEL", "")),
    }
    for key, value in legacy_model_map.items():
        if value and not creds.models.get(key):
            creds.models[key] = value

    return creds


def resolve_model(
    tool: str,
    *,
    role: str | None = None,
    override: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Return the model name for a benchmark tool (CLI override wins)."""
    if override and str(override).strip():
        return str(override).strip()

    creds = load_benchmark_credentials(env)
    models = creds.models
    default = str(models.get("default") or "deepseek-v4-pro-0813").strip()

    tool_key = tool.strip().lower()
    if role:
        role_key = f"{tool_key}_{role.strip().lower()}"
        value = models.get(role_key)
        if value:
            return str(value).strip()

    direct = models.get(tool_key)
    if direct and not isinstance(direct, (list, dict)):
        return str(direct).strip()

    env_name = TOOL_MODEL_ENV.get(tool_key)
    if env_name and env:
        env_value = (env.get(env_name) or "").strip()
        if env_value:
            return env_value

    return default


def resolve_model_list(
    tool: str,
    *,
    list_key: str,
    env: dict[str, str] | None = None,
) -> list[str]:
    creds = load_benchmark_credentials(env)
    raw = creds.models.get(list_key) or creds.models.get(f"{tool}_{list_key}")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def apply_benchmark_credentials(env: dict[str, str] | None = None) -> dict[str, str]:
    """Merge central credentials into env using legacy variable names all tools expect."""
    merged = dict(env or os.environ)
    creds = load_benchmark_credentials(merged)

    if creds.llm_api_key:
        merged["OPENAI_API_KEY"] = creds.llm_api_key
        merged["CUSTOM_OPENAI_API_KEY"] = creds.llm_api_key
    if creds.llm_base_url:
        base = creds.llm_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        merged["OPENAI_API_BASE"] = base
        merged["OPENAI_BASE_URL"] = base
        merged["CUSTOM_OPENAI_BASE_URL"] = base.rstrip("/")
        merged["API_BASE_URL"] = base
    if creds.llm_provider:
        merged["EVOSCIENTIST_PROVIDER"] = creds.llm_provider

    if creds.s2_api_key:
        merged["S2_API_KEY"] = creds.s2_api_key
    if creds.github_token:
        merged["GITHUB_TOKEN"] = creds.github_token
        merged["GITHUB_AI_TOKEN"] = creds.github_token
    if creds.kaggle_api_token:
        # Modern Kaggle auth (KGAT_...). Preferred over legacy kaggle.json username/key.
        merged["KAGGLE_API_TOKEN"] = creds.kaggle_api_token
        # Ensure CLI/kagglehub can find the token even when HOME is remapped in sandbox.
        merged.setdefault("KAGGLE_CONFIG_DIR", str(Path.home() / ".kaggle"))
    if creds.openrouter_api_key:
        merged["OPENROUTER_API_KEY"] = creds.openrouter_api_key
    if creds.openrouter_base_url:
        merged["OPENROUTER_API_BASE"] = creds.openrouter_base_url.rstrip("/")

    models = creds.models
    default = str(models.get("default") or "deepseek-v4-pro-0813")

    def _set_model(env_key: str, model_key: str, fallback: str | None = None) -> None:
        value = str(models.get(model_key) or fallback or default).strip()
        if value:
            merged[env_key] = value

    _set_model("EVOSCIENTIST_MODEL", "evoscientist")
    _set_model("AI_SCIENTIST_MODEL", "researchclaw")
    _set_model("DEEPSCIENTIST_MODEL", "deepscientist")
    _set_model("TINY_SCIENTIST_MODEL", "tinyscientist")
    _set_model("ARIS_MODEL", "aris_executor")
    _set_model("ARIS_REVIEWER_MODEL", "aris_reviewer", models.get("aris_executor", default))
    _set_model("AI_SCIENTIST_FEEDBACK_MODEL", "aiscientist_feedback")
    _set_model("AI_SCIENTIST_VLM_MODEL", "aiscientist_vlm")
    _set_model("COMPLETION_MODEL", "airesearcher")
    _set_model("CHEEP_MODEL", "airesearcher_cheap", models.get("airesearcher", default))

    # AI-Scientist-v2 code model uses AI_SCIENTIST_MODEL at runtime; prefer aiscientist_code.
    code_model = str(models.get("aiscientist_code") or models.get("researchclaw") or default).strip()
    if code_model:
        merged["AI_SCIENTIST_MODEL"] = code_model

    return merged


def require_llm_api_key(env: dict[str, str] | None = None) -> bool:
    merged = apply_benchmark_credentials(env)
    return bool(merged.get("OPENAI_API_KEY") or merged.get("CUSTOM_OPENAI_API_KEY"))


def init_credentials_file(force: bool = False) -> Path:
    """Create benchmark_credentials.yaml from example + legacy .env values."""
    if yaml is None:
        raise RuntimeError("PyYAML is required")

    target = credentials_file_path()
    if target.is_file() and not force:
        raise FileExistsError(f"Credentials file already exists: {target}")

    if not EXAMPLE_CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(f"Missing template: {EXAMPLE_CREDENTIALS_FILE}")

    data = yaml.safe_load(EXAMPLE_CREDENTIALS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid example credentials template")

    legacy_v2 = _read_dotenv(AI_SCIENTIST_ROOT / ".env")
    legacy_ar = _read_dotenv(AI_RESEARCHER_ROOT / ".env")

    llm = data.setdefault("llm", {})
    if isinstance(llm, dict):
        llm["api_key"] = _coalesce(legacy_v2.get("OPENAI_API_KEY", ""), legacy_ar.get("OPENAI_API_KEY", ""))
        llm["base_url"] = _coalesce(
            legacy_v2.get("OPENAI_API_BASE", ""),
            legacy_v2.get("OPENAI_BASE_URL", ""),
            legacy_ar.get("OPENAI_API_BASE", ""),
            llm.get("base_url", ""),
        )
        llm["provider"] = _coalesce(legacy_v2.get("EVOSCIENTIST_PROVIDER", ""), llm.get("provider", ""))

    s2 = data.setdefault("semantic_scholar", {})
    if isinstance(s2, dict):
        s2["api_key"] = _coalesce(legacy_v2.get("S2_API_KEY", ""), s2.get("api_key", ""))

    gh = data.setdefault("github", {})
    if isinstance(gh, dict):
        gh["token"] = _coalesce(legacy_ar.get("GITHUB_AI_TOKEN", ""), gh.get("token", ""))

    orouter = data.setdefault("openrouter", {})
    if isinstance(orouter, dict):
        orouter["api_key"] = _coalesce(legacy_ar.get("OPENROUTER_API_KEY", ""), orouter.get("api_key", ""))
        orouter["base_url"] = _coalesce(legacy_ar.get("OPENROUTER_API_BASE", ""), orouter.get("base_url", ""))

    models = data.setdefault("models", {})
    if isinstance(models, dict):
        models.setdefault("default", legacy_v2.get("AI_SCIENTIST_MODEL", models.get("default", "")))
        models.setdefault("evoscientist", legacy_v2.get("EVOSCIENTIST_MODEL", models.get("evoscientist", "")))
        models.setdefault("researchclaw", legacy_v2.get("AI_SCIENTIST_MODEL", models.get("researchclaw", "")))
        models.setdefault("deepscientist", legacy_v2.get("DEEPSCIENTIST_MODEL", models.get("deepscientist", "")))
        models.setdefault("tinyscientist", legacy_v2.get("TINY_SCIENTIST_MODEL", models.get("tinyscientist", "")))
        models.setdefault("aiscientist_code", legacy_v2.get("AI_SCIENTIST_MODEL", models.get("aiscientist_code", "")))
        models.setdefault("airesearcher", legacy_ar.get("COMPLETION_MODEL", models.get("airesearcher", "")))
        models.setdefault("airesearcher_cheap", legacy_ar.get("CHEEP_MODEL", models.get("airesearcher_cheap", "")))

    target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    target.chmod(0o600)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage ai_scientist_benchmark credentials file")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create benchmark_credentials.yaml from example + legacy .env files",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing credentials file")
    parser.add_argument("--show-path", action="store_true", help="Print resolved credentials file path")
    args = parser.parse_args(argv)

    if args.show_path:
        print(credentials_file_path())
        return 0

    if args.init:
        path = init_credentials_file(force=args.force)
        print(f"Wrote credentials file: {path}")
        return 0

    creds = load_benchmark_credentials()
    print(f"credentials_file: {credentials_file_path()}")
    print(f"sources: {creds.source_files or ['legacy .env fallback']}")
    print(f"llm_api_key: {'set' if creds.llm_api_key else 'missing'}")
    print(f"s2_api_key: {'set' if creds.s2_api_key else 'missing'}")
    print(f"github_token: {'set' if creds.github_token else 'missing'}")
    for tool in sorted(TOOL_MODEL_ENV):
        print(f"model[{tool}]: {resolve_model(tool)}")
    return 0 if creds.llm_api_key else 1


if __name__ == "__main__":
    raise SystemExit(main())
