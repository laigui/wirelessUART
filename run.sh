#!/bin/sh

# delay for correct system time
YEAR=`date +%Y`
if [ $YEAR = 1970 ]; then
	sleep 10
fi

if [ ! -d ~/znld-logs ]; then mkdir ~/znld-logs; fi
cd ~/works/wirelessUART/src
python startup.py
