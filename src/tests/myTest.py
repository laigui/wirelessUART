#!/usr/bin/python
# -*- coding: utf-8 -*-

import random, string, time
import threading
from libs.E32Serial import E32
import logging
from Queue import Queue
from libs.myException import RxTimeOutError
import os
if os.uname()[4].find('arm') == 0:
    import RPi.GPIO as GPIO
    ISRPI = True
else:
    ISRPI = False

_TAG = "=="

class PacketGen(object):
    """A packet generation class"""
    def __init__(self, min_len=3, max_len=10):
        self._max_len = max_len + 1
        self._min_len = min_len
        self._tag = _TAG

    def generate(self):
        length = random.sample(range(self._min_len, self._max_len), 1)[0]
        str = self._tag + \
              ''.join(random.choice(string.letters + string.digits) for i in range(length))
        return str


class MyTest(object):
    """"My test class
    generate packets
    transmit over serial
    receive from serial
    bit true check
    """
    def __init__(self, tx_interval=5, rx_timeout=5, pkt_min_len=3, pkt_max_len=10):
        self.event_rx_end = threading.Event()
        self.t_rx = None
        self.inTest = False
        self.logger = logging.getLogger("myLogger.myTest")
        self.gui_log = Queue(0)
        self.log_buffer = ''
        self._rx_timeout = rx_timeout
        self._tx_interval = tx_interval
        self._pkt_min_len = pkt_min_len
        self._pkt_max_len = pkt_max_len
        self._GPIO_LED = 21
        if ISRPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._GPIO_LED, GPIO.OUT)
        self._tx_cnt = 0
        self._rx_cnt = 0
        self._rx_nok_cnt = 0
        self._rx_nok_cnt_mismatch = 0
        self._rx_nok_cnt_in_pkt_rx_timeout = 0
        self._rx_nok_cnt_rx_timeout = 0
        self._rx_ok_cnt = 0
        self._pkt_len = 0
        self._str_txed = ''
        self._str_rxed = ''
        if ISRPI:
            port = '/dev/ttyS0'
        else:
            port = '/dev/ttyUSB0'
        self.ser = E32(port=port, inHex=False)

    def __del__(self):
        if ISRPI:
            GPIO.cleanup()

    def configure(self, tx_interval=5, rx_timeout=5, pkt_min_len=3, pkt_max_len=10):
        self._rx_timeout = rx_timeout
        self._tx_interval = tx_interval
        self._pkt_min_len = pkt_min_len
        self._pkt_max_len = pkt_max_len
        self.data = PacketGen(min_len=self._pkt_min_len, max_len=self._pkt_max_len)

    def test_init(self):
        if self.ser.open():
            #pull out gabage bytes in RX FIFO
            self.ser.reset()

    def toGUI(self):
        message = self.gui_log.get(True)
        self.gui_log.task_done()
        return message

    def start_tx(self, loop):
        if self.inTest == False:
            self.logger.debug('Start TX...')
            self.test_init()
            self.inTest = True
            self.start_rx()
            self._loop = loop
            if self._loop > 0:
                self._infinity = False
            else:
                self._infinity = True

            while self._infinity or self._loop > self._rx_cnt:
                # wait for loopback rx check
                if self._tx_cnt == self._rx_cnt:
                    if ISRPI:
                        GPIO.output(self._GPIO_LED, GPIO.LOW)
                    self._str_txed = self.data.generate()
                    self._pkt_len = len(self._str_txed)
                    self.ser.transmit(self._str_txed)
                    self._tx_cnt += 1
                time.sleep(self._tx_interval)
            self.stop_tx()
            self.logger.info("Thread-TX end")

    def stop_tx(self):
        if self.inTest == True:
            self.event_rx_end.set()
            if self.t_rx != None:
                self.t_rx.join()
                self.t_rx = None
            self.logger.debug('Stop TX...')
            self.inTest = False
            self._infinity = False
            self._loop = 0
            self._tx_cnt = 0
            self._rx_cnt = 0
            self._rx_nok_cnt = 0
            self._rx_nok_cnt_mismatch = 0
            self._rx_nok_cnt_in_pkt_rx_timeout = 0
            self._rx_nok_cnt_rx_timeout = 0
            self._rx_ok_cnt = 0
            self._str_txed = ''
            self._str_rxed = ''
            self.ser.reset()
            self.ser.close()


    def start_rx(self):
        if self.t_rx == None:
            self.logger.debug('Start RX...')
            self.event_rx_end.clear()
            self.t_rx = threading.Thread(target=self.do_receiving, name="Thread-RX", args=(self.event_rx_end,))
            self.t_rx.start()

    def do_receiving(self, e_end):
        pkt_started = False
        time_loop = 0
        rx_len = 0
        str_p = ''
        while not e_end.isSet():
            if self._tx_cnt > self._rx_cnt: # TXed packet out
                try:
                    str = self.ser.receive(self._pkt_len, self._rx_timeout)
                except RxTimeOutError as e: # not receive enough bytes until timeout
                    self._rx_nok_cnt += 1
                    self._rx_nok_cnt_rx_timeout += 1
                    self.logger.error("RX %d bytes timeout\n%s", self._pkt_len, e)
                    self.gui_log.put("RX {0} bytes timeout\n{1}\n".format(self._pkt_len, e))
                    self.logger.error("!!! loop %d RX timeout (P: %d F: %d [%d, %d, %d]) !!!",
                                      self._tx_cnt, self._rx_ok_cnt, self._rx_nok_cnt, self._rx_nok_cnt_mismatch,
                                      self._rx_nok_cnt_in_pkt_rx_timeout, self._rx_nok_cnt_rx_timeout)
                    self.gui_log.put(
                        "!!! loop {0} RX timeout (P: {1} F: {2} [{3}, {4}, {5}]) !!!\n".format(self._tx_cnt,
                                                                                   self._rx_ok_cnt,
                                                                                   self._rx_nok_cnt,
                                                                                   self._rx_nok_cnt_mismatch,
                                                                                   self._rx_nok_cnt_in_pkt_rx_timeout,
                                                                                   self._rx_nok_cnt_rx_timeout))
                else: # 1st time of receiving required bytes
                    if str == self._str_txed: # match with the exact length
                        self._str_rxed = str
                        self._rx_ok_cnt += 1
                        if ISRPI:
                            GPIO.output(self._GPIO_LED, GPIO.HIGH)
                        self.logger.info("+++ loop %d succeeded (P: %d F: %d [%d, %d, %d]) +++",
                                         self._tx_cnt, self._rx_ok_cnt, self._rx_nok_cnt, self._rx_nok_cnt_mismatch,
                                         self._rx_nok_cnt_in_pkt_rx_timeout, self._rx_nok_cnt_rx_timeout)
                        self.gui_log.put("+++ loop {0} succeeded (P: {1} F: {2} [{3}, {4}, {5}]) +++\n".format(self._tx_cnt,
                                                                                   self._rx_ok_cnt,
                                                                                   self._rx_nok_cnt,
                                                                                   self._rx_nok_cnt_mismatch,
                                                                                   self._rx_nok_cnt_in_pkt_rx_timeout,
                                                                                   self._rx_nok_cnt_rx_timeout))
                    else: # mismatch so continue receiving until timeout
                        index_s = str.find(self._str_txed)
                        while index_s == -1:
                            if time_loop > self._rx_timeout:
                                self._rx_nok_cnt += 1
                                self._rx_nok_cnt_mismatch += 1
                                self.logger.error("*** Data mismatch ***")
                                self.logger.error("TX: %s", self._str_txed)
                                self.logger.error("RX: %s", str)
                                self.logger.error("*** loop %d failed (P: %d F: %d [%d, %d, %d]) ***",
                                                  self._tx_cnt, self._rx_ok_cnt, self._rx_nok_cnt, self._rx_nok_cnt_mismatch,
                                                  self._rx_nok_cnt_in_pkt_rx_timeout, self._rx_nok_cnt_rx_timeout)
                                self.gui_log.put("*** loop {0} failed (P: {1} F: {2} [{3}, {4}, {5}]) ***\n".format(self._tx_cnt,
                                                                                    self._rx_ok_cnt,
                                                                                    self._rx_nok_cnt,
                                                                                    self._rx_nok_cnt_mismatch,
                                                                                    self._rx_nok_cnt_in_pkt_rx_timeout,
                                                                                    self._rx_nok_cnt_rx_timeout))
                                break
                            time.sleep(1)
                            str = str + self.ser.receive()
                            index_s = str.find(self._str_txed)
                            time_loop += 1
                        else: # match here
                            self._rx_ok_cnt += 1
                            time_loop = 0
                            index_e = index_s + self._pkt_len - 1
                            self._str_rxed = str[index_s:index_e]
                            if ISRPI:
                                GPIO.output(self._GPIO_LED, GPIO.HIGH)
                            self.logger.info("+++ loop %d succeeded (P: %d F: %d [%d, %d, %d]) +++",
                                             self._tx_cnt, self._rx_ok_cnt, self._rx_nok_cnt, self._rx_nok_cnt_mismatch,
                                             self._rx_nok_cnt_in_pkt_rx_timeout, self._rx_nok_cnt_rx_timeout)
                            self.gui_log.put(
                                "+++ loop {0} succeeded (P: {1} F: {2} [{3}, {4}, {5}]) +++\n".format(self._tx_cnt,
                                                                                  self._rx_ok_cnt,
                                                                                  self._rx_nok_cnt,
                                                                                  self._rx_nok_cnt_mismatch,
                                                                                  self._rx_nok_cnt_in_pkt_rx_timeout,
                                                                                  self._rx_nok_cnt_rx_timeout))

                self._rx_cnt += 1
            time.sleep(1)
        self.logger.info("Thread-RX end")

