#!/bin/sh

sleep 5

if [ ! -e ./rtc-stress-result.txt ]; then
	touch ./rtc-stress-result.txt
fi

# delay for correct system time
YEAR=`date +%Y`
if [ $YEAR = 1970 ]; then
	exit 1
fi
echo 1 >> rtc-stress-result.txt
reboot

