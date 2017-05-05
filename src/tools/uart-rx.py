#!/usr/bin/python
# -*- coding:utf-8 -*-
import serial
from time import sleep
from time import localtime, strftime

#ser = serial.Serial("/dev/ttyS0",115200)
ser = serial.Serial(port="/dev/ttyUSB1",baudrate=9600,timeout=10)

print('serial test start ...')
rx_cnt = 0
try:
	while True:
            if ser.in_waiting > 0:
                    current_time = strftime("test-%y%m%d-%H:%M:%S  ", localtime())
        	    print current_time + ser.read(ser.in_waiting) + '\n'
            sleep(1)
except KeyboardInterrupt:
	if ser != None:
		ser.close()
