"""No-progress circuit breaker for AI-Researcher agent loops.

Upstream ``MetaChain`` returns tool exceptions to the model as ordinary tool
messages, so a broken tool (e.g. ``case_resolved`` raising ``KeyError:
'math_formula'``) can be retried indefinitely; each retry is a full LLM round
trip and burns API quota.

This module installs in-process patches only — the AI-Researcher source tree is
never modified. It counts consecutive identical failures, keyed by
``(tool name, arguments, normalized error)``, and once the streak reaches the
limit it stops the *next* LLM call so the current agent turn ends instead of
spinning.

Env:
    AIRESEARCHER_NO_PROGRESS_ENABLED  0/1 (default 1)
    AIRESEARCHER_NO_PROGRESS_MAX      consecutive identical failures (default 3)
"""

from __future__ import annotations

import hashlib
import json
import os
import re

BREAKER_PREFIX = "[No Progress Circuit Breaker]"
_TOOL_ERROR_PREFIX = "[Tool Call Error]"
_INSTALLED_FLAG = "_benchmark_no_progress_installed"


class NoProgressAbort(RuntimeError):
    """Raised in place of an LLM call once the breaker has tripped."""


def is_enabled() -> bool:
    raw = (os.environ.get("AIRESEARCHER_NO_PROGRESS_ENABLED") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def max_identical_failures() -> int:
    try:
        return max(1, int(os.environ.get("AIRESEARCHER_NO_PROGRESS_MAX") or "3"))
    except ValueError:
        return 3


def _args_digest(raw_arguments) -> str:
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            parsed = raw_arguments
    else:
        parsed = raw_arguments
    if isinstance(parsed, dict):
        parsed = {k: v for k, v in parsed.items() if k != "context_variables"}
    try:
        payload = json.dumps(parsed, sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        payload = str(parsed)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _error_signature(content: str) -> str:
    """Collapse an upstream tool-error message into a stable fingerprint."""
    tail = content.split("Error:", 1)[1] if "Error:" in content else content
    return re.sub(r"\s+", " ", tail).strip()[:200]


class _BreakerState:
    def __init__(self) -> None:
        self.last_signature: tuple | None = None
        self.streak = 0
        self.blocked: set[tuple] = set()
        self.tripped_reason: str | None = None

    def reset_turn(self) -> None:
        self.last_signature = None
        self.streak = 0
        self.tripped_reason = None


def _state(chain) -> _BreakerState:
    state = getattr(chain, "_benchmark_no_progress_state", None)
    if state is None:
        state = _BreakerState()
        chain._benchmark_no_progress_state = state
    return state


def _breaker_text(tool_name: str, error_sig: str, streak: int, limit: int) -> str:
    return (
        f"{BREAKER_PREFIX} Tool `{tool_name}` failed identically {streak} time(s) "
        f"(limit={limit}, error={error_sig}). Retrying the same call cannot make "
        "progress, so this agent turn is ending to avoid burning API quota."
    )


def install_no_progress_breaker(core_module) -> bool:
    """Patch ``MetaChain`` in ``core_module``; returns False when disabled/already done."""
    if not is_enabled():
        print("[airesearcher] no-progress circuit breaker disabled", flush=True)
        return False
    chain_cls = getattr(core_module, "MetaChain", None)
    if chain_cls is None or getattr(chain_cls, _INSTALLED_FLAG, False):
        return False

    limit = max_identical_failures()
    orig_handle_tool_calls = chain_cls.handle_tool_calls
    orig_get_chat_completion = chain_cls.get_chat_completion
    orig_try_completion = chain_cls.try_completion_with_truncation
    orig_run = chain_cls.run
    orig_run_async = chain_cls.run_async

    def _record(chain, tool_calls, response):
        state = _state(chain)
        args_by_id = {}
        for call in tool_calls or []:
            function = getattr(call, "function", None)
            args_by_id[getattr(call, "id", None)] = getattr(function, "arguments", "")

        for message in getattr(response, "messages", None) or []:
            if message.get("role") != "tool":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            name = message.get("name") or "<unknown>"
            if not content.startswith(_TOOL_ERROR_PREFIX):
                state.last_signature = None
                state.streak = 0
                continue

            signature = (
                name,
                _args_digest(args_by_id.get(message.get("tool_call_id"), "")),
                _error_signature(content),
            )
            if signature == state.last_signature:
                state.streak += 1
            else:
                state.last_signature = signature
                state.streak = 1

            # A signature blocked earlier in this run trips again immediately.
            if state.streak >= limit or signature in state.blocked:
                state.blocked.add(signature)
                text = _breaker_text(name, signature[2], state.streak, limit)
                state.tripped_reason = text
                # Not a "[Tool Call Error]" string, so upstream's case_resolved
                # branch ends the turn instead of looping on `continue`.
                message["content"] = text
                chain.logger.info(text, title="No Progress Circuit Breaker", color="red")
                print(f"[airesearcher] {text}", flush=True)

    def patched_handle_tool_calls(
        self, tool_calls, functions, context_variables, debug, handle_mm_func=None
    ):
        response = orig_handle_tool_calls(
            self, tool_calls, functions, context_variables, debug,
            handle_mm_func=handle_mm_func,
        )
        try:
            _record(self, tool_calls, response)
        except Exception as exc:  # never let the breaker break the run
            print(f"[airesearcher] no-progress breaker bookkeeping failed: {exc}", flush=True)
        return response

    def _guard(chain):
        reason = _state(chain).tripped_reason
        if reason:
            raise NoProgressAbort(reason)

    def patched_get_chat_completion(self, *args, **kwargs):
        _guard(self)
        return orig_get_chat_completion(self, *args, **kwargs)

    async def patched_try_completion(self, *args, **kwargs):
        _guard(self)
        return await orig_try_completion(self, *args, **kwargs)

    def patched_run(self, *args, **kwargs):
        _state(self).reset_turn()
        try:
            return orig_run(self, *args, **kwargs)
        except NoProgressAbort as exc:
            print(f"[airesearcher] agent turn aborted: {exc}", flush=True)
            return core_module.Response(
                messages=[{"role": "assistant", "content": str(exc)}],
                agent=args[0] if args else kwargs.get("agent"),
                context_variables=kwargs.get("context_variables", {}) or {},
            )

    async def patched_run_async(self, *args, **kwargs):
        _state(self).reset_turn()
        try:
            return await orig_run_async(self, *args, **kwargs)
        except NoProgressAbort as exc:
            print(f"[airesearcher] agent turn aborted: {exc}", flush=True)
            return core_module.Response(
                messages=[{"role": "assistant", "content": str(exc)}],
                agent=args[0] if args else kwargs.get("agent"),
                context_variables=kwargs.get("context_variables", {}) or {},
            )

    chain_cls.handle_tool_calls = patched_handle_tool_calls
    chain_cls.get_chat_completion = patched_get_chat_completion
    chain_cls.try_completion_with_truncation = patched_try_completion
    chain_cls.run = patched_run
    chain_cls.run_async = patched_run_async
    setattr(chain_cls, _INSTALLED_FLAG, True)

    print(
        f"[airesearcher] no-progress circuit breaker armed "
        f"(max identical tool failures={limit})",
        flush=True,
    )
    return True
