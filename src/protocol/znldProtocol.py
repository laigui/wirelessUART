import threading
from libs.E32Serial import E32
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class protocol(threading.Thread):
    def __init__(self, id, role='RC', timeout=5):
        self._timeout = timeout # in seconds
        self._role = role # three roles: 'RC', 'Node', 'Relay'
        self._id = id

    def send_message(self, dest_id, message):
        pass

    def recv_message(self):
        pass