from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

client = MongoClient(os.getenv("MONGO_URI"))

db = client["seatchecker"]
collection = db["seat_logs"]


@app.route("/")
def home():
    return "SeatChecker server running"


@app.route("/seat_status", methods=["POST"])
def seat_status():
    data = request.get_json()

    seat_id = data.get("seat_id")
    status = data.get("status")

    record = {
        "seat_id": seat_id,
        "status": status,
        "timestamp": datetime.utcnow()
    }

    collection.insert_one(record)

    return jsonify({
        "message": "Status logged",
        "seat_id": seat_id,
        "status": status
    })


@app.route("/seat_logs", methods=["GET"])
def get_logs():
    logs = list(collection.find({}, {"_id": 0}))
    return jsonify(logs)


if __name__ == "__main__":
    app.run(debug=True)