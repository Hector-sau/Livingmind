from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.api.errors import ApiError
from app.clock import Clock
from app.contracts import MemoryView, Person, RestPreference, SpaceRule
from app.demo import seed


@dataclass
class PersonContext:
    """What an agent may know about the acting person."""

    person: Person  # with the current preference filled in
    preference: RestPreference
    shared_rules: list[SpaceRule]


class MemoryService:
    def __init__(self, clock: Clock):
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._prefs: dict[str, RestPreference] = {
            p.person_id: p.rest_preference.model_copy() for p in seed.PERSONS if p.rest_preference
        }
        self._updated: dict[str, datetime] = {}

    def _person(self, person_id: str) -> Person:
        return next(p for p in seed.PERSONS if p.person_id == person_id)

    def preference(self, person_id: str) -> RestPreference:
        return self._prefs[person_id]

    def context_for(self, person_id: str, space_id: str) -> PersonContext:
        pref = self.preference(person_id)
        person = self._person(person_id).model_copy(update={"rest_preference": pref})
        return PersonContext(person=person, preference=pref, shared_rules=list(seed.SPACE_RULES.get(space_id, [])))

    def view(self, person_id: str, space_id: str) -> MemoryView:
        person = self._person(person_id)
        return MemoryView(
            person_id=person_id,
            is_guest=person.is_guest,
            preference=self.preference(person_id),
            editable=not person.is_guest,
            updated_at=self._updated.get(person_id),
            shared_rules=list(seed.SPACE_RULES.get(space_id, [])),
        )

    def update(self, person_id: str, preference: RestPreference) -> Optional[str]:
        """Update one's own preference. Returns a short change description."""
        person = self._person(person_id)
        if person.is_guest:
            raise ApiError("NOT_EDITABLE", "访客没有个人偏好，不能编辑", {"personId": person_id})
        if preference.light_brightness > seed.NIGHT_LIGHT_MAX:
            raise ApiError(
                "VALIDATION_ERROR",
                f"休息偏好的灯光不能超过 {seed.NIGHT_LIGHT_MAX}%（空间规则）",
                {"field": "lightBrightness"},
            )
        old = self._prefs[person_id]
        self._prefs[person_id] = preference.model_copy()
        self._updated[person_id] = self._clock()
        changes = []
        if old.light_brightness != preference.light_brightness:
            changes.append(f"灯光 {old.light_brightness}%→{preference.light_brightness}%")
        if old.ac_target_temp_c != preference.ac_target_temp_c:
            changes.append(f"空调 {old.ac_target_temp_c:g}°C→{preference.ac_target_temp_c:g}°C")
        if old.curtain_open_percent != preference.curtain_open_percent:
            changes.append(f"窗帘 {old.curtain_open_percent}%→{preference.curtain_open_percent}%")
        return "、".join(changes) or "没有变化"
