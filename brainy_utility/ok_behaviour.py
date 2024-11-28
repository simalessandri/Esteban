# brainy_utility/ok_behaviour.py
import requests
import time
from brainy_utility.behaviour import Behaviour  

class OKBehaviour(Behaviour):
    def __init__(self, redis_conn, camerabot_port,dummy_api_port, cooldown=5):
        super().__init__(redis_conn, cooldown)
        self.camerabot_port = camerabot_port
        self.dummy_api_url = f"http://localhost:{dummy_api_port}"


    def action(self):
        """Listen for the 'OK' gesture on the Redis queue."""
        while True:
            gesture = self.redis_conn.lindex("gesture_queue", -1)
            if gesture and gesture.decode("utf-8") == "Thumb_Up":
                if self.check_cooldown():
                    self.reaction()
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage

    def reaction(self):
        """Trigger the take_photo action via CameraBot."""
        try:
            url = f"{self.dummy_api_url}/ok_triggered"

            try:
                # Make request to dummy server with the step size
                response = requests.post(url)
            except Exception as e:
                self.logger.error("Error triggering take photo sound: %s", e)
                return {"error": str(e)}
            
            time.sleep(2)

            response = requests.get(f"http://localhost:{self.camerabot_port}/take_photo")
            if response.status_code == 200:
                self.logger.info("OK gesture detected, photo taken successfully.")
            else:
                self.logger.error("Failed to take photo, status code: %s", response.status_code)
        except Exception as e:
            self.logger.error("Error triggering photo capture: %s", e)
