import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
import time
import json
import redis
from fastapi import FastAPI
from threading import Thread
import mediapipe as mp
import cv2
import numpy as np
import asyncio
import uvicorn

# Configure logging with class name reference
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

class Palmist:
    def __init__(self, settings):
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            self.settings = settings["Palmist"]
            self.queue_settings = settings["queue"]
            self.logger.info("Palmist initialized successfully.")
            self.last_hand_position = (None, None)  # To store the last (x, y) position
            self.notfoundnotified=True
        except Exception as e:
            self.logger.error("Error initializing Palmist: %s", e)
    
    def process_init(self):
        try:
            # Initialize settings and Redis connection
            self.redis_conn = redis.Redis(
                host=self.queue_settings["host"],
                port=self.queue_settings["port"],
                db=self.queue_settings["db"]
            )
            self.current_gesture = None
            self.app = FastAPI()

            # Setup Mediapipe GestureRecognizer
            self.setup_mediapipe()
            self.setup_routes()
            self.logger.info("Palmist process initialized successfully.")
        
        except Exception as e:
            self.logger.error("Error initializing Palmist: %s", e)

    def setup_mediapipe(self):
        BaseOptions = mp.tasks.BaseOptions
        GestureRecognizer = mp.tasks.vision.GestureRecognizer
        GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
        RunningMode = mp.tasks.vision.RunningMode

        # Initialize GestureRecognizer with callback for result processing
        self.options = GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path='gesture_recognizer.task'),
            running_mode=RunningMode.LIVE_STREAM,
            result_callback=self.gesture_callback
        )
        self.gesture_recognizer = GestureRecognizer.create_from_options(self.options)

    def gesture_callback(self, result, img, timestamp_ms):
        # Handle gesture recognition result
        if result.gestures:
            top_gesture = result.gestures[0][0]
            gesture_name = top_gesture.category_name
            confidence = top_gesture.score

            # Check if the detected gesture is different from the current one
            if confidence > 0.50 and gesture_name != self.current_gesture:
                self.current_gesture = gesture_name
                # Push the new gesture into the gesture_queue
                self.redis_conn.rpush("gesture_queue", gesture_name)
                self.logger.info("New gesture detected and pushed to gesture_queue: %s", gesture_name)
            elif gesture_name!= self.current_gesture:
                self.current_gesture = "No gesture"
                self.redis_conn.rpush("gesture_queue", self.current_gesture)

        else:
            self.current_gesture = "No gesture"
            self.redis_conn.rpush("gesture_queue", self.current_gesture)


         # Handle hand position
        if result.hand_landmarks:
            self.notfoundnotified=False
            hand_landmarks = result.hand_landmarks[0]
            wrist_landmark = hand_landmarks[0]
            hand_x = wrist_landmark.x
            hand_y = wrist_landmark.y
            
            # Calculate the difference from the last known position
            last_x, last_y = self.last_hand_position
            if last_x is not None and last_y is not None:
                delta_x = abs(hand_x - last_x)
                delta_y = abs(hand_y - last_y)

                # Check if the change is greater than the defined offset
                if delta_x > self.settings["position_offest"] or delta_y > self.settings["position_offest"]:
                    # Push hand position to the hand_position_queue
                    self.redis_conn.rpush("hand_position_queue", f"Hand position: ({hand_x}, {hand_y})")
                    self.logger.info("New hand position detected and pushed to hand_position_queue: (%f, %f)", hand_x, hand_y)
                    # Update the last known hand position
                    self.last_hand_position = (hand_x, hand_y)
            else:
                # If there was no last position, initialize it
                self.last_hand_position = (hand_x, hand_y)
        else:
            if not self.notfoundnotified:
                self.redis_conn.rpush("hand_position_queue", f"Hand position: (0, 0)")
                self.logger.info("Hand not found")
                self.notfoundnotified=True

    def setup_routes(self):
        @self.app.get("/current_gesture")
        async def current_gesture():
            # Return the current detected gesture
            return {"gesture": self.current_gesture or "No gesture detected"}

        self.logger.info("Routes setup completed successfully.")

    def process_frame(self, frame):
        try:
            # Convert frame data into the format required by Mediapipe
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            self.gesture_recognizer.recognize_async(image, int(time.time() * 1e6))
        except Exception as e:
            self.logger.error("Error processing frame for gesture recognition: %s", e)

    def read_stream_and_detect(self):
        while True:
            try:
                # Get the latest frame from the Redis streaming queue
                frame_data = self.redis_conn.get("streaming_queue")
                if frame_data:
                    frame = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                    self.process_frame(frame)
                else:
                    self.logger.warning("No frame available in Redis streaming queue.")
                time.sleep(1 / self.settings["fps_streaming"])

            except Exception as e:
                self.logger.error("Error in read_stream_and_detect loop: %s", e)
                break

    def run(self):
        try:
            # Start frame reading and gesture recognition in a separate thread
            self.process_init()
            self.logger.info("Starting Palmist frame processing.")
            Thread(target=self.read_stream_and_detect).start()

            # Run FastAPI server
            self.logger.info("Starting Palmist FastAPI server.")
            uvicorn.run(self.app, host="0.0.0.0", port=self.settings["fastapi_port"])

        except Exception as e:
            self.logger.error("Error running Palmist: %s", e)
