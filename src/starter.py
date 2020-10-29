#!/usr/bin/python3
import os
import os.path
import json
import shutil
import sensors
import datetime
import traceback
import db
from xml.dom import minidom
from xml.dom.minidom import parse, Text

HISTORY = "/home/pi/kadd-pi/data/rideHistory.json"
CURRENT_RIDES = "/home/pi/kadd-pi/data/rides/current/"
UNSENT_RIDES = "/home/pi/kadd-pi/data/rides/unsent/"
SENT_RIDES = "/home/pi/kadd-pi/data/rides/sent/"
ERR_LOG = "/home/pi/kadd-pi/data/errorLog.txt"
CONFIG = "/home/pi/kadd-pi/data/about.xml"

# Load Config
if os.path.isfile(CONFIG):
    config = minidom.parse(CONFIG)
    GPS_RATE = float(config.getElementsByTagName('gpsSampRate')[0].firstChild.data)
    IMU_RATE = float(config.getElementsByTagName('imuSampRate')[0].firstChild.data)
    MODE = int(config.getElementsByTagName('mode')[0].firstChild.data)
else:
    GPS_RATE = 15
    IMU_RATE = 1
    MODE = 1 # Farm Mode

# Get the serial number for the device's processor
#
# Returns a string representing serial number
def getSerial():
    # Extract serial from cpuinfo file
    try:
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:6]=='Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = "ERROR"
 
    return cpuserial

# Get the model name for the device
#
# Returns a string representing model name
def getModel():
  # Extract model from cpuinfo file
    try:
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:5]=='Model':
                model = line[9:-1]
        f.close()
    except:
        model = "ERROR"
 
    return model

# Configure CONFIG file with device serial and model information
#
# While this information is not used by the pi, it is used as
# identifying informaiton for the device in the database
def configXml():
    # Read in config file
    config = minidom.parse(CONFIG)
    
    serial = config.getElementsByTagName('serial')[0]
    if serial.firstChild == None:
        # Serial element is empty, add value
        serialText = Text()
        serialText.data = getSerial()
        serial.appendChild(serialText)
        
    model = config.getElementsByTagName('model')[0]
    if model.firstChild == None:
        # Model elemetn is empty, add value
        modelText = Text()
        modelText.data = getModel()
        model.appendChild(modelText)

    # Write updated data to file
    with open(CONFIG, "w") as f:
        config.writexml(f)

# Prepare files for creating new rides and sending old rides by moving
# all old files stored in current rides to the unsent rides folder
def prepFiles():
    try:
        # Collect list of all files stored in current rides
        oldCurrentFiles = os.listdir(CURRENT_RIDES)
        # Move each file in current rides to unsent
        for file in oldCurrentFiles:
            if file != ".gitignore":
                shutil.move(CURRENT_RIDES + file, UNSENT_RIDES + file)
    except Exception as exc:
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+"\n")
            traceback.print_tb(exc.__traceback__, file=errorLog)

# Read the ride history json and convert it to a dict
#
# Returns a dictionary with the last ride index (int) and sent rides list
def getRideHistory():
    with open(HISTORY) as rideHistoryJson:
        rideHistory = json.load(rideHistoryJson)

    return rideHistory

# Update the ride history json with new info for all of it's parameters
#
# @rideHistory: a dict representing the parameters to be written to the ride history json
def setRideHistory(rideHistory):
    with open(HISTORY, "w") as rideHistoryJson:
        rideHistoryJson.write(json.dumps(rideHistory))

# Determine the current ride's name by reading the ride history json
# and incrementing the "lastRide" value
#
# Returns string representing new ride name
def determineRideName():
    rideHistory = getRideHistory()

    # Determine current ride name
    if rideHistory["lastRide"] == None:
        # No previous rides
        rideHistory["lastRide"] = 0
        currentRide = "ride" + str(rideHistory["lastRide"])
    else:
        # Previous ride exists
        rideHistory["lastRide"] = rideHistory["lastRide"] + 1
        currentRide = "ride" + str(rideHistory["lastRide"])

    return currentRide

# Creates two threads: a parent Database transmission thread, and a ride tracking thread
# continues operations until the terminal is terminated (a device shutdown)
def main():
    with open(ERR_LOG, "a") as errorLog:
        errorLog.write(str(datetime.datetime.now())+f"\nStarting main()\n")
    
    # Send model and serial data to xml that can be read by app
    configXml()
    # Move completed rides to unsent folder
    prepFiles()
    # Determine ride number
    currentRide = determineRideName()
    
    # Fork process between database ops (parent) and ride ops (child)
    pid = os.fork()
    if pid:
        # Parent thread, attempts to send rides
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+f"\nStarting data transmission thread\n")
            
        print("Attempting to send data!")
        # Get list of files in unsent rides dir
        unsentRides = os.listdir(UNSENT_RIDES)
        
        for ride in unsentRides:
            if ride != ".gitignore":
                db.sendFileToDb(UNSENT_RIDES + ride)
                with open(ERR_LOG, "a") as errorLog:
                    errorLog.write(str(datetime.datetime.now())+"\n")
                    errorLog.write(f"Attempt made to file: {UNSENT_RIDES + ride} to database!\n")
                try:
                    # attempt to move sent file to sent rides dir
                    shutil.move(UNSENT_RIDES + ride, SENT_RIDES + ride)
                except Exception as exc:
                    with open(ERR_LOG, "a") as errorLog:
                        errorLog.write(str(datetime.datetime.now())+"\n")
                        traceback.print_tb(exc.__traceback__, file=errorLog)
    else:
        # Child thread
        print(f"Starting {currentRide}!")
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+f"\nStarting {currentRide}\n")
            
        try:
            sensors.startSampling(currentRide, GPS_RATE, IMU_RATE, MODE)
        except Exception as exc:
            with open(ERR_LOG, "a") as errorLog:
                errorLog.write(str(datetime.datetime.now())+"\n")
                traceback.print_tb(exc.__traceback__, file=errorLog)
main()
