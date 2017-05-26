import binascii, ctypes, struct
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
    class LampControl:
        FRAME_HEADER = '\x55\x55'
        BYTE_RESERVED = '\x00'
        BYTE_ALL_OFF = '\x00'
        BYTE_ALL_ON = '\x03'
        BYTE_LEFT_ON = '\x01'
        BYTE_RIGHT_ON = '\x02'
        TAG_ACK = '\x01'
        TAG_LAMP_CTRL = '\x05'

        MESG_LAMP_ALL_ON = TAG_LAMP_CTRL + BYTE_ALL_ON + '\xFF' * 2
        MESG_LAMP_ALL_OFF = TAG_LAMP_CTRL + BYTE_ALL_OFF + BYTE_RESERVED * 2
        MESG_ACK = TAG_ACK + BYTE_RESERVED * 3
        MESG_NACK = TAG_ACK + '\x01' + BYTE_RESERVED * 2
        pass

    def __init__(self, id, role='RC', timeout=5):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self._timeout = timeout # in seconds
        self._role = role # three roles: 'RC', 'Node', 'Relay'
        assert role=='RC' or role=='Node' or role=='Relay', 'Protocol role mistake!'
        self._id = id
        self._tx_frame_len = 23
        if self._role == 'RC':
            self._rx_frame_len = 23
        elif self._role == 'Node':
            self._rx_frame_len = 23
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
        self._frame_no = 0

    def __del__(self):
        self.ser.close()

    def send_message(self, dest_id, message):
        if self._role == 'RC':
            assert len(message) == 4, 'RC message length is not 4'
        if self._role == 'Node':
            assert len(message) == 4, 'Node message length is not 4'
        tx_str = self.LampControl.FRAME_HEADER + self._id + dest_id + chr(self._frame_no) + message
        #crc32 = hex(int(ctypes.c_uint32(binascii.crc32(tx_str)).value))[2:]
        crc32 = struct.pack('>L', ctypes.c_uint32(binascii.crc32(tx_str)).value) # MSB firstly
        tx_str = tx_str + crc32
        logger.debug('TX: {0}'.format(binascii.b2a_hex(tx_str)))
        try:
            self.ser.transmit(tx_str)
        except:
            logger.error('Tx error!')
        else:
            self._frame_no += 1
            if self._frame_no == 250:
                self._frame_no = 0
        pass

    def _recv_frame(self):
        '''
        check the frame header and later the checksum, return the whole frame until the checksum is correct.
        :return: the received frame
        '''
        done = False
        got_header = False
        rx_str = ''
        rx_len = self._rx_frame_len
        while not done:
            rx_str = rx_str + self.ser.receive(rx_len)  # keep receiving until getting required bytes
            if not got_header:
                index = rx_str.find(self.LampControl.FRAME_HEADER)
                if index == -1:
                    rx_str = ''
                else:
                    got_header = True
                    rx_str = rx_str[index:]
                    rx_len = self._rx_frame_len - rx_len + index
                    logger.debug('Header got')
            else:
                rx_crc32 = rx_str[-4 :]
                str_payload = rx_str[0 : self._rx_frame_len - 5]
                crc32 = struct.pack('>L', ctypes.c_uint32(binascii.crc32(str_payload)).value)  # MSB firstly
                if crc32 == rx_crc32:
                    done = True
                else:
                    got_header = False
                    rx_str = rx_str[2 :]
                    rx_len = 2
                    logger.debug('CRC32 check failed, remove Header and continue: %s != %s', rx_crc32, crc32)
        logger.debug('RX: {0}'.format(binascii.b2a_hex(rx_str)))
        return rx_str

    def _frame_process(self, rx_frame):
        '''
        received frame processing per the protocol
        :param rx_frame: the received frame
        :return: 
        '''
        pass

    def run(self):
        logger.info('Thread receiving starts running until it is stop on purpose.')
        while not self.thread_stop:
            rx_frame = self._recv_frame()
            self._frame_process(rx_frame)
        pass

    def stop(self):
        self.thread_stop = True


if __name__ == "__main__":
    try:
        logging.basicConfig(level='DEBUG')
        RC_ID = '\x00\x00\x00\x00\x00\x01'
        Node1_ID = '\x00\x00\x00\x00\x00\x02'
        foo = Protocol(id=RC_ID)
        foo.setName('Thread receiving')
        foo.start()
        while True:
            sleep(3)
            foo.send_message(Node1_ID,Protocol.LampControl.MESG_LAMP_ALL_ON)
            pass
    except KeyboardInterrupt:
        foo.stop()
        foo.join()
        pass