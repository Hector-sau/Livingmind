"""Execution progress, idempotent confirmations and journal recovery with no hardware."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

from app.family.gateway import VirtualFamilyGateway
from app.family.service import FamilyError, FamilyEvening


class MemoryJournal:
    def __init__(self):
        self.latest = None
        self.history = []

    def load(self):
        return deepcopy(self.latest)

    def save(self, checkpoint):
        self.latest = deepcopy(checkpoint)
        self.history.append(self.latest)


def propose_arrival(session):
    snapshot = session.dispatch("POST", "/events", {"type": "arrival", "memberId": "mother", "eventId": "e1"})
    return {"suggestionId": snapshot["suggestion"]["id"], "memberId": "mother", "decision": "confirm"}


class FamilyExecutionTests(unittest.TestCase):
    def test_readers_see_committed_progress_while_confirmation_waits_on_gateway(self):
        entered, release = Event(), Event()

        class SlowSecondAction(VirtualFamilyGateway):
            def submit(self, action_id, device_id, value):
                with self.lock:
                    if device_id == "living-curtain":
                        entered.set()
                        if not release.wait(5):
                            raise RuntimeError("test transport was not released")
                    return super().submit(action_id, device_id, value)

        session = FamilyEvening(gateway_factory=SlowSecondAction)
        request = propose_arrival(session)
        with ThreadPoolExecutor(max_workers=3) as pool:
            confirm = pool.submit(session.dispatch, "POST", "/decision", request)
            try:
                self.assertTrue(entered.wait(2))
                replay = pool.submit(session.dispatch, "POST", "/decision", request)
                progress = pool.submit(session.dispatch, "GET", "/state").result(timeout=1)
                self.assertEqual(progress["lastOutcome"], "executing")
                self.assertIsNone(progress["suggestion"])
                self.assertEqual(progress["execution"], {"suggestionId": request["suggestionId"], "memberId": "mother",
                                                         "completedActions": 1, "totalActions": 3})
                self.assertEqual([r["deviceId"] for r in progress["receipts"]], ["living-light"])
                self.assertEqual(next(d["value"] for d in progress["devices"] if d["id"] == "living-light"), 45)
                progress["receipts"].clear()
                self.assertEqual(len(session.state()["receipts"]), 1)
            finally:
                release.set()
            result = confirm.result(timeout=2)
            retry = replay.result(timeout=2)
        self.assertIsNone(result["execution"])
        self.assertEqual(result["decisionResult"]["outcome"], "confirmed")
        self.assertTrue(retry["decisionReplayed"])
        self.assertEqual(result["decisionResult"], retry["decisionResult"])
        self.assertEqual(len(session.gateway.receipts), 3)

    def test_restart_keeps_completed_action_marks_inflight_unknown_and_never_sends_tail(self):
        writes = []
        journal = MemoryJournal()

        class SimulatedPowerLoss(BaseException):
            pass

        class DeviceGateway(VirtualFamilyGateway):
            def export_state(self):
                return self.snapshot()

            def restore_state(self, data):
                VirtualFamilyGateway.__init__(self, data)

            def mark_unobserved(self, device_id):
                self.set_mode(device_id, "unknown")

            def submit(self, action_id, device_id, value):
                index = len(writes)
                intent = journal.latest["execution"]
                recorded = (intent["dispatching"], intent["actions"][index]["deviceId"])
                writes.append((device_id, recorded))
                result = super().submit(action_id, device_id, value)
                if device_id == "living-curtain":
                    raise SimulatedPowerLoss()
                return result

        session = FamilyEvening(gateway_factory=DeviceGateway, store=journal)
        request = propose_arrival(session)
        with self.assertRaises(SimulatedPowerLoss):
            session.dispatch("POST", "/decision", request)
        with self.assertRaises(FamilyError) as stale_writer:
            session.dispatch("POST", "/events", {"type": "sleep", "memberId": "mother", "eventId": "e2"})
        self.assertEqual(stale_writer.exception.payload["error"]["code"], "RECOVERY_REQUIRED")
        expected_writes = [("living-light", (0, "living-light")), ("living-curtain", (1, "living-curtain"))]
        self.assertEqual(writes, expected_writes)
        self.assertEqual(journal.latest["execution"]["dispatching"], 1)
        self.assertEqual(journal.latest["view"]["execution"]["completedActions"], 1)
        recovered = FamilyEvening(gateway_factory=DeviceGateway, store=journal)
        state = recovered.state()
        self.assertIsNone(state["suggestion"])
        self.assertIsNone(state["execution"])
        self.assertEqual(state["lastOutcome"], "incomplete")
        self.assertEqual([r["status"] for r in state["receipts"]], ["confirmed", "unknown", "skipped"])
        self.assertEqual([r["observed"] for r in state["receipts"]], [45, None, None])
        self.assertEqual(next(d["mode"] for d in state["devices"] if d["id"] == "living-curtain"), "unknown")
        with self.assertRaises(FamilyError) as wrong:
            recovered.dispatch("POST", "/decision", {**request, "memberId": "child"})
        self.assertEqual(wrong.exception.status, 403)
        replay = recovered.dispatch("POST", "/decision", request)
        self.assertTrue(replay["decisionReplayed"])
        self.assertEqual(replay["decisionResult"]["receipts"], state["receipts"])
        self.assertEqual(writes, expected_writes)
        self.assertEqual(FamilyEvening(gateway_factory=DeviceGateway, store=journal).state(), state)
        between_writes = MemoryJournal()
        between_writes.latest = next(c for c in journal.history if c["execution"]
                                     and c["execution"]["dispatching"] is None and len(c["state"]["receipts"]) == 1)
        restored = FamilyEvening(gateway_factory=DeviceGateway, store=between_writes)
        self.assertEqual([r["status"] for r in restored.state()["receipts"]], ["confirmed", "skipped", "skipped"])
        self.assertEqual(writes, expected_writes)

    def test_failed_intent_checkpoint_blocks_device_io_and_further_mutation(self):
        class FailingJournal(MemoryJournal):
            def save(self, checkpoint):
                if checkpoint["execution"] is not None:
                    raise OSError("test checkpoint unavailable")
                super().save(checkpoint)

        journal = FailingJournal()
        session = FamilyEvening(store=journal)
        request = propose_arrival(session)
        for payload in (request, request):
            with self.assertRaises(FamilyError) as stopped:
                session.dispatch("POST", "/decision", payload)
            self.assertEqual(stopped.exception.payload["error"]["code"], "CHECKPOINT_UNAVAILABLE")
        self.assertEqual(session.gateway.receipts, {})
        self.assertEqual(session.state(), journal.latest["view"])
        self.assertEqual(session.state()["suggestion"]["id"], request["suggestionId"])


if __name__ == "__main__":
    unittest.main()
