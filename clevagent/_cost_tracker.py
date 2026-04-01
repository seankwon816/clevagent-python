"""Auto cost tracking — monkey-patches OpenAI and Anthropic SDK clients.

⚠️  SDK versioning risk: internal class paths may change between library versions.
    All patches are wrapped in try/except. On failure: logs a warning, leaves auto_cost
    inactive, and directs the user to clevagent.log_cost() for manual tracking.

OpenAI v1.x: patches openai.resources.chat.completions.Completions.create
             patches openai.resources.chat.completions.AsyncCompletions.create
Anthropic:   patches anthropic.resources.messages.Messages.create
             patches anthropic.resources.messages.AsyncMessages.create

⚠️  Streaming (stream=True) is NOT auto-tracked in v0.1.0.
    For streaming calls, use clevagent.log_cost(tokens=N, cost_usd=X.XX) manually.
    Streaming auto-cost is planned for v0.2.0.
"""

import logging
from typing import Optional

logger = logging.getLogger("clevagent")

# Store original methods for uninstall
_originals: dict = {}


# ── Pricing tables ─────────────────────────────────────────────────────────────

# USD per 1,000 input/output tokens
_OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini":       {"input": 0.000150, "output": 0.000600},
    "gpt-4o":            {"input": 0.005,    "output": 0.015},
    "gpt-4-turbo":       {"input": 0.01,     "output": 0.03},
    "gpt-4":             {"input": 0.03,     "output": 0.06},
    "gpt-3.5-turbo":     {"input": 0.0005,   "output": 0.0015},
}

# USD per 1,000,000 input/output tokens
_ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4":    {"input": 0.80,  "output": 4.0},
    "claude-sonnet-4":   {"input": 3.0,   "output": 15.0},
    "claude-opus-4":     {"input": 15.0,  "output": 75.0},
    "claude-3-haiku":    {"input": 0.25,  "output": 1.25},
    "claude-3-5-sonnet": {"input": 3.0,   "output": 15.0},
    "claude-3-opus":     {"input": 15.0,  "output": 75.0},
}


def _match_pricing(model: str, table: dict) -> Optional[dict]:
    """Find the best pricing entry for a model name (substring match)."""
    model_lower = model.lower()
    for key, pricing in table.items():
        if key in model_lower:
            return pricing
    return None


def _calc_openai_cost(model: str, usage) -> float:
    pricing = _match_pricing(model, _OPENAI_PRICING)
    if not pricing:
        return 0.0
    return (
        (getattr(usage, "prompt_tokens", 0) / 1000) * pricing["input"] +
        (getattr(usage, "completion_tokens", 0) / 1000) * pricing["output"]
    )


def _calc_anthropic_cost(model: str, usage) -> float:
    pricing = _match_pricing(model, _ANTHROPIC_PRICING)
    if not pricing:
        return 0.0
    return (
        (getattr(usage, "input_tokens", 0) / 1_000_000) * pricing["input"] +
        (getattr(usage, "output_tokens", 0) / 1_000_000) * pricing["output"]
    )


# ── Patches ────────────────────────────────────────────────────────────────────

def _patch_openai() -> bool:
    """
    Patch OpenAI SDK v1.x (openai.resources.chat.completions.Completions.create).
    Returns True if patch was applied successfully.
    """
    try:
        from openai.resources.chat.completions import Completions  # type: ignore
        from ._state import _state

        _original = Completions.create
        _originals["openai.resources.chat.completions.Completions.create"] = _original

        def _patched(self_inner, *args, **kwargs):
            if kwargs.get("stream"):
                logger.warning(
                    "clevagent auto_cost: stream=True detected — streaming is not auto-tracked "
                    "in v0.1.0. Use clevagent.log_cost(tokens=N, cost_usd=X) manually."
                )
                return _original(self_inner, *args, **kwargs)
            resp = _original(self_inner, *args, **kwargs)
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    model = getattr(resp, "model", "")
                    tokens = getattr(usage, "total_tokens", 0)
                    cost = _calc_openai_cost(model, usage)
                    # Count and log tool calls from response choices
                    tool_calls = 0
                    choices = getattr(resp, "choices", [])
                    if choices:
                        tc = getattr(getattr(choices[0], "message", None), "tool_calls", None)
                        if tc:
                            tool_calls = len(tc)
                            for t in tc:
                                fn = getattr(t, "function", None)
                                if fn:
                                    _state.log_tool_call(
                                        name=getattr(fn, "name", "unknown"),
                                        args_summary=str(getattr(fn, "arguments", ""))[:200],
                                    )
                    _state.accumulate_cost(tokens=tokens, cost_usd=cost, tool_calls=tool_calls)
            except Exception:
                pass  # Never let tracking errors affect the actual API call
            return resp

        Completions.create = _patched
        logger.debug("OpenAI SDK patched (Completions.create)")
        return True

    except (ImportError, AttributeError) as exc:
        logger.debug("OpenAI patch skipped: %s", exc)
        return False


def _patch_openai_async() -> bool:
    """
    Patch OpenAI SDK v1.x async client (AsyncCompletions.create).
    Returns True if patch was applied successfully.
    """
    try:
        from openai.resources.chat.completions import AsyncCompletions  # type: ignore
        from ._state import _state

        _original = AsyncCompletions.create
        _originals["openai.resources.chat.completions.AsyncCompletions.create"] = _original

        async def _patched_async(self_inner, *args, **kwargs):
            if kwargs.get("stream"):
                logger.warning(
                    "clevagent auto_cost: stream=True detected — streaming is not auto-tracked "
                    "in v0.1.0. Use clevagent.log_cost(tokens=N, cost_usd=X) manually."
                )
                return await _original(self_inner, *args, **kwargs)
            resp = await _original(self_inner, *args, **kwargs)
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    model = getattr(resp, "model", "")
                    tokens = getattr(usage, "total_tokens", 0)
                    cost = _calc_openai_cost(model, usage)
                    tool_calls = 0
                    choices = getattr(resp, "choices", [])
                    if choices:
                        tc = getattr(getattr(choices[0], "message", None), "tool_calls", None)
                        if tc:
                            tool_calls = len(tc)
                            for t in tc:
                                fn = getattr(t, "function", None)
                                if fn:
                                    _state.log_tool_call(
                                        name=getattr(fn, "name", "unknown"),
                                        args_summary=str(getattr(fn, "arguments", ""))[:200],
                                    )
                    _state.accumulate_cost(tokens=tokens, cost_usd=cost, tool_calls=tool_calls)
            except Exception:
                pass
            return resp

        AsyncCompletions.create = _patched_async
        logger.debug("OpenAI SDK patched (AsyncCompletions.create)")
        return True

    except (ImportError, AttributeError) as exc:
        logger.debug("OpenAI async patch skipped: %s", exc)
        return False


def _patch_anthropic() -> bool:
    """
    Patch Anthropic SDK (anthropic.resources.messages.Messages.create).
    Returns True if patch was applied successfully.
    """
    try:
        from anthropic.resources.messages import Messages  # type: ignore
        from ._state import _state

        _original = Messages.create
        _originals["anthropic.resources.messages.Messages.create"] = _original

        def _patched(self_inner, *args, **kwargs):
            if kwargs.get("stream"):
                logger.warning(
                    "clevagent auto_cost: stream=True detected — streaming is not auto-tracked "
                    "in v0.1.0. Use clevagent.log_cost(tokens=N, cost_usd=X) manually."
                )
                return _original(self_inner, *args, **kwargs)
            resp = _original(self_inner, *args, **kwargs)
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    model = getattr(resp, "model", "")
                    tokens = (
                        getattr(usage, "input_tokens", 0) +
                        getattr(usage, "output_tokens", 0)
                    )
                    cost = _calc_anthropic_cost(model, usage)
                    _state.accumulate_cost(tokens=tokens, cost_usd=cost)
                # Auto-log tool_use content blocks for semantic analysis
                for block in getattr(resp, "content", []):
                    if getattr(block, "type", None) == "tool_use":
                        _state.log_tool_call(
                            name=getattr(block, "name", "unknown"),
                            args_summary=str(getattr(block, "input", ""))[:200],
                        )
            except Exception:
                pass
            return resp

        Messages.create = _patched
        logger.debug("Anthropic SDK patched (Messages.create)")
        return True

    except (ImportError, AttributeError) as exc:
        logger.debug("Anthropic patch skipped: %s", exc)
        return False


def _patch_anthropic_async() -> bool:
    """
    Patch Anthropic SDK async client (AsyncMessages.create).
    Returns True if patch was applied successfully.
    """
    try:
        from anthropic.resources.messages import AsyncMessages  # type: ignore
        from ._state import _state

        _original = AsyncMessages.create
        _originals["anthropic.resources.messages.AsyncMessages.create"] = _original

        async def _patched_async(self_inner, *args, **kwargs):
            if kwargs.get("stream"):
                logger.warning(
                    "clevagent auto_cost: stream=True detected — streaming is not auto-tracked "
                    "in v0.1.0. Use clevagent.log_cost(tokens=N, cost_usd=X) manually."
                )
                return await _original(self_inner, *args, **kwargs)
            resp = await _original(self_inner, *args, **kwargs)
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    model = getattr(resp, "model", "")
                    tokens = (
                        getattr(usage, "input_tokens", 0) +
                        getattr(usage, "output_tokens", 0)
                    )
                    cost = _calc_anthropic_cost(model, usage)
                    _state.accumulate_cost(tokens=tokens, cost_usd=cost)
                for block in getattr(resp, "content", []):
                    if getattr(block, "type", None) == "tool_use":
                        _state.log_tool_call(
                            name=getattr(block, "name", "unknown"),
                            args_summary=str(getattr(block, "input", ""))[:200],
                        )
            except Exception:
                pass
            return resp

        AsyncMessages.create = _patched_async
        logger.debug("Anthropic SDK patched (AsyncMessages.create)")
        return True

    except (ImportError, AttributeError) as exc:
        logger.debug("Anthropic async patch skipped: %s", exc)
        return False


def install_auto_cost() -> None:
    """
    Activate auto cost tracking. Patches available AI SDKs; skips missing ones.
    If no SDK is found, logs guidance for manual tracking via clevagent.log_cost().
    """
    from ._state import _state

    patched = _patch_openai() | _patch_openai_async() | _patch_anthropic() | _patch_anthropic_async()

    if patched:
        _state.auto_cost_active = True
        logger.info("Auto cost tracking enabled")
    else:
        logger.info(
            "Auto cost tracking inactive — openai/anthropic not installed. "
            "Use clevagent.log_cost(tokens=N, cost_usd=X.XX) for manual tracking."
        )


def uninstall_auto_cost() -> None:
    """Restore original SDK methods, undoing monkey-patches."""
    for key, original in _originals.items():
        try:
            module_path, attr = key.rsplit(".", 1)
            parts = module_path.split(".")
            mod = __import__(parts[0])
            for part in parts[1:]:
                mod = getattr(mod, part)
            setattr(mod, attr, original)
        except Exception:
            pass
    _originals.clear()
    from ._state import _state
    _state.auto_cost_active = False
    logger.debug("Auto cost tracking uninstalled")
