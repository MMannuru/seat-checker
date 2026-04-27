# Seat Checker

Seat Checker is a project we built to deal with seat hogging in library study areas.  
The idea is simple: detect if someone is actually at the desk, and if they leave for too long, mark that seat as available.

## How it works

The camera feed runs through OpenCV and decides if a person is present or not.
That status (`occupied` or `vacant`) gets sent to a Flask backend.

A timer controller tracks how long the seat has been vacant.
If the time goes over a limit, the state changes to `alerted`.

The dashboard polls the backend and shows the current state live.

## System components

- Vision node (OpenCV): detects person presence from webcam feed
- Backend (Flask): receives status updates and serves API endpoints
- Controller (VacancyTimer): handles vacant timer and alert transition
- Dashboard (HTML/JS): shows occupied / vacant / alerted in real time
- Database (MongoDB Atlas): logs events and supports basic analytics

## Demo flow

Normal flow is:

`occupied` -> `vacant` -> `alerted` -> `occupied` (reset)

When someone leaves, timer starts.
If they come back before timeout, it resets.
If not, it goes to `alerted`.

## Setup

1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Set MongoDB Atlas URI

```bash
export MONGODB_URI="your_mongodb_atlas_uri"
```

3. Run backend

```bash
python app.py
```

4. Run vision script

```bash
python vision_node.py
```

5. Open dashboard

`http://127.0.0.1:5000/dashboard`

## Example API endpoints

- `POST /update_status`
- `GET /seat_timer`
- `GET /stats`

## Notes / limitations

- Detection is not perfect and can flicker sometimes.
- Lighting and camera angle affect OpenCV results a lot.
- This is a prototype project, not a production deployment.

## Future improvements

- Improve detection stability to reduce false flips.
- Add per-seat support for monitoring multiple desks.
- Add simple auth so only trusted clients can update status.
