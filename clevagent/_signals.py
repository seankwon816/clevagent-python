"""SIGTERM/SIGINT signal handler — calls clevagent.shutdown() on process termination.

Must be installed from the main thread; safely skips if called from a non-main thread
(e.g., when the user embeds clevagent in a thread-based framework).
"""

import logging
import signal

logger = logging.getLogger("clevagent")


def install_signal_handlers() -> None:
    """Register SIGTERM and SIGINT handlers to call clevagent.shutdown()."""

    def _handle(signum: int, frame) -> None:  # noqa: ARG001
        logger.info("clevagent: signal %s received — shutting down gracefully", signum)
        # Import at call-time to avoid circular import at module load
        import clevagent
        clevagent.shutdown()

    try:
        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)
        logger.debug("Signal handlers registered (SIGTERM, SIGINT)")
    except (OSError, ValueError):
        # signal.signal() raises ValueError if called from a non-main thread,
        # and OSError on some restricted environments.
        logger.debug(
            "clevagent: signal handler registration skipped "
            "(not in main thread or restricted environment)"
        )
