"""
Crash handler — captures unhandled exceptions and sends an emergency heartbeat.

Chains the existing sys.excepthook so other libraries (e.g., IPython, pytest)
are not broken. Only fires if clevagent.init() has been called.
"""

import sys
import traceback

_original_excepthook = sys.excepthook


def _crash_handler(exc_type, exc_value, exc_tb):
    error_msg = f"{exc_type.__name__}: {exc_value}"
    tb_short = "".join(traceback.format_tb(exc_tb)[-3:])

    try:
        from clevagent._state import _state
        if _state.initialized:
            import time
            import json
            from clevagent._client import send_heartbeat
            send_heartbeat(
                endpoint=_state.endpoint,
                api_key=_state.api_key,
                agent=_state.agent,
                status="error",
                message=f"CRASH: {error_msg}",
                custom_data=json.dumps({"traceback": tb_short, "crash": True}),
            )
            time.sleep(1)  # Wait for network request to complete before process exits
    except Exception:
        pass  # Never let crash-capture errors suppress the real traceback

    _original_excepthook(exc_type, exc_value, exc_tb)


def install():
    """Install the crash handler as sys.excepthook."""
    sys.excepthook = _crash_handler
