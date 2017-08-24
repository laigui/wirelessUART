#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

from mySerial import aSerial
import binascii
import time
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import os
if os.uname()[4].find('arm') == 0:
    import RPi.GPIO as GPIO
    ISRPI = True
else:
    ISRPI = False

class E32(aSerial):
    """A class implementation for E32 from CDEBYTE"""
    def __init__(self, port, inHex=False):
        super(E32, self).__init__(port=port, inHex=inHex, baudrate=9600, timeout=None, bytesize=8,
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
        if ISRPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.GPIO_M0, GPIO.OUT)
            GPIO.setup(self.GPIO_M1, GPIO.OUT)
            GPIO.setup(self.GPIO_AUX, GPIO.IN, GPIO.PUD_UP)
            self.set_E32_mode(0)

    def __del__(self):
        super(E32, self).__del__()
        if ISRPI:
            GPIO.cleanup()

    def set_E32_mode(self, mode):
        if ISRPI:
            if mode == 0: # normal TX mode
                GPIO.output(self.GPIO_M0, GPIO.LOW)
                GPIO.output(self.GPIO_M1, GPIO.LOW)
            elif mode == 3: # configuration mode
                GPIO.output(self.GPIO_M0, GPIO.HIGH)
                GPIO.output(self.GPIO_M1, GPIO.HIGH)

    def get_version(self, inHex=True):
        cmd_str = '\xC3\xC3\xC3'
        self.transmit(cmd_str)
        time.sleep(1)
        if inHex:
            return self.receive(n=4,s=3)
        else:
            return binascii.hexlify(self.receive(n=4,s=3))

    def get_config(self, inHex=True):
        cmd_str = '\xC1\xC1\xC1'
        self.transmit(cmd_str)
        time.sleep(1)
        if inHex:
            return self.receive(n=6,s=3)
        else:
            return binascii.hexlify(self.receive(n=6,s=3))

    def set_config(self, config=None):
        ''' set config to the default: 9600bps for uart and air, addr=1, channel=1
        10dbm, FEC on, transparent TX, push-pull IO, 250ms wakeup time
        '''
        if config == None:
            default_config = '\xc0\x00\x00\x1c\x14\x47'
        else:
            default_config = config
        self.transmit(default_config)
        time.sleep(1)
        if self.get_config() == default_config:
            logger.info('set config successfully')
        else:
            logger.error('set config failed')

    def get_AUX(self):
        if ISRPI:
            if GPIO.input(self.GPIO_AUX):
                return True
            else:
                return False
        else:
            return True

    def transmit(self, aStr):
        cnt = 0
        while self.get_AUX() == False:
            cnt += 1
            if cnt >= self.AUX_timeout:
                logger.error("can't get AUX high before sending data to E32!")
                break
            time.sleep(1)
        else:
            super(E32, self).transmit(aStr)


if __name__ == "__main__":
    logging.basicConfig(level='DEBUG')
    if ISRPI:
        port = '/dev/ttyAMA0'
    else:
        port = '/dev/ttyUSB0'
    ser = E32(port=port, inHex=False)
    ser.open()
    ser.set_E32_mode(3)
    print ser.get_version(inHex=False)
    print ser.get_config(inHex=False)
    ser.set_config()
    print ser.get_config(inHex=False)
    ser.set_E32_mode(0)
    ser.close()
