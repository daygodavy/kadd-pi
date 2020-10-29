# Setup
This directory contains all setup componenets for this device to function, however, these setup files were not created with the bluetooth interface (bleno) in mind. Additional setup *may* be required for those features.

## Basic Overview
* .bashrc
	* When this file is used to replace the existing `.bashrc` file in `/home/pi/` (this file is hidden by default) it allows the kadd-pi scripts to run as soon as the terminal is opened
* autostart
	* Automatically causes the terminal to launch on boot when placed in `/home/pi/.config/lxsession/LXDE-pi`
* pip
	* All the Python modules used to run the kadd-pi scripts
* setup.sh
	* Script to setup a new device from scratch
	* Installs latest Raspbian GPIO interface, Python3, and all modules listed in `pip`
	* Moves `autorun` to correct directory to automaticall open the terminal on boot
	* Creates a bakc for the original `.bashrc` (placed on the Desktop as bashrcBackup) and places the modified `.bashrc` file in its place
		* Automatically runs scripts whenever terminal is opened
		* 20 second grace period before scripts start
