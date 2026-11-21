"""Verify the public speaker response for both decisions, without installing a model."""
import io
import json
import subprocess
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.family.api import family_app


class SpeakerResponseTests(unittest.TestCase):
    def test_per_profile_diagnostics_stay_off_the_http_response(self):
        audio = io.BytesIO()
        with wave.open(audio, "wb") as stream:
            stream.setparams((1, 2, 8000, 0, "NONE", "PCM"))
            stream.writeframes(bytes(16000))

        with TestClient(family_app()) as client:
            for comparison, candidate in (("candidate", "mother"), ("unknown", None)):
                local_result = {"comparison": comparison, "candidate": candidate,
                                "scores": {"mother": 0.65, "father": 0.2},
                                "threshold": 0.25, "required_margin": 0.1}
                worker = subprocess.CompletedProcess([], 0, json.dumps(local_result), "")
                with self.subTest(comparison=comparison), \
                     patch("app.family.speaker_upload.config", return_value=(Path("model"), [])), \
                     patch("app.family.speaker_upload.subprocess.run", return_value=worker):
                    response = client.post("/speaker/identify", content=audio.getvalue(),
                                           headers={"Content-Type": "audio/wav"})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {
                        "candidate": candidate, "comparison": comparison, "deviceAuthorized": False})
