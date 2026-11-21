import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.family.profile import create_family_session


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "family-miot-profile.json"


class FamilyProfileTests(unittest.TestCase):
    def test_profile_controls_confirmed_packet_after_reset(self):
        with patch.dict("os.environ", {"LIVINGMIND_FAMILY_MIOT_PROFILE": str(EXAMPLE)}):
            session = create_family_session()
        for _ in range(2):
            proposed = session.dispatch("POST", "/events", {"eventId": "arrival", "type": "arrival", "memberId": "mother"})
            self.assertEqual(proposed["receipts"], [])
            result = session.dispatch("POST", "/decision", {"suggestionId": proposed["suggestion"]["id"],
                                      "decision": "confirm", "memberId": "mother"})
            receipts = {r["deviceId"]: r for r in result["receipts"]}
            packet = {"did": "demo-lamp-01", "siid": 3, "piid": 7, "value": 45}
            self.assertEqual(receipts["living-light"]["propertyRequest"], packet)
            self.assertEqual(receipts["living-light"]["readReply"], {**packet, "code": 0})
            self.assertEqual(receipts["living-light"]["source"], "simulated")
            self.assertEqual(receipts["living-ac"]["propertyRequest"]["did"], "sim-living-ac")
            session.dispatch("POST", "/reset", {})

    def test_invalid_binding_fails_at_startup(self):
        lamp = {"deviceId": "living-light", "did": "demo-1", "siid": 2, "piid": 7}
        profiles = ([], [lamp, lamp], [{**lamp, "deviceId": "absent"}], [{**lamp, "piid": True}],
                    [{**lamp, "did": ""}], [{**lamp, "did": "sim-desk-light", "piid": 2}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            for profile in profiles:
                with self.subTest(profile=profile):
                    path.write_text(json.dumps(profile), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Cannot load MIoT simulation profile"):
                        create_family_session(path)
