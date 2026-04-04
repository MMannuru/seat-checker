from flask import Flask, request, jsonify
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

USE_MOCK_DB = os.getenv("USE_MOCK_DB", "true").lower() == "true"

if USE_MOCK_DB:
    print("[DB] Running with IN-MEMORY mock database (USE_MOCK_DB=true)")

    _mock_store: list = []

    class _MockCollection:
        def insert_one(self, doc: dict):
            _mock_store.append({k: v for k, v in doc.items()})

        def find(self, query=None, projection=None):
            if projection:
                excluded = {k for k, v in projection.items() if v == 0}
                return [{k: v for k, v in doc.items() if k not in excluded} for doc in _mock_store]
            return list(_mock_store)

        def delete_many(self, query):
            _mock_store.clear()

    collection = _MockCollection()

else:
    from pymongo import MongoClient
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set. Either set it in .env or set USE_MOCK_DB=true")
    print("[DB] Connecting to MongoDB Atlas...")
    client = MongoClient(mongo_uri)
    db = client["seatchecker"]
    collection = db["seat_logs"]
    print("[DB] Connected.")

_timer_state: dict = {
    "seat_id": None,
    "state": "unknown",
    "elapsed_s": 0,
    "remaining_s": None,
    "last_updated": None,
}


@app.route("/")
def home():
    mode = "mock" if USE_MOCK_DB else "mongodb"
    return jsonify({"message": "SeatChecker server running", "db_mode": mode})


@app.route("/seat_status", methods=["POST"])
def seat_status():
    data = request.get_json(force=True, silent=True) or {}

    seat_id = data.get("seat_id")
    status = data.get("status")

    if not seat_id or not status:
        return jsonify({"error": "seat_id and status are required"}), 400

    record = {
        "seat_id": seat_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if "elapsed_s" in data:
        record["elapsed_s"] = data["elapsed_s"]

    collection.insert_one(record)

    _timer_state["seat_id"] = seat_id
    _timer_state["last_updated"] = record["timestamp"]
    if status in ("occupied", "vacant", "alert"):
        _timer_state["state"] = status

    return jsonify({"message": "Status received", "seat_id": seat_id, "status": status})


@app.route("/seat_logs", methods=["GET"])
def get_logs():
    logs = collection.find({}, {"_id": 0})
    safe = []
    for log in logs:
        for k, v in log.items():
            if isinstance(v, datetime):
                log[k] = v.isoformat()
        safe.append(log)
    return jsonify(safe)


@app.route("/seat_logs", methods=["DELETE"])
def clear_logs():
    collection.delete_many({})
    return jsonify({"message": "All logs cleared."})


@app.route("/seat_timer", methods=["GET"])
def seat_timer():
    return jsonify(_timer_state)


if __name__ == "__main__":
    app.run(debug=True)
