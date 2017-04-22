#!/usr/bin/python
# -*- coding: utf-8 -*-

import random, string, time
import threading
from libs.E32Serial import E32
import logging
from Queue import Queue
import RPi.GPIO as GPIO

_TAG = "5"

class PacketGen(object):
    """A packet generation class"""
    def __init__(self, min_len=3, max_len=10):
        self._max_len = max_len
        self._min_len = min_len
        self._tag = _TAG

    def generate(self):
        length = random.sample(range(self._min_len, self._max_len), 1)[0]
        print "random {0}".format(length)
        str = self._tag + \
              ''.join(random.choice(string.letters) for i in range(length))
        return str


class MyTest(object):
    """"My test class
    generate packets
    transmit over serial
    receive from serial
    bit true check
    """
    def __init__(self, tx_interval_ms=3000, rx_timeout_ms=5000, pkt_min_len=3, pkt_max_len=10):
        self.logger = logging.getLogger("myLogger.myTest")
        self.gui_log = Queue(0)
        self.log_buffer = ''
        self._rx_timeout_ms = rx_timeout_ms
        self._tx_interval_ms = tx_interval_ms
        self._pkt_min_len = pkt_min_len
        self._pkt_max_len = pkt_max_len
        self._GPIO_LED = 21
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._GPIO_LED, GPIO.OUT)
        self._tx_cnt = 0
        self._rx_cnt = 0
        self._rx_nok_cnt = 0
        self._rx_ok_cnt = 0
        self._pkt_len = 0
        self._str_txed = ''
        self._str_rxed = ''
        self.ser = E32(port='/dev/ttyS0', inHex=False)
        self.test_init()

    def __del__(self):
        GPIO.cleanup()

    def configure(self, tx_interval_ms=3000, rx_timeout_ms=5000, pkt_min_len=3, pkt_max_len=10):
        self._rx_timeout_ms = rx_timeout_ms
        self._tx_interval_ms = tx_interval_ms
        self._pkt_min_len = pkt_min_len
        self._pkt_max_len = pkt_max_len
        self.data = PacketGen(min_len=self._pkt_min_len, max_len=self._pkt_max_len)

    def test_init(self):
        if self.ser.open():
            #pull out gabage bytes in RX FIFO
            self.ser.receive()
            self.start_rx()

    def toGUI(self):
        message = self.gui_log.get(True)
        self.gui_log.task_done()
        return message

    def start_tx(self, loop):
        self._loop = loop
        if self._loop > 0:
            self._infinity = False
        else:
            self._infinity = True

        while self._infinity or self._loop > self._rx_cnt:
            # wait for loopback rx check
            if self._tx_cnt == self._rx_cnt:
                GPIO.output(self._GPIO_LED, GPIO.LOW)
                self._str_txed = self.data.generate()
                self._pkt_len = len(self._str_txed)
                self.ser.transmit(self._str_txed)
                self._tx_cnt += 1
                time.sleep(self._tx_interval_ms/1000)
        self.stop_tx()

    def stop_tx(self):
        self._infinity = 0
        self._loop = 0
        self._tx_cnt = 0
        self._rx_cnt = 0
        self._rx_nok_cnt = 0
        self._rx_ok_cnt = 0

    def start_rx(self):
        global t1
        t1 = threading.Thread(target=self.do_receiving, name="Thread-RX")
        t1.daemon = True
        t1.start()

    def do_receiving(self):
        pkt_started = False
        time_loop = 0
        rx_len = 0
        while True:
            str = self.ser.receive()

            if str:
                try:
                    index = str.index(_TAG)
                except ValueError:
                    if pkt_started: # normal receiving after TAG is detected
                        self._str_rxed = ''.join([self._str_rxed, str])
                        rx_len += len(str)
                    else:
                        self.logger.error("TAG %s not found", _TAG)
                        self.gui_log.put("TAG {0} not found\n".format(_TAG))
                        continue
                else: # TAG is detected
                    self._str_rxed = str[index:]
                    rx_len = len(self._str_rxed)
                    pkt_started = True
                
            if pkt_started:
                if time_loop < self._rx_timeout_ms:
                    if rx_len >= self._pkt_len: # one packet receiving done
                        pkt_started = False
                        self._rx_cnt += 1
                        time_loop = 0
                        if self._str_rxed == self._str_txed:
                            self._rx_ok_cnt += 1
                            GPIO.output(self._GPIO_LED, GPIO.HIGH)
                            self.logger.info("+++ loop %d succeeded (P: %d F: %d) +++",
                                             self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt)
                            self.gui_log.put("+++ loop {0} succeeded (P: {1} F: {2}) +++\n".format(self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt))
                        else:
                            self.logger.error("*** loop %d failed (P: %d F: %d) ***",
                                             self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt)
                            self.gui_log.put("*** loop {0} failed (P: {1} F: {2}) ***\n".format(self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt))
                            self.logger.error("*** Data mismatch ***")
                            self.logger.error("TX: %s", self._str_txed)
                            self.logger.error("RX: %s", self._str_rxed)
                            self._rx_nok_cnt += 1
                    else:
                        time.sleep(0.001) # sleep for 1ms
                        time_loop += 1
                else:
                    self._rx_nok_cnt += 1
                    pkt_started = False
                    self._rx_cnt += 1
                    time_loop = 0
                    self.logger.error("!!! loop %d RX timeout (P: %d F: %d) !!!",
                                      self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt)
                    self.gui_log.put("!!! loop {0} RX timeout (P: {1} F: {2}) !!!\n".format(self._rx_cnt, self._rx_ok_cnt, self._rx_nok_cnt))

