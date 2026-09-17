"""Space Execution Agent: turns an experience target (or a direct device command) into device
actions the space can actually perform. It checks capabilities and space rules, but it never
writes devices — confirmed plans are executed by harness/executor.py."""

from app.agents.space_execution.agent import CommandTarget, SpaceExecutionAgent

__all__ = ["CommandTarget", "SpaceExecutionAgent"]
