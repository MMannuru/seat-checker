# INSTRUCTIONS.md

## Project Overview

SeatChecker is a backend system that tracks seat occupancy for study spaces. The server receives seat status updates ("occupied" or "vacant") through a REST API and stores them in a MongoDB database. The backend will later integrate with a computer vision component that detects whether a desk is occupied using a camera feed.

This file provides instructions so that a developer or an AI system (such as GPT, Claude, or Gemini) can understand how to build, run, and test the project.

---

## Technology Stack

- Python 3
- Flask (REST API server)
- MongoDB Atlas (cloud database)
- PyMongo (MongoDB driver)
- python-dotenv (environment variable management)

---

## Repository Structure

```
seatchecker/
├── app.py
├── requirements.txt
├── README.md
├── INSTRUCTIONS.md
├── .env
└── venv/
```

### Important Files

- **app.py** – Main Flask server and API routes
- **requirements.txt** – Python dependencies required to run the project
- **.env** – Environment variables such as the MongoDB connection string

---

## Environment Setup

Create a Python virtual environment:

```
python3 -m venv venv
source venv/bin/activate
```

Install project dependencies:

```
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the root directory of the project.

Example format:

```
MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
```

This variable is used by the Flask server to connect to MongoDB Atlas.

---

## Running the Server

Start the Flask backend with:

```
python app.py
```

The server will start locally at:

```
http://127.0.0.1:5000
```

---

## API Endpoints

### POST /seat_status

Logs a seat occupancy update.

Example request:

```
curl -X POST http://127.0.0.1:5000/seat_status \
-H "Content-Type: application/json" \
-d '{"seat_id":"desk1","status":"occupied"}'
```

Request body format:

```
{
  "seat_id": "desk1",
  "status": "occupied"
}
```

The server records the event in MongoDB along with a timestamp.

---

### GET /seat_logs

Returns all stored seat occupancy records.

Example request:

```
http://127.0.0.1:5000/seat_logs
```

Example response:

```
[
  {
    "seat_id": "desk1",
    "status": "occupied",
    "timestamp": "2026-03-10T02:33:29"
  }
]
```

---

## Testing the System

1. Start the Flask server using `python app.py`.
2. Send a POST request to `/seat_status` with a sample seat status update.
3. Verify that the record appears in MongoDB Atlas under the `seat_logs` collection.
4. Access `/seat_logs` to confirm that the stored records can be retrieved.

---

## Planned Next Steps

The next stage of the project will involve implementing a computer vision component using OpenCV to detect whether a desk is occupied. The vision module will send automatic updates to the `/seat_status` endpoint so the backend can log seat activity.
