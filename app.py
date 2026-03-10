from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "SeatChecker server running"

@app.route("/seat_status", methods=["POST"])
def seat_status():

    data = request.get_json()

    seat_id = data.get("seat_id")
    status = data.get("status")

    print(f"Seat {seat_id} is {status}")

    return jsonify({
        "message": "Status received",
        "seat_id": seat_id,
        "status": status
    })


if __name__ == "__main__":
    app.run(debug=True)