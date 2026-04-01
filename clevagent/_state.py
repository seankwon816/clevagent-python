"""Shared SDK state — single mutable object shared across all SDK modules."""

import threading
from typing import Optional


class _SDKState:
    """Thread-safe container for SDK runtime state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Configuration (set by init())
        self.api_key: str = ""
        self.agent: str = ""
        self.agent_type: Optional[str] = None  # generic/claude/openai/langchain/custom/foragent-relay/etc.
        self.interval: int = 60
        self.endpoint: str = "https://clevagent.io"
        self.on_loop = "alert_only"        # "stop" | "alert_only" | "force_stop" | callable
        self.on_cost_exceeded = "alert_only"  # "stop" | "alert_only" | callable

        # Runtime
        self.agent_id: Optional[int] = None
        self.auto_cost_active: bool = False
        self.initialized: bool = False

        # Accumulated cost/usage between heartbeats (reset after each send)
        self._tokens: int = 0
        self._cost_usd: float = 0.0
        self._tool_calls: int = 0
        self._iteration_count: Optional[int] = None

        # Tool call log for semantic analysis — max 20 entries, flushed with each heartbeat
        self._tool_call_log: list = []
        self._TOOL_CALL_LOG_MAX = 20

    def accumulate_cost(
        self,
        tokens: int = 0,
        cost_usd: float = 0.0,
        tool_calls: int = 0,
    ) -> None:
        """Thread-safe accumulation of usage data."""
        with self._lock:
            self._tokens += tokens
            self._cost_usd += cost_usd
            self._tool_calls += tool_calls

    def log_tool_call(self, name: str, args_summary: str = "") -> None:
        """Record a tool call for semantic analysis. Thread-safe. Max 20 retained (FIFO)."""
        entry: dict = {"name": name}
        if args_summary:
            entry["args"] = args_summary[:200]  # truncate to prevent bloat
        with self._lock:
            self._tool_call_log.append(entry)
            if len(self._tool_call_log) > self._TOOL_CALL_LOG_MAX:
                self._tool_call_log = self._tool_call_log[-self._TOOL_CALL_LOG_MAX:]

    def flush_and_reset(self) -> dict:
        """Return accumulated data as a dict and reset counters. Thread-safe."""
        with self._lock:
            data = {
                "tokens_used": self._tokens if self._tokens else None,
                "cost_usd": self._cost_usd if self._cost_usd else None,
                "tool_calls": self._tool_calls if self._tool_calls else None,
                "iteration_count": self._iteration_count,
                "tool_call_log": list(self._tool_call_log) if self._tool_call_log else None,
                "agent_type": self.agent_type,  # static config — not reset
            }
            self._tokens = 0
            self._cost_usd = 0.0
            self._tool_calls = 0
            self._tool_call_log = []
            # iteration_count is set externally by log_iteration() — don't reset
            return data


# Module-level singleton
_state = _SDKState()
