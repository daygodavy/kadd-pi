# Set Up
## Hardware Config
### IMU
![LSM9DS1 Setup with SPI](https://cdn-learn.adafruit.com/assets/assets/000/067/332/medium640/sensors_raspi_lsm9ds1_spi_bb.jpg?1544215916)

* Pi 3V3 to sensor VIN
* Pi GND to sensor GND
* Pi SCLK to sensor SCL
* Pi MOSI to sensor SDA
* Pi MISO to sensor SDOAG AND sensor SDOM
* Pi GPIO5 to sensor CSAG
* Pi GPIO6 to sensor CSM

### GPS
![GPS Breakout v3 UART wiring](https://cdn-learn.adafruit.com/assets/assets/000/062/852/medium640/adafruit_products_sensors_uartgps_bb.png?1538430197)

* GPS Vin  to 3.3V (red wire)
* GPS Ground to Ground (black wire)
* GPS RX to TX (green wire)
* GPS TX to RX (white wire)

### RockBLOCK
* Connect to any USB-A Port

## Setup Script
1. Plug a mini HDMI cable into the Pi to connect it to a monitor and connect a mouse and keyboard
2. Power on the Pi by plugging in a USB-C cable connected to a power supply capable of producing 15W
3. Clone this repository to `/home/pi/`
	 - It is important to clone this repository to this directory since file paths are absolute due to issues running some threads before Raspbian has finished booting up.
4. Run `setup.sh` found in `kadd-pi/setup` (**NOTE:** You may need to run the command `chmod +x setup.sh` if you get an error about permissions)
         - This should set everything up for you and make a backup of `.bashrc` placed onto the desktop
5. Obtain new security JSON file from Firestore (https://console.firebase.google.com/ -> Settings -> Service Accounts -> Firebase Admin SDK -> Generate new private key) and rename it `agCert.json` and place it in `kadd-pi/src/`



## Manual Method
### If the script doesn't work for you for what ever reason, here are the steps it performs
1. Install the latest Raspbian GPIO package with `sudo apt-get update` and then `sudo apt-get install python3-rpi.gpio`
2. Show hidden folders in the directory `/home/pi` by opening the directory in the file explorer and right clicking on the window, this should give you the option to "show hidden folders"
3. Install Python 3 with `sudo apt-get install python3`
4. Install all the Python packages in `home/pi/kadd-pi/setup/pip` using pip3
	 - `sudo apt-get install python3-pip` 
	 - `pip3 install PackageNameFromPipFile`
5. Copy contents of `/home/pi/kadd-pi/setup/autostart` in `/home/pi/.config/lxsession/LXDE-pi`.
	 - This will cause the terminal to launch at boot
6. Copy  `/home/pi/kadd-pi/setup/.bashrc` and replace the existing `.bashrc` file in `/home/pi` with it
	- **NOTE:** Make a backup of the original `.bashrc` before overwriting it!
7. Restart the Raspberry pi while still connected to the monitor to see if any errors pop up after the main script boots.
9. If you see accelerometer data streaming across the terminal the device has been successfully configured.
10. Now you can start configuring the device by editing the values in `/home/pi/kadd-pi/data/about.xml`
