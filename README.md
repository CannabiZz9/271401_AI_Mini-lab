# 271401_AI_Mini-lab
AI-integrated mini-lab project for the Dobot MG400 robotic arm — built with Python + OpenCV to perform color-based object detection and pick-and-place.

650610828 นาย จักรพงศ์ วงศ์วิวัฒน์ธนะ
650610829 นาย จินตพัฒน์ ตาอ้าย
650610853 นาย ภูรินท์ ภัทโรวาสน์

Overview 

  This project connects a Dobot MG400 robot with a Python vision system to detect and classify colored objects (red, green, blue, yellow) using HSV color segmentation.
The robot performs pick and place operations based on the detected color and its position in the camera frame, using a calibrated perspective transform to convert pixel coordinates to world coordinates.

Key Features
  1. OpenCV-based vision for real-time color detection and contour tracking after morphology process. 
  2. HSV configuration interface with trackbars for live tuning (Setup.py)
  3. Dobot MG400 control via TCP/IP client (Client.py)
  4. Perspective calibration for accurate pixel-to-robot coordinate mapping
  5. JSON configuration file (hsv_config.json) to store HSV and morphology settings

Project Structure 
  1. Dobot_import/          # Import this folder into Dobot Studio
  2. Client.py              # Main script integrating OpenCV vision and MG400 communication
  3. Setup.py               # HSV configuration and calibration tool
  4. hsv_config.json        # Saved HSV color and morphology settings
  5. README.md              # (This file)


Dependencies
  1. Python 3.8+
  2. OpenCV (cv2)
  3. NumPy
  4. Socket
  5. Dobot Studio

How to Run
  1. Run Setup.py to tune HSV color ranges and save hsv_config.json.
  2. Press “P” in the console to print detected camera coordinates of each cube.
  3. Open Dobot studio and connect your Dobot MG400 to the same local network. Then import folder Dobot_import
  4. Manually move the robot arm to touch each cube color in the sequence printed in the console.
  5. Read the corresponding position values(X,Y) from Dobot Studio and edit the code in Client.py for each cube’s world coordinate return.
  6. Repeat the calibration process until all cube values are filled. At least 2 cubes are required for proper operation, but 3 or more are recommended for better accuracy.
  7. Adjust settings via the “Controls” window or keyboard shortcuts (S = save, R = reset, Q = quit).
  8. Run program in Dobot studio
  9. Run Client.py to start real-time color detection and robot control.
  10. In control panel choose what color to pick then set start bar to 1.

How It Works
  1. The user sets conditions.
  2. Python and the Dobot MG400 establish a handshake for communication.
  3. Python processes real-time images from the camera using OpenCV to detect color thresholds:
  
    3.1 Fix distortion
    3.2 Detect color regions
    3.3 Apply morphology operations
     
  5. Find minimum (x, y) and maximum (x, y) positions of each cube for bounding box, rotation and center(x,y) then map into world space.
  6. The Dobot sends a request to Python asking for the cube position.
  7. Python returns the cube coordinates in world space.
  8. The Dobot moves to the predefined pick-up point.
  9. The Dobot moves to the cube position.
  10. The Dobot picks up the cube and places it in the designated area.
  11. The Dobot returns to its home position and waits for Python’s next position update (waiting state).
