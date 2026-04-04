# SeatChecker — Developer Instructions

## Project Overview

SeatChecker detects and tracks seat occupancy at library study desks using computer vision.
A camera-equipped edge node classifies desks as **occupied** or **vacant**, POSTs updates to a
Flask REST API, and a controller service manages a countdown timer. When a seat stays vacant
longer than the configured limit, an alert fires to notify other students the spot can be taken.

---

## Architecture

```
Camera / Edge Node          Controller Service       Flask Backend          MongoDB (or mock)
  (vision_node.py)    →→→    (controller.py)    →→→    (app.py)        →→→   seat_logs
  OpenCV / MOG2              VacancyTimer               REST API               collection
  Background sub.            Countdown logic            /seat_status
  Contour detection          Alert trigger              /seat_logs
                                                        /seat_timer
```

---

## File Reference

| File | Purpose |
|---|---|
| `app.py` | Flask REST API + mock/live MongoDB |
| `vision_node.py` | OpenCV camera feed → occupancy detection → POST to API |
| `controller.py` | VacancyTimer countdown logic → alert on timeout |
| `test_seatchecker.py` | Full unit + integration test suite (no camera/DB needed) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for environment variables |

---

## Environment Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

---

## Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `USE_MOCK_DB` | `true` | Use in-memory store instead of MongoDB |
| `MONGO_URI` | *(unset)* | MongoDB Atlas connection string (required if `USE_MOCK_DB=false`) |

---

## Running the System

### 1 — Start the Flask backend (always first)
```bash
python app.py
# Server starts at http://127.0.0.1:5000
```

### 2 — Start the vision node (requires webcam)
```bash
python vision_node.py
# Opens camera feed; press Q to quit
```

### 3 — Start the controller (in a separate terminal)
```bash
python controller.py
# Polls /seat_logs every 5s; manages countdown timer
```

All three can run simultaneously. The vision node and controller are independent —
vision_node writes status, controller reads it and manages the timer.

---

## Configuration

### vision_node.py
| Constant | Default | Description |
|---|---|---|
| `SEAT_ID` | `"desk1"` | Seat identifier sent to API |
| `SERVER_URL` | `http://127.0.0.1:5000/seat_status` | Backend endpoint |
| `CAMERA_INDEX` | `0` | OpenCV camera index (0 = built-in) |
| `MIN_CONTOUR_AREA` | `3000` | Min pixel² to count as a person |
| `STABILITY_FRAMES` | `8` | Consecutive frames before committing state |
| `BLUR_KERNEL` | `(21, 21)` | Gaussian blur kernel size |

### controller.py
| Constant | Default | Description |
|---|---|---|
| `ABSENCE_LIMIT_SECONDS` | `3600` | Seconds before alert fires (set to 30 for quick demo) |
| `POLL_INTERVAL_SECONDS` | `5` | How often controller checks seat status |
| `SEAT_ID` | `"desk1"` | Which seat to monitor |

---

## API Endpoints

### `GET /`
Health check. Returns server status and DB mode (`mock` or `mongodb`).

### `POST /seat_status`
Log a seat occupancy event.
```bash
curl -X POST http://127.0.0.1:5000/seat_status \
  -H "Content-Type: application/json" \
  -d '{"seat_id":"desk1","status":"occupied"}'
```
**Body:** `{ "seat_id": string, "status": "occupied" | "vacant" | "alert" }`

### `GET /seat_logs`
Returns all logged occupancy events.
```bash
curl http://127.0.0.1:5000/seat_logs
```

### `DELETE /seat_logs`
Clears all logs (useful for testing).

### `GET /seat_timer`
Returns the last-known timer state as updated by the controller.
```json
{
  "seat_id": "desk1",
  "state": "vacant",
  "elapsed_s": 142,
  "remaining_s": 3458,
  "last_updated": "2026-04-03T01:00:00"
}
```

---

## Running Tests

No MongoDB or webcam required.

```bash
python test_seatchecker.py
```

Expected output: **20 tests, 0 failures**

Tests cover:
- All Flask API endpoints (GET, POST, DELETE)
- Input validation (missing fields → 400)
- Mock database read/write/clear
- `VacancyTimer` state transitions (occupied → vacant → alerted → reset)
- Countdown accuracy and alert firing
- Edge cases (redundant status updates, alerted-state behavior)

---

## Switching to Live MongoDB

1. Set `USE_MOCK_DB=false` in your `.env`
2. Set `MONGO_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/...`
3. Restart `app.py`

No other code changes needed — the API and controller are database-agnostic.
