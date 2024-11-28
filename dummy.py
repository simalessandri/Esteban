import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
import gpiozero
from gpiozero.pins.pigpio import PiGPIOFactory
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import RPi.GPIO as GPIO
from multiprocessing import Process
from typing import Optional
import time

# Model for the request body
class MoveRequest(BaseModel):
    step: int

class BuzzerController:
    def __init__(self, pin):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        self.buzzer = GPIO.PWM(pin,1000)

    def play_sound(self, frequency: int, duration: float):
        self.buzzer.ChangeFrequency(frequency)  # Set buzzer to desired frequency
        self.buzzer.start(50)  # Start PWM with 50% duty cycle
        time.sleep(duration)  # Wait for specified duration
        self.buzzer.stop()  # Stop the sound



class ServoController:
    def __init__(self, pin_horizontal, pin_vertical):
        factory = PiGPIOFactory()
        self.servo_horiz = gpiozero.AngularServo(pin_horizontal, min_angle=0, max_angle=180, 
                                                 min_pulse_width=0.0005, max_pulse_width=0.0024,
                                                 pin_factory=factory)
        self.servo_vert = gpiozero.AngularServo(pin_vertical, min_angle=0, max_angle=180,
                                                min_pulse_width=0.0005, max_pulse_width=0.0024,
                                                pin_factory=factory)
        self.horiz_angle = 90
        self.vert_angle = 90
        self.servo_horiz.angle = self.horiz_angle
        self.servo_vert.angle = self.vert_angle

    def move_horizontal(self, step):
        self.horiz_angle = max(0, min(180, self.horiz_angle + step))
        self.servo_horiz.angle = self.horiz_angle
        return self.horiz_angle

    def move_vertical(self, step):
        self.vert_angle = max(0, min(180, self.vert_angle + step))
        self.servo_vert.angle = self.vert_angle
        return self.vert_angle

class Dummy:
    def __init__(self, settings):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings["Dummy"]

    def init_process(self):
        self.controller = ServoController(self.settings["pin_horizontal"], self.settings["pin_vertical"])
        self.buzzer = BuzzerController(self.settings["buzzer_pin"])  # Add buzzer pin

        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):
        @self.app.post("/move_horizontal")
        async def move_horizontal(request: MoveRequest):
            try:
                new_step = self.controller.move_horizontal(request.step)
                return {"status": "success", "new_horizontal_angle": new_step}
            except Exception as e:
                self.logger.error("Failed to move horizontal servo: %s", e)
                raise HTTPException(status_code=500, detail="Failed to move horizontal servo")

        @self.app.post("/move_vertical")
        async def move_vertical(request: MoveRequest):
            try:
                new_step = self.controller.move_vertical(request.step)
                return {"status": "success", "new_vertical_angle": new_step}
            except Exception as e:
                self.logger.error("Failed to move vertical servo: %s", e)
                raise HTTPException(status_code=500, detail="Failed to move vertical servo")

        @self.app.post("/photo_taken_sound")
        async def photo_taken_sound():
            """Endpoint to play a sound indicating a photo has been taken."""
            try:
                self.buzzer.play_sound(1000, 0.5)  # Play sound at 1000 Hz for 0.5 seconds
                return {"status": "success", "message": "Photo taken sound played."}
            except Exception as e:
                self.logger.error("Failed to play photo taken sound: %s", e)
                raise HTTPException(status_code=500, detail="Failed to play photo taken sound")
            
        @self.app.post("/ok_triggered")
        async def ok_triggered():
            """Endpoint to play a sound indicating a photo has been taken."""
            try:
                self.buzzer.play_sound(2000, 0.5)  # Play sound at 1000 Hz for 0.5 seconds
                return {"status": "success", "message": "Photo taken sound played."}
            except Exception as e:
                self.logger.error("Failed to play photo taken sound: %s", e)
                raise HTTPException(status_code=500, detail="Failed to play photo taken sound")            
            

    def run(self):
        self.init_process()
        import uvicorn
        self.logger.info("Starting Dummy service with FastAPI.")
        uvicorn.run(self.app, host="0.0.0.0", port=self.settings["api_port"])
