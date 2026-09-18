"""State carried between graph nodes.

Only data goes in here. Device adapters, id generators and the agents themselves are
dependencies of the runtime, not state, so a checkpoint never tries to serialise a socket
or a function. Everything below is either a plain value or a contract model.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from app.contracts import AgentStep, EnergyAdvice, Plan, PlannerMode, WakeTime


def _extend(current: list[AgentStep], new: list[AgentStep]) -> list[AgentStep]:
    """Trace steps accumulate in node order."""
    return [*current, *new]


class LivingMindState(TypedDict, total=False):
    # request
    request_id: str
    account_id: str
    person_id: str
    space_id: str
    utterance: str
    planner_mode: Optional[PlannerMode]
    energy_mode: str
    wake_time: WakeTime
    forced_intent: Optional[str]
    # routing and intermediates
    intent: str
    person_context: Any  # PersonContext (dataclass of contract models)
    experience: Any  # ExperienceOutcome
    energy_advice: Optional[EnergyAdvice]
    experience_target: Any  # RestPreference after the energy stage
    device_actions: list[Any]
    night_schedule: list[Any]
    execution_notes: list[str]
    # output
    trace: Annotated[list[AgentStep], _extend]
    plan: Optional[Plan]
    answer: Optional[str]
    reply_kind: str
