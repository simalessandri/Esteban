import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
import threading
import redis
from brainy_utility.ok_behaviour import OKBehaviour  # Import from brainy_utility
from brainy_utility.open_palm_behaviour import OpenPalmBehaviour

class Brainy:
    def __init__(self, settings):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings["Brainy"]
        self.queue_settings = settings["queue"]
        self.camerabot_port = settings["CameraBot"]["fastapi_port"]
        self.dummy_api_port = settings["Dummy"]["api_port"]

        
        # Initialize Redis connection
        self.redis_conn = redis.Redis(
            host=self.queue_settings["host"],
            port=self.queue_settings["port"],
            db=self.queue_settings["db"]
        )
        
        # Initialize behaviours
        self.behaviours = [
            OKBehaviour(self.redis_conn, self.camerabot_port,  self.dummy_api_port,cooldown=self.settings.get("ok_cooldown", 5)),
            OpenPalmBehaviour(self.redis_conn, self.dummy_api_port, cooldown=self.settings.get("open_palm_cooldown", 5))

        ]
        self.logger.info("Brainy initialized with behaviours.")

    def start_behaviour_threads(self):
        threads = []
        for behaviour in self.behaviours:
            thread = threading.Thread(target=behaviour.action, daemon=True)
            thread.start()
            threads.append(thread)
            self.logger.info("%s behaviour started in a new thread.", behaviour.__class__.__name__)
        return threads

    def run(self):
        try:
            self.logger.info("Starting Brainy service.")
            threads = self.start_behaviour_threads()
            for thread in threads:
                thread.join()  # Wait for each thread to complete
            self.logger.info("Brainy service completed all behaviours.")
        except Exception as e:
            self.logger.error("Error running Brainy service: %s", e)
