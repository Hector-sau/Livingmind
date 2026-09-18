"""Interface reservation for a future smart-speaker/voice gateway.

No microphone, cloud transcription, or wake-word implementation is included in
the demo. A gateway should return text plus provenance, then invoke the same
assistant-message contract as the tablet UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class VoiceTranscript:
    audio_id: str
    text: str
    source: str
    captured_at_iso: str
    language: str = "zh-CN"
    speaker_id: Optional[str] = None
    space_id: Optional[str] = None
    confidence: Optional[float] = None


@runtime_checkable
class VoiceInputAdapter(Protocol):
    def transcribe(self, audio: bytes) -> VoiceTranscript: ...


@runtime_checkable
class VoiceGateway(VoiceInputAdapter, Protocol):
    """Future smart-speaker seam. Identity resolution still belongs to the application service."""

    def speak(self, space_id: str, text: str, response_id: str) -> None: ...

    def cancel(self, response_id: str) -> None: ...
