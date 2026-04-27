from pathlib import Path
import os

from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient

import threading
import time

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

MONGODB_URI = os.environ.get("MONGODB_URI")
events_collection = None

if MONGODB_URI:
    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client["seatchecker"]
        events_collection = mongo_db["events"]
        print("[DB] Connected to MongoDB Atlas (seatchecker.events)", flush=True)
    except Exception as exc:
        events_collection = None
        print(f"[DB][WARN] MongoDB connection failed: {exc}", flush=True)
else:
    print("[DB][WARN] MONGODB_URI not set; DB logging disabled.", flush=True)


@app.after_request
def log_request(response):
    print(
        f"[BACKEND] {request.method} {request.path} -> {response.status_code}",
        flush=True
    )
    return response


class VacancyTimer:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.state = "occupied"
        self.vacant_start = None
        self._lock = threading.Lock()

    def set_occupied(self):
        with self._lock:
            if self.state != "occupied":
                print("[BACKEND] -> OCCUPIED", flush=True)
            self.state = "occupied"
            self.vacant_start = None

    def set_vacant(self):
        with self._lock:
            print("[DEBUG] set_vacant called", flush=True)

            if self.state == "occupied":
                self.state = "vacant"
                self.vacant_start = time.time()
                print("[BACKEND] -> VACANT (timer started)", flush=True)

    def update(self):
        with self._lock:
            if self.state == "vacant" and self.vacant_start:
                elapsed = time.time() - self.vacant_start
                if elapsed >= self.timeout:
                    self.state = "alerted"
                    print("[BACKEND] -> ALERTED", flush=True)

    def get(self):
        with self._lock:
            return {
                "state": self.state,
                "elapsed": 0 if not self.vacant_start else time.time() - self.vacant_start
            }


controller = VacancyTimer()


def timer_loop():
    print("[DEBUG] Timer thread started", flush=True)
    while True:
        controller.update()
        time.sleep(0.5)


threading.Thread(target=timer_loop, daemon=True).start()


@app.route("/update_status", methods=["POST"])
def update_status():
    payload = request.get_json(silent=True) or {}
    print(f"[DEBUG] Incoming payload: {payload}", flush=True)

    status = payload.get("status")

    if status == "occupied":
        controller.set_occupied()
    elif status == "vacant":
        controller.set_vacant()
    else:
        return jsonify({"ok": False, "error": "invalid status"}), 400

    if events_collection is not None:
        try:
            event_doc = {
                "status": status,
                "timestamp": time.time(),
            }
            events_collection.insert_one(event_doc)
            print(f"[DB] Logged event: {event_doc}", flush=True)
        except Exception as exc:
            print(f"[DB][WARN] Failed to insert event: {exc}", flush=True)

    return jsonify({"ok": True})


@app.route("/seat_timer", methods=["GET"])
def seat_timer():
    return jsonify(controller.get())


@app.route("/stats", methods=["GET"])
def stats():
    if events_collection is None:
        return jsonify({
            "total_events": 0,
            "occupied_count": 0,
            "vacant_count": 0,
            "warning": "database_unavailable",
        }), 503

    try:
        total_events = events_collection.count_documents({})
        occupied_count = events_collection.count_documents({"status": "occupied"})
        vacant_count = events_collection.count_documents({"status": "vacant"})
        return jsonify({
            "total_events": total_events,
            "occupied_count": occupied_count,
            "vacant_count": vacant_count,
        })
    except Exception as exc:
        print(f"[DB][WARN] Failed to compute /stats: {exc}", flush=True)
        return jsonify({"error": "stats_unavailable"}), 500


@app.route("/recent", methods=["GET"])
def recent():
    if events_collection is None:
        return jsonify({"events": [], "warning": "database_unavailable"}), 503

    try:
        cursor = events_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10)
        return jsonify(list(cursor))
    except Exception as exc:
        print(f"[DB][WARN] Failed to fetch /recent: {exc}", flush=True)
        return jsonify({"error": "recent_unavailable"}), 500


@app.route("/avg_vacancy_time", methods=["GET"])
def avg_vacancy_time():
    if events_collection is None:
        return jsonify({
            "avg_vacancy_time_seconds": 0.0,
            "pairs_count": 0,
            "warning": "database_unavailable",
        }), 503

    try:
        events = list(
            events_collection.find(
                {"status": {"$in": ["vacant", "occupied"]}},
                {"_id": 0, "status": 1, "timestamp": 1},
            ).sort("timestamp", 1)
        )

        durations = []
        vacancy_start = None

        for event in events:
            status = event.get("status")
            ts = event.get("timestamp")
            if not isinstance(ts, (int, float)):
                continue

            if status == "vacant":
                if vacancy_start is None:
                    vacancy_start = ts
            elif status == "occupied" and vacancy_start is not None:
                duration = ts - vacancy_start
                if duration >= 0:
                    durations.append(duration)
                vacancy_start = None

        avg_duration = sum(durations) / len(durations) if durations else 0.0
        return jsonify({
            "avg_vacancy_time_seconds": avg_duration,
            "pairs_count": len(durations),
        })
    except Exception as exc:
        print(f"[DB][WARN] Failed to compute /avg_vacancy_time: {exc}", flush=True)
        return jsonify({"error": "avg_vacancy_time_unavailable"}), 500


@app.route("/dashboard")
def dashboard():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(debug=True)