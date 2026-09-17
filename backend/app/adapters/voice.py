"""Interface reservation for a future smart-speaker/voice gateway.

No microphone, cloud transcription, or wake-word implementation is included in
the demo. A gateway should return text plus provenance, then invoke the same
assistant-message contract as the tablet UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VoiceTranscript:
    text: str
    source: str
    captured_at_iso: str


class VoiceInputAdapter(Protocol):
    def transcribe(self, audio: bytes) -> VoiceTranscript: ...
