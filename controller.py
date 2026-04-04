import requests
import time
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CTRL ] %(message)s",
    datefmt="%H:%M:%S"
)

SERVER_URL = "http://127.0.0.1:5000"
SEAT_ID = "desk1"
ABSENCE_LIMIT_SECONDS = 3600
POLL_INTERVAL_SECONDS = 5


class VacancyTimer:

    OCCUPIED = "occupied"
    VACANT = "vacant"
    ALERTED = "alerted"

    def __init__(self, seat_id: str, limit_seconds: int):
        self.seat_id = seat_id
        self.limit = limit_seconds
        self._lock = threading.Lock()
        self._state = self.OCCUPIED
        self._vacant_since = None
        self._elapsed = 0.0

    def update(self, new_status: str) -> dict:
        with self._lock:
            if new_status == "occupied":
                self._on_occupied()
            elif new_status == "vacant":
                self._on_vacant()
            self._refresh_elapsed()
            return self._snapshot()

    def tick(self) -> dict:
        with self._lock:
            self._refresh_elapsed()
            return self._snapshot()

    def _refresh_elapsed(self):
        if self._state == self.VACANT and self._vacant_since is not None:
            self._elapsed = time.time() - self._vacant_since
            if self._elapsed >= self.limit:
                self._state = self.ALERTED
                logging.warning(
                    f"[{self.seat_id}] ALERT — vacant for "
                    f"{self._elapsed:.0f}s (limit: {self.limit}s)"
                )

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _on_occupied(self):
        if self._state != self.OCCUPIED:
            logging.info(
                f"[{self.seat_id}] Occupied — timer reset "
                f"(was vacant {self._elapsed:.0f}s)"
            )
        self._state = self.OCCUPIED
        self._vacant_since = None
        self._elapsed = 0.0

    def _on_vacant(self):
        if self._state == self.OCCUPIED:
            self._state = self.VACANT
            self._vacant_since = time.time()
            self._elapsed = 0.0
            logging.info(
                f"[{self.seat_id}] Now VACANT — countdown started "
                f"({self.limit}s limit)"
            )

    def _snapshot(self) -> dict:
        remaining = max(0.0, self.limit - self._elapsed)
        return {
            "seat_id": self.seat_id,
            "state": self._state,
            "elapsed_s": round(self._elapsed, 1),
            "remaining_s": round(remaining, 1),
            "limit_s": self.limit,
            "alert_fired": self._state == self.ALERTED,
        }


def fetch_latest_status(seat_id: str) -> str | None:
    try:
        resp = requests.get(f"{SERVER_URL}/seat_logs", timeout=3)
        resp.raise_for_status()
        logs = resp.json()
        for entry in reversed(logs):
            if entry.get("seat_id") == seat_id:
                return entry.get("status")
    except requests.exceptions.ConnectionError:
        logging.warning("Cannot reach server — is app.py running?")
    except requests.exceptions.RequestException as e:
        logging.warning(f"GET /seat_logs failed: {e}")
    return None


def post_alert(seat_id: str, elapsed_s: float) -> bool:
    payload = {"seat_id": seat_id, "status": "alert", "elapsed_s": elapsed_s}
    try:
        resp = requests.post(f"{SERVER_URL}/seat_status", json=payload, timeout=3)
        resp.raise_for_status()
        logging.info(f"Alert POSTed to server (elapsed={elapsed_s:.0f}s)")
        return True
    except requests.exceptions.RequestException as e:
        logging.warning(f"Alert POST failed: {e}")
    return False


def run_controller():
    logging.info(
        f"Controller starting — seat={SEAT_ID}, "
        f"limit={ABSENCE_LIMIT_SECONDS}s, poll={POLL_INTERVAL_SECONDS}s"
    )

    timer = VacancyTimer(SEAT_ID, ABSENCE_LIMIT_SECONDS)
    alert_posted = False

    while True:
        status = fetch_latest_status(SEAT_ID)

        if status is not None:
            snap = timer.update(status)
        else:
            snap = timer.tick()

        snap = timer.tick()

        state = snap["state"]
        elapsed = snap["elapsed_s"]
        remaining = snap["remaining_s"]

        if state == VacancyTimer.OCCUPIED:
            logging.info(f"[{SEAT_ID}] Occupied")
            alert_posted = False

        elif state == VacancyTimer.VACANT:
            minutes, seconds = divmod(int(remaining), 60)
            logging.info(
                f"[{SEAT_ID}] Vacant — "
                f"{elapsed:.0f}s elapsed, "
                f"{minutes:02d}:{seconds:02d} remaining"
            )
            alert_posted = False

        elif state == VacancyTimer.ALERTED and not alert_posted:
            logging.warning(
                f"[{SEAT_ID}] ALERT — seat vacant for {elapsed:.0f}s. "
                f"Triggering indicator."
            )
            post_alert(SEAT_ID, elapsed)
            alert_posted = True

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_controller()
