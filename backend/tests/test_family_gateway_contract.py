"""MIoT property transport contract checks. No Xiaomi account, SDK or network is used."""
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from app.family.gateway import DEVICES, MiotPropertyGateway, VirtualFamilyGateway, fixture, property_packet


class PropertyTransportTests(unittest.TestCase):
    def setUp(self):
        self.prop = fixture("lamp", "阅读灯", "study", "light", "brightness", "%", 15,
                            [0, 100, 1], did="example-device", siid=5, piid=8)
        self.address = {"did": "example-device", "siid": 5, "piid": 8}
        self.transport = Mock(spec=["write_property", "read_property"])
        self.transport.write_property.return_value = {**self.address, "code": 0}
        self.transport.read_property.return_value = {**self.address, "code": 0, "value": 37}
        self.gateway = MiotPropertyGateway([self.prop], self.transport)

    def test_custom_address_is_used_for_both_operations(self):
        self.transport.write_property.return_value["code"] = 1
        receipt = self.gateway.submit("trial", "lamp", 37)
        self.transport.write_property.assert_called_once_with({**self.address, "value": 37})
        self.transport.read_property.assert_called_once_with(self.address)
        self.assertEqual(receipt["status"], "confirmed")
        self.assertEqual(receipt["source"], "injected-transport")
        self.assertEqual(self.gateway.snapshot()[0]["lastObserved"], 37)

    def test_observed_mismatch_reports_and_preserves_the_actual_value(self):
        self.transport.read_property.return_value["value"] = 29
        receipt = self.gateway.submit("trial", "lamp", 37)
        self.assertEqual((receipt["status"], receipt["requested"], receipt["observed"]), ("mismatch", 37, 29))
        self.assertEqual(self.gateway.snapshot()[0]["value"], 29)

    def test_uncertain_observation_keeps_previous_value_and_prevents_reexecution(self):
        bad_replies = [None, [], {**self.address, "code": 0, "value": True},
                       {**self.address, "code": 0, "value": 110}, {**self.address, "code": -1, "value": 37}]
        for field, wrong in (("did", "another"), ("siid", 4), ("piid", 6)):
            bad_replies.append({**self.address, field: wrong, "code": 0, "value": 37})
        for reply in bad_replies:
            with self.subTest(reply=reply):
                self.transport.reset_mock()
                self.transport.read_property.return_value = reply
                gateway = MiotPropertyGateway([self.prop], self.transport)
                receipt = gateway.submit("one", "lamp", 37)
                self.assertEqual((receipt["status"], receipt["observed"]), ("unknown", None))
                self.assertEqual((gateway.snapshot()[0]["lastObserved"], gateway.snapshot()[0]["mode"]), (15, "unknown"))
                self.assertEqual(gateway.submit("one", "lamp", 37), receipt)
                self.transport.write_property.assert_called_once()

    def test_transport_exception_is_unknown_and_concurrent_retries_do_not_reissue(self):
        for at in ("write", "read"):
            with self.subTest(at=at):
                self.transport.reset_mock(side_effect=True)
                getattr(self.transport, at + "_property").side_effect = TimeoutError("transport timed out")
                gateway = MiotPropertyGateway([self.prop], self.transport)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    receipts = list(pool.map(lambda _: gateway.submit("same", "lamp", 37), range(8)))
                self.assertTrue(all(r["status"] == "unknown" for r in receipts))
                self.transport.write_property.assert_called_once()

    def test_unaddressed_or_negative_write_reply_cannot_confirm_or_cause_a_read(self):
        for reply, status in (({**self.address, "did": "wrong", "code": 0}, "unknown"),
                              ({**self.address, "code": -1}, "rejected")):
            with self.subTest(reply=reply):
                self.transport.write_property.return_value = reply
                receipt = self.gateway.submit(status, "lamp", 37)
                self.assertEqual(receipt["status"], status)
                self.transport.read_property.assert_not_called()

    def test_access_and_decimal_step_apply_before_writing(self):
        thermostat = fixture("temp", "温控", "living", "climate", "setpoint", "°C", 22,
                             [16, 30, 0.1], did="example-ac", siid=4, piid=3)
        addr = property_packet(thermostat)
        self.transport.write_property.return_value = {**addr, "code": 0}
        self.transport.read_property.return_value = {**addr, "code": 0, "value": 22.1}
        gateway = MiotPropertyGateway([thermostat], self.transport)
        for value in (22.15, True, 40):
            self.assertEqual(gateway.submit("bad" + str(value), "temp", value)["status"], "rejected")
        self.transport.write_property.assert_not_called()
        self.assertEqual(gateway.submit("ok", "temp", 22.1)["status"], "confirmed")
        thermostat["capability"]["access"] = ["read"]
        read_only = MiotPropertyGateway([thermostat], self.transport)
        self.assertEqual(read_only.submit("ro", "temp", 22.1)["status"], "rejected")
        self.transport.write_property.assert_called_once()

    def test_reconnect_reads_virtual_device_but_preserves_original_receipt(self):
        gateway = VirtualFamilyGateway([self.prop])
        gateway.set_mode("lamp", "unknown")
        lost = gateway.submit("lost", "lamp", 37)
        self.assertEqual((lost["status"], gateway.snapshot()[0]["lastObserved"]), ("unknown", 15))
        gateway.set_mode("lamp", "offline")
        self.assertEqual(gateway.submit("off", "lamp", 80)["status"], "offline")
        gateway.set_mode("lamp", "online")
        self.assertEqual((gateway.snapshot()[0]["mode"], gateway.snapshot()[0]["value"]), ("online", 37))
        self.assertEqual(gateway.submit("lost", "lamp", 37), lost)
        self.assertEqual(lost["propertyRequest"], {**self.address, "value": 37})

    def test_explicit_addresses_do_not_alias_or_change_default_fixtures(self):
        second = copy.deepcopy(self.prop)
        second["id"] = "another-property"
        with self.assertRaises(ValueError):
            MiotPropertyGateway([self.prop, second], self.transport)
        second["capability"]["piid"] += 1
        gateway = VirtualFamilyGateway([self.prop, second])
        gateway.submit("lamp-a", "lamp", 37)
        self.assertEqual(gateway.snapshot()[1]["value"], 15)
        self.assertEqual(property_packet(VirtualFamilyGateway().snapshot()[0]),
                         {"did": "sim-living-light", "siid": 2, "piid": 2})
        self.assertEqual(DEVICES[0]["value"], 0)
