"""Offline registry metadata flows through family planning, validation and simulated readback."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.family.agents import capability_actions
from app.family.gateway import MiotPropertyGateway, VirtualFamilyGateway, property_packet, supports_value
from app.family.profile import bind_addresses, create_family_session
from app.family.service import FamilyEvening, FamilyError


PROFILE = Path(__file__).resolve().parents[1] / "examples" / "family-miot-two-models.json"


class ModelProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def test_two_model_study_plan_reads_actual_property_addresses_on_confirmation(self):
        family = create_family_session(profile_path=PROFILE)
        for _ in range(2):
            view = family.dispatch("POST", "/events", {"type": "study", "memberId": "child", "eventId": "read"})
            self.assertEqual(view["receipts"], [])
            self.assertEqual({a["deviceId"] for a in view["suggestion"]["actions"]}, {"desk-light", "study-fan"})
            result = family.dispatch("POST", "/decision", {"decision": "confirm", "memberId": "child",
                                                           "suggestionId": view["suggestion"]["id"]})
            actual = {}
            for receipt in result["receipts"]:
                self.assertEqual((receipt["status"], receipt["source"]), ("confirmed", "simulated"))
                self.assertEqual(receipt["readReply"], {**receipt["propertyRequest"], "code": 0})
                actual[receipt["deviceId"]] = receipt["propertyRequest"]
            self.assertEqual(actual, {"desk-light": {"did": "sim-model-desk-lamp", "siid": 2, "piid": 2, "value": 75},
                                      "study-fan": {"did": "sim-model-study-fan", "siid": 2, "piid": 4, "value": 1}})
            family.dispatch("POST", "/reset", {})

    def test_import_exposes_exact_native_access_bounds_enums_and_instance_identity(self):
        devices = {d["id"]: d for d in bind_addresses(self.profile)}
        lamp = devices["desk-light"]
        fan = devices["study-fan"]
        self.assertEqual(lamp["modelSpec"]["model"], "yeelink.light.lamp4")
        self.assertTrue(lamp["modelSpec"]["source"].endswith(lamp["modelSpec"]["urn"]))
        self.assertEqual(lamp["capability"]["unit"], "percentage")
        self.assertEqual(lamp["capability"]["valueRange"], [1, 100, 1])
        info = next(p for p in lamp["modelSpec"]["properties"] if p["property"] == "model")
        self.assertEqual((info["siid"], info["piid"], info["format"], info["access"]), (1, 2, "string", ["read"]))
        catalog = {p["piid"]: p for p in fan["modelSpec"]["properties"]}
        self.assertEqual(catalog[4]["access"], ["read", "write", "notify"])
        self.assertEqual([o["value"] for o in catalog[4]["valueList"]], [1, 2, 3, 4])
        self.assertEqual(catalog[6]["property"], catalog[4]["property"])
        self.assertEqual(catalog[6]["valueRange"], [1, 100, 1])
        self.assertTrue(supports_value(catalog[5], 140))
        self.assertFalse(supports_value(catalog[5], 135))
        self.assertEqual(catalog[7]["access"], ["write"])
        self.assertNotIn("modelSpec", devices["living-ac"])

    def test_sparse_enum_is_enforced_in_planning_edit_write_and_readback(self):
        # Exercise a sparse fan gear variant in addition to the registry's actual sparse swing-angle enum.
        fan_entry = self.profile["models"]["dmaker.fan.p5"]["instance"]["services"][0]["properties"][0]
        fan_entry["value-list"] = [{"value": 1, "description": "Low"}, {"value": 4, "description": "High"}]
        self.profile["bindings"][1]["initial"] = 4
        devices = bind_addresses(self.profile)
        by_id = {d["id"]: d for d in devices}
        fan = by_id["study-fan"]
        self.assertEqual(capability_actions([("study-fan", 2)], by_id), ([], ["study-fan"]))
        transport = Mock()
        gateway = MiotPropertyGateway([fan], transport)
        self.assertEqual(gateway.submit("denied", "study-fan", 2)["status"], "rejected")
        transport.write_property.assert_not_called()
        address = property_packet(fan)
        transport.write_property.return_value = {**address, "code": 0}
        transport.read_property.return_value = {**address, "code": 0, "value": 2}
        result = gateway.submit("readback", "study-fan", 1)
        self.assertEqual((result["status"], result["observed"]), ("unknown", None))
        family = FamilyEvening(gateway_factory=lambda: VirtualFamilyGateway(devices))
        view = family.dispatch("POST", "/events", {"eventId": "e", "type": "study", "memberId": "child"})
        with self.assertRaisesRegex(FamilyError, "数值超出设备支持范围"):
            family.dispatch("POST", "/decision", {"memberId": "child", "suggestionId": view["suggestion"]["id"],
                                                   "decision": "edit", "onlyDeviceId": "study-fan", "value": 2})
        self.assertEqual(family.state()["receipts"], [])

    def test_read_only_selected_property_never_enters_a_plan_or_transport(self):
        prop = self.profile["models"]["yeelink.light.lamp4"]["instance"]["services"][1]["properties"][0]
        prop["access"] = ["read", "notify"]
        devices = bind_addresses(self.profile)
        by_id = {d["id"]: d for d in devices}
        self.assertEqual(capability_actions([("desk-light", 75)], by_id), ([], ["desk-light"]))
        transport = Mock()
        result = MiotPropertyGateway(devices, transport).submit("ro", "desk-light", 75)
        self.assertEqual(result["status"], "rejected")
        transport.write_property.assert_not_called()

    def test_write_only_property_does_not_acquire_a_readback_on_reconnect(self):
        prop = self.profile["models"]["yeelink.light.lamp4"]["instance"]["services"][1]["properties"][0]
        prop["access"] = ["write"]
        gateway = VirtualFamilyGateway(bind_addresses(self.profile))
        self.assertEqual(gateway.devices["desk-light"]["mode"], "unknown")
        receipt = gateway.submit("set", "desk-light", 75)
        self.assertEqual((receipt["status"], receipt["readReply"]), ("unknown", None))
        gateway.set_mode("desk-light", "online")
        self.assertIsNone(gateway.devices["desk-light"]["lastObserved"])
        self.assertEqual(gateway.devices["desk-light"]["mode"], "unknown")

    def test_bad_bindings_do_not_substitute_another_property_or_fake_initial_reading(self):
        for update in ({"piid": 5}, {"piid": 10}, {"siid": True}, {"initial": 0}, {"model": "missing"}):
            with self.subTest(update=update):
                profile = json.loads(PROFILE.read_text(encoding="utf-8"))
                profile["bindings"][1].update(update)
                with self.assertRaises(ValueError):
                    bind_addresses(profile)
        lamp_service = self.profile["models"]["yeelink.light.lamp4"]["instance"]["services"][1]
        lamp_service["properties"][0]["unit"] = "kelvin"
        with self.assertRaisesRegex(ValueError, "unit"):
            bind_addresses(self.profile)
        lamp_service["properties"].append(lamp_service["properties"][0])
        with self.assertRaisesRegex(ValueError, "Repeated property"):
            bind_addresses(self.profile)
