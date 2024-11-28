# brainy_utility/open_palm_behaviour.py
import requests
import time
import json
import logging
from brainy_utility.behaviour import Behaviour

class OpenPalmBehaviour(Behaviour):
    def __init__(self, redis_conn, dummy_api_port, cooldown=5):
        super().__init__(redis_conn, cooldown)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dummy_api_url = f"http://localhost:{dummy_api_port}"

    def action(self):
        while True:
            gesture = self.redis_conn.lindex("gesture_queue", -1)
            if gesture and gesture.decode("utf-8") == "Open_Palm":
                if self.check_cooldown():
                    self.reaction()
            time.sleep(0.1)

    def reaction(self):
        self.logger.info("Open Palm gesture detected, starting hand positioning adjustments.")
        
        while True:
            hand_position_data = self.redis_conn.lindex("hand_position_queue", -1)
            if hand_position_data:
                hand_position = hand_position_data.decode("utf-8")
                hand_x, hand_y = map(float, hand_position.strip("Hand position: ()").split(", "))

                move_x = 0.5-hand_x
                move_y = 0.5-hand_y 

                step_x = self.convert_to_step(move_x)
                step_y = self.convert_to_step(move_y)

                self.logger.info(f"Adjusting position: Move X by {step_x} degrees, Move Y by {step_y} degrees.")

                try:
                    if abs(step_x) > 0:
                        self.move_motor("horizontal", step_x)
                    if abs(step_y) > 0:
                        self.move_motor("vertical", step_y)
                except Exception as e:
                    self.logger.error(f"Failed to send move command to Dummy: {e}")

                time.sleep(0.5)

            gesture = self.redis_conn.lindex("gesture_queue", -1)


            if (not gesture or gesture.decode("utf-8") != "Open_Palm"):
                self.logger.info("No open_palm gesture detected for more than 1 second, stopping adjustments.")
                break
            time.sleep(0.1)

    def convert_to_step(self, move_value, max_step=10):
        return int(move_value * max_step)

    def move_motor(self, direction, step):
        url = f"{self.dummy_api_url}/move_{direction}"
        response = requests.post(url, json={"step": step})
        if response.status_code != 200:
            self.logger.error(f"Failed to move {direction} motor: {response.text}")
