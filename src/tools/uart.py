#!/usr/bin/python
# -*- coding:utf-8 -*-
import serial
from time import sleep

#ser = serial.Serial("/dev/ttyAMA0",115200)
#ser = serial.Serial("/dev/ttyS0",115200)
ser = serial.Serial(port="/dev/ttyUSB0",baudrate=9600,timeout=10)

print('serial test start ...')
cnt = 0
str1 = 'Hello World '
try:
	while True:
            str2 = str1 + str(cnt) + str('\n')
            ser.write(str2)
            cnt += 1
            sleep(3)
except KeyboardInterrupt:
	if ser != None:
		ser.close()
