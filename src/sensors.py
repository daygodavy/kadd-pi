#!/usr/bin/python3
import time
import datetime
import serial
import os
import os.path
import json
import adafruit_gps

import board
import busio
import adafruit_lsm9ds1
from digitalio import DigitalInOut, Direction

import rockBlock
import math
import traceback

from xml.dom import minidom
import RPi.GPIO as GPIO

# File path to store .csv
HISTORY = "/home/pi/kadd-pi/data/rideHistory.json"
PATH = "/home/pi/kadd-pi/data/rides/current/"
IMU_FULL_REC_PATH = "/home/pi/kadd-pi/data/rides/imuComplete/"
ERR_LOG = "/home/pi/kadd-pi/data/errorLog.txt"
CONFIG = "/home/pi/kadd-pi/data/about.xml"

if os.path.isfile(CONFIG):
    config = minidom.parse(CONFIG)
    MIN_ACCEL = float(config.getElementsByTagName('coneMinAccel')[0].firstChild.data)
    MAX_ACCEL = float(config.getElementsByTagName('coneMaxAccel')[0].firstChild.data)
    SENSITIVITY = float(config.getElementsByTagName('coneSensitivity')[0].firstChild.data)
    CRASHTHRESH = float(config.getElementsByTagName('crashTimerThreshold')[0].firstChild.data)
    FOB_GPIO = int(config.getElementsByTagName('keyfobGpio')[0].firstChild.data)
    PHONE = str(config.getElementsByTagName('phone')[0].firstChild.data)
    DEV_ID = str(config.getElementsByTagName('devId')[0].firstChild.data)
else:
    # Minimum (largest negative) acceleration for z axis to be considered a steady-state
    # rollover, also z coordinate for tip of cone
    MIN_ACCEL = -11 #-10.682
    # Maximum acceleration for z axis to be considered a steady state rollover,
    # also z coordinate for base of cone
    MAX_ACCEL = -1 #-4.5 # Calculated to be -6.39, but testing proves larger values are better
    # Coefficient k from cone equation x^2+y^2=(MIN_ACCEL/(MAX_ACCEL-MIN_ACCEL)(z-MIN_ACCEL)*k)^2
    # adjusts the sensitivity of the algorithm by making the cone wider
    SENSITIVITY = 2
    # Number of Seconds that the vehicle must be in a rollover state before message sent
    CRASHTHRESH = 10
    # GPIO Channel that listens for keyfob activation
    FOB_GPIO = 23
    # Phone number for emergency services (0 = Noonlight service, phone# = sms)
    PHONE = 0
    # Device ID
    DEV_ID = "default_device"

# Main cone coefficient
CONE_COEFF = MIN_ACCEL/(MAX_ACCEL-MIN_ACCEL)
# Conversion factor from knots to other units
CONV = 1.852 #kph
# Size of IMU data history stored in cyclical array
IMU_SAMPLE_SIZE = 60
# Imu refresh rate in seconds if farm mode is active
FARM_IMU_RATE = 1.0

# Class that creates a cyclical array
#
# Initilization takes the maximum size (int) as a parameter
# Add values with append
# Iterable; iterates through array contents
# Print contents with display
# Get the last element in the array with getEnd
class cyclicalArray:
    data = []
    endIndex = 0
    maxLen = 0
    size = 0
    def __init__(self, maxLen):
        self.maxLen = maxLen
    def __iter__(self):
        return iter(self.data)
    def append(self, val):
        if self.size < self.maxLen:
            self.data.insert(self.endIndex, val)
        else:
            self.data[self.endIndex] = val
        self.endIndex = (self.endIndex + 1) % self.maxLen
        self.size = self.size + 1
    def clear(self):
        self.data = []
        self.endIndex = 0
        self.size = 0
    def display(self):
        print(self.data)
    def length(self):
        return len(self.data)
    def getEnd(self):
        if self.endIndex == 0:
            return self.data[self.maxLen - 1]
        else:
            return self.data[self.endIndex - 1]

# Creates a LSM9D1_SPI object to represent the device's IMU using SPI
#
# Returns a LSM9D1_SPI object
def createImu():
    #SPI connection:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    csag = DigitalInOut(board.D5)
    csag.direction, csag.value = Direction.OUTPUT, True
    csm = DigitalInOut(board.D6)
    csm.direction, csm.value = Direction.OUTPUT, True
    imu = adafruit_lsm9ds1.LSM9DS1_SPI(spi, csag, csm)
    return imu

# Detects a Rollover scenario by judging if the current IMU sample is within
# the "critical value cone" determined by x^2+y^2=((MIN_ACCEL/(MAX_ACCEL-MIN_ACCEL))*(z-MIN_ACCEL)*SENSITIVITY)^2
#
# @sample: the sample to be assessed for a rollover
#
# Returns True if there was a rollover, False otherwise
def detectRollover(sample):
    # MAX_ACCEL <= z <= MIN_ACCEL
    if sample["accelZ"] >= MIN_ACCEL and sample["accelZ"] <= MAX_ACCEL:
        r = math.sqrt((CONE_COEFF*(sample["accelZ"]-MIN_ACCEL)*SENSITIVITY)**2)
        distFromZ = math.sqrt((sample["accelX"]*sample["accelX"])+(sample["accelY"]*sample["accelY"]))
        print(f"Radius of cone at height {sample['accelZ']}: {r}")
        print(f"Point ({sample['accelX']},{sample['accelY']},{sample['accelZ']}) is {distFromZ} away from the z-axis")
        if distFromZ <= r:
            return True
        else:
            return False
    
    return False

# Updates the number of seconds a vehicle has been rolled over
#
# @rollCount: int representing the current number of seconds the device has been rolled over
# @sample: an IMU sample to check for roll over
def updateRollCount(rollCount, sample):
    if sample['didRoll'] and rollCount <= CRASHTHRESH:
        rollCount += 1
    elif (rollCount > 0):
        rollCount -= 1

    return rollCount

# Takes a sample of the IMU's accelerometer and gyroscope
#
# @imu: IMU instance representing the sensor to be sampled
# returns dicitonary including accel and gyro data for all 3 axis and didRoll if roll was detected
def sampleImu(imu):
    accelX, accelY, accelZ = imu.acceleration
    gyroX, gyroY, gyroZ = imu.gyro

    accelX, accelY, accelZ = round(accelX, 5), round(accelY, 5), round(accelZ,5)
    gyroX, gyroY, gyroZ = round(gyroX, 5), round(gyroY, 5), round(gyroZ,5)

    print('Accel (x,y,z): ' + f'{accelX}' + "," + f'{accelY}' + "," + f'{accelZ}' + '\n' \
          + 'Gyro (x,y,z): ' + f'{gyroX}' + "," + f'{gyroY}' + "," + f'{gyroZ}' + '\n')

    sample = {
        'time': datetime.datetime.now(),
        'accelX': accelX,
        'accelY': accelY,
        'accelZ': accelZ,
        'gyroX': gyroX,
        'gyroY': gyroY,
        'gyroZ': gyroZ,
        'didRoll': False,
        'rollover': False
    }

    sample['didRoll'] = detectRollover(sample)
    return sample

# Writes an array of IMU samples out to a file path called fn
#
# @fn: file path to output to
# @array: data to write
def writeImuArray(fn, array):
    # Append every sample in array to .csv
    with open(fn, "w") as outFile:
        outFile.write('time,accelX,accelY,accelZ,gyroX,gyroY,gyroZ,possibleRoll,rollover\n')
        for sample in array:
            outFile.write(f'{sample["time"]},{sample["accelX"]},{sample["accelY"]},{sample["accelZ"]},'\
                            f'{sample["gyroX"]},{sample["gyroY"]},{sample["gyroZ"]},{sample["didRoll"]},{sample["rollover"]}\n')

# Writes a single imu sample to a file specified by fn
#
# @fn: file path to output to
# @sample: imu sample to write
def writeImuSample(fn, sample):
    # Create .csv if it doesn't exist
    if(not (os.path.exists(fn))):
        with open(fn, 'a') as outFile:
            outFile.write('time,accelX,accelY,accelZ,gyroX,gyroY,gyroZ,possibleRoll,rollover\n')

    # Append every sample in array to .csv
    with open(fn, "a") as outFile:
        outFile.write(f'{sample["time"]},{sample["accelX"]},{sample["accelY"]},{sample["accelZ"]},'\
                    f'{sample["gyroX"]},{sample["gyroY"]},{sample["gyroZ"]},{sample["didRoll"]},{sample["rollover"]}\n')
        
# Creates a gps instance by setting up UART and creating a GPS object
#
# Returns a GPS object
def createGps():
    uart = serial.Serial("/dev/ttyS0", baudrate=9600, timeout=10)
    gps = adafruit_gps.GPS(uart, debug=False)
    # Turn on the basic GGA and RMC info
    gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
    # Set update rate to once a second (1hz)
    gps.send_command(b'PMTK220,1000')
    return gps

# Samples the GPS
#
# @gps: GPS object to be sampled
#
# Returns a dictionary containing GPS parameters or None if there is no signal
# time, latitude, longitude, speed, altitude, and satellites
def sampleGps(gps):
    lat, long, speedKph, sats, alt = 0,0,0,0,0
    gps.update()

    if not gps.has_fix:
        # Try again if we don't have a fix yet.
        print('Waiting for fix...')
        return None

    print('='*40)
    if gps.latitude is not None:
        print('Latitude: {0:.6f} degrees'.format(gps.latitude))
        lat = gps.latitude
    if gps.longitude is not None:
        print('Longitude: {0:.6f} degrees'.format(gps.longitude))
        long = gps.longitude
    if gps.satellites is not None:
        print('# satellites: {}'.format(gps.satellites))
        sats = gps.satellites
    if gps.altitude_m is not None:
        print('Altitude: {} meters'.format(gps.altitude_m))
        alt = gps.altitude_m
    if gps.speed_knots is not None:
        speedKph = gps.speed_knots * CONV
        print('Speed: {} kph'.format(round(speedKph,5)))

    sample = {
        'time': datetime.datetime.now(),
        'lat': round(lat,5),
        'long': round(long,5),
        'speed': round(speedKph,5),
        'alt': round(alt,5),
        'sats': sats
    }
    return sample


# Writes both GPS and corresponding IMU data to the file fn
#
# @gpsSample: GPS data to send to fn
# @imuSample: IMU data to send to fn
def writeGpsSamples(gpsSample, imuSample, fn):
        # Create .csv if one does not exist
    if(not (os.path.exists(fn))):
        with open(fn, 'a') as outFile:
            outFile.write('time,lat,long,vel,alt,sats,accelX,accelY,accelZ,possibleRoll,rollover\n')

    # Write content to file
    if gpsSample and imuSample:
        with open(fn, "a") as outFile:
            outFile.write(f'{gpsSample["time"]},' \
                            f'{gpsSample["lat"]},' \
                            f'{gpsSample["long"]},' \
                            f'{gpsSample["speed"]},' \
                            f'{gpsSample["alt"]},' \
                            f'{gpsSample["sats"]},' \
                            f'{imuSample["accelX"]},' \
                            f'{imuSample["accelY"]},' \
                            f'{imuSample["accelZ"]},' \
                            f'{imuSample["didRoll"]},' \
                            f'{imuSample["rollover"]}\n')
    else:
        with open(fn, "a") as outFile:
            outFile.write(f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null,' \
                            f'null\n')

# Inherited class of rockBlockProtocol for sending outbound messages
# Has a send method that takes a message 'msg' to transmit via rockblock
# The other three methods are event handlers for starting an attempt,
# failing an attempt, and succedding an attempt
class moMessage (rockBlock.rockBlockProtocol):
    content = ""

    def send(self):
        try:
            rb = rockBlock.rockBlock("/dev/ttyUSB0", self)
            rb.sendMessage(self.content)
            rb.close()
        except Exception as exc:
            with open(ERR_LOG, "a") as errorLog:
                errorLog.write(str(datetime.datetime.now())+"\n")
                traceback.print_tb(exc.__traceback__, file=errorLog)

    def rockBlockTxStarted(self):
        print("rockBlockTxStarted")

    def rockBlockTxFailed(self):
        print ("rockBlockTxFailed")
        self.send()

    def rockBlockTxSuccess(self,momsn):
        print ("rockBlockTxSuccess " + str(momsn))

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

def updateRideHistory(index, item):
    rideHistory = getRideHistory()

    rideHistory[item] = index
        
    with open(HISTORY, "w") as rideHistoryJson:
        rideHistoryJson.write(json.dumps(rideHistory))

# Processes IMU data depending on which mode is selected
# NOTE: This function exists as a helper for startSampling
#
# @mode: device mode
# @index: current ride's index
# @imuData: dictionary containing imu data to process
# @imuCompleteFilename: filename for research logs
# @rollCount: rollover counter
# @recentImuSamples: circular array of IMU samples
#
# Returns an updated Rollcount
def logImu(mode, index, imuData, imuCompleteFilename, rollCount, recentImuSamples):
    if mode == 1:
        writeImuSample(imuCompleteFilename, imuData)
        updateRideHistory(index, "lastResearchRide")
    else:
        rollCount = updateRollCount(rollCount, imuData)
        recentImuSamples.append(imuData)
        
    return rollCount

# Processes GPS data
# NOTE: This function exists as a helper for startSampling
#
# @index: current ride's index
# @gpsData: dictionary containing GPS data
# @imuData: dictionary containing imu data
# @filename: filename for GPS data log
def logGps(index, gpsData, imuData, filename):
    try:         
        if gpsData and imuData:
            print('*'*16 + ' writing ' + '*'*15)
            writeGpsSamples(gpsData, imuData, filename)
            updateRideHistory(index, "lastRide")          
    except Exception as exc:
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+"\n")
            traceback.print_tb(exc.__traceback__, file=errorLog)
        
# Samples the GPS and IMU every second, outputs to a csv every sampleRate seconds
#
# @fn: a string that is the desired output filename
# @sampleRate: a double that represents the number of seconds until a sample is writen to fn
def startSampling(fn, gpsSampleRate, imuSampleRate, mode):
    lastGpsWrite = 0.0
    lastImuWrite = 0.0
    rollCount = 0
    gps, imu = None, None
    recentImuSamples = cyclicalArray(IMU_SAMPLE_SIZE)
    
    # Get index for this ride
    rideHistory = getRideHistory()
    if mode == 0:
        index = rideHistory["lastRide"] + 1
    else:
        index = rideHistory["lastResearchRide"] + 1
    
    # Setup GPIO channel for keyfob
    GPIO.setup(FOB_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # Create rockblock message instance
    outMessage = moMessage()
    
    # Create sensor instances
    try:
        gps = createGps()
        imu = createImu()

        # Setup file I/O, and create Header for .csv
        filename = PATH + fn + '.csv'
        imuFilename = PATH + fn + '_imu.csv'
        imuCompleteFilename = IMU_FULL_REC_PATH + 'ride' + str(index) + '_imuComplete.csv'

        # Main loop
        while True:
            # Check if mode is Farm (0) or Research (1)
            currentTime = time.monotonic()
            if currentTime - lastImuWrite >= imuSampleRate:
                imuData = sampleImu(imu)
                rollCount = logImu(mode, index, imuData, imuCompleteFilename, rollCount, recentImuSamples)
                print(f'Rollcount: {rollCount}')
                
                lastImuWrite = currentTime
          
            # Sample GPS and write data to file
            currentTime = time.monotonic()
            if currentTime - lastGpsWrite >= gpsSampleRate:
                gpsData = sampleGps(gps)
                imuData = sampleImu(imu)
                logGps(index, gpsData, imuData, filename)
                
                lastGpsWrite = currentTime
                            
            # Assess rollover scenario
            if ((mode == 0) and (rollCount == CRASHTHRESH)) or ((mode == 0) and (GPIO.input(FOB_GPIO))):
                # Rollover Scenario
                print('*'*15 + ' Rollover! ' + '*'*15)
                with open(ERR_LOG, "a") as errorLog:
                    errorLog.write(str(datetime.datetime.now())+"\nLogging Rollover\n")
                # Update most recent IMU sample to rollover status
                recentImuSamples.getEnd()["rollover"] = True
                writeImuArray(imuFilename, recentImuSamples)
                if gpsData and imuData:
                    writeGpsSamples(gpsData, imuData, filename)
                    # Update rideHistory.json with new ride index due to file write
                    updateRideHistory(index, "lastRide")
                    # Send emergency message
                    emergencyMsg = f"{PHONE},{gpsData['long']},{gpsData['lat']},{DEV_ID}"
                else:
                    # No gps connection at time of crash
                    emergencyMsg = f"{PHONE},,,{DEV_ID}"
                outMessage.content = emergencyMsg
                with open(ERR_LOG, "a") as errorLog:
                    errorLog.write(str(datetime.datetime.now())+"\n")
                    errorLog.write(f"Attempting to send string: {emergencyMsg} to Rock7!\n")
                outMessage.send()
                
    except Exception as exc:
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+"\n")
            traceback.print_tb(exc.__traceback__, file=errorLog)
        startSampling(fn, gpsSampleRate, imuSampleRate, mode)
