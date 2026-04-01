"""
ClevAgent step callback for CrewAI.

Usage:
    from clevagent.integrations.crewai import clevagent_step_callback

    crew = Crew(
        agents=[...],
        tasks=[...],
        step_callback=clevagent_step_callback,
    )
"""
from typing import Any
import clevagent


def clevagent_step_callback(step_output: Any) -> None:
    """
    CrewAI step callback that pings ClevAgent after each agent step.

    Pass this to Crew(step_callback=clevagent_step_callback).
    """
    message = str(step_output)[:200] if step_output else "step completed"
    clevagent.ping(status="ok", message=message)
