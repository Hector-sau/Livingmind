"""Check the restart and concurrency boundary using real SQLite files and separate processes."""
import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.request import ProxyHandler, Request, build_opener

from app.family.gateway import DEVICES, VirtualFamilyGateway
from app.family.profile import create_family_session
from app.family.storage import SharedFamilySession, SQLiteFamilyStore


ARRIVAL = {"type": "arrival", "memberId": "mother", "eventId": "arrive"}
BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def http_server(db):
    command = [sys.executable, "-u", str(BACKEND / "family_demo.py"), "--port", "0", "--state-db", str(db)]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) as process:
        try:
            base = process.stdout.readline().strip().split()[-1] + "/api/family"
            def call(path, body=None):
                request = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"})
                with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
                    return json.load(response)
            yield call
        finally:
            process.terminate()
            process.wait(timeout=5)


def slow_writer(db, decision, started, release, writes):
    class PausedGateway(VirtualFamilyGateway):
        def submit(self, action_id, device_id, value):
            with open(writes, "a", encoding="utf-8") as stream:
                stream.write(device_id + "\n")
            if device_id == "living-curtain":
                started.set()
                release.wait(15)
            return super().submit(action_id, device_id, value)

    session = SharedFamilySession(SQLiteFamilyStore(db, DEVICES), PausedGateway)
    session.dispatch("POST", "/decision", decision)


class SharedHouseholdTests(unittest.TestCase):
    def test_two_http_servers_restart_and_replay_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "house.sqlite3"
            with http_server(db) as first:
                proposal = first("/events", ARRIVAL)["suggestion"]
                edit = first("/decision", {"suggestionId": proposal["id"], "memberId": "mother",
                             "decision": "edit", "text": "今晚只调客厅灯到65%"})["suggestion"]
            confirm = {"suggestionId": edit["id"], "memberId": "mother", "decision": "confirm"}
            with http_server(db) as a, http_server(db) as b, ThreadPoolExecutor(2) as pool:
                self.assertEqual(b("/state")["suggestion"], edit)
                futures = [pool.submit(call, "/decision", confirm) for call in (a, b)]
                replies = [future.result() for future in futures]
                self.assertEqual(sorted(r["decisionReplayed"] for r in replies), [False, True])
                expected = replies[0]["decisionResult"]
                self.assertEqual(expected, replies[1]["decisionResult"])
                self.assertEqual(expected["receipts"][0]["observed"], 65)
                self.assertEqual(a("/events", ARRIVAL)["lastOutcome"], "duplicate")
                self.assertEqual(b("/state")["time"], replies[0]["time"])
            with http_server(db) as restarted:
                self.assertEqual(restarted("/decision", confirm)["decisionResult"], expected)
                self.assertEqual(len([e for e in restarted("/state")["timeline"] if e["kind"] == "confirmed"]), 1)
                fresh = restarted("/reset", {})
                self.assertIsNone(fresh["suggestion"])
                self.assertEqual(fresh["receipts"], [])
            self.assertEqual(create_family_session(state_db=db).state(), fresh)

    def test_dead_writer_is_recovered_without_a_second_device_call(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            db, writes = Path(tmp) / "house.sqlite3", Path(tmp) / "calls.txt"
            resident = create_family_session(state_db=db)
            sid = resident.dispatch("POST", "/events", ARRIVAL)["suggestion"]["id"]
            decision = {"decision": "confirm", "memberId": "mother", "suggestionId": sid}
            started, release = ctx.Event(), ctx.Event()
            worker = ctx.Process(target=slow_writer, args=(db, decision, started, release, writes))
            worker.start()
            try:
                self.assertTrue(started.wait(8), "second action did not start")
                live = resident.dispatch("GET", "/state")
                self.assertEqual(live["lastOutcome"], "executing")
                self.assertEqual(live["execution"]["completedActions"], 1)
                self.assertTrue(worker.is_alive())
                worker.terminate()  # Actual process exit after intent, before its receipt.
                worker.join(5)
                self.assertFalse(worker.is_alive())
                result = resident.dispatch("POST", "/decision", decision)
                self.assertTrue(result["decisionReplayed"])
                self.assertEqual([r["status"] for r in result["decisionResult"]["receipts"]],
                                 ["confirmed", "unknown", "skipped"])
                self.assertEqual(result["lastOutcome"], "incomplete")
                curtain = next(d for d in result["devices"] if d["id"] == "living-curtain")
                self.assertEqual(curtain["mode"], "unknown")
                self.assertEqual(writes.read_text().splitlines(), ["living-light", "living-curtain"])
                self.assertEqual(resident.dispatch("GET", "/state")["receipts"], result["decisionResult"]["receipts"])
            finally:
                if worker.is_alive():
                    worker.terminate()
                worker.join(5)

    def test_other_profile_cannot_overwrite_an_existing_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "one.db"
            home = create_family_session(state_db=db)
            state = home.dispatch("POST", "/events", ARRIVAL)
            with self.assertRaisesRegex(ValueError, "different MIoT profile"):
                create_family_session(BACKEND / "examples" / "family-miot-profile.json", db)
            self.assertEqual(home.state(), state)
