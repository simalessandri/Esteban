import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from threading import Thread, Condition
from fastapi import FastAPI, WebSocket
from picamera2.outputs import FileOutput
import uvicorn
import io
import redis
import time
import threading
import asyncio
import requests

# Configure logging with class name reference
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)  # Logger with class name
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        try:
            with self.condition:
                self.frame = buf
                self.condition.notify_all()
        except Exception as e:
            self.logger.error("Error writing frame to output: %s", e)

class CameraBot:
    def __init__(self, settings):
        self.logger = logging.getLogger(self.__class__.__name__)  # Logger with class name
        try:
            # Use specific group settings and initialize Redis
            self.settings = settings["CameraBot"]
            self.queue_settings = settings["queue"]
            self.dummy_port = settings["Dummy"]["api_port"]  # Set dummy port here

           
        
        except Exception as e:
            self.logger.error("Error initializing CameraBot: %s", e)

    def process_init(self):
            self.redis_conn = redis.Redis(
                host=self.queue_settings["host"],
                port=self.queue_settings["port"],
                db=self.queue_settings["db"]
            )
            self.logger.info("Connected to Redis on %s:%s.", self.queue_settings["host"], self.queue_settings["port"])
            
            #!!!! non puoi inmizializzare la risorsa camera qui altrimenti nel nuovo processo muore
            self.app = FastAPI()

            self.setup_routes()
            self.logger.info("CameraBot initialized successfully.")

            self.camera = Picamera2()
            config = self.camera.create_video_configuration(buffer_count=4,
                main={"size": self.settings["photo_size"], "format": 'RGB888'},
                lores={"size": self.settings["streaming_size"],"format": 'YUV420'},encode="main"
            )
            
            self.camera.configure(config)
            self.logger.info("Camera configured with settings: %s", config)
            
            # Encoder and streaming setup
            self.encoder = MJPEGEncoder()
            self.streamOut = StreamingOutput()
            self.encoder.output = FileOutput(self.streamOut)
            self.encoder.framerate = 10
            self.encoder.size = config["lores"]["size"]
            self.encoder.format = "RGB888"

    def get_frame(self):
        try:
            with self.streamOut.condition:
                self.streamOut.condition.wait()
                self.frame = self.streamOut.frame

            return self.frame
        except Exception as e:
            self.logger.error("Error retrieving frame: %s", e)
            return None

    def setup_routes(self):
        try:
            @self.app.get("/take_photo")
            async def take_photo():
                try:
                    # Capture photo and store in Redis queue
                    file_path = f"/home/pi/photos/photo_{int(time.time())}.jpg"
                    self.camera.capture_file(file_path)
                    #self.redis_conn.rpush("photo_queue", file_path)
                    self.logger.info("Photo taken and added to Redis queue with path %s", file_path)

                    url = f"http://localhost:{self.dummy_port}/photo_taken_sound"

                    try:
                        # Make request to dummy server with the step size
                        response = requests.post(url)
                    except Exception as e:
                        self.logger.error("Error triggering take photo sound: %s", e)
                        return {"error": str(e)}


                    return {"message": "Photo taken", "path": file_path}
                except Exception as e:
                    self.logger.error("Error taking photo: %s", e)
                    return {"error": str(e)}
                

            @self.app.websocket("/stream")
            async def stream(websocket: WebSocket):
                await websocket.accept()
                self.logger.info("WebSocket connection accepted.")

                try:
                    while True:
                        frame = self.get_frame()
                        if frame:
                            await websocket.send_bytes(frame)
                        else:
                            self.logger.warning("No frame available to send over WebSocket.")
                        await asyncio.sleep(0)  # Yield control

                except Exception as e:
                    self.logger.error("Error during WebSocket streaming: %s", e)
                finally:
                    await websocket.close()  # Explicitly close WebSocket on exit
                    self.logger.info("WebSocket connection closed.")


            self.logger.info("Routes setup completed successfully.")
        
        except Exception as e:
            self.logger.error("Error setting up routes: %s", e)



    def run(self):
        try:
            # Start streaming and camera encoder on the main thread
            self.logger.info("Starting camera streaming and encoder.")
            self.process_init()
            time.sleep(1)
            self.camera.start_encoder(self.encoder)
            self.camera.start()

            self.logger.info("CameraBot started and camera streaming initialized.")
            self.logger.info("Starting CameraBot FastAPI server.")
            Thread(target=self.stream_frames).start()
            uvicorn.run(self.app, host="0.0.0.0", port=self.settings["fastapi_port"])
        
        except Exception as e:
            self.logger.error("Error running CameraBot: %s", e)

    def stream_frames(self):
        self.logger.info("Entering in stream_frames queue loop.")
        while True:
            try:
                # Push frames into streaming queue at specified FPS
                frame = self.get_frame()
                if frame:
                    self.redis_conn.set("streaming_queue", frame)
                else:
                    self.logger.warning("No frame available to push to Redis streaming queue.")
                time.sleep(1 / self.settings["fps_streaming"])
            
            except Exception as e:
                self.logger.error("Error in stream_frames loop: %s", e)
                break
