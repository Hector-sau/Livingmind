"""Executable checks for the reserved real-device, voice and sensor integration seams."""

from datetime import datetime, timezone

from app.adapters.events import EnvironmentEvent, EnvironmentEventAdapter
from app.adapters.protocol import (
    DeviceCommandReceipt,
    DeviceCommandRequest,
    DeviceDescriptor,
    DeviceGateway,
)
from app.adapters.voice import VoiceGateway, VoiceTranscript


class FakeDeviceGateway:
    def __init__(self):
        self.receipts = {}

    def list_devices(self, space_id):
        return [DeviceDescriptor("lamp-1", space_id, "light", ())]

    def advance_fence(self, space_id, service_epoch):
        self.fence = (space_id, service_epoch)

    def submit(self, request: DeviceCommandRequest):
        receipt = DeviceCommandReceipt(request.action_id, "accepted", None, None)
        self.receipts[request.action_id] = receipt
        return receipt

    def query(self, action_id):
        return self.receipts.get(action_id)


class FakeVoiceGateway:
    def transcribe(self, audio):
        return VoiceTranscript("audio-1", "关灯", "speaker", datetime.now(timezone.utc).isoformat(), space_id="s1")

    def speak(self, space_id, text, response_id):
        return None

    def cancel(self, response_id):
        return None


class FakeEventAdapter:
    def subscribe(self, handler):
        handler(EnvironmentEvent("e1", "sensor:e1", "sensor", "s1", "sleep_detected", datetime.now(timezone.utc), True))
        return lambda: None


def test_reserved_adapter_protocols_have_executable_contract_doubles():
    device = FakeDeviceGateway()
    voice = FakeVoiceGateway()
    events = FakeEventAdapter()
    assert isinstance(device, DeviceGateway)
    assert isinstance(voice, VoiceGateway)
    assert isinstance(events, EnvironmentEventAdapter)

    request = DeviceCommandRequest(
        action_id="a1",
        service_id="svc1",
        service_epoch=3,
        device_id="lamp-1",
        device_type="light",
        command="set_brightness",
        value=20,
        requested_at=datetime.now(timezone.utc),
    )
    assert device.submit(request).status == "accepted"
    assert device.query("a1").action_id == "a1"
    assert voice.transcribe(b"audio").space_id == "s1"
    seen = []
    events.subscribe(seen.append)
    assert seen[0].dedupe_key == "sensor:e1"
