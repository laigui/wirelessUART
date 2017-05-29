#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

import serial
import binascii
from time import sleep
from myException import RxTimeOutError
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class aSerial(object):
    """a serial class implementation with additional features"""
    def __init__(self, port, baudrate=9600,
                 timeout=None, bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                 xonxoff=False, rtscts=False, inHex=False):
        # serial control parameters
        self.isOpen = False
        self.inHex = inHex
        self.rx_cnt = 0
        self.tx_cnt = 0

        # serial related parameters
        self.sp = None
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.parity = parity
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.rtscts = rtscts

    def __del__(self):
        self.close()

    def open(self):
        if self.port:
            try:
                self.sp = serial.Serial(port=self.port, baudrate=self.baudrate,
                                        timeout=self.timeout, bytesize=self.bytesize,
                                        parity=self.parity, stopbits=self.stopbits,
                                        xonxoff=self.xonxoff, rtscts=self.rtscts,
                                        dsrdtr=False)
            except serial.SerialException:
                logger.error("Serial open failed!")
                raise
            if self.sp.isOpen():
                logger.debug("%s is opened", self.port)
                self.isOpen = True
                self._reset()
            return True
        else:
            logger.error("Serial port is NULL")
            return False

    def close(self):
        self.isOpen = False
        if self.sp:
            self.sp.close()
            logger.debug("%s is closed", self.port)

    def _reset(self):
        self.tx_cnt = 0
        self.sp.flushOutput()
        self.rx_cnt = 0
        self.sp.flushInput()


    def receive(self, n=0, s=0):
        '''
        :param n: n bytes to be received, if n=-1, return whatever are received, if n=0, return nothing.
        :param s: s in seconds for timeout, if s=0, no timeout
        :return: the string received
        '''
        aStr = ''
        rxStr = ''
        rx_cnt = 0
        timeout = 0
        if self.isOpen == True and n != 0:
            try:
                if n == -1:
                    rxStr = self.sp.read(self.sp.inWaiting())
                else:
                    while rx_cnt < n:
                        rxn = self.sp.inWaiting()
                        left = n - rxn - rx_cnt
                        if left >= 0:
                            rxStr = rxStr + self.sp.read(rxn)
                            rx_cnt = rx_cnt + rxn
                            if s != 0:
                                timeout += 1
                                if timeout > s:
                                    raise RxTimeOutError(rxStr, n, s)
                        else:
                            rxStr = rxStr + self.sp.read(n - rx_cnt)
                            rx_cnt = n
                        sleep(1)
            except (serial.SerialTimeoutException, serial.SerialException)as e:
                logger.error("serial read error!")
                logger.error(e)
            else:
                if self.inHex:
                    aStr = binascii.hexlify(rxStr)
                else:
                    aStr = rxStr
                self.rx_cnt += len(rxStr)
                logger.debug("RX (%d/%d bytes): %s", len(rxStr), self.rx_cnt, aStr)
        return aStr

    def transmit(self, aStr):
        tx_cnt = len(aStr)
        if self.isOpen == True:
            if self.inHex:
                try:
                    bStr = binascii.unhexlify(aStr)
                except TypeError:
                    logger.error("Input Error: need Even-length string for transmition in HEX mode!")
                    raise
            else:
                bStr = aStr
            try:
                self.sp.write(bStr)
            except serial.SerialTimeoutException as e:
                logger.error("serial write error!")
                logger.error(e)
                raise
            else:
                self.tx_cnt += tx_cnt
                logger.debug("TX (%d/%d bytes): %s", tx_cnt, self.tx_cnt, bStr)