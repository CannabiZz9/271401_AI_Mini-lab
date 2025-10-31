import cv2
import numpy as np
import socket
import time
import json
import os
from threading import Thread

# ====== CONFIG ======
DEFAULT_HSV_RANGES = [
    {"name": "Yellow", "lower": (3,   137, 131), "upper": (47,  226, 220)},
    {"name": "Red",    "lower": (150, 147, 137), "upper": (226, 255, 196)},
    {"name": "Blue",   "lower": (87,   77,  63), "upper": (150, 250, 255)},
    {"name": "Green",  "lower": (36,   68, 114), "upper": (74,  219, 184)},
]
DRAW_COLORS = [(0,255,255), (0,0,255), (255,0,0), (0,255,0)]
MIN_AREA  = 200
BOX_TYPE  = 0
THICKNESS = 2

CONFIG_PATH = "hsv_config.json"

IP_ROBOT = "192.168.1.6"
PORT = 6601

# ====== Perspective Calibration ======
camera_points = np.float32([[585, 314], [243, 321], [563, 98], [239, 131]])
world_points = np.float32([[368.39, 93.74], [371.16, -29.02], [292.13, 83.77], [302.78, -29.97]])
matrix = cv2.getPerspectiveTransform(camera_points, world_points)

def to_pos_robot(box1):
    camera_x, camera_y, r = box1[0], box1[1], box1[2]
    camera_coord = np.float32([[camera_x, camera_y]])
    robot_coord = cv2.perspectiveTransform(camera_coord.reshape(-1, 1, 2), matrix)
    robotx, roboty = robot_coord[0][0][0], robot_coord[0][0][1]
    return robotx, roboty, 90 - r

def compute_distortion_map(w, h, k):
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    max_rad = np.sqrt(cx**2 + cy**2)
    x = np.linspace(0, w - 1, w, dtype=np.float32)
    y = np.linspace(0, h - 1, h, dtype=np.float32)
    X, Y = np.meshgrid(x, y)
    Xc, Yc = X - cx, Y - cy
    xn, yn = Xc / max_rad, Yc / max_rad
    r2 = xn*xn + yn*yn
    scale = 1.0 + k * r2
    Xd = (xn * scale) * max_rad + cx
    Yd = (yn * scale) * max_rad + cy
    return Xd.astype(np.float32), Yd.astype(np.float32)

def ensure_odd(n): return max(1, n | 1)
def nothing(_): pass

def load_config_or_default():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "ranges": data.get("ranges", DEFAULT_HSV_RANGES),
            "distortion_kx100": int(data.get("distortion_kx100", 100)),
            "morph_op": int(data.get("morph_op", 0)),
            "kernel_size": int(data.get("kernel_size", 3)),
            "iterations": int(data.get("iterations", 1)),
        }
    else:
        return {
            "ranges": DEFAULT_HSV_RANGES,
            "distortion_kx100": 100,
            "morph_op": 0,
            "kernel_size": 3,
            "iterations": 1,
        }

def save_config(ranges, kx100, morph_op, ksize, iters):
    data = {
        "ranges": ranges,
        "distortion_kx100": int(kx100),
        "morph_op": int(morph_op),
        "kernel_size": int(ksize),
        "iterations": int(iters),
    }
    for r in data["ranges"]:
        r["lower"] = list(r["lower"])
        r["upper"] = list(r["upper"])
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved settings to {CONFIG_PATH}")

def create_controls_windows(cfg):
    cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Controls", 520, 400)
    cv2.createTrackbar("Distortion k x100", "Controls", cfg["distortion_kx100"], 200, nothing)
    cv2.createTrackbar("Morph Op (0-4)", "Controls", cfg["morph_op"], 4, nothing)
    cv2.createTrackbar("Kernel Size", "Controls", cfg["kernel_size"], 31, nothing)
    cv2.createTrackbar("Iterations", "Controls", cfg["iterations"], 10, nothing)
    cv2.createTrackbar("Start Mg400", "Controls", 0, 1, nothing)

    # per-color enable trackbars (allow multiple selection)
    ranges = cfg.get("ranges", DEFAULT_HSV_RANGES)
    for i, spec in enumerate(ranges):
        name = spec.get("name", f"Color{i}")
        track_name = f"Enable {name}"
        # default enable = 1 (enabled). Change as you like.
        cv2.createTrackbar(track_name, "Controls", 1, 1, nothing)

def read_controls(cfg):
    kx100 = cv2.getTrackbarPos("Distortion k x100", "Controls")
    morph = cv2.getTrackbarPos("Morph Op (0-4)", "Controls")
    ksize = ensure_odd(cv2.getTrackbarPos("Kernel Size", "Controls"))
    iters = cv2.getTrackbarPos("Iterations", "Controls")

    # read per-color enables
    enabled = []
    ranges = cfg.get("ranges", DEFAULT_HSV_RANGES)
    for i, spec in enumerate(ranges):
        name = spec.get("name", f"Color{i}")
        track_name = f"Enable {name}"
        try:
            val = cv2.getTrackbarPos(track_name, "Controls")
        except:
            val = 1
        enabled.append(bool(val))
    return kx100, morph, ksize, iters, enabled

# ====== Communication Thread ======
class Mg400(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.status = 'wait'
        self.pos_frame = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((IP_ROBOT, PORT))
        time.sleep(1)
        self.sock.send('hi'.encode())
        print('Connected to robot.')

    def run(self):
        while True:
            print(self.status)
            if self.status == 'wait':
                data = self.sock.recv(50)
                if data == b'start':
                    self.status = 'find'
                    time.sleep(1)
                elif data == b'pos?':
                    self.status = 'find_pos'
                    time.sleep(1)

            if self.status == 'find':
                if self.pos_frame:
                    self.sock.send('found'.encode())
                    print('found')
                    self.status = 'wait'
                else:
                    print("Not Found!!")
                time.sleep(1)

            if self.status == 'find_pos':
                print("Mg400 pos_frame:", self.pos_frame)
                if self.pos_frame:
                    x, y, r = to_pos_robot(self.pos_frame)
                    msg = f'{x:.2f},{y:.2f},{r:.2f}'
                    self.sock.send(msg.encode())
                    print(f'Sent: {msg}')
                    self.status = 'wait'
                else:
                    print('Not found')
                    self.sock.send('finish'.encode())
                time.sleep(1)

            time.sleep(0.1)

# ====== Vision Thread ======
class VisionProcessing(Thread):
    def __init__(self, mg400, cfg):
        Thread.__init__(self)
        self.daemon = True
        self.mg400 = mg400
        self.cfg = cfg
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(0)
        self.kernel = np.ones((5, 5), np.uint8)
        self.last_w = self.last_h = -1
        self.last_k = None
        self.map_x = self.map_y = None
        self.start()

    def run(self):
        font = cv2.FONT_HERSHEY_SIMPLEX
        while True:
            ret, frame = self.cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            kx100, morph, ksize, iters, enabled = read_controls(self.cfg)
            k_val = (kx100 - 100) / 100.0

            # Recompute remap if needed
            if (w != self.last_w) or (h != self.last_h) or (k_val != self.last_k) or (self.map_x is None):
                self.map_x, self.map_y = compute_distortion_map(w, h, k_val)
                self.last_w, self.last_h, self.last_k = w, h, k_val

            # Apply distortion ONCE
            distorted = cv2.remap(frame, self.map_x, self.map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

            hsv = cv2.cvtColor(distorted, cv2.COLOR_BGR2HSV)
            annotated = distorted.copy()
            pos_frame_0 = []
            all_masks = []

            # iterate cfg ranges but only process enabled ones
            ranges = self.cfg.get("ranges", DEFAULT_HSV_RANGES)
            for i, spec in enumerate(ranges):
                is_enabled = enabled[i] if i < len(enabled) else True
                lower = np.array(spec["lower"], dtype=np.uint8)
                upper = np.array(spec["upper"], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower, upper)

                # store mask for combined/single display
                all_masks.append(mask)

                if not is_enabled:
                    # skip processing/drawing for disabled colors
                    continue

                # apply morphology and contour processing for enabled masks
                if ksize > 1 and iters > 0:
                    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
                    if morph == 1:   mask = cv2.erode(mask, kern, iterations=iters)
                    elif morph == 2: mask = cv2.dilate(mask, kern, iterations=iters)
                    elif morph == 3: mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern, iterations=iters)
                    elif morph == 4: mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern, iterations=iters)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_cnt = None
                best_score = 0.0
                for c in contours:
                    area = cv2.contourArea(c)
                    if area < MIN_AREA:
                        continue
                    x, y, ww, hh = cv2.boundingRect(c)
                    box_area = max(1, ww * hh)
                    fill_ratio = float(area) / float(box_area)
                    score = area * fill_ratio
                    if score > best_score:
                        best_cnt = c
                        best_score = score

                color = DRAW_COLORS[i % len(DRAW_COLORS)]
                label_name = spec.get("name", f"Color{i}")

                if best_cnt is not None:
                    M = cv2.moments(best_cnt)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        x, y, w0, h0 = cv2.boundingRect(best_cnt)
                        cx, cy = x + w0 // 2, y + h0 // 2

                    rect = cv2.minAreaRect(best_cnt)
                    angle = rect[-1]
                    if angle < -45:
                        angle = 90 + angle
                    angle = round(angle, 0)

                    pos_frame_0.append([cx, cy, angle])

                    if BOX_TYPE == 0:
                        x, y, w0, h0 = cv2.boundingRect(best_cnt)
                        cv2.rectangle(annotated, (x, y), (x + w0, y + h0), color, THICKNESS)
                    else:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        cv2.polylines(annotated, [box], True, color, THICKNESS)

                    cv2.circle(annotated, (cx, cy), 4, (0,0,0), -1)
                    cv2.circle(annotated, (cx, cy), 3, color, -1)
                    robotx, roboty, robotr = to_pos_robot([cx, cy, angle])
                    text = f"{label_name} Robot({robotx:.1f},{roboty:.1f}) angle:{robotr:.1f}"
                    cv2.putText(annotated, text, (cx + 6, cy - 6), font, 0.6, (0,0,0), 3, cv2.LINE_AA)
                    cv2.putText(annotated, text, (cx + 6, cy - 6), font, 0.6, (255,255,255), 1, cv2.LINE_AA)

            # Send the first found cube position to Mg400 thread
            if pos_frame_0:
                #print("Detected cube:", pos_frame_0[0])
                self.mg400.pos_frame = pos_frame_0[0]
            else:
                self.mg400.pos_frame = None

            # show combined or per-mask view depending on '[' / ']' handling elsewhere
            if all_masks:
                combined_mask = np.zeros_like(all_masks[0])
                for m in all_masks:
                    combined_mask = cv2.bitwise_or(combined_mask, m)
                cv2.imshow("Combined Mask", combined_mask)

            cv2.imshow("Annotated Output", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):
                kx100, morph, ksize, iters, _ = read_controls(self.cfg)
                save_config(DEFAULT_HSV_RANGES, kx100, morph, ksize, iters)
                break
            elif key in (ord('s'), ord('S')):
                kx100, morph, ksize, iters, _ = read_controls(self.cfg)
                save_config(DEFAULT_HSV_RANGES, kx100, morph, ksize, iters)
            elif key in (ord('r'), ord('R')):
                print("Reset to defaults.")
                cv2.destroyAllWindows()
                self.cfg = load_config_or_default()
                create_controls_windows(self.cfg)

        self.cap.release()
        cv2.destroyAllWindows()

def main():
    cfg = load_config_or_default()
    create_controls_windows(cfg)
    mg400_thread = Mg400()
    vision_thread = VisionProcessing(mg400_thread, cfg)
    started = False
    print("Controls: S = save, R = reset to defaults, Q/ESC = quit")
    try:
        while True:
            time.sleep(0.1)
            cv2.waitKey(1)  # <-- Add this line to keep the Controls window responsive
            start_val = cv2.getTrackbarPos("Start Mg400", "Controls")
            if start_val == 1 and not started:
                mg400_thread.start()
                print("Mg400 thread started!")
                started = True
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()