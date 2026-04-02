# ClevAgent Python SDK

[![PyPI version](https://badge.fury.io/py/clevagent.svg)](https://pypi.org/project/clevagent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://pypi.org/project/clevagent/)

**Runtime monitoring for AI agents.** Heartbeat watchdog, loop detection, cost tracking, auto-restart — in 2 lines of code.

```python
import clevagent
clevagent.init(api_key="cv_xxx", agent="my-agent")
```

That's it. ClevAgent sends heartbeats every 60 seconds. If your agent goes silent, you get an alert. If it loops, it gets killed. If it crashes, it gets restarted.

## Install

```bash
pip install clevagent
```

Optional extras for auto cost tracking:
```bash
pip install clevagent[openai]     # OpenAI auto-capture
pip install clevagent[anthropic]  # Anthropic auto-capture
pip install clevagent[all]        # Both
```

## Quick Start

```python
import os
import clevagent

clevagent.init(
    api_key=os.environ["CLEVAGENT_API_KEY"],
    agent="my-trading-bot",
    interval=60,          # heartbeat every 60s
    auto_cost=True,       # auto-capture OpenAI/Anthropic token usage
)

# Your agent code runs here — ClevAgent monitors in the background

# Optional: manual ping from inside your work loop (recommended)
clevagent.ping(
    status="ok",
    message="Processed 42 signals",
    tokens_used=1500,
)
```

### Two Levels of Protection

| Level | How | What it catches |
|-------|-----|-----------------|
| **Liveness** (default) | `clevagent.init()` — background thread | Crashes, OOM kills, clean exits |
| **Work-progress** (recommended) | `clevagent.ping()` inside your loop | + Zombie states, hung API calls, logic deadlocks |

## Features

- **Heartbeat watchdog** — detect dead agents in seconds, not hours
- **Loop detection** — catch runaway tool-call loops before they drain your budget
- **Cost tracking** — auto-capture for OpenAI/Anthropic; manual `log_cost()` for others
- **Auto-restart** — restart Docker/systemd/launchd containers when agents die
- **Crash capture** — emergency heartbeat with stack trace on unhandled exceptions
- **Daily reports** — email/Telegram/Slack/Discord summaries of agent health

## Framework Integrations

### LangChain / LangGraph

```python
import clevagent
from clevagent.integrations.langchain import ClevAgentCallbackHandler

clevagent.init(api_key=os.environ["CLEVAGENT_API_KEY"], agent="my-chain")

handler = ClevAgentCallbackHandler()
llm = ChatOpenAI(callbacks=[handler])

# Automatically:
# - Sends heartbeat with token usage after each LLM call
# - Logs tool calls for semantic drift detection
# - Reports errors on LLM/chain failures
```

### CrewAI

```python
import clevagent
from clevagent.integrations.crewai import clevagent_step_callback

clevagent.init(api_key=os.environ["CLEVAGENT_API_KEY"], agent="my-crew")

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    step_callback=clevagent_step_callback,
)
# Pings ClevAgent after each agent step
```

### Any Framework (HTTP API)

Don't use Python? Send heartbeats directly:

```bash
curl -X POST https://clevagent.io/api/v1/heartbeat \
  -H "X-API-Key: cv_xxx" \
  -H "Content-Type: application/json" \
  -d '{"agent": "my-agent", "status": "ok", "tokens_used": 500}'
```

## Cost Tracking

| Method | SDKs |
|--------|------|
| Auto ✅ | OpenAI (`gpt-4o`, `gpt-4o-mini`), Anthropic (`claude-3`, `claude-4`) |
| Manual 📝 | Any SDK — `clevagent.log_cost(tokens=N, cost_usd=X)` |

```python
# Manual cost logging for unsupported SDKs
clevagent.log_cost(tokens=1500, cost_usd=0.0023)
```

## API Reference

| Function | Description |
|----------|-------------|
| `clevagent.init(...)` | Initialize monitoring (call once at startup) |
| `clevagent.ping(...)` | Send manual heartbeat with optional metrics |
| `clevagent.log_cost(...)` | Log token usage and cost manually |
| `clevagent.log_tool_call(...)` | Record tool call for drift detection |
| `clevagent.log_iteration(...)` | Log loop iteration count |
| `clevagent.shutdown()` | Stop monitoring gracefully |

## Links

- **Dashboard**: [clevagent.io](https://clevagent.io)
- **Docs**: [clevagent.io/docs](https://clevagent.io/docs)
- **PyPI**: [pypi.org/project/clevagent](https://pypi.org/project/clevagent/)
- **Issues**: [GitHub Issues](https://github.com/seankwon816/clevagent-python/issues)
- **Support**: [support@clevagent.io](mailto:support@clevagent.io)

## License

MIT — see [LICENSE](LICENSE).

### AutoGen

```python
from clevagent.integrations.autogen import monitored_chat

# Simple wrapper — registers monitoring on both agents
result = monitored_chat(user_proxy, assistant, message="Analyze this data...")

# Or register manually:
from clevagent.integrations.autogen import clevagent_reply_func
assistant.register_reply([Agent], clevagent_reply_func)
```
