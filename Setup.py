import cv2
import json
import os
import numpy as np

# ========= Default CONFIG (used on first run or after Reset) =========
DEFAULT_HSV_RANGES = [
    {"name": "Yellow", "lower": (3,   137, 131), "upper": (47,  226, 220)},
    {"name": "Red",    "lower": (150, 147, 137), "upper": (226, 255, 196)},
    {"name": "Blue",   "lower": (87,   77,  63), "upper": (150, 250, 255)},
    {"name": "Green",  "lower": (36,   68, 114), "upper": (74,  219, 184)},
]

# Per-range drawing colors (B,G,R). Extend/cycle as needed.
DRAW_COLORS = [(0,255,255), (0,0,255), (255,0,0), (0,255,0)]

# Contour filtering & drawing
MIN_AREA  = 500     # ignore tiny blobs
BOX_TYPE  = 0       # 0 = axis-aligned, 1 = rotated
THICKNESS = 2

# Save file
CONFIG_PATH = "hsv_config.json"

# ================= Distortion helper ====================
def compute_distortion_map(w, h, k):
    """Simple radial barrel/pincushion remap. k in [-1,+1]."""
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

# ================= Load/Save config =====================
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
        "ranges": ranges,  # [{"name":..., "lower":[H,S,V], "upper":[H,S,V]}, ...]
        "distortion_kx100": int(kx100),
        "morph_op": int(morph_op),
        "kernel_size": int(ksize),
        "iterations": int(iters),
    }
    # convert tuples to lists (json friendly)
    for r in data["ranges"]:
        r["lower"] = list(r["lower"])
        r["upper"] = list(r["upper"])
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved settings to {CONFIG_PATH}")

# ================== UI creation helpers =================
def create_controls_windows(cfg):
    # Global controls
    cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Controls", 520, 400)
    cv2.createTrackbar("Distortion k x100", "Controls", cfg["distortion_kx100"], 200, nothing)
    cv2.createTrackbar("Morph Op (0-4)", "Controls", cfg["morph_op"], 4, nothing)
    cv2.createTrackbar("Kernel Size", "Controls", cfg["kernel_size"], 31, nothing)
    cv2.createTrackbar("Iterations", "Controls", cfg["iterations"], 10, nothing)

    # Add trackbars for world coordinates for up to 4 cubes
    for i in range(4):
        cv2.createTrackbar(f"Cube{i+1} World X", "Controls", 0, 1000, nothing)
        cv2.createTrackbar(f"Cube{i+1} World Y", "Controls", 0, 1000, nothing)

    # Per-range HSV windows
    for spec in cfg["ranges"]:
        win = f"HSV - {spec['name']}"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 420, 260)
        lh, ls, lv = spec["lower"]
        hh, hs, hv = spec["upper"]
        cv2.createTrackbar("Low H",  win, int(lh), 255, nothing)
        cv2.createTrackbar("Low S",  win, int(ls), 255, nothing)
        cv2.createTrackbar("Low V",  win, int(lv), 255, nothing)
        cv2.createTrackbar("High H", win, int(hh), 255, nothing)
        cv2.createTrackbar("High S", win, int(hs), 255, nothing)
        cv2.createTrackbar("High V", win, int(hv), 255, nothing)

def read_controls(cfg):
    # Read global controls
    kx100 = cv2.getTrackbarPos("Distortion k x100", "Controls")
    morph = cv2.getTrackbarPos("Morph Op (0-4)", "Controls")
    ksize = ensure_odd(cv2.getTrackbarPos("Kernel Size", "Controls"))
    iters = cv2.getTrackbarPos("Iterations", "Controls")

    # Read per-range HSV
    ranges = []
    for spec in cfg["ranges"]:
        win = f"HSV - {spec['name']}"
        lh = cv2.getTrackbarPos("Low H",  win)
        ls = cv2.getTrackbarPos("Low S",  win)
        lv = cv2.getTrackbarPos("Low V",  win)
        hh = cv2.getTrackbarPos("High H", win)
        hs = cv2.getTrackbarPos("High S", win)
        hv = cv2.getTrackbarPos("High V", win)
        ranges.append({"name": spec["name"], "lower": (lh, ls, lv), "upper": (hh, hs, hv)})

    return ranges, kx100, morph, ksize, iters


# ============== Contour selection (ONE per label) ==============
def score_contour(cnt):
    """Return a confidence score for a contour."""
    area = cv2.contourArea(cnt)
    if area <= 0:
        return 0.0
    x, y, w, h = cv2.boundingRect(cnt)
    box_area = max(1, w * h)
    fill_ratio = float(area) / float(box_area)  # 0..1
    return area * fill_ratio  # bigger & more compact blobs score higher

def pick_best_contour(contours, min_area=0):
    """Return (best_contour, score) or (None, 0)."""
    best = None
    best_score = 0.0
    for c in contours:
        if cv2.contourArea(c) < min_area:
            continue
        s = score_contour(c)
        if s > best_score:
            best = c
            best_score = s
    return best, best_score

# ============================= Main ==============================
def main():
    cfg = load_config_or_default()
    create_controls_windows(cfg)

    cap = cv2.VideoCapture(0,cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera 0")
        return

    last_w = last_h = -1
    last_k = None
    map_x = map_y = None
    font = cv2.FONT_HERSHEY_SIMPLEX

    print("Controls: S = save, R = reset to defaults P = ShowPOSITION, Q/ESC = quit")
    print("Press ] to rotate mask to each color, [ to show all masks.")

    mask_mode = "all"  # "all" or "single"
    mask_index = 0

    # --- Add your fixed calibration points and matrix ---
    camera_points = np.float32([[226, 84], [418, 164], [493, 314], [154, 372]])
    world_points = np.float32([[253.22, -39.64], [288.03, 38.95], [348.7, 70.22], [371.82, -70.98]])
    matrix = cv2.getPerspectiveTransform(camera_points, world_points)
    print("Perspective matrix:\n", matrix)

    def to_pos_robot(box1):
        camera_x, camera_y, r = box1[0], box1[1], box1[2]
        camera_coord = np.float32([[camera_x, camera_y]])
        robot_coord = cv2.perspectiveTransform(camera_coord.reshape(-1, 1, 2), matrix)
        robotx, roboty = robot_coord[0][0][0], robot_coord[0][0][1]
        return robotx, roboty, 90 - r

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        h, w = frame.shape[:2]

        # Read UI
        ranges, kx100, morph, ksize, iters = read_controls(cfg)
        k_val = (kx100 - 100) / 100.0

        # Recompute remap if needed
        if (w != last_w) or (h != last_h) or (k_val != last_k) or (map_x is None):
            map_x, map_y = compute_distortion_map(w, h, k_val)
            last_w, last_h, last_k = w, h, k_val

        # Apply distortion ONCE
        distorted = cv2.remap(frame, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        hsv = cv2.cvtColor(distorted, cv2.COLOR_BGR2HSV)
        annotated = distorted.copy()
        all_masks = []

        # Build shared kernel (if any)
        kernel = None
        if ksize > 1 and iters > 0 and morph > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))

        cube_centroids = []

        # Process each HSV range
        for i, spec in enumerate(ranges):
            lower = np.array(spec["lower"], dtype=np.uint8)
            upper = np.array(spec["upper"], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)

            if kernel is not None:
                if morph == 1:   mask = cv2.erode(mask, kernel, iterations=iters)
                elif morph == 2: mask = cv2.dilate(mask, kernel, iterations=iters)
                elif morph == 3: mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=iters)
                elif morph == 4: mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=iters)

            all_masks.append(mask)

            # Find contours and keep ONLY ONE best contour
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_cnt, best_score = pick_best_contour(contours, MIN_AREA)
            color = DRAW_COLORS[i % len(DRAW_COLORS)]
            label_name = spec["name"]

            if best_cnt is not None:
                # centroid
                M = cv2.moments(best_cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    x, y, w0, h0 = cv2.boundingRect(best_cnt)
                    cx, cy = x + w0 // 2, y + h0 // 2

                cube_centroids.append([cx, cy])

                # bounding box (axis or rotated)
                if BOX_TYPE == 0:
                    x, y, w0, h0 = cv2.boundingRect(best_cnt)
                    cv2.rectangle(annotated, (x, y), (x + w0, y + h0), color, THICKNESS)
                else:
                    rect = cv2.minAreaRect(best_cnt)
                    box = np.int32(cv2.boxPoints(rect))
                    cv2.polylines(annotated, [box], True, color, THICKNESS)

                # draw centroid + text (name + coords + score)
                cv2.circle(annotated, (cx, cy), 4, (0,0,0), -1)
                cv2.circle(annotated, (cx, cy), 3, color, -1)
                conf = f"{best_score:.0f}"

                # Use robot coordinates for annotation
                robotx, roboty, robotr = to_pos_robot([cx, cy, 0])
                text = f"{label_name} Robot({robotx:.1f},{roboty:.1f}) conf:{conf}"
                cv2.putText(annotated, text, (cx + 6, cy - 6), font, 0.6, (0,0,0), 3, cv2.LINE_AA)
                cv2.putText(annotated, text, (cx + 6, cy - 6), font, 0.6, (255,255,255), 1, cv2.LINE_AA)

        # --- Mask display logic ---
        key = cv2.waitKey(1) & 0xFF
        if key == ord(']'):
            mask_mode = "single"
            mask_index = (mask_index + 1) % len(all_masks)
        elif key == ord('['):
            mask_mode = "all"
        elif key == ord('p'):
            # Print out camera points in requested format
            if cube_centroids:
                print("camera_points = np.float32([", end="")
                print(", ".join(f"[{cx}, {cy}]" for cx, cy in cube_centroids), end="")
                print("])")
                # Print color order line
                color_order = " -> ".join([spec["name"] for spec in ranges])
                print(f"#{color_order}")
            else:
                print("No cubes detected.")

        if mask_mode == "all":
            combined_mask = np.zeros_like(all_masks[0]) if all_masks else np.zeros((h, w), np.uint8)
            for m in all_masks:
                combined_mask = cv2.bitwise_or(combined_mask, m)
            cv2.imshow("Combined Mask", combined_mask)
        elif mask_mode == "single":
            if all_masks:
                cv2.imshow("Combined Mask", all_masks[mask_index])
            else:
                cv2.imshow("Combined Mask", np.zeros((h, w), np.uint8))

        cv2.imshow("Annotated Output", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):
            save_config(ranges, kx100, morph, ksize, iters)
            break
        elif key in (ord('s'), ord('S')):
            save_config(ranges, kx100, morph, ksize, iters)
        elif key in (ord('r'), ord('R')):
            # Reload saved config from hsv_config.json (do NOT force DEFAULT_HSV_RANGES)
            print("Reloading saved config.")
            cv2.destroyAllWindows()
            cfg = load_config_or_default()
            create_controls_windows(cfg)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
