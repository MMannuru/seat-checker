import cv2
import requests
import time
from pathlib import Path

# MODEL LOADING
BASE_DIR = Path(__file__).resolve().parent
prototxt = str(BASE_DIR / "models" / "MobileNetSSD_deploy.prototxt")

MODEL_CANDIDATES = [
    BASE_DIR / "models" / "MobileNetSSD_deploy.caffemodel",
    BASE_DIR / "models" / "mobilenet_iter_73000.caffemodel",
]

def load_net():
    last_error = None
    for model_path in MODEL_CANDIDATES:
        if not model_path.exists():
            continue
        try:
            net = cv2.dnn.readNetFromCaffe(prototxt, str(model_path))

            # warmup
            warmup = cv2.dnn.blobFromImage(
                cv2.UMat(300, 300, cv2.CV_8UC3).get(),
                0.007843,
                (300, 300),
                127.5
            )
            net.setInput(warmup)
            net.forward()

            print(f"[INFO] Loaded model: {model_path.name}")
            return net
        except cv2.error as e:
            last_error = e

    raise RuntimeError("No compatible model found.") from last_error


net = load_net()

CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant",
           "sheep", "sofa", "train", "tvmonitor"]

CONF_THRESHOLD = 0.5
HISTORY_SIZE = 10
API_URL = "http://127.0.0.1:5000/update_status"

history = []
last_sent_status = None

cap = cv2.VideoCapture(0)

print("[INFO] Vision node started. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    (h, w) = frame.shape[:2]

    # Run detection
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    current_detected = False

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]

        if confidence > CONF_THRESHOLD:
            idx = int(detections[0, 0, i, 1])
            label = CLASSES[idx]

            if label == "person":
                current_detected = True

                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (startX, startY, endX, endY) = box.astype("int")

                cv2.rectangle(frame, (startX, startY), (endX, endY),
                              (0, 255, 0), 2)
                cv2.putText(frame, "PERSON", (startX, startY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Smooth detection over time
    history.append(1 if current_detected else 0)
    if len(history) > HISTORY_SIZE:
        history.pop(0)

    occupied = sum(history) > (HISTORY_SIZE // 2)
    status = "occupied" if occupied else "vacant"

    if status != last_sent_status:
        try:
            print(f"[VISION] Sending status={status}")
            requests.post(API_URL, json={"status": status}, timeout=1)
        except Exception as e:
            print("[WARN] API send failed:", e)

        last_sent_status = status

    # Display UI
    cv2.putText(
        frame,
        f"Status: {status.upper()}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0) if occupied else (0, 0, 255),
        2
    )

    cv2.imshow("Seat Monitor", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    time.sleep(0.2)

cap.release()
cv2.destroyAllWindows()