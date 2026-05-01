# 271401_AI_Mini-lab

AI-integrated mini-lab project for the **Dobot MG400** robotic arm — built with Python + OpenCV to perform **color-based object detection** and **automated pick-and-place**.

| ID | Name |
|----|------|
| 650610828 | นาย จักรพงศ์ วงศ์วิวัฒน์ธนะ |
| 650610829 | นาย จินตพัฒน์ ตาอ้าย |
| 650610853 | นาย ภูรินท์ ภัทโรวาสน์ |

---

## Overview

This project connects a **Dobot MG400** robotic arm with a **Python vision system** to detect and classify colored cubes (Yellow, Red, Blue, Green) using **HSV color segmentation**. The robot autonomously performs pick-and-place operations by:

1. Capturing frames from a USB camera.
2. Correcting lens distortion via a radial barrel/pincushion remap.
3. Detecting colored regions in HSV space with per-color threshold windows.
4. Applying morphological operations (erode, dilate, open, close) to clean masks.
5. Selecting the best contour per color using an `area × fill_ratio` scoring heuristic.
6. Mapping pixel centroids to robot-world coordinates via a **4-point perspective transform** (`cv2.getPerspectiveTransform`).
7. Communicating the world-space position to the MG400 over **TCP/IP** for autonomous grasping and placement.

---

## Key Features

- **Real-time multi-color detection** — simultaneous tracking of 4 HSV color ranges (Yellow, Red, Blue, Green), each with independent enable/disable control.
- **Live HSV tuning UI** (`Setup.py`) — dedicated OpenCV trackbar windows per color for adjusting H/S/V lower and upper bounds in real time.
- **Barrel/pincushion lens distortion correction** — adjustable `k` parameter via trackbar; remap is cached and recomputed only when resolution or `k` changes.
- **Morphological pipeline** — selectable operation (None / Erode / Dilate / Open / Close) with configurable kernel size and iteration count.
- **Contour scoring** — `area × fill_ratio` heuristic selects the single best (largest + most compact) contour per color, rejecting noise blobs below `MIN_AREA`.
- **Perspective calibration** — 4-point camera-to-world mapping; `Setup.py` includes a `P` key to print detected centroids for easy calibration point capture.
- **Robot angle estimation** — `minAreaRect` angle extraction with quadrant correction (`90 - angle`), transmitted alongside X/Y coordinates.
- **Persistent configuration** — all HSV ranges, distortion, and morphology settings are saved/loaded from `hsv_config.json`.
- **Threaded architecture** (`Client.py`) — separate `VisionProcessing` and `Mg400` communication threads for non-blocking operation.
- **Dobot Lua program** (`src0.lua`) — TCP server on the MG400 that implements a full pick-and-place state machine with suction gripper control and auto-incrementing placement grid.

---

## Project Structure

```
271401_AI_Mini-lab/
├── Client.py              # Main runtime — vision + MG400 TCP client (threaded)
├── Setup.py               # HSV calibration & perspective point capture tool
├── hsv_config.json        # Persisted HSV ranges, distortion & morphology settings
├── Dobot_import/          # Import this entire folder into Dobot Studio
│   ├── src0.lua           # Main Lua program (TCP server + pick-and-place logic)
│   ├── global.lua         # Global variable declarations for Lua
│   ├── point.json         # Teach points (P1–P6) used by the Lua program
│   ├── point.json.lua     # Lua-formatted teach points
│   ├── prj.json           # Dobot Studio project manifest
│   └── fileCRCCode.json   # File integrity checksums
└── README.md              # This file
```

---

## File Details

### `Setup.py` — HSV Calibration Tool

A standalone OpenCV application for tuning color detection parameters **without** a robot connection.

**What it does:**
- Opens the default camera (index 0).
- Creates a **Controls** window with trackbars for distortion `k`, morphology operation/kernel/iterations, and per-cube world coordinate input.
- Creates **4 individual HSV windows** (one per color: Yellow, Red, Blue, Green) with Low H/S/V and High H/S/V trackbars for real-time threshold adjustment.
- Displays an **Annotated Output** window showing bounding boxes, centroids, confidence scores, and robot-space coordinates overlaid on the distortion-corrected frame.
- Displays a **Combined Mask** window showing the union of all color masks (toggle `]` to cycle individual masks, `[` to show combined).

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `S` | Save current HSV ranges, distortion & morphology settings to `hsv_config.json` |
| `R` | Reload saved settings from `hsv_config.json` and recreate all windows |
| `P` | Print detected cube centroids as a NumPy array (for calibration point capture) |
| `]` | Cycle through individual color masks |
| `[` | Show combined (all colors) mask |
| `Q` / `ESC` | Save settings and quit |

**Perspective calibration output (`P` key):**
```
camera_points = np.float32([[226, 84], [418, 164], [493, 314], [154, 372]])
#Yellow -> Red -> Blue -> Green
```

---

### `Client.py` — Main Runtime

Integrates vision processing with MG400 robot communication using two daemon threads:

#### `VisionProcessing` Thread
- Captures frames from camera index 0 (uses `CAP_DSHOW` on Windows).
- Applies distortion correction, HSV segmentation, morphology, and contour analysis (same pipeline as `Setup.py`).
- Per-color **enable/disable toggles** via trackbars in the Controls window allow selecting which colors to detect at runtime.
- Publishes the **first detected cube's** `[cx, cy, angle]` to the `Mg400` thread via `mg400.pos_frame`.
- Displays the annotated output and combined mask windows.

#### `Mg400` Communication Thread
- Connects to the MG400 TCP server at `192.168.1.6:6601`.
- Sends an initial `"hi"` handshake on connection.
- Operates a state machine:

| State | Trigger | Action |
|-------|---------|--------|
| `wait` | Receives `"start"` | Transitions to `find` |
| `wait` | Receives `"pos?"` | Transitions to `find_pos` |
| `find` | `pos_frame` available | Sends `"found"` → returns to `wait` |
| `find_pos` | `pos_frame` available | Converts pixel coords to world coords via `to_pos_robot()`, sends `"x.xx,y.yy,r.rr"` → returns to `wait` |
| `find_pos` | No detection | Sends `"finish"` |

#### `to_pos_robot()` — Coordinate Transform
```python
camera_points = [[585, 314], [243, 321], [563, 98], [239, 131]]
world_points  = [[368.39, 93.74], [371.16, -29.02], [292.13, 83.77], [302.78, -29.97]]
# matrix = cv2.getPerspectiveTransform(camera_points, world_points)
# Returns: (robot_x, robot_y, 90 - angle)
```

#### Controls Window Trackbars

| Trackbar | Range | Description |
|----------|-------|-------------|
| Distortion k ×100 | 0–200 | Lens distortion coefficient (100 = no distortion) |
| Morph Op (0–4) | 0–4 | 0=None, 1=Erode, 2=Dilate, 3=Open, 4=Close |
| Kernel Size | 1–31 | Morphology kernel size (auto-forced to odd) |
| Iterations | 0–10 | Morphology iteration count |
| Start Mg400 | 0–1 | Set to 1 to start the robot communication thread |
| Enable Yellow | 0–1 | Toggle Yellow color detection |
| Enable Red | 0–1 | Toggle Red color detection |
| Enable Blue | 0–1 | Toggle Blue color detection |
| Enable Green | 0–1 | Toggle Green color detection |

---

### `Dobot_import/src0.lua` — Robot-Side Program

A Lua script that runs on the MG400 inside Dobot Studio. It implements:

1. **TCP Server** — listens on `192.168.1.6:6601` and waits for the Python client's `"hi"` handshake.
2. **Pick-and-Place Loop:**
   - Moves to home position **P1** and sends `"start"` to Python.
   - Waits for `"found"` confirmation, then sends `"pos?"` to request coordinates.
   - Receives `"x,y,r"` string, parses it, and sets **P2** coordinates.
   - Moves to P2 at safe Z (−90), descends to pick Z (−139), activates suction (`DO(1,1)`).
   - Lifts to safe Z, moves via **P4** (transit point) to **P5** (place point).
   - Releases suction (`DO(1,0)`), activates blow-off (`DO(2,1)`) for 2 seconds.
   - Returns via P4 to home.
3. **Auto-Incrementing Placement Grid:**
   - After every pick, P5's X coordinate shifts by +40 mm.
   - Every 4th cube, P5's X resets (−160 mm) and Z increments (+30 mm) to stack on the next row.

**Teach Points (from `point.json`):**

| Point | X | Y | Z | Purpose |
|-------|---|---|---|---------|
| P1 | 266.98 | 229.79 | −37.86 | Home / scanning position |
| P2 | (dynamic) | (dynamic) | −90 → −139 | Pick position (set by Python) |
| P4 | 330.00 | −204.02 | −23.59 | Transit waypoint |
| P5 | 219.27 | −202.27 | −135.00 | Place position (auto-increments) |
| P6 | 350.77 | −16.00 | 7.81 | (Unused / auxiliary) |

---

### `hsv_config.json` — Persistent Settings

Stores all tunable parameters in JSON format:

```json
{
  "ranges": [
    {"name": "Yellow", "lower": [H, S, V], "upper": [H, S, V]},
    {"name": "Red",    "lower": [H, S, V], "upper": [H, S, V]},
    {"name": "Blue",   "lower": [H, S, V], "upper": [H, S, V]},
    {"name": "Green",  "lower": [H, S, V], "upper": [H, S, V]}
  ],
  "distortion_kx100": 95,
  "morph_op": 1,
  "kernel_size": 5,
  "iterations": 0
}
```

This file is automatically loaded on startup by both `Setup.py` and `Client.py`. Press `S` to save or `R` to reload.

---

## Vision Pipeline

```
Camera Frame
    │
    ▼
┌──────────────────────────┐
│  Radial Distortion Remap │  k = (trackbar - 100) / 100
│  cv2.remap()             │  Barrel (k<0) or Pincushion (k>0)
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  BGR → HSV Conversion    │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Per-Color HSV Masking   │  cv2.inRange(hsv, lower, upper)
│  (Yellow, Red, Blue,     │  4 independent masks
│   Green)                 │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Morphological Cleanup   │  Erode / Dilate / Open / Close
│  (configurable kernel    │  with adjustable iterations
│   size & iterations)     │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Contour Detection       │  cv2.findContours(RETR_EXTERNAL)
│  Best contour selection  │  Score = area × fill_ratio
│  (1 per color, ≥MIN_AREA)│
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Centroid + Angle Calc   │  cv2.moments() → (cx, cy)
│                          │  cv2.minAreaRect() → angle
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Perspective Transform   │  4-point homography
│  Pixel → Robot World     │  cv2.perspectiveTransform()
│  (x_mm, y_mm, 90-angle) │
└──────────────────────────┘
    │
    ▼
  TCP → MG400 Robot
```

---

## Communication Protocol

The Python client (`Client.py`) and MG400 Lua server (`src0.lua`) communicate over a raw **TCP socket** on port **6601**.

```
Python (Client)                    MG400 (Server)
     │                                  │
     │──── "hi" ───────────────────────▶│  Handshake
     │                                  │
     │◀──── "start" ───────────────────│  Robot at home, ready
     │                                  │
     │──── "found" ───────────────────▶│  Vision confirmed cube detected
     │                                  │
     │◀──── "pos?" ────────────────────│  Request coordinates
     │                                  │
     │──── "368.39,93.74,45.00" ──────▶│  World X, Y, Rotation
     │                                  │
     │          ... robot picks and places ...
     │                                  │
     │◀──── "start" ───────────────────│  Ready for next cube
     │                                  │
     │──── "finish" ──────────────────▶│  No cube detected (cycle ends)
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.8+ | Runtime |
| OpenCV (`cv2`) | 4.x | Camera capture, HSV segmentation, morphology, contours, perspective transform |
| NumPy | 1.x | Array operations, coordinate math |
| Dobot Studio | — | MG400 firmware IDE (to import and run `Dobot_import/`) |

> **Note:** The `socket`, `time`, `json`, `os`, and `threading` modules are part of the Python standard library.

### Install Python dependencies

```bash
pip install opencv-python numpy
```

---

## How to Run

### Phase 1 — HSV Calibration (`Setup.py`)

1. Place all 4 colored cubes (Yellow, Red, Blue, Green) in the camera's field of view.
2. Run the calibration tool:
   ```bash
   python Setup.py
   ```
3. Adjust the **HSV trackbars** for each color window until only the target cube is visible in the mask. Use the `]` key to cycle through individual masks for fine-tuning.
4. Adjust the **Distortion k ×100** trackbar if the camera has noticeable barrel or pincushion distortion (100 = neutral).
5. Set morphology operation, kernel size, and iterations as needed to clean up noisy masks.
6. Press **`S`** to save settings to `hsv_config.json`.

### Phase 2 — Perspective Calibration

1. In `Setup.py`, position the cubes at known locations in the robot's workspace.
2. Press **`P`** to print the detected camera pixel coordinates of each cube centroid.
3. In **Dobot Studio**, manually jog the robot arm to touch each cube and note the displayed world coordinates (X, Y).
4. Edit the `camera_points` and `world_points` arrays in **`Client.py`** (lines 27–28) with the captured values:
   ```python
   camera_points = np.float32([[pixel_x1, pixel_y1], [pixel_x2, pixel_y2], ...])
   world_points  = np.float32([[robot_x1, robot_y1], [robot_x2, robot_y2], ...])
   ```
5. **Minimum 4 corresponding points** are required (exactly 4 for a perspective transform). More cubes visible improves point selection but only 4 are used.

### Phase 3 — Robot Setup (Dobot Studio)

1. Connect the MG400 to the same local network as the PC (default IP: `192.168.1.6`).
2. Open **Dobot Studio** and import the `Dobot_import/` folder.
3. Verify/adjust the teach points (P1, P4, P5) in Dobot Studio to match your physical workspace layout.
4. Run the Lua program in Dobot Studio — the robot will wait for the Python client's `"hi"` handshake.

### Phase 4 — Run the System (`Client.py`)

1. Start `Client.py`:
   ```bash
   python Client.py
   ```
2. The Python client connects to the MG400 and sends `"hi"`.
3. Use the **Controls** window to:
   - **Enable/disable colors** — toggle which cubes to detect.
   - **Adjust distortion and morphology** in real time.
4. Set the **"Start Mg400"** trackbar to **1** to begin the communication thread.
5. The system will now autonomously:
   - Detect the enabled cube with the highest contour score.
   - Transform its pixel position to robot-world coordinates.
   - Send the coordinates to the MG400 for pick-and-place.
   - The robot places cubes in an auto-incrementing grid pattern.

### Keyboard Shortcuts (Both Scripts)

| Key | Action |
|-----|--------|
| `S` | Save current settings to `hsv_config.json` |
| `R` | Reset/reload settings from `hsv_config.json` |
| `Q` / `ESC` | Save and quit |

---

## How It Works — Full Cycle

```
  ┌─────────────┐      TCP "hi"       ┌─────────────┐
  │  Client.py  │─────────────────────▶│  MG400 Lua  │
  │  (Python)   │                      │  (src0.lua) │
  └──────┬──────┘                      └──────┬──────┘
         │                                    │
         │   1. Robot moves to Home (P1)      │
         │◀──── "start" ─────────────────────│
         │                                    │
         │   2. Vision detects cube           │
         │──── "found" ─────────────────────▶│
         │                                    │
         │   3. Robot requests position       │
         │◀──── "pos?" ──────────────────────│
         │                                    │
         │   4. Perspective transform         │
         │      pixel → world coords          │
         │──── "x.xx,y.yy,r.rr" ───────────▶│
         │                                    │
         │   5. Robot picks cube:             │
         │      • MovJ to P2 (x,y) at Z=-90  │
         │      • Descend to Z=-139           │
         │      • Suction ON (DO 1,1)         │
         │      • Lift to Z=-90              │
         │                                    │
         │   6. Robot places cube:            │
         │      • Move via P4 (transit)       │
         │      • Move to P5 (place)          │
         │      • Suction OFF (DO 1,0)        │
         │      • Blow-off ON (DO 2,1) 2s     │
         │      • Blow-off OFF (DO 2,0)       │
         │      • P5.x += 40mm               │
         │      • Every 4th: reset X, Z += 30 │
         │                                    │
         │   7. Return to Home via P4         │
         │◀──── "start" (next cycle) ────────│
         │                                    │
         ▼                                    ▼
      Repeat until no cubes detected
      ("finish" sent to end session)
```

---

## Configuration Reference

### Default HSV Ranges (hardcoded fallback)

| Color | Lower (H, S, V) | Upper (H, S, V) |
|-------|-----------------|-----------------|
| Yellow | (3, 137, 131) | (47, 226, 220) |
| Red | (150, 147, 137) | (226, 255, 196) |
| Blue | (87, 77, 63) | (150, 250, 255) |
| Green | (36, 68, 114) | (74, 219, 184) |

### Contour Detection Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MIN_AREA` | 200 (Client) / 500 (Setup) | Minimum contour area in pixels² |
| `BOX_TYPE` | 0 | 0 = axis-aligned bbox, 1 = rotated bbox |
| `THICKNESS` | 2 | Drawing line thickness |

### Network Configuration

| Parameter | Value |
|-----------|-------|
| Robot IP | `192.168.1.6` |
| TCP Port | `6601` |
| Protocol | Raw TCP socket, UTF-8 strings |
