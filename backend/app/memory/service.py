from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.api.errors import ApiError
from app.clock import Clock
from app.contracts import MemoryView, Person, RestPreference, SpaceRule
from app.demo import seed
from app.memory.repository import InMemoryPreferenceRepository, PreferenceRepository


@dataclass
class PersonContext:
    """What an agent may know about the acting person."""

    person: Person  # with the current preference filled in
    preference: RestPreference
    shared_rules: list[SpaceRule]


class MemoryService:
    """Preferences live in a repository, so the demo can run in memory or on PostgreSQL."""

    def __init__(self, clock: Clock, repository: Optional[PreferenceRepository] = None):
        self._clock = clock
        self._repo: PreferenceRepository = repository or InMemoryPreferenceRepository()
        self.ensure_seeded()

    def ensure_seeded(self) -> None:
        """Write the seeded preferences for anyone who has none yet. Never overwrites an edit."""
        for person in seed.PERSONS:
            if person.rest_preference and self._repo.get(person.person_id) is None:
                self._repo.put(person.person_id, person.rest_preference, None)

    def reset(self) -> None:
        self._repo.clear()
        self.ensure_seeded()

    def _person(self, person_id: str) -> Person:
        return next(p for p in seed.PERSONS if p.person_id == person_id)

    def _stored(self, person_id: str):
        stored = self._repo.get(person_id)
        if stored is None:  # a person known to the seed but missing from the store
            person = self._person(person_id)
            assert person.rest_preference is not None
            self._repo.put(person_id, person.rest_preference, None)
            stored = self._repo.get(person_id)
            assert stored is not None
        return stored

    def preference(self, person_id: str) -> RestPreference:
        return self._stored(person_id).preference

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
            updated_at=self._stored(person_id).updated_at,
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
        old = self.preference(person_id)
        self._repo.put(person_id, preference, self._clock())
        changes = []
        if old.light_brightness != preference.light_brightness:
            changes.append(f"灯光 {old.light_brightness}%→{preference.light_brightness}%")
        if old.ac_target_temp_c != preference.ac_target_temp_c:
            changes.append(f"空调 {old.ac_target_temp_c:g}°C→{preference.ac_target_temp_c:g}°C")
        if old.curtain_open_percent != preference.curtain_open_percent:
            changes.append(f"窗帘 {old.curtain_open_percent}%→{preference.curtain_open_percent}%")
        return "、".join(changes) or "没有变化"
