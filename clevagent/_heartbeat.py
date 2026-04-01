"""Background heartbeat thread.

A daemon thread sends POST /api/v1/heartbeat every `_state.interval` seconds.
On shutdown(), a final "shutdown" heartbeat is sent before the thread exits.
The stop event allows immediate wake-up when shutdown() is called mid-sleep.
"""

import logging
import os
import sys
import threading
from typing import Any, Optional

from ._client import send_heartbeat
from ._state import _state

logger = logging.getLogger("clevagent")


class HeartbeatThread(threading.Thread):

    def __init__(self) -> None:
        super().__init__(daemon=True, name="clevagent-heartbeat")
        self._stop_event = threading.Event()

    def run(self) -> None:
        logger.debug(
            "Heartbeat thread started (agent=%s interval=%ds endpoint=%s)",
            _state.agent, _state.interval, _state.endpoint,
        )
        # Send initial heartbeat immediately so the server knows the agent is alive.
        self._send_heartbeat()

        # wait(timeout) returns True if stop was requested, False on timeout.
        # Loop continues as long as the event is NOT set (i.e., normal operation).
        while not self._stop_event.wait(timeout=_state.interval):
            self._send_heartbeat()

    def _send_heartbeat(
        self,
        status: str = "ok",
        message: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Send one heartbeat, including accumulated cost/usage data."""
        data = _state.flush_and_reset()
        if extra:
            data.update({k: v for k, v in extra.items() if v is not None})

        resp = send_heartbeat(
            endpoint=_state.endpoint,
            api_key=_state.api_key,
            agent=_state.agent,
            status=status,
            message=message,
            **data,
        )

        if resp and resp.get("agent_id"):
            _state.agent_id = resp["agent_id"]
            logger.debug("Heartbeat OK — agent_id=%s server_status=%s",
                         _state.agent_id, resp.get("status"))

        # Handle server-side warning (loop detected / cost exceeded)
        # Skip during shutdown — _stop_event is set, process is already exiting
        if resp and resp.get("warning") and not self._stop_event.is_set():
            warning = resp["warning"]
            reason = resp.get("reason", "")
            if warning == "loop_detected":
                action = _state.on_loop
                if action == "stop":
                    print(f"[clevagent] ⚠️ Loop detected: {reason}. Stopping agent.")
                    self._stop_event.set()
                    # CA-6: os._exit instead of sys.exit — sys.exit only kills the thread, not the process
                    os._exit(1)
                elif action == "force_stop":
                    print(f"[clevagent] ⚠️ Loop detected: {reason}. Force-stopping agent.")
                    os._exit(1)
                elif callable(action):
                    print(f"[clevagent] ⚠️ Loop detected: {reason}. Running custom handler.")
                    action()
                else:  # "alert_only"
                    print(f"[clevagent] ⚠️ Loop detected: {reason}. Alert only — no action taken.")
            elif warning == "cost_exceeded":
                action = _state.on_cost_exceeded
                if action == "stop":
                    print(f"[clevagent] ⚠️ Cost exceeded: {reason}. Stopping agent.")
                    self._stop_event.set()
                    # CA-6: os._exit instead of sys.exit — sys.exit only kills the thread, not the process
                    os._exit(1)
                elif action == "force_stop":
                    print(f"[clevagent] ⚠️ Cost exceeded: {reason}. Force-stopping agent.")
                    os._exit(1)
                elif callable(action):
                    print(f"[clevagent] ⚠️ Cost exceeded: {reason}. Running custom handler.")
                    action()
                else:  # "alert_only"
                    print(f"[clevagent] ⚠️ Cost exceeded: {reason}. Alert only — no action taken.")

    def send_now(
        self,
        status: str = "ok",
        message: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Trigger an immediate out-of-band heartbeat (used by ping())."""
        self._send_heartbeat(status=status, message=message, extra=extra)

    def stop(self, send_final: bool = True) -> None:
        """Signal the thread to stop. If send_final=True, sends a shutdown heartbeat."""
        self._stop_event.set()
        if send_final:
            try:
                self._send_heartbeat(status="shutdown", message="Agent shutting down gracefully")
            except Exception as exc:
                logger.debug("Final heartbeat skipped: %s", exc)
        self.join(timeout=10)
        logger.debug("Heartbeat thread stopped")
