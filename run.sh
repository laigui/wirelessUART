#!/bin/sh

if [ ! -d ~/znld-logs ]; then mkdir ~/znld-logs; fi
cd ~/works/wirelessUART/src
python startup.py
