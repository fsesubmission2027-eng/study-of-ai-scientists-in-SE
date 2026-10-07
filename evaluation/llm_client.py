"""Minimal OpenAI-compatible chat helper for evaluation."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parent
BENCHMARK_ROOT = EVAL_ROOT.parent
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"

if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import scrub_base_url  # noqa: E402
from benchmark_credentials import apply_benchmark_credentials  # noqa: E402


def resolve_llm_config(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = apply_benchmark_credentials(dict(env or os.environ))
    base = scrub_base_url(merged).rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    model = (merged.get("BENCHMARK_EVAL_MODEL") or merged.get("OPENAI_MODEL") or "").strip()
    if not model:
        try:
            from benchmark_credentials import load_benchmark_credentials, resolve_model

            creds = load_benchmark_credentials()
            model = resolve_model("default", env=merged) or str((creds.models or {}).get("default") or "")
        except Exception:  # noqa: BLE001
            model = ""
    if not model:
        model = "gemini-3.5-flash"
    api_key = (merged.get("OPENAI_API_KEY") or "").strip()
    return {"base_url": base, "api_key": api_key, "model": model}


def _extract_message_text(payload: dict[str, Any]) -> str:
    """Return the answer text. Thinking traces are not JSON."""
    choice = ((payload.get("choices") or [{}])[0]) or {}
    message = choice.get("message") or {}
    for key in ("content", "text"):
        val = message.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for key in ("text", "content"):
        val = choice.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # A few gateways leave content empty and put the final object in reasoning_content.
    # Accept that only when the field itself is a JSON object, not a think-trace.
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str):
        stripped = reasoning.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
    return ""


# Extra completion tokens reserved so reasoning does not consume the whole budget.
THINKING_ANSWER_RESERVE = 8000


def _is_reasoner_model(model: str) -> bool:
    name = (model or "").lower()
    return "deepseek" in name or "reasoner" in name


def _thinking_budget(requested: int) -> int:
    """Leave the caller's answer budget intact after the reasoning trace."""
    return max(int(requested) + THINKING_ANSWER_RESERVE, 12000)


_thinking_logged = False


def _apply_thinking(body: dict[str, Any], model: str, *, enabled: bool) -> None:
    global _thinking_logged
    if not _is_reasoner_model(model):
        return
    body["thinking"] = {"type": "enabled" if enabled else "disabled"}
    if enabled and not _thinking_logged:
        print(
            f"[eval] thinking enabled for {model}; max_tokens={body.get('max_tokens')}",
            file=sys.stderr,
            flush=True,
        )
        _thinking_logged = True


def _answer_starved(payload: dict[str, Any], content: str) -> bool:
    """True when reasoning finished by hitting the token cap before any answer."""
    if (content or "").strip():
        return False
    choice = ((payload.get("choices") or [{}])[0]) or {}
    finish = str(choice.get("finish_reason") or "").lower()
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
    try:
        reasoning = int(details.get("reasoning_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        reasoning, completion = 0, 0
    if reasoning and completion and reasoning >= completion - 8:
        return True
    return finish == "length"


def _looks_like_plan(text: str) -> bool:
    head = (text or "").strip()[:160].lower()
    return head.startswith(
        ("we need", "i need", "the user", "let me", "need answer", "need respond", "need produce")
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    content = (content or "").strip()
    if not content:
        raise RuntimeError("LLM returned empty content")

    # Strip common reasoning wrappers / fences.
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.I).strip()
    content = re.sub(r"\[thinking\][\s\S]*?\[/thinking\]", "", content, flags=re.I).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Salvage the largest JSON object substring.
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        candidate = content[start : end + 1]
        for candidate_try in (
            candidate,
            re.sub(r",\s*}", "}", re.sub(r",\s*]", "]", candidate)),
        ):
            try:
                data = json.loads(candidate_try)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

    raise RuntimeError(f"LLM did not return JSON: {content[:300]}")


def chat_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    env: dict[str, str] | None = None,
    retries: int = 3,
    repair_retries: int = 2,
    validate: Any = None,
) -> dict[str, Any]:
    cfg = resolve_llm_config(env)
    if not cfg["api_key"]:
        raise RuntimeError(
            "Missing OPENAI_API_KEY / llm.api_key for evaluation LLM calls."
        )
    use_model = model or cfg["model"]
    endpoint = f"{cfg['base_url']}/chat/completions"

    last_error: Exception | None = None
    is_reasoner = _is_reasoner_model(use_model)
    output_budget = _thinking_budget(max_tokens) if is_reasoner else max_tokens
    send_thinking_param = True
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": user
            + "\n\nIMPORTANT: Reply with a single JSON object only. No markdown fences, no analysis prose.",
        },
    ]

    def _reject_for_retry(reason: Exception, previous: str) -> None:
        nonlocal messages, last_error
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": (previous or "")[:6000]},
            {
                "role": "user",
                "content": (
                    "Your previous reply was rejected "
                    f"({reason}). Resend ONLY one corrected JSON object that satisfies the schema. "
                    "Fill every required field with real values from the source text. "
                    "Do not copy schema placeholders, enum lists, or empty objects."
                ),
            },
        ]
        last_error = reason

    for attempt in range(retries + 1):
        body: dict[str, Any] = {
            "model": use_model,
            "temperature": temperature,
            "max_tokens": output_budget,
            "messages": messages,
        }
        if attempt == 0:
            body["response_format"] = {"type": "json_object"}
        if send_thinking_param:
            _apply_thinking(body, use_model, enabled=True)

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
                "User-Agent": "ai_scientist_benchmark-evaluation/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            content = _extract_message_text(payload)
            if is_reasoner and _answer_starved(payload, content):
                output_budget += 4000
                starved = RuntimeError(
                    "LLM reasoning consumed the token budget and returned no JSON; "
                    f"retrying with max_tokens={output_budget}"
                )
                if attempt >= retries:
                    raise starved
                _reject_for_retry(starved, content)
                time.sleep(1.0)
                continue
            parse_exc: Exception | None = None
            validated = False
            for repair_attempt in range(repair_retries + 1):
                try:
                    data = _parse_json_object(content)
                    if validate is not None:
                        verr = validate(data)
                        if verr:
                            raise RuntimeError(f"LLM JSON failed validation: {verr}")
                    validated = True
                    break
                except Exception as exc:  # noqa: BLE001
                    parse_exc = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
                    reason = str(parse_exc)
                    # Empty objects and schema echoes cannot be repaired from BAD_OUTPUT:
                    # that prompt does not include the paper. Retry the original request.
                    skip_repair = (
                        reason.startswith("LLM JSON failed validation")
                        or "empty content" in reason.lower()
                    )
                    if skip_repair or repair_attempt >= repair_retries:
                        if attempt >= retries:
                            raise parse_exc
                        _reject_for_retry(parse_exc, content)
                        time.sleep(1.0)
                        break

                    repair_body: dict[str, Any] = {
                        "model": use_model,
                        "temperature": 0.0,
                        "max_tokens": min(max_tokens, 2500),
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You repair malformed model output into valid JSON. "
                                    "Return exactly one JSON object and nothing else."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Convert the following content into a single valid JSON object. "
                                    "If the content already contains JSON, preserve the fields and values. "
                                    "If there is extra prose, discard it.\n\n"
                                    f"BAD_OUTPUT_START\n{content[:12000]}\nBAD_OUTPUT_END"
                                ),
                            },
                        ],
                    }
                    # Repair is a format fix. Keep thinking off so it does not narrate a plan.
                    _apply_thinking(repair_body, use_model, enabled=False)
                    repair_req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(repair_body).encode("utf-8"),
                        headers={
                            "Authorization": f"Bearer {cfg['api_key']}",
                            "Content-Type": "application/json",
                            "User-Agent": "ai_scientist_benchmark-evaluation/1.0",
                        },
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(repair_req, timeout=180) as repair_resp:
                            repair_payload = json.loads(repair_resp.read().decode("utf-8"))
                        repaired_content = _extract_message_text(repair_payload)
                        if (
                            repaired_content.strip()
                            and "{" in repaired_content
                            and not _looks_like_plan(repaired_content)
                        ):
                            content = repaired_content
                            payload = repair_payload
                    except Exception:
                        # If repair call itself fails, fall back to the normal retry path.
                        if attempt >= retries and repair_attempt >= repair_retries:
                            raise parse_exc
                        continue
            else:
                raise parse_exc or RuntimeError("LLM JSON parse failed")

            if not validated:
                continue

            data["_meta"] = {
                "model": use_model,
                "base_url": cfg["base_url"],
                "usage": payload.get("usage"),
                "attempt": attempt,
            }
            return data
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = RuntimeError(f"LLM HTTP {exc.code}: {detail}")
            if exc.code == 400 and "thinking" in detail.lower():
                send_thinking_param = False
            if exc.code == 400 and attempt < retries:
                time.sleep(1.0)
                continue
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_error from exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_error or RuntimeError("LLM call failed")
