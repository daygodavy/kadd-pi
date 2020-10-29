#!/usr/bin/python3
import re
import os
import os.path
import csv
import time
import traceback
import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from xml.dom import minidom

UNSENT_RIDES = "/home/pi/kadd-pi/data/rides/unsent/"
SENT_RIDES = "/home/pi/kadd-pi/data/rides/sent/"
CERT = "/home/pi/kadd-pi/src/agCert.json"
ERR_LOG = "/home/pi/kadd-pi/data/errorLog.txt"
CONFIG = "/home/pi/kadd-pi/data/about.xml"
DATE = '%Y-%m-%d %H:%M:%S.%f'

if os.path.isfile(CONFIG):
    config = minidom.parse(CONFIG)
    USER_NAME = str(config.getElementsByTagName('uid')[0].firstChild.data)
    DEVICE_NAME = str(config.getElementsByTagName('devId')[0].firstChild.data)
else:
    USER_NAME = "default_user"
    DEVICE_NAME = "default_device"
# For testing purposes
RIDE_NAME = "ride"

# Class containing all accelerometer data at a specific point
# collected as part of compatibility with iOS application's usage of database
class TerrainPoint:
    def __init__(self, xVal, yVal, zVal, rollVal):
        self.x = xVal
        self.y = yVal
        self.z = zVal
        self.didRollover = rollVal
    def to_dict(self):
        return({
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'didRollover': self.didRollover
            })
    def __repr__(self):
        return(u'TerrainPoint(x={}, y={}, z={}, didRollover={})'\
               .format(self.x,self.y,self.z,self.didRollover))

# Performs transmission of data to the database, retry if no connection
#
# @db: firebase database object
# @data: information to send
# @dest: destination collection
# @docName: destination document name
def sendToDB(db, data, dest, docName):
    try:
        # Attempt to send data to db
        result = db.collection(dest)\
        .document(docName)\
        .set(data, merge=True)

        return result
    except Exception as exc:
        # Connection could not be established or was interrupted
        with open(ERR_LOG, "a") as errorLog:
            errorLog.write(str(datetime.datetime.now())+"\n")
            traceback.print_tb(exc.__traceback__, file=errorLog)
        print("Exception occured sending file to DB, retrying in 10 seconds!")
        time.sleep(10)
        sendToDB(db, data, dest, docName)

# Remove null characters that may appear when the device suddenly loses power
#
# @fn: file to be cleaned
# Replaces fn with a cleaned version, works with any file type that doesn't require spaces
def cleanFile(fn):
    cleanedText = ""
    # Use a regex to remove null and whitespace characters from csv
    with open(fn, 'r') as f:
        for line in f:
            result = re.sub(r'\x00+',"",str(line))
            cleanedText += result

    # Write cleaned file out
    with open(fn, 'w') as outFile:
        outFile.write(cleanedText)

# Collects all GPS data from a csv file containing GPS data and returns it as a dictionary
#
# @fn: path to file containing gps data
# Returns a dictionary containing all columns from the file as lists
def getGPS(fn):
    line = 0
    didRollover = False
    headers = []
    times,locations,velocities,altitudes,satellites,accelXs,accelYs,accelZs,ros = [],[],[],[],[],[],[],[],[]

    # Clean out possible null characters (result from abrupt power loss)
    cleanFile(fn)
    # Parse GPS
    with open(fn, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            # Reset lat and long params for geopoint call
            latSet = False
            longSet = False

            if(line == 0):
                for header in row:
                    headers.append(header)
                line += 1
            else:
                for i, item in enumerate(row):
                    if(headers[i] == 'time'):
                        times.append(datetime.datetime.strptime(item,DATE))
                    elif(headers[i] == 'lat'):
                        lat = float(item)
                        latSet = True
                    elif(headers[i] == 'long'):
                        long = float(item)
                        longSet = True
                    elif(headers[i] == 'sats'):
                        satellites.append(float(item))
                    elif(headers[i] == 'vel'):
                        velocities.append(float(item))
                    elif(headers[i] == 'alt'):
                        altitudes.append(float(item))
                    elif(headers[i] == 'accelX'):
                        accelXs.append(float(item))
                    elif(headers[i] == 'accelY'):
                        accelYs.append(float(item))
                    elif(headers[i] == 'accelZ'):
                        accelZs.append(float(item))
                    elif(headers[i] == 'rollover'):
                        ros.append(item)
                        if item == True:
                            didRollover = True

                    # Create GeoPoint from both lat and long
                    if(latSet and longSet):
                        latSet = False
                        longSet = False
                        locations.append(firestore.GeoPoint(lat, long))
                line += 1

    terrainPoints = []
    for i in range(0, len(accelXs)):
        terrainPoints.append(TerrainPoint(accelXs[i],accelYs[i],accelZs[i],ros[i]).to_dict())

    res = {
        u'coordinates': locations,
        u'gps_timestamps': times,
        u'velocities': velocities,
        u'altitudes': altitudes,
        u'satellites': satellites,
        # IMU data, here for iOS db code compatibility
        u'terrain_timestamps': times,
        u'did_rollover': didRollover,
        u'terrain_point': terrainPoints
    }
    return res

# Collects all IMU information from an imu.csv file fn and returns it in a dictionary
#
# @fn: expects path to a csv containing imu data
# Returns dictionary containing all columns in lists
def getIMU(fn):
    line = 0
    headers = []
    times,accelXs,accelYs,accelZs,gyroXs,gyroYs,gyroZs,possRolls,ros = [],[],[],[],[],[],[],[],[]

    # Clean out possible null characters (result from abrupt power loss)
    cleanFile(fn)
    # Parse IMU
    with open(fn, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if(line == 0):
                for header in row:
                    headers.append(header)
                line += 1
            else:
                for i, item in enumerate(row):
                    if(headers[i] == 'time'):
                        times.append(datetime.datetime.strptime(item,DATE))
                    elif(headers[i] == 'accelX'):
                        accelXs.append(float(item))
                    elif(headers[i] == 'accelY'):
                        accelYs.append(float(item))
                    elif(headers[i] == 'accelZ'):
                        accelZs.append(float(item))
                    elif(headers[i] == 'gyroX'):
                        gyroXs.append(float(item))
                    elif(headers[i] == 'gyroY'):
                        gyroYs.append(float(item))
                    elif(headers[i] == 'gyroZ'):
                        gyroZs.append(float(item))
                    elif(headers[i] == 'possibleRoll'):
                        possRolls.append(item)
                    elif(headers[i] == 'rollover'):
                        ros.append(item)
            line += 1

    res = {
        "times": times,
        "accelX": accelXs,
        "accelY": accelYs,
        "accelZ": accelZs,
        "gyroX": gyroXs,
        "gyroY": gyroYs,
        "gyroZ": gyroZs,
        "possRoll": possRolls,
        "rollover": ros
    }
    return res


# Sends file data corresponding to the files generated for rideName
#
# @filename: expects a string representing the ride whose IMU and GPS data is going to be sent to the db
def sendFileToDb(filename):
    # Extract index number from filename
    regex = re.compile(r'\d+')
    postIndex = regex.findall(filename)[0]

    # Configure Firebase Admin SDK, checks protected member to see if session already exists
    if not firebase_admin._apps:
        cred = credentials.Certificate(CERT)
        app = firebase_admin.initialize_app(cred)
    db = firestore.client()

    # Collect data from gps or imu file
    if "_imu" in filename:
        print(filename + " is an imu file")
        try:
            imuData = getIMU(filename)
            imuData["dev_id"] = DEVICE_NAME
            imuData["index"] = int(postIndex)
            print(imuData)
#             sendToDB(db, imuData, "imuhistoryDev", RIDE_NAME+postIndex+"_imu")
            sendToDB(db, imuData, "imuhistory", None)
        except:
            print("Unable to send " + filename)
    else:
        print(filename + " is a gps file")
        try:
            gpsData = getGPS(filename)
            gpsData["dev_id"] = DEVICE_NAME
            gpsData["index"] = int(postIndex)
            print(gpsData)
#             sendToDB(db, gpsData, "ridehistoryDev", RIDE_NAME+postIndex)
            sendToDB(db, gpsData, "ridehistory", None)
        except:
            with open(ERR_LOG, "a") as errorLog:
                errorLog.write(str(datetime.datetime.now())+"\n")
                errorLog.write(f"Unable to send: {filename} to database.\n")
