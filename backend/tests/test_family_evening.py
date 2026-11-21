"""stdlib-compatible regression tests; run from backend with unittest discovery."""
import itertools
from concurrent.futures import ThreadPoolExecutor
import unittest

from app.family.agents import capability_actions
from app.family.gateway import VirtualFamilyGateway, decode_observation, property_packet
from app.family.service import FamilyEvening, FamilyError


class EveningTests(unittest.TestCase):
    def setUp(self):
        self.house = FamilyEvening()
        self.ids = itertools.count()

    def post(self, path, **data):
        return self.house.dispatch("POST", path, data)

    def event(self, typ="arrival", member="mother", **extra):
        return self.post("/events", eventId=str(next(self.ids)), type=typ, memberId=member, **extra)

    def decide(self, choice, **data):
        plan = self.house.state()["suggestion"]
        return self.post("/decision", suggestionId=plan["id"], memberId=plan["memberId"], decision=choice, **data)

    @staticmethod
    def actions(state):
        return {a["deviceId"]: a["value"] for a in state["suggestion"]["actions"]}

    def test_arrival_plans_without_writing(self):
        before = self.house.state()
        proposed = self.event()
        self.assertEqual(self.actions(proposed), {"living-light": 45, "living-curtain": 45, "living-ac": 25})
        self.assertEqual(proposed["devices"], before["devices"])
        self.assertEqual(proposed["receipts"], [])
        self.assertEqual(len(proposed["suggestion"]["trace"]), 3)
        self.assertEqual(proposed["plannerSource"], "rule")
        done = self.decide("confirm")
        self.assertEqual(done["lastOutcome"], "confirmed")
        self.assertEqual(len(done["receipts"]), 3)

    def test_three_members_have_distinct_preferences(self):
        for mid, target in [("mother", 45), ("father", 55), ("child", 50)]:
            self.assertEqual(self.actions(self.event(member=mid))["living-light"], target)

    def test_partial_failures_preserve_per_device_receipts(self):
        self.event()
        self.post("/devices", deviceId="living-ac", mode="unknown")
        self.post("/devices", deviceId="living-light", mode="offline")
        state = self.decide("confirm")
        self.assertEqual(state["lastOutcome"], "incomplete")
        receipts = {r["deviceId"]: r for r in state["receipts"]}
        self.assertIsNone(receipts["living-ac"]["observed"])
        self.assertEqual(receipts["living-ac"]["writeReply"]["code"], 0)
        self.assertEqual(receipts["living-ac"]["status"], "unknown")
        self.assertEqual(receipts["living-light"]["status"], "offline")
        self.assertEqual(receipts["living-curtain"]["observed"], 45)

    def test_gated_tonight_only_changes_expire(self):
        before = self.house.state()
        sid = self.event()["suggestion"]["id"]
        edited = self.decide("edit", text="我今晚还要看书，客厅亮一点，卧室先别动")
        self.assertEqual(self.actions(edited), {"living-light": 65})
        self.assertEqual(edited["devices"], before["devices"])
        with self.assertRaises(FamilyError):
            self.post("/decision", suggestionId=sid, memberId="mother", decision="confirm")
        done = self.decide("confirm")
        self.assertEqual(len(done["receipts"]), 1)
        self.assertEqual(self.event()["lastOutcome"], "coalesced")
        self.assertEqual(self.event()["lastOutcome"], "coalesced")
        self.assertEqual(self.event()["lastOutcome"], "no_change")
        tomorrow = self.post("/next-day")
        self.assertEqual(tomorrow["day"], 2)
        self.assertEqual(tomorrow["members"], before["members"])
        self.assertEqual(self.actions(self.event())["living-light"], 45)
        self.assertIn("next_day", [v["kind"] for v in tomorrow["timeline"]])

    def test_scope_edits_are_conservative(self):
        plan = self.event()["suggestion"]
        for text in ["今晚客厅都处理掉", "今晚只调客厅灯到999%", "今晚只调客厅灯到30度", "今晚只开客厅灯并打开空调"]:
            with self.subTest(text=text), self.assertRaises(FamilyError):
                self.decide("edit", text=text)
        self.assertEqual(self.house.state()["suggestion"], plan)
        self.assertEqual(self.actions(self.decide("edit", text="今晚只开客厅灯，空调先别开")), {"living-light": 45})

    def test_decisions_reject_other_members(self):
        sid = self.event()["suggestion"]["id"]
        for decision in ("confirm", "dismiss", "edit", "mute"):
            with self.assertRaises(FamilyError) as caught:
                self.post("/decision", suggestionId=sid, memberId="father", decision=decision)
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.house.state()["receipts"], [])

    def test_atomic_concurrent_confirmation(self):
        sid = self.event()["suggestion"]["id"]
        def confirm(_):
            return self.post("/decision", suggestionId=sid, memberId="mother", decision="confirm")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(confirm, range(6)))
        self.assertEqual(len(self.house.gateway.receipts), 3)
        self.assertEqual(sum(e["kind"] == "confirmed" for e in results[-1]["timeline"]), 1)

    def test_mute_and_dismiss_have_different_scopes(self):
        self.event()
        self.decide("dismiss")
        self.assertIsNotNone(self.event("study", "child")["suggestion"])
        self.decide("mute")
        muted = self.event("tv", "father")
        self.assertIsNone(muted["suggestion"])
        self.assertTrue(muted["muted"])
        self.assertFalse(self.post("/next-day")["muted"])
        self.assertIsNotNone(self.event("tv", "father")["suggestion"])

    def test_snooze_expires_by_simulated_time(self):
        self.event()
        self.decide("snooze")
        for _ in range(5):
            self.assertIsNone(self.event()["suggestion"])
        self.assertIsNotNone(self.event()["suggestion"])

    def test_uncertain_and_duplicate_signals(self):
        first = self.post("/events", eventId="u", type="unknown_arrival")
        self.assertFalse(first["suggestion"])
        self.assertEqual(first["lastOutcome"], "identity_uncertain")
        duplicate = self.post("/events", eventId="u", type="unknown_arrival")
        self.assertEqual(duplicate["timeline"], first["timeline"])
        with self.assertRaises(FamilyError):
            self.post("/events", eventId="u", type="arrival", memberId="mother")

    def test_new_id_same_signal_preserves_edited_plan(self):
        self.event()
        edit = self.decide("edit", text="今晚只调客厅灯到 35%")
        repeated = self.event()
        self.assertEqual(repeated["lastOutcome"], "coalesced")
        self.assertEqual(repeated["suggestion"], edit["suggestion"])
        self.assertEqual(repeated["timeline"], edit["timeline"])
        self.assertEqual(repeated["devices"], edit["devices"])
        self.assertEqual(self.decide("confirm")["receipts"][0]["observed"], 35)

    def test_dismissed_arrival_does_not_return_on_next_sensor_tick(self):
        self.event()
        self.decide("dismiss")
        repeated = self.event()
        self.assertEqual(repeated["lastOutcome"], "coalesced")
        self.assertIsNone(repeated["suggestion"])

    def test_actual_activity_change_invalidates_prior_proposal(self):
        self.event()
        sleeping = self.event("sleep")["suggestion"]["id"]
        returned = self.event()
        self.assertEqual(returned["suggestion"]["eventType"], "arrival")
        with self.assertRaises(FamilyError):
            self.post("/decision", memberId="mother", suggestionId=sleeping, decision="confirm")

    def test_study_tv_sleep_have_observable_shared_constraints(self):
        self.assertEqual(self.actions(self.event("study", "child")), {"desk-light": 75, "study-fan": 1})
        self.decide("confirm")
        self.assertEqual(self.actions(self.event("tv", "father")), {"living-light": 20, "living-speaker": 18})
        with self.assertRaises(FamilyError):
            self.decide("edit", onlyDeviceId="living-speaker", value=90)
        self.decide("confirm")
        sleeping = self.actions(self.event("sleep", "mother"))
        self.assertEqual(sleeping, {"bed-light": 8, "bed-curtain": 0, "living-speaker": 12})
        done = self.decide("confirm")
        desk = next(d for d in done["devices"] if d["id"] == "desk-light")
        self.assertEqual(desk["value"], 75)

    def test_shared_room_preserves_readers_light(self):
        self.event("study", "child", roomId="living")
        self.decide("confirm")
        self.assertEqual(self.actions(self.event("tv", "father")), {"living-speaker": 18})
        self.assertIn("共享灯", self.house.state()["suggestion"]["reason"])

    def test_stale_after_reset(self):
        sid = self.event()["suggestion"]["id"]
        reset = self.post("/reset")
        self.assertEqual(len(reset["timeline"]), 1)
        with self.assertRaises(FamilyError):
            self.post("/decision", suggestionId=sid, memberId="mother", decision="confirm")

    def test_codec_and_receipt_idempotence(self):
        gw = VirtualFamilyGateway()
        device = gw.snapshot()[0]
        addr = {"did": "sim-living-light", "siid": 2, "piid": 2}
        self.assertEqual(property_packet(device, 35), dict(addr, value=35))
        write = dict(addr, code=0)
        self.assertEqual(decode_observation(device, write, None, 35), ("unknown", None))
        self.assertEqual(decode_observation(device, write, dict(write, value=30), 35), ("mismatch", 30))
        self.assertEqual(decode_observation(device, write, dict(write, did="sim-other", value=35), 35), ("unknown", None))
        receipt = gw.submit("key", "living-light", 35)
        gw.set_mode("living-light", "offline")
        self.assertEqual(gw.submit("key", "living-light", 35), receipt)
        with self.assertRaises(ValueError):
            gw.submit("key", "living-light", 22)
        self.assertEqual(capability_actions([("missing", 5), ("living-light", 500)], {"living-light": device}),
                         ([], ["missing", "living-light"]))

    def test_optional_model_cannot_write_or_expand_scope(self):
        class Provider:
            reply = '{"deviceId":"living-light","value":36}'

            def complete_json(self, *_):
                return self.reply

        provider = Provider()
        self.house = FamilyEvening(edit_provider=provider)
        before = self.event()
        for reply in ('{"deviceId":"desk-light","value":36}', '{"clarify":true}', 'garbled',
                      '{"deviceId":"living-light","value":999}'):
            provider.reply = reply
            with self.assertRaises(FamilyError):
                self.decide("edit", text="请把客厅灯设成三成六")
        self.assertEqual(self.house.state()["suggestion"], before["suggestion"])
        provider.reply = '{"deviceId":"living-light","value":36}'
        with self.assertRaises(FamilyError):
            self.decide("edit", text="别设客厅灯到三成六")
        after = self.decide("edit", text="请把客厅灯设成三成六")
        self.assertEqual(after["suggestion"]["editSource"], "model")
        self.assertEqual(after["devices"], before["devices"])
        self.assertEqual(self.actions(after), {"living-light": 36})
        self.assertEqual(self.decide("confirm")["receipts"][0]["observed"], 36)

    def test_model_result_cannot_revive_a_dismissed_plan(self):
        class Provider:
            def complete_json(provider, *_):
                self.decide("dismiss")
                return '{"deviceId":"living-light","value":36}'

        self.house = FamilyEvening(edit_provider=Provider())
        self.event()
        with self.assertRaises(FamilyError) as caught:
            self.decide("edit", text="请把客厅灯设成三成六")
        self.assertEqual(caught.exception.status, 409)
        self.assertIsNone(self.house.state()["suggestion"])


if __name__ == "__main__":
    unittest.main()
