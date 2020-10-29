#!/bin/bash
sudo apt-get update
sudo apt-get install python3
pip3 install adafruit-blinka adafruit-circuitpython-gps adafruit-circuitpython-lsm9ds1 google-cloud-firestore firebase-admin
cp -f /home/pi/kadd-pi/setup/autostart /home/pi/.config/lxsession/LXDE-pi
cp /home/pi/.bashrc /home/pi/Desktop/bashrcBackup
cp -f /home/pi/kadd-pi/setup/.bashrc /home/pi/.bashrc
