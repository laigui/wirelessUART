import binascii, ctypes, struct, Queue
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
from libs.myException import *


class Protocol(threading.Thread):
    class LampControl:
        BROADCAST_ID = '\x00\x00\x00\x00\x00\x00'
        FRAME_HEADER = '\x55\x55'
        BYTE_RESERVED = '\x00'
        BYTE_ALL_OFF = '\x00'
        BYTE_ALL_ON = '\x03'
        BYTE_LEFT_ON = '\x01'
        BYTE_RIGHT_ON = '\x02'
        TAG_ACK = '\x01'
        TAG_NACK = '\x02'
        TAG_LAMP_CTRL = '\x05'
        TAG_POLL = '\x03'
        TAG_POLL_ACK = '\x04'

        TAG_DICT = {TAG_ACK: 'ACK/',
                    TAG_NACK: 'NACK',
                    TAG_LAMP_CTRL: 'Lamp control',
                    TAG_POLL: 'Poll',
                    TAG_POLL_ACK: 'Poll ACK',}

        MESG_LAMP_ALL_ON = TAG_LAMP_CTRL + BYTE_ALL_ON + '\xFF' * 2
        MESG_LAMP_ALL_OFF = TAG_LAMP_CTRL + BYTE_ALL_OFF + BYTE_RESERVED * 2
        MESG_ACK = TAG_ACK + BYTE_RESERVED * 3
        MESG_NACK = TAG_NACK + BYTE_RESERVED * 3
        pass

    def __init__(self, id, role='RC', timeout=5, retry=3):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self._timeout = timeout # in seconds
        self._retry = retry
        self._RC_queue = Queue.Queue(0) # create no limited queue
        self._role = role # three roles: 'RC', 'STA', 'RELAY'
        assert role=='RC' or role=='STA' or role=='RELAY', 'Protocol role mistake!'
        self._id = id
        self._tx_frame_len = 21
        if self._role == 'RC':
            self._rx_frame_len = 21
        elif self._role == 'STA' or self._role == 'RELAY':
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
        self._frame_no = -1

    def __del__(self):
        self.ser.close()

    def _send_message(self, dest_id, message):
        if self._role == 'RC':
            assert len(message) == 4, 'RC message length is not 4'
        if self._role == 'STA':
            assert len(message) == 4, 'STA message length is not 4'
        self._frame_no += 1
        if self._frame_no == 250:
            self._frame_no = 0
        tx_str = self.LampControl.FRAME_HEADER + self._id + dest_id + chr(self._frame_no) + message
        crc = struct.pack('>H', ctypes.c_uint16(binascii.crc_hqx(tx_str, 0xFFFF)).value) # MSB firstly
        tx_str = tx_str + crc
        logger.debug('TX: {0}'.format(binascii.b2a_hex(tx_str)))
        try:
            self.ser.transmit(tx_str)
        except:
            logger.error('Tx error!')
        pass

    def _forward_frame(self, frame):
        if self._role == 'RELAY':
            try:
                self.ser.transmit(frame)
            except:
                logger.error('Tx error!')

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
            else:
                rx_crc = rx_str[-2 :]
                str_payload = rx_str[0 : self._rx_frame_len-2]
                crc = struct.pack('>H', ctypes.c_uint16(binascii.crc_hqx(str_payload, 0xFFFF)).value)  # MSB firstly
                if crc == rx_crc:
                    done = True
                else:
                    got_header = False
                    rx_str = rx_str[2 :]
                    rx_len = 2
                    logger.debug('A frame is received: %s', binascii.b2a_hex(rx_str))
                    logger.debug('Payload: %s', binascii.b2a_hex(str_payload))
                    logger.debug('RX CRC: %s', binascii.b2a_hex(rx_crc))
                    logger.debug('calculated CRC: %s', binascii.b2a_hex(crc))
                    logger.debug('CRC check failed, remove Header and continue')
        logger.debug('RX: {0}'.format(binascii.b2a_hex(rx_str)))
        return rx_str

    def _STA_frame_process(self, rx_frame):
        '''
        STA/RELAY received frame processing per the protocol
        :param rx_frame: the received frame
        :return: 
        '''
        src_id = rx_frame[2:8]
        dest_id = rx_frame[8:14]
        sn = ord(rx_frame[14])
        tag = rx_frame[15]
        value = rx_frame[16:19]

        if dest_id == self._id or dest_id == self.LampControl.BROADCAST_ID:
            if sn > self._frame_no:
                self._frame_no = sn
                if self.LampControl.TAG_DICT.has_key(tag):
                    if tag == self.LampControl.TAG_LAMP_CTRL:
                        self._STA_do_lamp_ctrl(value)
                        logger.debug('send ACK')
                        self._send_message(src_id, self.LampControl.MESG_ACK)
                else:
                    logger.debug('send NACK')
                    self._send_message(src_id, self.LampControl.MESG_NACK)
            else:
                logger.debug('duplicated frame received')
        else:
            # do relay if self._role is 'RELAY'
            if self._role == 'RELAY' and sn > self._frame_no:
                self._frame_no = sn
                logger.info('RELAY sn = %s' % str(sn))
                self._forward_frame(rx_frame)
        pass

    def run(self):
        logger.info('Thread receiving starts running until it is stop on purpose.')
        while not self.thread_stop:
            rx_frame = self._recv_frame()
            if self._role == 'RC':
                # place rx_frame into queue for RC tx routine process
                self._RC_queue.put(rx_frame)
            else:
                # process here for STA & RELAY
                self._STA_frame_process(rx_frame)
        logger.debug('Thread receiving end')

    def stop(self):
        self.thread_stop = True

    def _STA_do_lamp_ctrl(self, value):
        pass

    def RC_lamp_ctrl(self, dest_id, value):
        count = 0
        mesg = self.LampControl.TAG_LAMP_CTRL + value
        while count < self._retry:
            logger.debug('RC send message %s times' % str(count+1))
            self._send_message(dest_id, mesg)
            if dest_id == self.LampControl.BROADCAST_ID:
                # no response is expected on broadcast TX
                logger.info('Boardcast mesg: %s' % binascii.b2a_hex(mesg))
                break
            try:
                if self._RC_wait_for_resp(self.LampControl.TAG_ACK, self._timeout):
                    logger.debug('RC got expected response from STA')
                    break
                else:
                    count += 1
            except RxTimeOut:
                count += 1
            except RxNack:
                logger.debug('NACK is received')
                count += 1
        else:
            logger.debug('RC didn\'t get expected response from STA')
        pass

    def _RC_wait_for_resp(self, tag, timeout):
        try:
            rx_frame = self._RC_queue.get(True, timeout)
            self._RC_queue.task_done()
        except Queue.Empty:
            raise RxTimeOut
        else:
            if rx_frame[15] == self.LampControl.TAG_NACK:
                raise RxNack
            elif rx_frame[15] == tag:
                return True
            else:
                logger.debug('unexpected frame received with TAG %s', hex(ord(tag)))
                return False



if __name__ == "__main__":
    logging.basicConfig(level='DEBUG')

    role = 'RC'
    #role = 'STA'
    #role = 'RELAY'

    if role == 'RC':
        delay = 1
    else:
        delay = 30

    STA1_ID = '\x00\x00\x00\x00\x00\x02'
    STA2_ID = '\x00\x00\x00\x00\x00\x03'
    if role == 'RC':
        ID = '\x00\x00\x00\x00\x00\x01'
    elif role == 'STA':
        ID = STA1_ID
    elif role == 'RELAY':
        ID = STA2_ID

    foo = Protocol(id=ID, role=role)
    foo.setName('Thread receiving')
    foo.setDaemon(True)
    try:
        foo.start()
        sleep(1)
        if role == 'RC':
            foo.RC_lamp_ctrl(STA1_ID, '\x03\xFF\xFF')
    except KeyboardInterrupt:
        logger.debug('Stopping Thread by Ctrl-C')
        foo.stop()
    finally:
        logger.debug('Waiting for thread end')
        foo.join(delay)
        logger.debug('End')
    pass