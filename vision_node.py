import cv2
import requests
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VISION] %(message)s",
    datefmt="%H:%M:%S"
)

SEAT_ID = "desk1"
SERVER_URL = "http://127.0.0.1:5000/seat_status"
CAMERA_INDEX = 0
MIN_CONTOUR_AREA = 3000
STABILITY_FRAMES = 8
POST_COOLDOWN = 2.0
BLUR_KERNEL = (21, 21)


def post_status(status: str) -> bool:
    payload = {"seat_id": SEAT_ID, "status": status}
    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=3)
        resp.raise_for_status()
        logging.info(f"POST -> {status.upper()}  (HTTP {resp.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        logging.warning("Server unreachable — is app.py running?")
    except requests.exceptions.RequestException as e:
        logging.warning(f"POST failed: {e}")
    return False


def run_vision_node():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logging.error(f"Cannot open camera index {CAMERA_INDEX}.")
        return

    logging.info("Camera opened. Starting occupancy detection — press Q to quit.")

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=500,
        varThreshold=50,
        detectShadows=True
    )

    current_status = None
    candidate_status = None
    stable_count = 0
    last_post_time = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            logging.warning("Empty frame received — camera may have disconnected.")
            time.sleep(0.1)
            continue

        blurred = cv2.GaussianBlur(frame, BLUR_KERNEL, 0)
        fg_mask = subtractor.apply(blurred)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        significant = [c for c in contours if cv2.contourArea(c) > MIN_CONTOUR_AREA]
        raw_status = "occupied" if significant else "vacant"

        if raw_status == candidate_status:
            stable_count += 1
        else:
            candidate_status = raw_status
            stable_count = 1

        committed = stable_count >= STABILITY_FRAMES

        now = time.time()
        if committed and raw_status != current_status:
            if now - last_post_time >= POST_COOLDOWN:
                if post_status(raw_status):
                    current_status = raw_status
                    last_post_time = now

        display_status = current_status or "initializing..."
        color = (0, 255, 0) if display_status == "occupied" else (0, 0, 255)
        label = f"Status: {display_status}"

        for c in significant:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        cv2.putText(frame, label, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Stable: {stable_count}/{STABILITY_FRAMES}", (15, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        cv2.imshow("SeatChecker — Camera Feed", frame)
        cv2.imshow("SeatChecker — Foreground Mask", fg_mask)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            logging.info("Quit signal received.")
            break

    cap.release()
    cv2.destroyAllWindows()
    logging.info("Vision node stopped.")


if __name__ == "__main__":
    run_vision_node()
