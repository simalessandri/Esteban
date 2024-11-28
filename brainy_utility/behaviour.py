# behaviour.py
import abc
import time
import logging

class Behaviour(abc.ABC):
    def __init__(self, redis_conn, cooldown=5):
        self.redis_conn = redis_conn
        self.cooldown = cooldown
        self.last_triggered = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def action(self):
        """Define the condition to listen for specific events."""
        pass

    @abc.abstractmethod
    def reaction(self):
        """Define the response to an event."""
        pass

    def check_cooldown(self):
        """Check if cooldown period has passed since the last trigger."""
        current_time = time.time()
        if current_time - self.last_triggered >= self.cooldown:
            self.last_triggered = current_time
            return True
        return False
