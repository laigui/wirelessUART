import threading
from time import sleep

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

import os
if os.uname()[4].find('arm') == 0:
    import RPi.GPIO as GPIO
    ISRPI = True
else:
    ISRPI = False

from libs.E32Serial import E32


class Protocol(threading.Thread):
    def __init__(self, id, role='RC', timeout=5):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self._timeout = timeout # in seconds
        self._role = role # three roles: 'RC', 'Node', 'Relay'
        assert role=='RC' or role=='Node' or role=='Relay', 'Protocol role mistake!'
        self._id = id
        self._tx_frame_len = 0
        if self._role == 'RC':
            self._rx_frame_len = 34
        elif self._role == 'Node':
            self._rx_frame_len = 21
        if ISRPI:
            port = '/dev/ttyS0'
        else:
            port = '/dev/ttyUSB0'
        self.ser = E32(port=port, inHex=False)
        try:
            self.ser.open()
        except:
            logger.error('The serial %s open failed!' % port)
            raise
        self._frame_header = '5555'
        self._frame_no = '00'
        self._frame_crc = '00000000'

    def __del__(self):
        self.ser.close()

    def send_message(self, dest_id, message):
        if self._role == 'RC':
            assert len(message) == 4, 'RC message length is not 4'
        if self._role == 'Node':
            assert len(message) == 17, 'Node message length is not 17'
        tx_str = self._frame_header + self._id + dest_id + self._frame_no + message
        try:
            self.ser.transmit(tx_str)
        except:
            logger.error('Tx error!')
        pass

    def recv_message(self):
        pass

    def run(self):
        logger.debug('Thread receiving start running until it is stop on purpose.')
        while not self.thread_stop:
            rx_str = self.ser.receive(self._rx_frame_len) # keep receiving until getting required bytes
            logger.debug(rx_str)
        pass

    def stop(self):
        self.thread_stop = True


if __name__ == "__main__":
    try:
        logging.basicConfig(level='DEBUG')
        foo = Protocol(id='123')
        foo.setName('Thread receiving')
        foo.start()
        while True:
            sleep(1)
            foo.send_message('11','hell')
            pass
    except KeyboardInterrupt:
        foo.stop()
        foo.join()
        pass