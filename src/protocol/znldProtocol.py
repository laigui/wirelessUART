import binascii, ctypes, struct, Queue
import threading
import random
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
        MESG_LENGTH = 5
        BROADCAST_ID = '\x00\x00\x00\x00\x00\x00'
        FRAME_HEADER = '\x55\x55'
        BYTE_RESERVED = '\x00'
        BYTE_ALL_OFF = '\x00'
        BYTE_ALL_ON = '\x03'
        BYTE_LEFT_ON = '\x01'
        BYTE_RIGHT_ON = '\x02'
        TAG_SN = '\x00'
        TAG_ACK = '\x01'
        TAG_NACK = '\x02'
        TAG_LAMP_CTRL = '\x05'
        TAG_POLL = '\x03'
        TAG_POLL_ACK = '\x04'

        TAG_DICT = {TAG_SN: 'SN update',
                    TAG_ACK: 'ACK',
                    TAG_NACK: 'NACK',
                    TAG_LAMP_CTRL: 'Lamp control',
                    TAG_POLL: 'Poll',
                    TAG_POLL_ACK: 'Poll ACK',}

        MESG_VALUE_LAMP_ALL_ON = BYTE_ALL_ON + '\xFF' * 2 + BYTE_RESERVED
        MESG_LAMP_ALL_ON = TAG_LAMP_CTRL + MESG_VALUE_LAMP_ALL_ON
        MESG_VALUE_LAMP_ALL_OFF = BYTE_ALL_OFF + BYTE_RESERVED * 3
        MESG_LAMP_ALL_OFF = TAG_LAMP_CTRL + MESG_VALUE_LAMP_ALL_OFF
        MESG_ACK = TAG_ACK + BYTE_RESERVED * (MESG_LENGTH - 1)
        MESG_NACK = TAG_NACK + BYTE_RESERVED * (MESG_LENGTH - 1)
        MESG_POLL = TAG_POLL + BYTE_RESERVED * (MESG_LENGTH - 1)
        MESG_NULL = BYTE_RESERVED * MESG_LENGTH
        pass

    def __init__(self, id, role='RC', retry=3, hop=0, baudrate=9600, testing='FALSE', timeout=5,
                 e32_delay=5, relay_delay=1, relay_random_backoff=3):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self._retry = retry
        self._RC_queue = Queue.Queue(0) # create no limited queue
        self._role = role # three roles: 'RC', 'STA', 'RELAY'
        assert role=='RC' or role=='STA' or role=='RELAY', 'Protocol role mistake!'
        self._id = id
        # to simplify protocol, use the same length for TX & RX
        self._tx_frame_len = 22
        self._rx_frame_len = 22
        self._max_frame_len = max(self._tx_frame_len, self._rx_frame_len)
        self._frame_no = -2
        self._max_frame_no = 25
        self._STA_led_status = '\x00'
        
        # for testing identification, we will update the last 2 bytes of payload with sequential number
        # _testing = True to enable this feature
        if testing == 'TRUE':
            self._testing = True
        else:
            self._testing = False
        self._count = 0

        self._GPIO_LED = 21
        if ISRPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._GPIO_LED, GPIO.OUT)

        if ISRPI:
            port = '/dev/ttyS0'
        else:
            port = '/dev/ttyUSB0'
        self.ser = E32(port=port, inHex=False)
        if self.ser.open() == False:
            self.thread_stop = True
        # else:
        #     #dump E32 version and configuration, disabled for 1st ver board now
        #     self.ser.set_E32_mode(3)
        #     logger.info('E32 Version: %s', self.ser.get_version(inHex=False))
        #     logger.info('E32 Configuration: %s', self.ser.get_config(inHex=False))
        #     self.ser.set_E32_mode(0)

        self.timeout = (3 + 3 * hop) * 2 * self._max_frame_len * 10 / baudrate + timeout
        self.e32_delay = e32_delay # E32 initial communication delay, unknown to us so far. let it be 5 so far
        self.relay_delay = relay_delay # delay x seconds to avoid conflicting with STA response
        self.relay_random_backoff = relay_random_backoff # max. random backoff delay to avoid conflicting between RELAYs
        self.hop = hop
        logger.info('%s (%s) initialization done with timeout=%s, e32_delay=%s, relay_delay=%s, relay_random_backoff=%s, hop=%s'
                    % (self._role, binascii.b2a_hex(self._id), repr(self.timeout), repr(self.e32_delay),
                       repr(self.relay_delay), repr(self.relay_random_backoff), repr(self.hop)))

    def __del__(self):
        if ISRPI:
            GPIO.cleanup()

    def _send_message(self, dest_id, message):
        assert len(message) == self.LampControl.MESG_LENGTH, 'payload length is not 5'
        if self._role == 'RC':
            # have to increase it by 2 to avoid conflicting with STA's response when it isn't received by RC
            self._frame_no += 2
        if self._role == 'STA' or self._role == 'RELAY':
            self._frame_no += 1

        tx_str_reset_sn = None
        if self._frame_no >= self._max_frame_no and self._role == 'RC':
            if dest_id == self.LampControl.BROADCAST_ID:
                self._frame_no = 0
                tx_str_reset_sn = self.LampControl.FRAME_HEADER + self._id + self.LampControl.BROADCAST_ID\
                         + chr(self._frame_no) + self.LampControl.MESG_NULL
                self._frame_no = 1
            else:
                # no need to send 2nd broadcast frame if it is already broadcast.
                self._frame_no = 0
        tx_str_message = self.LampControl.FRAME_HEADER + self._id + dest_id + chr(self._frame_no) + message
        if tx_str_reset_sn:
            tx_str_list = [tx_str_reset_sn, tx_str_message]
        else:
            tx_str_list = [tx_str_message]

        for index in range(len(tx_str_list)):
            tx_str =  tx_str_list[index]
            
            if self._testing:
                # for testing only, replace the last two bytes of message to self._count
                # self._count will increase for every frame for identification
                count_str = struct.pack('>H', self._count)
                tx_str = tx_str[0:len(tx_str)-2] + count_str
                self._count += 1

            crc = struct.pack('>H', ctypes.c_uint16(binascii.crc_hqx(tx_str, 0xFFFF)).value) # MSB firstly
            tx_str = tx_str + crc
            logger.debug('TX: {0}'.format(binascii.b2a_hex(tx_str)))
            try:
                self.ser.transmit(tx_str)
            except:
                logger.error('Tx error!')
            if index == 0 and tx_str_reset_sn:
                logger.debug('broadcast sn=0 update frame')
                # need to consider network delay here given relay hop number
                sleep(self.hop * (self.relay_random_backoff + self.e32_delay))
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
            rx_str = rx_str + self.ser.receive(n=rx_len)  # keep receiving until getting required bytes
            if not got_header:
                index = rx_str.find(self.LampControl.FRAME_HEADER)
                if index == -1:
                    rx_str = ''
                else:
                    got_header = True
                    rx_str = rx_str[index:]
                    rx_len = index
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
                    logger.error('A frame is received: %s', binascii.b2a_hex(rx_str))
                    logger.error('Payload: %s', binascii.b2a_hex(str_payload))
                    logger.error('RX CRC: %s', binascii.b2a_hex(rx_crc))
                    logger.error('calculated CRC: %s', binascii.b2a_hex(crc))
                    logger.error('CRC check failed, remove Header and continue')
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
        value = rx_frame[16:20]
        update_frame_no = False

        if dest_id == self._id or dest_id == self.LampControl.BROADCAST_ID:
            logger.debug('frame received: Nsn=%s, Psn=%s' % (str(sn), str(self._frame_no)))
            if sn > self._frame_no or (sn == 0 and sn != self._frame_no):
                update_frame_no = True
                self._frame_no = sn
                if self.LampControl.TAG_DICT.has_key(tag):
                    # need to deal with different protocol TAG here
                    if tag == self.LampControl.TAG_LAMP_CTRL:
                        logger.debug('got TAG_LAMP_CTRL')
                        self._STA_do_lamp_ctrl(value)
                        if dest_id != self.LampControl.BROADCAST_ID:
                            logger.debug('sent ACK')
                            self._send_message(src_id, self.LampControl.MESG_ACK)
                        else:
                            logger.debug('no ACK to broadcast')
                    elif tag == self.LampControl.TAG_POLL:
                        logger.debug('got TAG_POLL')
                        MESG_POLL_ACK = self.LampControl.TAG_POLL_ACK + self._STA_led_status \
                                        + self.LampControl.BYTE_RESERVED * 3
                        self._send_message(src_id, MESG_POLL_ACK)
                else:
                    logger.debug('got unknown CMD TAG, sent NACK')
                    self._send_message(src_id, self.LampControl.MESG_NACK)
            else:
                logger.debug('duplicated frame received')

        # do relay if self._role is 'RELAY'
        if self._role == 'RELAY' and dest_id != self._id:
            logger.debug('RELAY: Nsn=%s, Psn=%s' % (str(sn), str(self._frame_no)))
            if update_frame_no: # handle broadcast frame again
                # each RELAY need random backoff before TX to avoid E32 RF conflicting
                sleep(random.sample(range(self.relay_random_backoff + 1), 1)[0])
                logger.info('RELAY sn = %s' % str(sn))
                self._forward_frame(rx_frame)
            else:
                if sn > self._frame_no or (sn == 0 and sn != self._frame_no):
                    update_frame_no = True
                    self._frame_no = sn
                    # each RELAY need a fixed delay before random backoff TX to avoid E32 RF conflicting with STA response
                    sleep(self.relay_delay)
                    # each RELAY need random backoff before TX to avoid E32 RF conflicting
                    sleep(random.sample(range(self.relay_random_backoff + 1), 1)[0])
                    logger.info('RELAY sn = %s' % str(sn))
                    self._forward_frame(rx_frame)
        pass

    def run(self):
        if self._role == 'RC':
            # broadcast frame number reset frame upon the startup to avoid STA confusing issue
            self._send_message(self.LampControl.BROADCAST_ID, self.LampControl.MESG_NULL)

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
        if value[0] == self.LampControl.BYTE_ALL_ON:
            logger.info('LED ALL ON')
            if ISRPI:
                GPIO.output(self._GPIO_LED, GPIO.LOW)
        else:
            logger.info('LED ALL OFF')
            if ISRPI:
                GPIO.output(self._GPIO_LED, GPIO.HIGH)
        self._STA_led_status = value[0]
        pass

    def _RC_wait_for_resp(self, src_id, tag, timeout):
        result = False
        while result == False:
            try:
                rx_frame = self._RC_queue.get(True, timeout)
                self._RC_queue.task_done()
            except Queue.Empty:
                raise RxTimeOut
            else:
                rx_src_id = rx_frame[2:8]
                rx_dest_id = rx_frame[8:14]
                rx_sn = ord(rx_frame[14])
                rx_tag = rx_frame[15]
                if rx_src_id == src_id and rx_dest_id == self._id:
                    if rx_sn > self._frame_no:
                        self._frame_no = rx_sn
                        if rx_tag == self.LampControl.TAG_NACK:
                            raise RxNack
                        elif rx_tag == tag:
                            result = True
                        else:
                            logger.debug('unexpected frame received with TAG %s', binascii.b2a_hex(rx_tag))
                            break
        return (result, rx_frame[15:20])

    def RC_unicast_poll(self, dest_id, expected):
        '''
        unicast only, expect TAG_POLL_ACK
        for test, 1st byte of POLL_ACK has self._STA_led_status
        :param dest_id:
        :param expected: expected value in POLL_ACK
        :return: True on success, False on failure
        '''
        count = 0
        mesg = self.LampControl.MESG_POLL
        logger.info('RC send POLL to STA (%s)' % binascii.b2a_hex(dest_id))
        while count < self._retry:
            logger.info('RC send message %s times' % str(count + 1))
            self._send_message(dest_id, mesg)
            try:
                (result, data) = self._RC_wait_for_resp(src_id=dest_id, tag=self.LampControl.TAG_POLL_ACK, timeout=self.timeout)
                if result:
                    if data[1] == expected:
                        return True
                    else:
                        raise RxUnexpectedTag
                else:
                    count += 1
            except RxTimeOut:
                count += 1
            except RxNack:
                raise
        else:
            raise RxTimeOut
        pass

    def RC_lamp_ctrl(self, dest_id, value):
        '''
        can be unicast or broadcast, expect TAG_ACK
        :param dest_id:
        :param value:
        :return: True on success, False on failure
        '''
        count = 0
        mesg = self.LampControl.TAG_LAMP_CTRL + value
        logger.info('RC send lamp ctrl (%s) to STA (%s)' %
                    (binascii.b2a_hex(value), binascii.b2a_hex(dest_id)))
        while count < self._retry:
            logger.info('RC send message %s times' % str(count+1))
            self._send_message(dest_id, mesg)
            if dest_id == self.LampControl.BROADCAST_ID:
                # no response is expected on broadcast TX
                logger.info('Broadcast mesg: %s' % binascii.b2a_hex(mesg))
                return True
            try:
                (result, data) = self._RC_wait_for_resp(src_id=dest_id, tag=self.LampControl.TAG_ACK, timeout=self.timeout)
                if result:
                    logger.info('RC got TAG_ACK from STA (%s)' % binascii.b2a_hex(dest_id))
                    return True
                else:
                    count += 1
            except RxTimeOut:
                count += 1
            except RxNack:
                logger.error('NACK is received from STA (%s)' % binascii.b2a_hex(dest_id))
                return False
        else:
            logger.debug('RC didn\'t get expected response from STA (%s)' % binascii.b2a_hex(dest_id))
            return False
        pass





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
            foo.RC_lamp_ctrl(STA1_ID, '\x03\xFF\xFF\x00')
    except KeyboardInterrupt:
        logger.debug('Stopping Thread by Ctrl-C')
        foo.stop()
    finally:
        logger.debug('Waiting for thread end')
        foo.join(delay)
        logger.debug('End')
    pass
