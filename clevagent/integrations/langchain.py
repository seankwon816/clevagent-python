"""
ClevAgent callback handler for LangChain / LangGraph.

Usage:
    from clevagent.integrations.langchain import ClevAgentCallbackHandler

    handler = ClevAgentCallbackHandler()
    llm = ChatOpenAI(callbacks=[handler])
    # or
    chain.invoke(input, config={"callbacks": [handler]})
"""
from typing import Any, Optional
import clevagent


class ClevAgentCallbackHandler:
    """LangChain callback that sends heartbeat pings with token/cost data."""

    def __init__(self, ping_on_llm_end: bool = True, ping_on_chain_end: bool = False):
        self.ping_on_llm_end = ping_on_llm_end
        self.ping_on_chain_end = ping_on_chain_end
        self._total_tokens = 0
        self._total_cost = 0.0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Called when LLM call completes. Sends heartbeat with token usage."""
        tokens = 0
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            tokens = usage.get("total_tokens", 0)
        self._total_tokens += tokens
        if self.ping_on_llm_end and tokens > 0:
            clevagent.ping(status="ok", tokens_used=tokens)

    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        """Called when chain completes."""
        if self.ping_on_chain_end:
            clevagent.ping(status="ok", message="chain completed")

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        """Log tool calls for semantic drift detection."""
        name = serialized.get("name", "unknown_tool")
        clevagent.log_tool_call(name, input_str[:200])

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Report LLM errors."""
        clevagent.ping(status="error", message=f"LLM error: {str(error)[:200]}")

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        """Report chain errors."""
        clevagent.ping(status="error", message=f"Chain error: {str(error)[:200]}")
