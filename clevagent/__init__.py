"""
ClevAgent SDK — Monitor your AI agents in 2 lines of code.

    import clevagent
    clevagent.init(api_key="cv_xxx", agent="my-agent")

The SDK starts a background daemon thread that sends heartbeats to the
ClevAgent API every `interval` seconds. If the process dies, pings stop,
and the server detects the silence and fires an alert.
"""

import logging
from typing import Optional

from ._state import _state
from ._heartbeat import HeartbeatThread
from ._cost_tracker import install_auto_cost
from ._signals import install_signal_handlers
from ._crash_handler import install as _install_crash_handler

logger = logging.getLogger("clevagent")

# Module-level thread reference — replaced on each init() call
_thread: Optional[HeartbeatThread] = None


def init(
    api_key: str,
    agent: str,
    interval: int = 60,
    endpoint: str = "https://clevagent.io",
    auto_cost: bool = True,
    on_loop = "alert_only",
    on_cost_exceeded = "alert_only",
    agent_type: Optional[str] = None,
) -> None:
    """
    Initialize ClevAgent monitoring. Call once at agent startup.

    Args:
        api_key:          Project API key from the ClevAgent dashboard (cv_xxx).
        agent:            Unique agent name within the project. Auto-created on first ping.
        interval:         Heartbeat interval in seconds (default: 60).
        endpoint:         API base URL (override for self-hosted or local dev).
        auto_cost:        If True, monkey-patches OpenAI/Anthropic SDKs to capture usage.
                          Falls back gracefully if SDKs are not installed or have changed.
        on_loop:          Action when loop is detected. "alert_only" (default) logs the warning
                          without stopping. "stop" sets the stop event and calls sys.exit(1)
                          (graceful). "force_stop" calls os._exit(1) immediately. Pass a callable
                          for a custom safe-shutdown handler (e.g. close positions then exit).
        on_cost_exceeded: Action when cost threshold is exceeded. "alert_only" (default) logs only.
                          "stop" terminates the process. Callable for custom handler.
        agent_type:       Agent framework identifier (e.g. "claude", "openai", "langchain",
                          "foragent-relay"). Stored on the agent record in the dashboard.
    """
    global _thread

    # Stop existing thread if re-initializing
    if _thread is not None and _thread.is_alive():
        _thread.stop(send_final=False)

    _state.api_key = api_key
    _state.agent = agent
    _state.agent_type = agent_type
    _state.interval = interval
    _state.endpoint = endpoint.rstrip("/")
    _state.on_loop = on_loop
    _state.on_cost_exceeded = on_cost_exceeded
    _state.initialized = True

    if auto_cost:
        install_auto_cost()

    _install_crash_handler()

    _thread = HeartbeatThread()
    _thread.start()

    install_signal_handlers()

    logger.info(
        "ClevAgent initialized — agent=%s endpoint=%s interval=%ds auto_cost=%s",
        agent, _state.endpoint, interval, auto_cost,
    )
    print(f"[clevagent] Initialized — agent={agent} endpoint={_state.endpoint}")


def ping(
    status: str = "ok",
    message: Optional[str] = None,
    tokens_used: Optional[int] = None,
    cost_usd: Optional[float] = None,
    tool_calls: Optional[int] = None,
    iteration_count: Optional[int] = None,
    memory_mb: Optional[float] = None,
    custom: Optional[dict] = None,
) -> None:
    """
    Send a manual heartbeat ping.

    Use for granular control — e.g., after completing a task loop, or to
    report a warning/error state before the regular interval fires.

    Args:
        status:          "ok" | "warning" | "error"
        message:         Optional free-text status message (used for loop detection).
        tokens_used:     Token count for this ping cycle.
        cost_usd:        Cost for this ping cycle in USD.
        tool_calls:      Number of tool calls made since last ping.
        iteration_count: Current loop iteration count (for loop detection).
        memory_mb:       Current memory usage in MB.
        custom:          Arbitrary JSON-serializable dict stored in Heartbeat.custom_data.
    """
    if _thread is None:
        raise RuntimeError(
            "clevagent.init() must be called before ping(). "
            "Example: clevagent.init(api_key='cv_xxx', agent='my-agent')"
        )
    extra: dict = {}
    if custom is not None:
        import json
        extra["custom_data"] = json.dumps(custom)

    _thread.send_now(
        status=status,
        message=message,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        iteration_count=iteration_count,
        memory_mb=memory_mb,
        **extra,
    )


def log_tool_call(name: str, args_summary: str = "") -> None:
    """
    Record a tool call for semantic drift analysis.

    Called automatically when auto_cost=True and OpenAI/Anthropic SDK tool calls are detected.
    Call manually for custom tool frameworks or when auto_cost is disabled.

    The last 20 tool calls are included in each heartbeat payload for the
    semantic detector to check against the agent's task_description.

    Example:
        response = client.chat.completions.create(...)
        # Automatically captured if auto_cost=True

        # Or manually:
        clevagent.log_tool_call("db_query", "SELECT * FROM orders WHERE status='pending'")
    """
    _state.log_tool_call(name=name, args_summary=args_summary)


def log_cost(tokens: int, cost_usd: float, model: Optional[str] = None) -> None:  # noqa: ARG001
    """
    Explicitly log cost data. Use this as a fallback when auto_cost is
    unavailable or when you want precise cost accounting.

    Example:
        response = client.messages.create(...)
        clevagent.log_cost(
            tokens=response.usage.input_tokens + response.usage.output_tokens,
            cost_usd=0.0045,
        )
    """
    _state.accumulate_cost(tokens=tokens, cost_usd=cost_usd)


def log_iteration(count: int) -> None:
    """
    Log the current iteration count. Used by the loop detector to identify
    runaway agents that keep incrementing without progress.
    """
    _state._iteration_count = count


def shutdown() -> None:
    """
    Stop the heartbeat thread and clean up all resources.

    Sends a final "shutdown" heartbeat so the server knows the agent
    stopped intentionally (not crashed). Auto-called on SIGTERM/SIGINT.
    """
    global _thread
    if _thread is not None:
        _thread.stop(send_final=True)
        _thread = None

    # Restore sys.excepthook
    from clevagent._crash_handler import _original_excepthook
    import sys
    if sys.excepthook is not sys.__excepthook__:
        sys.excepthook = _original_excepthook

    # Restore signal handlers to default
    import signal
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except (OSError, ValueError):
        pass  # Not in main thread or restricted environment

    # Restore monkey-patched SDK methods
    try:
        from clevagent._cost_tracker import uninstall_auto_cost
        uninstall_auto_cost()
    except (ImportError, Exception):
        pass

    _state.initialized = False
    logger.info("ClevAgent shutdown complete")
