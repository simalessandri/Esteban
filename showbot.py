import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
import requests
import redis
import uvicorn
import asyncio
import os
import tempfile
import shutil

# Configure logging with class name reference
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

class ShowBot:
    def __init__(self, settings):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings["ShowBot"]
        self.camerabot_port = settings["CameraBot"]["fastapi_port"]
        self.palmist_port = settings["Palmist"]["fastapi_port"]
        self.dummy_port = settings["Dummy"]["api_port"]  # Set dummy port here
        self.queue_settings = settings["queue"]
        self.photos_dir = "/home/pi/photos" 



    def process_setup(self):
        # Initialize Redis connection
        self.redis_conn = redis.Redis(
            host=self.queue_settings["host"],
            port=self.queue_settings["port"],
            db=self.queue_settings["db"]
        )
        self.logger.info("Connected to Redis on %s:%s.", self.queue_settings["host"], self.queue_settings["port"])

        # Initialize FastAPI and templates
        self.app = FastAPI()
        @self.app.on_event("startup")
        async def startup_event():
            asyncio.create_task(self.hand_socket_listener())
        self.templates = Jinja2Templates(directory="templates")
        self.active_connections = []

        # Setup routes
        self.setup_routes()
        self.logger.info("ShowBot initialized successfully.")

    def setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            # Render the main HTML interface and pass the necessary ports
            return self.templates.TemplateResponse(
                "index.html",
                {"request": request, "camerabot_port": self.camerabot_port, "self_port": self.settings["port"],"dummy_port": self.dummy_port}
            )
        @self.app.get("/gallery", response_class=HTMLResponse)
        async def gallery(request: Request):
            # List all photo files in the photos directory
            try:
                photos = [
                    f for f in os.listdir(self.photos_dir)
                    if os.path.isfile(os.path.join(self.photos_dir, f)) and f.endswith(('.png', '.jpg', '.jpeg'))
                ]
                return self.templates.TemplateResponse(
                    "gallery.html",
                    {"request": request, "photos": photos, "self_port": self.settings["port"]}
                )
            except Exception as e:
                self.logger.error("Error loading gallery: %s", e)
                return HTMLResponse("Error loading gallery.", status_code=500)
            
        @self.app.get("/photos/{photo_name}")
        async def download_photo(photo_name: str):
            # Serve the photo for download
            file_path = os.path.join(self.photos_dir, photo_name)
            if os.path.exists(file_path):
                return FileResponse(file_path, filename=photo_name)
            else:
                return HTMLResponse("Photo not found.", status_code=404)
            
        @self.app.get("/photos/download_all")
        async def download_all_photos():
            # Create a temporary ZIP file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                zip_path = tmp_file.name
                with shutil.ZipFile(zip_path, "w") as zipf:
                    for photo_name in os.listdir(self.photos_dir):
                        photo_path = os.path.join(self.photos_dir, photo_name)
                        if os.path.isfile(photo_path) and photo_name.endswith(('.png', '.jpg', '.jpeg')):
                            zipf.write(photo_path, arcname=photo_name)
                self.logger.info("Created ZIP file for all photos.")
            return FileResponse(zip_path, filename="all_photos.zip", media_type="application/zip")

        @self.app.post("/take_photo")
        async def take_photo():
            # Trigger photo capture via CameraBot's API
            try:
                self.logger.info("Triggering photo capture on CameraBot.")
                response = requests.get(f"http://localhost:{self.camerabot_port}/take_photo")
                self.logger.info("Received response from CameraBot for photo capture.")
                return response.json()
            except Exception as e:
                self.logger.error("Error triggering photo capture: %s", e)
                return {"error": str(e)}
            
        @self.app.post("/move_camera")
        async def move_camera(request: Request):
            # Parse the request JSON for direction
            data = await request.json()
            direction = data.get("direction")
            step = 5 if direction in ["up", "right"] else -5

            # Set the endpoint based on direction
            endpoint = "/move_vertical" if direction in ["up", "down"] else "/move_horizontal"
            url = f"http://localhost:{self.dummy_port}{endpoint}"

            try:
                # Make request to dummy server with the step size
                response = requests.post(url, json={"step": step})
                return response.json()  # Return the dummy server response
            except Exception as e:
                self.logger.error("Error moving camera: %s", e)
                return {"error": str(e)}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                while True:
                    await websocket.receive_text()  # Keep connection open
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)

    async def hand_socket_listener(self):
        last_gesture = None
        last_hand_pos = {"x": 0, "y": 0}

        while True:
            # Fetch the latest gesture
            gesture = self.redis_conn.lindex("gesture_queue", -1)

            # Fetch the latest hand position and parse it
            hand_position_data = self.redis_conn.lindex("hand_position_queue", -1)
            hand_pos = None
            if hand_position_data:
                try:
                    # Decode and parse hand position
                    hand_position = hand_position_data.decode("utf-8")
                    hand_x, hand_y = map(float, hand_position.strip("Hand position: ()").split(", "))
                    hand_pos = {"x": hand_x, "y": hand_y}
                except ValueError as e:
                    self.logger.error("Failed to parse hand position data: %s", e)
            else:
                hand_pos = {"x": 0, "y": 0}

            # Decode gesture if it exists, else set to None
            gesture = gesture.decode("utf-8") if gesture else None

            # Check if there's a change in gesture or hand position
            if gesture != last_gesture or hand_pos != last_hand_pos:
                # Update last known values
                last_gesture = gesture
                last_hand_pos = hand_pos

                # Create the message payload
                message = {
                    "gesture": gesture,
                    "hand_pos": hand_pos  # Send as dictionary with 'x' and 'y'
                }

                # Broadcast the message
                await self.broadcast(message)

            # Wait before the next check
            await asyncio.sleep(0.4)



    async def broadcast(self, message):
        # Send the gesture and hand position to all active connections
        if self.active_connections:
            for connection in self.active_connections:
                await connection.send_json(message) 

    def run(self):
        try:
            self.process_setup()
            self.logger.info("Starting ShowBot FastAPI server.")
            uvicorn.run(self.app, host="0.0.0.0", port=self.settings["port"])
            self.logger.info("ShowBot server started successfully.")
        except Exception as e:
            self.logger.error("Error running ShowBot: %s", e)
