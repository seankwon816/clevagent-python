"""
ClevAgent reply function for Microsoft AutoGen.

Usage:
    from clevagent.integrations.autogen import clevagent_reply_func

    assistant = AssistantAgent("assistant", llm_config=...)
    assistant.register_reply([Agent], clevagent_reply_func)

Or as a simple wrapper:
    from clevagent.integrations.autogen import monitored_chat

    monitored_chat(user_proxy, assistant, message="Analyze this data...")
"""
from typing import Any, Callable, Optional
import clevagent


def clevagent_reply_func(
    recipient: Any,
    messages: Optional[list] = None,
    sender: Optional[Any] = None,
    config: Optional[Any] = None,
) -> tuple:
    """
    AutoGen reply function that pings ClevAgent after each agent reply.

    Register with: agent.register_reply([Agent], clevagent_reply_func)

    Returns (False, None) to allow normal reply flow to continue.
    """
    if messages:
        last = messages[-1] if messages else {}
        content = last.get("content", "") if isinstance(last, dict) else str(last)
        role = last.get("role", "unknown") if isinstance(last, dict) else "unknown"

        # Estimate tokens (rough: 1 token per 4 chars)
        token_estimate = len(content) // 4 if content else 0

        agent_name = getattr(recipient, "name", "unknown")
        clevagent.ping(
            status="ok",
            message=f"autogen:{agent_name} replied ({role})",
            tokens_used=token_estimate,
        )

    # Return (False, None) to not intercept the reply — just observe
    return False, None


def monitored_chat(
    initiator: Any,
    recipient: Any,
    message: str,
    **kwargs: Any,
) -> Any:
    """
    Convenience wrapper that registers monitoring on both agents
    before starting a chat.

    Usage:
        result = monitored_chat(user_proxy, assistant, "Analyze this data...")
    """
    try:
        from autogen import Agent as AutoGenAgent
    except ImportError:
        raise ImportError("autogen is required: pip install pyautogen")

    # Register reply func on recipient if not already registered
    recipient.register_reply([AutoGenAgent], clevagent_reply_func)

    clevagent.ping(status="ok", message=f"autogen:chat started with {recipient.name}")
    result = initiator.initiate_chat(recipient, message=message, **kwargs)
    clevagent.ping(status="ok", message=f"autogen:chat completed with {recipient.name}")
    return result
