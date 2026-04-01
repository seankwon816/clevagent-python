# ClevAgent SDK

Monitor your AI agents in 2 lines of code.

> Document role:
> - package-level usage guide for the Python SDK
> - focuses on installation and client-side integration
> - broader product policy and accepted cross-system contracts belong in the repo root docs

```python
import clevagent
clevagent.init(api_key=os.environ["CLEVAGENT_API_KEY"], agent="my-agent")
```

That's it. ClevAgent sends heartbeats every 60 seconds. If your agent goes silent, you get an alert.

## Install

```bash
pip install clevagent
```

## Features

- **Heartbeat watchdog** — detect dead agents automatically
- **Loop detection** — catch runaway tool-call loops
- **Cost tracking** — auto-capture for OpenAI/Anthropic SDKs; manual `log_cost()` for others
- **Auto-restart** — restart Docker containers when agents die (requires `container_id`)
- **Crash capture** — send last error as an emergency heartbeat on unhandled exceptions

## Quick Start

```python
import os
import clevagent

clevagent.init(
    api_key=os.environ["CLEVAGENT_API_KEY"],
    agent="my-trading-bot",        # agent name (auto-created on first ping)
    interval=60,                   # heartbeat interval in seconds
    auto_cost=True,                # auto-capture OpenAI/Anthropic usage
)

# --- your agent code runs here ---

# Optional: manual ping with context
clevagent.ping(
    status="ok",
    message="Processed 42 signals",
    iteration_count=42,
)

# Optional: manual cost logging (for other SDKs)
clevagent.log_cost(tokens=1500, cost_usd=0.0023)
```

## Cost Tracking

| Method | SDKs |
|--------|------|
| Auto ✅ | OpenAI (`gpt-4o`, `gpt-4o-mini`, etc.), Anthropic (`claude-3`, `claude-4`) |
| Manual 📝 | Any other SDK — use `clevagent.log_cost(tokens=N, cost_usd=X)` |
| Not supported ❌ | Streaming responses (use manual for those) |

## Auto-Restart

Auto-restart requires Docker and a `container_id` configured in the ClevAgent dashboard. For non-Docker deployments (systemd, launchd, process), use clevagent-runner for auto-restart support. See https://clevagent.io/docs#runner

## Links

- [Dashboard](https://clevagent.io)
- [Documentation](https://clevagent.io/docs)
- [Support](mailto:support@clevagent.io)
