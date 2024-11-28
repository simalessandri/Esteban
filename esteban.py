import logging
import os
import json
import signal
import sys
from datetime import datetime, timedelta
from multiprocessing import Process
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from glob import glob
import uvicorn
from time import sleep

# Import service classes
from camerabot import CameraBot
from showbot import ShowBot
from palmist import Palmist
from brainy import Brainy
from dummy import Dummy



class Esteban:
    def __init__(self, config_path):
        try:
            setup_logging()
            self.logger = logging.getLogger(self.__class__.__name__)  # Logger with class name
            self.settings = self.load_settings(config_path)
            self.processes = []  
            signal.signal(signal.SIGTERM, self.terminate_processes)  # Register signal handler
            signal.signal(signal.SIGINT, self.terminate_processes)
            self.logger.info("Esteban initialized with configuration file %s", config_path)
        except Exception as e:
            self.logger.error("Failed to initialize Esteban: %s", e)

    def load_settings(self, config_path):
        try:
            with open(config_path, "r") as file:
                settings = json.load(file)
            self.logger.info("Settings loaded successfully from %s", config_path)
            return settings
        except Exception as e:
            self.logger.error("Failed to load settings from %s: %s", config_path, e)
            sys.exit(1)

    def create_logging_app(self):
        app = FastAPI()

        templates = Jinja2Templates(directory="templates")

        @app.get("/", response_class=HTMLResponse)
        async def read_root(request: Request) -> HTMLResponse:
            log_files = glob("/home/pi/estevan/log/*.log")
            log_files = [os.path.basename(f) for f in log_files]  # Get only the file names
            return templates.TemplateResponse("log_view.html", {"request": request, "log_files": log_files})

        @app.get("/logs/{filename}", response_class=HTMLResponse)
        async def read_log_file(request: Request, filename: str, level: str = Query(None)) -> HTMLResponse:
            try:
                file_path = os.path.join("/home/pi/estevan/log", filename)
                if not os.path.isfile(file_path):
                    raise HTTPException(status_code=404, detail="Log file not found")

                log_entries = []
                with open(file_path, 'r') as file:
                    for line in file:
                        # Split the line by " - "
                        parts = line.split(" - ")
                        
                        # Check if the line has the expected number of parts
                        if len(parts) == 4:
                            log_entry = {
                                "date": parts[0].strip(),        # The date and time
                                "type": parts[1].strip(),        # The type of log (e.g., INFO)
                                "service": parts[2].strip(),     # The service name
                                "message": parts[3].strip()      # The log message
                            }
                            log_entries.append(log_entry)
                            
                log_entries.sort(key=lambda entry: entry["datetime"], reverse=True)
                return templates.TemplateResponse("log_view.html", {"request": request, "log_files": glob("/home/pi/estevan/log/*.log"), "log_entries": log_entries})
            except Exception as e:
                self.logger.error("Error serving logs: %s", e)

        return app
    
    def start_service(self, service_class):
        try:
            service = service_class(self.settings)  # Pass the full settings object
            process = Process(target=service.run)
            process.start()
            self.logger.info("%s service started in a new process with PID %s", service_class.__name__, process.pid)
            return process
        except Exception as e:
            self.logger.error("Error starting %s service: %s", service_class.__name__, e)

    def run(self):
        try:
            for service_class in [CameraBot, ShowBot, Palmist, Brainy, Dummy]:
                self.start_service(service_class)

            app = self.create_logging_app()
            uvicorn_process = Process(target=lambda: uvicorn.run(app, host="0.0.0.0", port=self.settings["Esteban"]["logging_port"]), daemon=True)
            uvicorn_process.start()
            self.processes.append(uvicorn_process)

            for process in self.processes:
                if process.is_alive():
                    process.join()
            self.logger.info("All services have completed execution.")
        except Exception as e:
            self.logger.error("Error running Esteban services: %s", e)
            self.terminate_processes()

    def terminate_processes(self, signum=None, frame=None):
        self.logger.info("Terminating all processes.")
        for process in self.processes:
            if process.is_alive():
                self.logger.info("Terminating process with PID %s.", process.pid)
                process.terminate()
                process.join()
        self.logger.info("All processes terminated.")

if __name__ == "__main__":
    retry_count = 3 
    for attempt in range(retry_count):
        try:
            esteban = Esteban("settings.json")
            esteban.run()
            break  
        except Exception as e:
            logging.error("Failed to start Esteban (attempt %d/%d): %s", attempt + 1, retry_count, e)
            sleep(5)  # Delay before retry
    else:
        logging.critical("Esteban failed to start after %d attempts. Exiting.", retry_count)
        sys.exit(1)


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",handlers=[
            logging.FileHandler("/home/pi/estevan/log/esteban.log"),
            logging.StreamHandler()  # Optional: log to console
            ])
    log_dir = "/home/pi/estevan/log"
    os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist
    log_filename = os.path.join(log_dir, "esteban.log")
    
    if os.path.exists(log_filename):
        file_mod_time = os.path.getmtime(log_filename)
        file_mod_datetime = datetime.fromtimestamp(file_mod_time)
        if datetime.now() - file_mod_datetime > timedelta(days=1):
            new_filename = os.path.join(log_dir, f"esteban_{file_mod_datetime.strftime('%Y%m%d_%H%M%S')}.log")
            os.rename(log_filename, new_filename)  # Rename the old log file
