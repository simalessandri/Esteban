# Esteban – Raspberry Pi Gesture-Controlled Camera System  

Esteban is a microservice-based system designed to enable gesture recognition, automated photo capture, and remote camera control using a Raspberry Pi 3 Model B+ and a Sony IMX708 camera sensor. The system leverages FastAPI, MediaPipe, and multiprocessing queues to create a responsive, modular environment that tracks hand gestures in real-time, adjusts camera angles, and captures high-resolution photos.  

The camera, mounted on a custom 3D-printed structure, can move horizontally using a stepper motor and tilt vertically with a servo motor. Camera operations are handled through the picamera2 library. All 3D-printed parts will soon be available for download.  

## Project Overview  

Esteban’s architecture is built on six microservices that handle distinct functionalities and communicate through queues and sockets. This design ensures modularity, scalability, and real-time responsiveness.  

### Core Technologies  
- **FastAPI** – Provides lightweight, asynchronous APIs for camera control and hardware I/O.  
- **MediaPipe** – Powers hand-tracking and gesture recognition.  
- **Multiprocessing Queue** – Enables fast, thread-safe communication between microservices.  

The system autonomously reacts to recognized gestures (such as capturing photos or repositioning the camera). A web interface allows users to control the system manually, view live streams, and download captured photos.  

## Microservice Architecture  

### 1. Esteban – System Orchestrator  
Esteban is the primary service responsible for initializing and managing all other microservices. It ensures the proper startup and shutdown of the system and manages configurations. Without Esteban running, the system cannot function, as it orchestrates dependencies between services.  

### 2. Brainy – Behavior and Logic Processor  
Brainy implements the system's behavior and acts as the interface between services. It reads gestures from the Palmist queue and makes decisions by invoking Dummy’s API to control motors or buzzers. Brainy uses a behavior-based architecture:  
- **Photo Capture** – Detects a thumbs-up (OK) gesture and triggers a delayed photo capture.  
- **Hand Centering** – Recognizes an open hand and repositions the camera to center the hand by adjusting the motors.  

To add new functionalities, developers can implement additional behavior classes within Brainy by extending the existing `Behavior` class.  

### 3. Camerabot – Camera Controller  
Camerabot provides FastAPI endpoints to trigger photo captures and manage live streaming. Depending on requirements, it streams video through a queue or socket connection. Camerabot interfaces directly with the Sony IMX708 sensor via picamera2.  

### 4. Palmist – Gesture Recognition  
Palmist utilizes MediaPipe to track hand positions and deduce gestures, continuously streaming results to Brainy through a queue. This real-time gesture recognition system enables fluid, interactive control.  

### 5. Dummy – Hardware I/O Handler  
Dummy exposes APIs (through FastAPI) to manage stepper and servo motors, as well as the buzzer. Brainy sends movement commands to Dummy to physically adjust the camera's orientation or trigger hardware responses.  

### 6. Showbot – Web Interface  
Showbot provides a web-based interface to interact with Esteban. Users can:  
- View live camera streams  
- Manually adjust the camera’s position (horizontal and vertical)  
- Capture photos  
- Download captured photos  

## Installation Process  

Esteban includes an installation script (`installation.sh`) located in the installation directory. This script installs Esteban as a systemd service, ensuring the system automatically starts on boot.  

### Installation Script Breakdown  
- **Directory Setup** – The script creates the installation directory (`/opt/esteban`) and copies project files.  
- **Systemd Integration** – A service file (`esteban.service`) is copied to `/etc/systemd/system`, enabling Esteban to run as a background service.  
- **Permissions and Startup** – File permissions are set, and the service is enabled and started. The script reloads systemd to recognize the new service.  

To install, run the following command:  
```bash
sudo ./install.sh
```
This will install and activate Esteban, ensuring the entire system launches on startup without manual intervention.

## Future To-Do List

Esteban is operational, but several enhancements are planned to expand its capabilities:

1. **Multi-Hand Recognition**  
   Extend Palmist to track multiple hands simultaneously. Brainy’s logic will be updated to handle concurrent gestures and prioritize actions.

2. **PID-Controlled Centering**  
   Implement a PID (Proportional-Integral-Derivative) loop for smoother, more accurate camera centering, replacing the current step-based approach.

3. **Working Modes (Dynamic Behaviors)**  
   Introduce different operational modes to control camera movement based on detected gestures:  
   - **Search Mode** – The camera scans the environment until a hand is detected.  
   - **Idle Mode** – The camera remains still until a gesture triggers movement.  
   - **Tracking Mode** – The camera follows a detected hand persistently.

4. **Gesture Chaining**  
   Develop logic to recognize gesture sequences, allowing more complex interactions (e.g., open hand followed by a thumbs-up triggers a special action).

5. **Voice Control Integration**  
   Explore integrating voice commands to control camera functions using lightweight voice recognition models.

6. **AI-Based Hand Gesture Expansion**  
   Train custom models to detect additional gestures, expanding the interaction possibilities and providing more nuanced control.
