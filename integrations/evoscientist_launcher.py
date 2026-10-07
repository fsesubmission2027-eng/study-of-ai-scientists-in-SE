#!/usr/bin/env python3
"""Launch EvoSci with benchmark-side DeepSeek compatibility patches.

EvoScientist only applies ``_patch_deepseek_reasoning_passback`` when
``provider == "deepseek"``. Benchmark runs use ``custom-openai`` against
umodelverse, so DeepSeek V4 thinking + tool_use turns lose
``reasoning_content`` on passback and the agent loop emits tool_calls with
empty names.

This launcher applies the passback patch for any model id containing
``deepseek`` before delegating to ``EvoScientist.cli.main``.
"""

from __future__ import annotations


def _apply_deepseek_custom_openai_patch() -> None:
    import EvoScientist.llm.models as models
    from EvoScientist.llm.patches import _patch_deepseek_reasoning_passback

    if getattr(models, "_benchmark_deepseek_patch_applied", False):
        return

    orig_get_chat_model = models.get_chat_model

    def get_chat_model_with_deepseek_passback(*args, **kwargs):
        chat_model = orig_get_chat_model(*args, **kwargs)
        model = kwargs.get("model") or (args[0] if args else "")
        if "deepseek" in str(model).lower():
            _patch_deepseek_reasoning_passback(chat_model)
        return chat_model

    models.get_chat_model = get_chat_model_with_deepseek_passback
    models._benchmark_deepseek_patch_applied = True


def main() -> None:
    _apply_deepseek_custom_openai_patch()
    from EvoScientist.cli import main as evosci_main

    evosci_main()


if __name__ == "__main__":
    main()
