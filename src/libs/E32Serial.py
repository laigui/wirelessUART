#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

from mySerial import aSerial
import time

class E32(aSerial):
    """A class implementation for E32 from CDEBYTE"""
    def __init__(self, port, inHex=False):
        super(E32, self).__init__(port=port, inHex=inHex, baudrate=9600, timeout=5.0, bytesize=8,
                 parity='N', stopbits=1, xonxoff=False, rtscts=False)
        # E32 other parameters
        self.baudrate_air = 1200
        self.addr_high = 0
        self.addr_low = 4
        self.channel = 0x17 # bit[0..4] map into 410MHz .. 441MHz
        self.FEC = True
        self.AUX_timeout = 3 # in second
        # GPIO for E32 control
        self.GPIO_M0 = 17
        self.GPIO_M1 = 18
        self.GPIO_AUX = 27

    def reset(self):
        pass

    def get_version(self):
        pass

    def get_config(self):
        pass

    def set_config(self):
        pass

    def get_AUX(self):
        return True

    def transmit(self, aStr):
        cnt = 0
        while self.get_AUX() == False:
            cnt += 1
            if cnt >= self.AUX_timeout:
                self.logger.error("can't get AUX high before sending data to E32!")
                break
            time.sleep(1)
        else:
            super(E32, self).transmit(aStr)

