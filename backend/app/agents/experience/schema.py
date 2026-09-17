"""Structured output the model must produce. Validated with Pydantic before anything else happens."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExperienceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=60, description="体验目标，一句话，中文")
    rationale: str = Field(min_length=1, max_length=160, description="为什么这样设置，一句话，中文")
    light_brightness: int = Field(ge=0, le=100)
    ac_target_temp_c: float = Field(ge=16, le=30)
    curtain_open_percent: int = Field(ge=0, le=100)
    needs_clarification: bool = False
    clarification_question: Optional[str] = Field(default=None, max_length=120)


OUTPUT_FORMAT_HINT = """{
  "goal": "string, <=60 chars, Chinese",
  "rationale": "string, <=160 chars, Chinese",
  "light_brightness": integer 0-100,
  "ac_target_temp_c": number 16-30 (one decimal at most),
  "curtain_open_percent": integer 0-100,
  "needs_clarification": boolean,
  "clarification_question": string or null
}"""
