#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

import binascii, ctypes, struct, Queue
import threading
import random
from time import sleep, time
from multiprocessing import Process, Manager, Pipe
from multiprocessing.managers import SyncManager

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

cmd_sn = 0
class ZnldCmd(object):
    '''
    ZNLD command structure for inputs locally or remotely
    '''
    CMD_LAMPCTRL = 1
    CMD_OTHER = 2

    def __init__(self):
        global cmd_sn
        self.cmd_id = cmd_sn # distinguish in cmds sequence
        cmd_sn += 1
        self.cmd_result = False # return True when cmd execution successful
        self.cmd = None # lamp control cmd or other cmd TBD
        self.dest_addr = 0  # destination logic addr, need to look up dest_id if it is None
        self.dest_id = None # 6 bytes in hex
        self.message = LampControl.MESG_NULL # 5 bytes in hex, including TAG & VALUE

class LampControl:
    '''
    Constants of lamp control frame
    '''
    # fields location inside frame for decoding
    HEADER_S = 0
    SRCID_S = 2
    DESTID_S = 8
    SN = 14
    TAG = 15
    VALUE_S = 16
    CRC_S = 20

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
    TAG_POLL = '\x03'
    TAG_POLL_ACK = '\x04'
    TAG_LAMP_CTRL = '\x05'
    TAG_POWER1_POLL = '\x06'
    TAG_POWER1_ACK = '\x07'
    TAG_POWER2_POLL = '\x08'
    TAG_POWER2_ACK = '\x09'
    TAG_ENV1_POLL = '\x0A'
    TAG_ENV1_ACK = '\x0B'
    TAG_ENV2_POLL = '\x0C'
    TAG_ENV2_ACK = '\x0D'

    TAG_DICT = {TAG_SN: 'TAG for SN update',
                TAG_ACK: 'TAG for ACK response',
                TAG_NACK: 'TAG for NACK response',
                TAG_POLL: 'TAG for poll',
                TAG_POLL_ACK: 'TAG for poll response',
                TAG_LAMP_CTRL: 'TAG for lamp control',
                TAG_POWER1_POLL: 'TAG for power status poll',
                TAG_POWER1_ACK: 'TAG for ',
                TAG_POWER2_POLL: 'TAG for ',
                TAG_POWER2_ACK: 'TAG for ',
                TAG_ENV1_POLL: 'TAG for ',
                TAG_ENV1_ACK: 'TAG for ',
                TAG_ENV2_POLL: 'TAG for ',
                TAG_ENV2_ACK: 'TAG for ',
                }

    MESG_VALUE_LAMP_ALL_ON = BYTE_ALL_ON + '\xFF' * 2 + BYTE_RESERVED
    MESG_LAMP_ALL_ON = TAG_LAMP_CTRL + MESG_VALUE_LAMP_ALL_ON
    MESG_VALUE_LAMP_ALL_OFF = BYTE_ALL_OFF + BYTE_RESERVED * 3
    MESG_LAMP_ALL_OFF = TAG_LAMP_CTRL + MESG_VALUE_LAMP_ALL_OFF
    MESG_ACK = TAG_ACK + BYTE_RESERVED * (MESG_LENGTH - 1)
    MESG_NACK = TAG_NACK + BYTE_RESERVED * (MESG_LENGTH - 1)
    MESG_POLL = TAG_POLL + BYTE_RESERVED * (MESG_LENGTH - 1)
    MESG_NULL = BYTE_RESERVED * MESG_LENGTH


class ThreadRx(threading.Thread):
    '''
    Protocol Rx thread
    Using Queue to send received frames to the main thread for processing
    '''
    def __init__(self, role, id, queue, frame_len, serial, name='Routine frames receiving', daemon=True, **kwargs):
        self._role = role
        self._id = id
        self._frames = queue # cmds input and results output pipe
        self._stop = False
        self._rx_frame_len = frame_len
        self.ser = serial
        super(ThreadRx, self).__init__()

    def run(self):
        logger.info('Thread receiving starts running ...')

        while not self._stop:
            rx_frame = self._recv_frame()
            dest_id = rx_frame[LampControl.DESTID_S : LampControl.SN]
            if (self._role == 'RC' and dest_id == self._id) \
                    or (self._role == 'STA' and (dest_id == self._id or dest_id == LampControl.BROADCAST_ID)) \
                    or (self._role == 'RELAY'):
                # place rx_frame into queue for tx routine process
                self._frames.put(rx_frame)
                logger.debug('A rx frame is queued!')

        logger.info('Thread receiving ends')
        pass

    def stop(self):
        self._stop = True

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
                index = rx_str.find(LampControl.FRAME_HEADER)
                if index == -1:
                    rx_str = ''
                    rx_len = self._rx_frame_len
                    got_header = False
                else:
                    got_header = True
                    rx_str = rx_str[index:]
                    rx_len = index
                    #logger.debug('0> received: %s', binascii.b2a_hex(rx_str))
                    #logger.debug('1> more to receive: %d', index)
            else:
                #logger.debug('2> received (len= %d): %s', len(rx_str), binascii.b2a_hex(rx_str))
                rx_crc = rx_str[-2 :]
                str_payload = rx_str[0 : self._rx_frame_len-2]
                crc = struct.pack('>H', ctypes.c_uint16(binascii.crc_hqx(str_payload, 0xFFFF)).value)  # MSB firstly
                if crc == rx_crc:
                    done = True
                else:
                    got_header = False
                    rx_str = rx_str[2 :]
                    rx_len = 2
                    logger.debug('Payload: %s', binascii.b2a_hex(str_payload))
                    logger.debug('RX CRC: %s', binascii.b2a_hex(rx_crc))
                    logger.debug('calculated CRC: %s', binascii.b2a_hex(crc))
                    logger.debug('CRC check failed, remove Header and continue')
                    logger.debug('left frame is (len= %d): %s', len(rx_str), binascii.b2a_hex(rx_str))
        logger.debug('RX: {0}'.format(binascii.b2a_hex(rx_str)))
        return rx_str


class Protocol(Process):
    '''
    The main process of the protocol.
    The main thread deals with TX loop & RX processing, and have another thread dealing with RX loop.
    Using Pipe for GUI commands input and results output.
    Using shared multiProcessing Queue for commands input from remote processes, e.g. cron task.
    Using shared stations dictionary to update lamp status in GUI
    '''
    def __init__(self, id, stations, role='RC', retry=3, hop=0, baudrate=9600, testing='FALSE', timeout=5,
                 e32_delay=2, relay_delay=1, relay_random_backoff=3, **kwargs):
        super(Protocol, self).__init__()
        self._stop = False
        self._retry = retry
        self._role = role # three roles: 'RC', 'STA', 'RELAY'
        assert role=='RC' or role=='STA' or role=='RELAY', 'Protocol role mistake!'
        self._id = id
        # to simplify protocol, use the same length for TX & RX
        self._tx_frame_len = 22
        self._rx_frame_len = 22
        self._max_frame_len = max(self._tx_frame_len, self._rx_frame_len)
        self._frame_no = -2
        self._max_frame_no = 25
        self.stations = stations # dictionary for station's info storage
        self._STA_lamp_status = '' # for station only

        if self._role == 'RC':
            # only need to initialize stas_dict for RC
            self._init_stas_dict()
        
        # for testing identification, we will update the last 2 bytes of payload with sequential number
        # _testing = True to enable this feature
        if testing == 'TRUE':
            self._testing = True
            self._count = 0
        else:
            self._testing = False

        self._GPIO_LED = 21
        if ISRPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._GPIO_LED, GPIO.OUT)
            port = '/dev/ttyS0'
        else:
            port = '/dev/ttyUSB0'

        self.ser = E32(port=port, inHex=False)
        if self.ser.open() == False:
            self._stop = True
        # else:
        #     #dump E32 version and configuration, disabled for 1st ver board now
        #     self.ser.set_E32_mode(3)
        #     logger.info('E32 Version: %s', self.ser.get_version(inHex=False))
        #     logger.info('E32 Configuration: %s', self.ser.get_config(inHex=False))
        #     self.ser.set_E32_mode(0)

        #self.timeout = (3 + 3 * hop) * 2 * self._max_frame_len * 10 / baudrate + timeout
        self.timeout = e32_delay + hop * (relay_delay + relay_random_backoff)
        self.e32_delay = e32_delay # E32 initial communication delay, unknown to us so far. let it be 5 so far
        self.relay_delay = relay_delay # delay x seconds to avoid conflicting with STA response
        self.relay_random_backoff = relay_random_backoff # max. random backoff delay to avoid conflicting between RELAYs
        self.hop = hop
        logger.info('%s (%s) initialization done with timeout=%s, e32_delay=%s, relay_delay=%s, relay_random_backoff=%s, hop=%s'
                    % (self._role, binascii.b2a_hex(self._id), repr(self.timeout), repr(self.e32_delay),
                       repr(self.relay_delay), repr(self.relay_random_backoff), repr(self.hop)))

        self.p_cmd, self._p_cmd = Pipe() # pipe for gui control commands & results communication
        self._Rx_queue = Queue.Queue(0)  # create no limited queue for RX frames
        self._t_rx = ThreadRx(role=self._role, queue=self._Rx_queue, id=self._id,
                              frame_len=self._rx_frame_len, serial=self.ser) # Thread for rx frames processing



    def __del__(self):
        self._t_rx.stop()
        self._t_rx.join()
        if ISRPI:
            GPIO.cleanup()

    def get_cmd_pipe(self):
        return self.p_cmd

    def get_stas_dict(self):
        return self.stations

    def _init_stas_dict(self):
        ''' initialize self.stations for data storage of each node
            control data: lamp_ctrl, lamp_adj1, lamp_adj2
            status data: lamp_ctrl_status,  lamp_adj1_status, lamp_adj2_status
            electric data: voltage, current, power, energy, power_factor, co2, board_temperature, freq
            environment data: pm2_5, pm10, temperature, humidity
            communication stats: comm_okay = +1 once communication succeeds;
                                comm_fail = +1 once communication fails;
                                comm_quality = +1 once communication fails and reset to 0 once communication succeeds;
        '''
        data = dict(lamp_ctrl=0, lamp_adj1=0, lamp_adj2=0, lamp_ctrl_status=0,  lamp_adj1_status=0, lamp_adj2_status=0,
                    voltage=0.0, current=0.0, power=0.0, energy=0.0, power_factor=0.0, co2=0.0, board_temperature=0.0,
                    freq=0.0, pm2_5=0.0, pm10=0.0, temperature=0.0, humidity=0.0, comm_okay=0, comm_fail=0, comm_quality=0)
        for sta in self.stations.iterkeys():
            self.stations[sta].update(data)
        pass

    def _send_message(self, dest_id, message):
        assert len(message) == LampControl.MESG_LENGTH, 'payload length is not 5'
        if self._role == 'RC':
            # have to increase it by 2 to avoid conflicting with STA's response when it isn't received by RC
            self._frame_no += 2
        if self._role == 'STA' or self._role == 'RELAY':
            self._frame_no += 1

        tx_str_reset_sn = None
        if self._frame_no >= self._max_frame_no and self._role == 'RC':
            if dest_id != LampControl.BROADCAST_ID:
                self._frame_no = 0
                tx_str_reset_sn = LampControl.FRAME_HEADER + self._id + LampControl.BROADCAST_ID\
                         + chr(self._frame_no) + LampControl.MESG_NULL
                logger.debug('broadcast sn=0 update frame')
                self._frame_no = 1
            else:
                # no need to send another broadcast frame if it is already broadcast.
                self._frame_no = 0
        tx_str_message = LampControl.FRAME_HEADER + self._id + dest_id + chr(self._frame_no) + message
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
            if self._role == 'RC':
                if (index == 0 and tx_str_reset_sn) or dest_id == LampControl.BROADCAST_ID:
                    # need a delay to avoid broadcast storm
                    sleep(self.hop * (self.relay_random_backoff + self.relay_delay) + self.e32_delay)

    def _forward_frame(self, frame):
        if self._role == 'RELAY':
            try:
                self.ser.transmit(frame)
            except:
                logger.error('Tx error!')

    def _STA_frame_process(self, rx_frame):
        '''
        STA/RELAY received frame processing per the protocol
        :param rx_frame: the received frame
        :return: 
        '''
        src_id = rx_frame[LampControl.SRCID_S:LampControl.DESTID_S]
        dest_id = rx_frame[LampControl.DESTID_S:LampControl.SN]
        sn = ord(rx_frame[LampControl.SN])
        tag = rx_frame[LampControl.TAG]
        value = rx_frame[LampControl.VALUE_S:LampControl.CRC_S]

        need_forward = False
        if dest_id == self._id or dest_id == LampControl.BROADCAST_ID:
            logger.debug('frame received: Nsn=%s, Psn=%s' % (str(sn), str(self._frame_no)))
            if sn > self._frame_no or (sn == 0 and sn != self._frame_no):
                self._frame_no = sn
                need_forward = True
                if LampControl.TAG_DICT.has_key(tag):
                    # need to deal with different protocol TAG here
                    if tag == LampControl.TAG_LAMP_CTRL:
                        logger.debug('got TAG_LAMP_CTRL')
                        self._STA_do_lamp_ctrl(value)
                        if dest_id != LampControl.BROADCAST_ID:
                            logger.debug('sent POLL ACK')
                            MESG_POLL_ACK = LampControl.TAG_POLL_ACK + self._STA_lamp_status
                            self._send_message(src_id, MESG_POLL_ACK)
                        else:
                            logger.debug('no ACK to broadcast')
                    elif tag == LampControl.TAG_POLL:
                        logger.debug('got POLL')
                        MESG_POLL_ACK = LampControl.TAG_POLL_ACK + self._STA_lamp_status
                        self._send_message(src_id, MESG_POLL_ACK)
                else:
                    logger.debug('got unknown CMD TAG, sent NACK')
                    self._send_message(src_id, LampControl.MESG_NACK)
            else:
                logger.debug('duplicated frame received')

        # do relay if self._role is 'RELAY'
        if self._role == 'RELAY':
            if dest_id == LampControl.BROADCAST_ID and need_forward: # handle broadcast frame again
                # each RELAY need random backoff before TX to avoid E32 RF conflicting
                sleep(random.sample(range(self.relay_random_backoff + 1), 1)[0])
                logger.info('RELAY sn = %s' % str(sn))
                self._forward_frame(rx_frame)
            elif dest_id != self._id:
                if sn > self._frame_no or (sn == 0 and sn != self._frame_no):
                    self._frame_no = sn
                    # each RELAY need a fixed delay before random backoff TX to avoid E32 RF conflicting with STA response
                    sleep(self.relay_delay)
                    # each RELAY need random backoff before TX to avoid E32 RF conflicting
                    sleep(random.sample(range(self.relay_random_backoff + 1), 1)[0])
                    logger.info('RELAY sn = %s' % str(sn))
                    self._forward_frame(rx_frame)

    def run(self):
        self._t_rx.start()
        logger.info('Thread transmitting starts running ...')

        if self._role == 'RC':
            # broadcast frame number reset frame upon the startup to avoid SN confusing issue
            self._send_message(LampControl.BROADCAST_ID, LampControl.MESG_NULL)
            # need a delay to avoid broadcast storm
            sleep(self.hop * (self.relay_random_backoff + self.relay_delay) + self.e32_delay)
            # self._frame_no = -2
            # self._send_message(LampControl.BROADCAST_ID, LampControl.MESG_NULL)
            # # need a delay to avoid broadcast storm
            # sleep(self.hop * (self.relay_random_backoff + self.relay_delay) + self.e32_delay)

        while not self._stop:
            if self._role == 'RC':
                # for RC, get cmds from input pipe and execute
                # cmd is an instance of ZnldCmd class
                cmd = self._poll_cmd()
                if cmd.cmd == ZnldCmd.CMD_LAMPCTRL:
                    if cmd.dest_id == None:
                        dest_id = self._get_id_from(cmd.dest_addr)
                        if dest_id == None:
                            logger.error('id look up failed by addr=%d' % cmd.dest_addr)
                            cmd.cmd_result = False
                            self._ack_cmd(cmd)
                            continue
                        else:
                            cmd.dest_id = binascii.a2b_hex(dest_id)
                    else:
                        dest_id = binascii.b2a_hex(cmd.dest_id)
                        if not dest_id in self.stations:
                            if cmd.dest_id != LampControl.BROADCAST_ID:
                                logger.error('id look up failed by id=%s' % dest_id)
                                cmd.cmd_result = False
                                self._ack_cmd(cmd)
                                continue
                     
                    if cmd.dest_id == LampControl.BROADCAST_ID:
                        if cmd.message[0] == LampControl.TAG_LAMP_CTRL:
                            # broadcast, no response
                            logger.info('RC broadcast mesg: %s' % binascii.b2a_hex(cmd.message))
                            self._send_message(cmd.dest_id, cmd.message)
                            for id in self.stations.iterkeys():
                                self.stations[id]['lamp_ctrl'] = cmd.message[1]
                                self.stations[id]['lamp_adj1'] = cmd.message[2]
                                self.stations[id]['lamp_adj2'] = cmd.message[3]
                            cmd.cmd_result = True
                            self._ack_cmd(cmd)
                        else:
                            logger.error('illegal broadcast cmd: %s' % binascii.b2a_hex(cmd.message))
                            cmd.cmd_result = False
                            self._ack_cmd(cmd)
                    else:
                        # unicast below, a response is expected
                        if cmd.message[0] == LampControl.TAG_POLL:
                            logger.info('RC send POLL to STA (%s)' % dest_id)
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_POLL_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)
                        elif cmd.message[0] == LampControl.TAG_POWER1_POLL:
                            logger.info('RC send POWER1 POLL to STA (%s)' % dest_id)
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_POWER1_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)
                        elif cmd.message[0] == LampControl.TAG_POWER2_POLL:
                            logger.info('RC send POWER2 POLL to STA (%s)' % dest_id)
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_POWER2_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)
                        elif cmd.message[0] == LampControl.TAG_ENV1_POLL:
                            logger.info('RC send ENV1 POLL to STA (%s)' % dest_id)
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_ENV1_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)
                        elif cmd.message[0] == LampControl.TAG_ENV2_POLL:
                            logger.info('RC send ENV2 POLL to STA (%s)' % dest_id)
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_ENV2_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)
                        elif cmd.message[0] == LampControl.TAG_LAMP_CTRL:
                            id = binascii.b2a_hex(cmd.dest_id)
                            logger.info('RC send lamp ctrl (%s) to STA (%s)' % (binascii.b2a_hex(cmd.message), dest_id))
                            self.stations[id]['lamp_ctrl'] = cmd.message[1]
                            self.stations[id]['lamp_adj1'] = cmd.message[2]
                            self.stations[id]['lamp_adj2'] = cmd.message[3]
                            if self.RC_unicast(dest_id=cmd.dest_id, message=cmd.message,
                                               expected=LampControl.TAG_POLL_ACK):
                                cmd.cmd_result = True
                            else:
                                cmd.cmd_result = False
                            self._ack_cmd(cmd)

                elif cmd.cmd == None:
                    # NULL CMD, return True/Success directly
                    cmd.cmd_result = True
                    self._ack_cmd(cmd)
                else:
                    # unknown CMD, return False/Failure
                    cmd.cmd_result = False
                    self._ack_cmd(cmd)
            else:
                # for STA/RELAY, call _STA_frame_process
                frame = self._Rx_queue.get()
                self._Rx_queue.task_done()
                self._STA_frame_process(frame)

        logger.info('Thread transmitting ends')

    def _poll_cmd(self):
        '''
        poll various cmd queues in round-robin manner for processing
        :return: cmd 
        '''
        cmd = self._p_cmd.recv()
        return cmd

    def _ack_cmd(self, cmd):
        '''
        response with updated cmd into various cmd queues
        :param cmd: 
        :return: None
        '''
        self._p_cmd.send(cmd)

    def _get_id_from(self, addr):
        '''
        look up node id from stations dictionary based on the logic addr
        if no match, return None.
        :param addr: the logic address
        :return: the node id in ASIC
        '''
        if addr == 0:
            return binascii.b2a_hex(LampControl.BROADCAST_ID)
        for id in self.stations.iterkeys():
            if self.stations[id]['addr'] == addr:
                return id
        return None

    def stop(self):
        self._stop = True

    def _STA_do_lamp_ctrl(self, value):
        if value[0] == LampControl.BYTE_ALL_ON:
            logger.info('LED ALL ON')
            if ISRPI:
                GPIO.output(self._GPIO_LED, GPIO.LOW)
        else:
            logger.info('LED ALL OFF')
            if ISRPI:
                GPIO.output(self._GPIO_LED, GPIO.HIGH)
        self._STA_lamp_status = value
        pass

    def _RC_wait_for_resp(self, src_id, tag, timeout):
        '''
        to avoid network storm, have to wait for time of "timeout" even the expected
        response is received properly.
        :param src_id: 
        :param tag: 
        :param timeout: 
        :return: 
        '''
        time_s = time()
        result = 1 # Timeout by default
        while (time() - time_s < timeout):
            try:
                rx_frame = self._Rx_queue.get(False)
            except Queue.Empty:
                continue
            else:
                logger.debug('A rx frame is popped!')
                self._Rx_queue.task_done()
                rx_src_id = rx_frame[LampControl.SRCID_S:LampControl.DESTID_S]
                rx_dest_id = rx_frame[LampControl.DESTID_S:LampControl.SN]
                rx_sn = ord(rx_frame[LampControl.SN])
                rx_tag = rx_frame[LampControl.TAG]
                rx_value = rx_frame[LampControl.VALUE_S:LampControl.CRC_S]
                message = rx_tag + rx_value
                if rx_src_id == src_id and rx_dest_id == self._id:
                    if rx_sn > self._frame_no:
                        self._frame_no = rx_sn
                        if rx_tag == LampControl.TAG_NACK:
                            logger.error('NACK is received')
                            result = 2
                        elif rx_tag == tag:
                            logger.debug('expected message received: %s', binascii.b2a_hex(message))
                            result = 0
                            recv_mesg = message
                        else:
                            logger.error('unexpected message received: %s', binascii.b2a_hex(message))
                            result = 3
        if result == 0:
            return recv_mesg
        elif result == 1:
            logger.error('RX Queue RxTimeOut!')
            raise RxTimeOut
        elif result == 2:
            raise RxNack
        elif result == 3:
            raise RxUnexpectedTag


    def RC_unicast(self, dest_id, message, expected):
        '''
        RC unicast only, expect TAG specified, will update stations dictionary if successful
        :param dest_id:
        :param message: 
        :param expected: expected TAG value
        :return: True on success, False on failure
        :exception RxNack, RxTimeOut
        '''
        result = False
        count = 0
        id = binascii.b2a_hex(dest_id)
        while count < self._retry:
            logger.info('RC send message %s times' % str(count + 1))
            self._send_message(dest_id, message)
            try:
                received_mesg = self._RC_wait_for_resp(src_id=dest_id, tag=expected, timeout=self.timeout*2)
            except (RxUnexpectedTag, RxNack, RxTimeOut):
                count += 1
                self.stations[id]['comm_fail'] += 1
                self.stations[id]['comm_quality'] += 1
            else:
                if received_mesg:
                    if expected == LampControl.TAG_POLL_ACK:
                        self.stations[id]['lamp_ctrl_status'] = received_mesg[1]
                        self.stations[id]['lamp_adj1_status'] = received_mesg[2]
                        self.stations[id]['lamp_adj2_status'] = received_mesg[3]
                    elif expected == LampControl.TAG_POWER1_ACK:
                        # TODO: need update for data storage
                        pass
                    elif expected == LampControl.TAG_POWER2_ACK:
                        pass
                    elif expected == LampControl.TAG_ENV1_ACK:
                        pass
                    elif expected == LampControl.TAG_ENV2_ACK:
                        pass
                    else:
                        pass
                    self.stations[id]['comm_okay'] += 1
                    self.stations[id]['comm_quality'] = 0
                    result = True
                    break
                else:
                    # never come here
                    count += 1
                    self.stations[id]['comm_fail'] += 1
                    self.stations[id]['comm_quality'] += 1

        return result

    def RC_lamp_ctrl(self, dest_id, value):
        '''
        can be unicast or broadcast, expect TAG_ACK
        :param dest_id:
        :param value:
        :return: True on success, False on failure
        '''
        count = 0
        mesg = LampControl.TAG_LAMP_CTRL + value
        logger.info('RC send lamp ctrl (%s) to STA (%s)' %
                    (binascii.b2a_hex(value), binascii.b2a_hex(dest_id)))
        while count < self._retry:
            logger.info('RC send message %s times' % str(count+1))
            self._send_message(dest_id, mesg)
            if dest_id == LampControl.BROADCAST_ID:
                # no response is expected on broadcast TX
                logger.info('Broadcast mesg: %s' % binascii.b2a_hex(mesg))
                return True
            try:
                (result, data) = self._RC_wait_for_resp(src_id=dest_id, tag=LampControl.TAG_ACK, timeout=self.timeout)
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
