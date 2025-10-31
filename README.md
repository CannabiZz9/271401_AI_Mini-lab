# 271401_AI_Mini-lab
AI-integrated mini-lab project for the Dobot MG400 robotic arm — built with Python + OpenCV to perform color-based object detection and pick-and-place.

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
  1. Dobot_import/              # Import this folder into Dobot Studio
  2. Client.py              # Main script integrating OpenCV vision and MG400 communication
  3. Setup.py               # HSV configuration and calibration tool
  4. hsv_config.json        # Saved HSV color and morphology settings
  5. README.md              # (This file)


Dependencies
  1.Python 3.8+
  2.OpenCV (cv2)
  3.NumPy
  4.Socket
  5.Dobot Studio

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
