import os
os.environ["USE_MOCK_DB"] = "true"

import sys
import time
import unittest

from app import app, _mock_store, collection
from controller import VacancyTimer


class TestFlaskAPI(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        _mock_store.clear()

    def test_home_returns_200(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("SeatChecker", data["message"])
        self.assertEqual(data["db_mode"], "mock")

    def test_post_occupied_status(self):
        r = self.client.post("/seat_status", json={"seat_id": "desk1", "status": "occupied"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["seat_id"], "desk1")
        self.assertEqual(data["status"], "occupied")

    def test_post_vacant_status(self):
        r = self.client.post("/seat_status", json={"seat_id": "desk1", "status": "vacant"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "vacant")

    def test_post_missing_fields_returns_400(self):
        r = self.client.post("/seat_status", json={"seat_id": "desk1"})
        self.assertEqual(r.status_code, 400)

    def test_post_empty_body_returns_400(self):
        r = self.client.post("/seat_status", json={})
        self.assertEqual(r.status_code, 400)

    def test_logs_empty_on_start(self):
        r = self.client.get("/seat_logs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    def test_logs_reflect_posted_statuses(self):
        self.client.post("/seat_status", json={"seat_id": "desk1", "status": "occupied"})
        self.client.post("/seat_status", json={"seat_id": "desk1", "status": "vacant"})
        logs = self.client.get("/seat_logs").get_json()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["status"], "occupied")
        self.assertEqual(logs[1]["status"], "vacant")

    def test_logs_contain_timestamp(self):
        self.client.post("/seat_status", json={"seat_id": "desk1", "status": "occupied"})
        logs = self.client.get("/seat_logs").get_json()
        self.assertIn("timestamp", logs[0])

    def test_delete_clears_logs(self):
        self.client.post("/seat_status", json={"seat_id": "desk1", "status": "occupied"})
        self.client.delete("/seat_logs")
        logs = self.client.get("/seat_logs").get_json()
        self.assertEqual(logs, [])

    def test_seat_timer_endpoint_exists(self):
        r = self.client.get("/seat_timer")
        self.assertEqual(r.status_code, 200)

    def test_seat_timer_updates_on_post(self):
        self.client.post("/seat_status", json={"seat_id": "desk1", "status": "vacant"})
        timer = self.client.get("/seat_timer").get_json()
        self.assertEqual(timer["state"], "vacant")
        self.assertEqual(timer["seat_id"], "desk1")


class TestVacancyTimer(unittest.TestCase):

    def _make_timer(self, limit=60):
        return VacancyTimer("desk1", limit_seconds=limit)

    def test_initial_state_is_occupied(self):
        t = self._make_timer()
        self.assertEqual(t.state, VacancyTimer.OCCUPIED)

    def test_transitions_to_vacant(self):
        t = self._make_timer()
        snap = t.update("vacant")
        self.assertEqual(snap["state"], VacancyTimer.VACANT)
        self.assertEqual(snap["alert_fired"], False)

    def test_reset_on_occupied(self):
        t = self._make_timer()
        t.update("vacant")
        snap = t.update("occupied")
        self.assertEqual(snap["state"], VacancyTimer.OCCUPIED)
        self.assertEqual(snap["elapsed_s"], 0)

    def test_elapsed_increases_while_vacant(self):
        t = self._make_timer(limit=10)
        t.update("vacant")
        time.sleep(0.2)
        snap = t.tick()
        self.assertGreater(snap["elapsed_s"], 0)
        self.assertLess(snap["elapsed_s"], 10)

    def test_alert_fires_after_limit(self):
        t = self._make_timer(limit=1)
        t.update("vacant")
        time.sleep(1.1)
        snap = t.tick()
        self.assertEqual(snap["state"], VacancyTimer.ALERTED)
        self.assertTrue(snap["alert_fired"])

    def test_remaining_decreases(self):
        t = self._make_timer(limit=30)
        t.update("vacant")
        time.sleep(0.1)
        snap = t.tick()
        self.assertLess(snap["remaining_s"], 30)

    def test_remaining_zero_when_alerted(self):
        t = self._make_timer(limit=1)
        t.update("vacant")
        time.sleep(1.2)
        snap = t.tick()
        self.assertEqual(snap["remaining_s"], 0)

    def test_redundant_vacant_does_not_restart_clock(self):
        t = self._make_timer(limit=30)
        t.update("vacant")
        time.sleep(0.15)
        elapsed_before = t.tick()["elapsed_s"]
        t.update("vacant")
        elapsed_after = t.tick()["elapsed_s"]
        self.assertGreaterEqual(elapsed_after, elapsed_before)

    def test_alerted_stays_alerted_until_occupied(self):
        t = self._make_timer(limit=1)
        t.update("vacant")
        time.sleep(1.2)
        t.tick()
        self.assertEqual(t.state, VacancyTimer.ALERTED)
        t.update("vacant")
        self.assertEqual(t.state, VacancyTimer.ALERTED)
        t.update("occupied")
        self.assertEqual(t.state, VacancyTimer.OCCUPIED)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestVacancyTimer))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
