import time
import unittest
from unittest.mock import MagicMock, patch

import app as backend


class EventListView:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction):
        reverse = direction == -1
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=reverse)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class TestVacancyTimer(unittest.TestCase):
    def setUp(self):
        self.timer = backend.VacancyTimer(timeout=10)

    def test_initial_state_and_elapsed(self):
        self.assertEqual(self.timer.state, "occupied")
        snapshot = self.timer.get()
        self.assertEqual(snapshot["state"], "occupied")
        self.assertEqual(snapshot["elapsed"], 0)

    def test_vacant_starts_timer_once(self):
        self.timer.set_vacant()
        first_start = self.timer.vacant_start
        self.assertIsNotNone(first_start)
        self.timer.set_vacant()
        self.assertEqual(self.timer.vacant_start, first_start)

    def test_occupied_resets_timer(self):
        self.timer.set_vacant()
        self.timer.set_occupied()
        self.assertEqual(self.timer.state, "occupied")
        self.assertIsNone(self.timer.vacant_start)
        self.assertEqual(self.timer.get()["elapsed"], 0)

    def test_update_transitions_to_alerted_after_timeout(self):
        self.timer.set_vacant()
        self.timer.vacant_start = time.time() - 11
        self.timer.update()
        self.assertEqual(self.timer.state, "alerted")


class TestFlaskAPI(unittest.TestCase):
    def setUp(self):
        backend.app.config["TESTING"] = True
        self.client = backend.app.test_client()
        backend.controller = backend.VacancyTimer(timeout=10)

    def test_update_status_accepts_valid_values(self):
        r1 = self.client.post("/update_status", json={"status": "vacant"})
        r2 = self.client.post("/update_status", json={"status": "occupied"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

    def test_update_status_rejects_invalid_values(self):
        r = self.client.post("/update_status", json={"status": "random"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_update_status_rejects_missing_status(self):
        r = self.client.post("/update_status", json={})
        self.assertEqual(r.status_code, 400)

    def test_seat_timer_reflects_state_changes(self):
        self.client.post("/update_status", json={"status": "vacant"})
        timer = self.client.get("/seat_timer").get_json()
        self.assertEqual(timer["state"], "vacant")
        self.assertGreaterEqual(timer["elapsed"], 0)

    def test_seat_timer_reaches_alerted_after_timeout(self):
        self.client.post("/update_status", json={"status": "vacant"})
        backend.controller.vacant_start = time.time() - 11
        timer = self.client.get("/seat_timer").get_json()
        self.assertEqual(timer["state"], "alerted")

    def test_update_status_logs_event_to_db_when_available(self):
        mock_collection = MagicMock()
        backend.events_collection = mock_collection
        with patch("app.time.time", return_value=1234.5):
            response = self.client.post("/update_status", json={"status": "vacant"})

        self.assertEqual(response.status_code, 200)
        mock_collection.insert_one.assert_called_once_with(
            {"status": "vacant", "timestamp": 1234.5}
        )

    def test_update_status_still_succeeds_when_db_insert_fails(self):
        mock_collection = MagicMock()
        mock_collection.insert_one.side_effect = Exception("DB down")
        backend.events_collection = mock_collection
        response = self.client.post("/update_status", json={"status": "occupied"})
        self.assertEqual(response.status_code, 200)

    def test_stats_503_when_db_unavailable(self):
        backend.events_collection = None
        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 503)

    def test_stats_counts_from_db(self):
        mock_collection = MagicMock()
        mock_collection.count_documents.side_effect = [9, 5, 4]
        backend.events_collection = mock_collection

        response = self.client.get("/stats")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["total_events"], 9)
        self.assertEqual(data["occupied_count"], 5)
        self.assertEqual(data["vacant_count"], 4)

    def test_recent_returns_latest_10(self):
        docs = [
            {"status": "occupied", "timestamp": 1.0},
            {"status": "vacant", "timestamp": 3.0},
            {"status": "occupied", "timestamp": 2.0},
        ]
        mock_collection = MagicMock()
        mock_collection.find.return_value = EventListView(docs)
        backend.events_collection = mock_collection

        response = self.client.get("/recent")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data[0]["timestamp"], 3.0)
        self.assertEqual(len(data), 3)

    def test_avg_vacancy_time_computes_pairs(self):
        docs = [
            {"status": "vacant", "timestamp": 10.0},
            {"status": "occupied", "timestamp": 14.0},
            {"status": "vacant", "timestamp": 20.0},
            {"status": "occupied", "timestamp": 28.0},
        ]
        mock_collection = MagicMock()
        mock_collection.find.return_value = EventListView(docs)
        backend.events_collection = mock_collection

        response = self.client.get("/avg_vacancy_time")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["pairs_count"], 2)
        self.assertAlmostEqual(data["avg_vacancy_time_seconds"], 6.0)

    def test_avg_vacancy_time_handles_no_pairs(self):
        docs = [{"status": "occupied", "timestamp": 1.0}]
        mock_collection = MagicMock()
        mock_collection.find.return_value = EventListView(docs)
        backend.events_collection = mock_collection

        response = self.client.get("/avg_vacancy_time")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["pairs_count"], 0)
        self.assertEqual(data["avg_vacancy_time_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
