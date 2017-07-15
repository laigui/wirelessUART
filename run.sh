#!/bin/sh

# delay for correct system time
sleep 10

if [ ! -d ~/znld-logs ]; then mkdir ~/znld-logs; fi
cd ~/works/wirelessUART/src
python startup.py
