"""Experience Agent: turns a person's utterance + preferences into a structured experience plan.

It only proposes settings. It never writes devices: its output becomes a Plan that goes through
the same confirmation and Executor path as rule plans.
"""

from app.agents.experience.agent import ExperienceAgent, ExperienceError, ExperienceResult
from app.agents.experience.schema import ExperienceOutput

__all__ = ["ExperienceAgent", "ExperienceError", "ExperienceResult", "ExperienceOutput"]
