"""
ClevAgent node callback for LangGraph.

Usage:
    from clevagent.integrations.langgraph import clevagent_node_callback

    def my_node(state):
        result = llm.invoke(state["messages"])
        clevagent_node_callback(node_name="my_node", tokens=result.usage.total_tokens)
        return {"messages": [result]}

Or as a wrapper:
    from clevagent.integrations.langgraph import monitored_node

    @monitored_node("research")
    def research_node(state):
        return llm.invoke(state["messages"])
"""
from typing import Any, Callable, Optional
import functools
import clevagent


def clevagent_node_callback(
    node_name: str,
    status: str = "ok",
    tokens: Optional[int] = None,
    message: Optional[str] = None,
) -> None:
    """
    Call after a LangGraph node executes. Sends a heartbeat ping.

    Args:
        node_name: Name of the graph node that just executed.
        status: "ok", "warning", or "error".
        tokens: Token count from this node's LLM call (if any).
        message: Optional status message.
    """
    msg = message or f"node:{node_name}"
    clevagent.ping(status=status, message=msg, tokens_used=tokens)


def monitored_node(node_name: str) -> Callable:
    """
    Decorator that wraps a LangGraph node function with ClevAgent monitoring.

    Usage:
        @monitored_node("research")
        def research_node(state):
            result = llm.invoke(state["messages"])
            return {"messages": [result]}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = func(state, *args, **kwargs)
                clevagent.ping(status="ok", message=f"node:{node_name} completed")
                return result
            except Exception as e:
                clevagent.ping(status="error", message=f"node:{node_name} error: {str(e)[:150]}")
                raise
        return wrapper
    return decorator
