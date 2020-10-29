# Data
This directory contains all data collected by the ATV device under normal operations

## Basic Overview
* rides
  * This directory contains all ride data collected by the device
  * This data is split into three differed sub-directories
    * current
      * Current ride data GPS (and IMU if in Farm mode and a rollover occurs)
    * unsent
      * Files queued for transmission to Firestore
    * sent
      * Files sent to Firestore
    * imuComplete
      * Complete IMU logs (only collected in **Research mode** and **not** sent to Firestore)
 * about.xml
    * Configuration for device, includes matadata and parameters
    * All parameters can be set manually, excluding: devId, uid, serial, model and manufacturer
 * rideHistory.json
    * Last ride indices for reference when creating new rides, helps avoid indexing issues on the database side
      
